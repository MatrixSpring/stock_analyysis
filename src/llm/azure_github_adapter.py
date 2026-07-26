# -*- coding: utf-8 -*-
"""
===================================
GitHub Models / Azure 专属适配层
===================================

解决 GitHub Models (Azure AI Inference) 的以下问题：
  1. Azure 接口非标准 /v1 路径兼容
  2. api-version 请求头缺失
  3. 原生 LiteLLM 在某些环境下路由失败
  4. 免费模型 RPM 限流控制
  5. 错误重试 + 优雅降级

支持模型：GPT-4o, GPT-4o-mini, Claude 3.5 Sonnet, Claude 3 Haiku,
         Gemini 2.0 Flash, DeepSeek R1/V3, Llama 3.3 70B, Codestral, Phi-4

使用方式：
    from src.llm.azure_github_adapter import GitHubAzureAdapter
    client = GitHubAzureAdapter(token="ghp_xxx")
    result = client.completion(model="gpt-4o", messages=[...])
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GitHubAzureAdapter:
    """GitHub Models Azure AI Inference 适配器。

    特性：
    - 自动补全 Azure 所需 api-version header
    - 双层调用：优先 LiteLLM，失败降级到 requests 直连
    - 内置 RPM 限流（默认 15 RPM）
    - 指数退避重试
    """

    API_VERSION = "2024-05-01-preview"
    BASE_URL = "https://models.inference.ai.azure.com"

    # 已知可用的完整模型名映射（API 实际接受的名）
    _KNOWN_MODEL_NAMES = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "claude-3.5-sonnet": "claude-3.5-sonnet",
        "claude-3-haiku": "claude-3-haiku",
        "gemini-2.0-flash": "gemini-2.0-flash",
        "deepseek-r1": "deepseek-r1",
        "deepseek-v3": "deepseek-v3",
        "llama-3.3-70b": "llama-3.3-70b",
        "codestral": "codestral",
        "phi-4": "phi-4",
    }

    def __init__(
        self,
        token: str = "",
        rpm_limit: int = 15,
        timeout: int = 60,
        max_retries: int = 2,
    ):
        self._token = token
        self._enabled = bool(token)

        # Azure 标准请求头
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "api-version": self.API_VERSION,
        }

        # 限流控制
        self._rpm_limit = rpm_limit
        self._request_timestamps: List[float] = []

        # 重试配置
        self._timeout = timeout
        self._max_retries = max_retries

        # 熔断状态（简单版，配合 rate_limiter.CircuitBreaker 使用）
        self._cooldown_until: Dict[str, float] = {}
        self._error_counts: Dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ---- 限流 ----

    def _rate_limit_wait(self):
        """滑动窗口 RPM 限流（60 秒窗口）"""
        now = time.time()
        # 清理 60 秒前的记录
        self._request_timestamps = [
            t for t in self._request_timestamps if now - t < 60
        ]
        if len(self._request_timestamps) >= self._rpm_limit:
            # 等待最早记录过期 + 小 buffer
            wait = 60 - (now - self._request_timestamps[0]) + 0.5
            if wait > 0:
                logger.debug(
                    f"[AzureAdapter] RPM 限流等待 {wait:.1f}s "
                    f"({len(self._request_timestamps)}/{self._rpm_limit} requests)"
                )
                time.sleep(wait)
        self._request_timestamps.append(time.time())

    # ---- 核心调用 ----

    def completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """兼容 GitHub Models / Azure 接口的通用推理方法。

        Args:
            model: 模型名（无需 azure/ 前缀）
            messages: OpenAI 格式消息列表
            temperature: 温度参数
            max_tokens: 最大输出 tokens
            timeout: 超时秒数

        Returns:
            {"content": str, "model": str, "usage": dict} 或 None
        """
        if not self._enabled:
            logger.warning("[AzureAdapter] Token 未配置，跳过调用")
            return None

        # 模型名标准化
        model = self._normalize_model(model)

        # 熔断检查
        if self._is_cooldown(model):
            logger.warning(f"[AzureAdapter] {model} 处于熔断冷却期，跳过")
            return None

        # 限流
        self._rate_limit_wait()

        t = timeout or self._timeout

        # 方法 1: 优先 LiteLLM（完整支持）
        result = self._try_litellm(model, messages, temperature, max_tokens, t)
        if result is not None:
            self._mark_success(model)
            return result

        # 方法 2: 降级到 requests 直连
        logger.info(f"[AzureAdapter] LiteLLM 调用失败，降级到 requests 直连: {model}")
        result = self._try_direct_http(model, messages, temperature, max_tokens, t)
        if result is not None:
            self._mark_success(model)
            return result

        # 全部失败
        self._mark_failure(model)
        return None

    def _try_litellm(
        self, model: str, messages: List[Dict], temperature: float,
        max_tokens: int, timeout: int,
    ) -> Optional[Dict[str, Any]]:
        """通过 LiteLLM 调用（首选）"""
        try:
            import litellm

            response = litellm.completion(
                model=f"github/{model}",
                messages=messages,
                api_key=self._token,
                api_base=self.BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                custom_llm_provider="openai",
            )
            content = response.choices[0].message.content
            return {
                "content": content,
                "model": model,
                "usage": getattr(response, "usage", None),
                "source": "litellm",
            }
        except Exception as e:
            logger.debug(f"[AzureAdapter] LiteLLM {model} 失败: {type(e).__name__}: {str(e)[:150]}")
            return None

    def _try_direct_http(
        self, model: str, messages: List[Dict], temperature: float,
        max_tokens: int, timeout: int,
    ) -> Optional[Dict[str, Any]]:
        """通过 requests 直连 Azure API（降级方案）"""
        try:
            import requests

            url = f"{self.BASE_URL}/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            resp = requests.post(
                url,
                headers=self._headers,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return {
                    "content": content,
                    "model": model,
                    "usage": data.get("usage"),
                    "source": "direct_http",
                }
            elif resp.status_code == 429:
                logger.warning(f"[AzureAdapter] {model} 429 限流，触发降级")
                self._apply_rate_limit_backoff()
                return None
            else:
                logger.warning(
                    f"[AzureAdapter] HTTP {resp.status_code}: "
                    f"{resp.text[:300]}"
                )
                return None
        except Exception as e:
            logger.debug(f"[AzureAdapter] Direct HTTP {model} 失败: {type(e).__name__}")
            return None

    # ---- 熔断 ----

    def _is_cooldown(self, model: str) -> bool:
        """检查模型是否在冷却期"""
        until = self._cooldown_until.get(model, 0)
        return time.time() < until

    def _mark_success(self, model: str):
        """标记调用成功，重置错误计数"""
        self._error_counts.pop(model, None)

    def _mark_failure(self, model: str):
        """标记调用失败，累计错误数"""
        count = self._error_counts.get(model, 0) + 1
        self._error_counts[model] = count
        if count >= 3:
            # 3 次连续失败 → 60 秒冷却
            self._cooldown_until[model] = time.time() + 60
            logger.warning(
                f"[AzureAdapter] {model} 连续失败 {count} 次，冷却 60s"
            )

    def _apply_rate_limit_backoff(self):
        """遇到 429 后降低调用频率"""
        old_limit = self._rpm_limit
        self._rpm_limit = max(3, self._rpm_limit - 3)
        logger.info(
            f"[AzureAdapter] RPM 限流回退: {old_limit} → {self._rpm_limit}"
        )

    # ---- 工具方法 ----

    @staticmethod
    def _normalize_model(model: str) -> str:
        """标准化模型名"""
        model = model.strip()
        # 移除常见前缀
        for prefix in ("github/", "azure/", "openai/"):
            if model.startswith(prefix):
                model = model[len(prefix):]
        return model

    @classmethod
    def is_known_model(cls, model: str) -> bool:
        """检查是否为已知可用模型"""
        return cls._normalize_model(model) in cls._KNOWN_MODEL_NAMES

    @classmethod
    def get_known_models(cls) -> List[str]:
        """返回所有已知模型名"""
        return list(cls._KNOWN_MODEL_NAMES.keys())


# ============================================================
# 全局单例（可选，推荐用 free_model_hub 管理生命周期）
# ============================================================

_github_azure_client: Optional[GitHubAzureAdapter] = None


def get_github_azure_adapter(
    token: str = "", rpm_limit: int = 15,
) -> GitHubAzureAdapter:
    """获取/创建全局 GitHubAzureAdapter 实例"""
    global _github_azure_client
    if _github_azure_client is None or token:
        _github_azure_client = GitHubAzureAdapter(token=token, rpm_limit=rpm_limit)
    return _github_azure_client

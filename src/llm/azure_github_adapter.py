# -*- coding: utf-8 -*-
"""
===================================
GitHub Models 公共版 原生 HTTP 适配层
===================================

**彻底根治 LiteLLM azure/ 路由 302 网页跳转解析失败**

根因：GitHub Models 是微软公开免费模型，不走标准 Azure 商用资源池逻辑。
     LiteLLM 原生 azure/ 路由会触发 302 重定向 → 返回网页 HTML → 解析失败。

修复方案：
  1. 完全弃用 LiteLLM azure/ 路由
  2. 使用 GitHub Models 官方原生 POST 接口
  3. 不带 api-version 头（公共版不需要，带参数反而 302）
  4. 精确模型名映射（匹配 GitHub 官方路由）

使用方式：
    from src.llm.azure_github_adapter import GitHubAzureAdapter
    client = GitHubAzureAdapter(token="ghp_xxx")
    resp = client.completion(model="gpt-4o", messages=[...])
    content = resp["choices"][0]["message"]["content"]
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GitHubAzureAdapter:
    """GitHub Models 公共版原生 HTTP 适配器。

    已移除所有 LiteLLM Azure 兼容逻辑。
    直接调用 GitHub Models 官方 REST API。
    """

    # GitHub Models 公共版官方接口（非商用 Azure 资源池）
    BASE_URL = "https://models.inference.ai.azure.com/chat/completions"

    # 官方精确模型名映射（必选——名称不一致直接 404）
    _OFFICIAL_MODEL_NAMES = {
        # OpenAI
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        # Anthropic — GitHub 官方路由使用带日期的版本名
        "claude-3.5-sonnet": "claude-3-5-sonnet-20240620",
        "claude-3-haiku": "claude-3-5-haiku-20241022",
        # Google
        "gemini-2.0-flash": "gemini-2.0-flash-001",
        # DeepSeek
        "deepseek-r1": "deepseek-r1",
        "deepseek-v3": "deepseek-v3",
        # Meta
        "llama-3.3-70b": "llama-3.3-70b-instruct",
        # Mistral
        "codestral": "codestral-2501",
        # Microsoft
        "phi-4": "phi-4",
        # xAI
        "grok-3": "grok-3-preview",
    }

    def __init__(
        self,
        token: str = "",
        rpm_limit: int = 15,
        timeout: int = 60,
    ):
        self._token = token
        self._enabled = bool(token)

        # 不带 api-version 的纯净请求头（公共版不需要，带参数反而 302）
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        self._rpm_limit = rpm_limit
        self._timeout = timeout
        self._last_request_time: float = 0.0

        # 模型黑名单：连续失败 3 次自动剔除
        self._blacklist: Dict[str, float] = {}  # model → 解封时间
        self._error_counts: Dict[str, int] = {}
        self._blacklist_threshold = 3
        self._blacklist_cooldown = 60.0  # 60 秒后重试

        # 统计
        self._total_requests = 0
        self._total_success = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ============================================================
    # 限流
    # ============================================================

    def _rate_limit_control(self):
        """精准 RPM 控频：确保每秒不超过 rpm/60 次"""
        now = time.time()
        interval = 60.0 / self._rpm_limit
        elapsed = now - self._last_request_time
        if elapsed < interval:
            wait = interval - elapsed
            logger.debug(f"[AzureAdapter] RPM 限速等待 {wait:.1f}s")
            time.sleep(wait)
        self._last_request_time = time.time()

    # ============================================================
    # 核心——纯原生 HTTP（无 LiteLLM）
    # ============================================================

    def completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """原生 HTTP POST 调用 GitHub Models 公共 API。

        完全绕过 LiteLLM，直接 HTTP，杜绝 302 网页跳转。

        Args:
            model: 简短模型名（如 "gpt-4o", "claude-3.5-sonnet"）
            messages: OpenAI 格式消息列表
            temperature: 温度
            max_tokens: 最大输出 token
            timeout: 超时秒数

        Returns:
            成功时返回原始 API JSON: {"choices": [{"message": {"content": "..."}}], ...}
            失败时返回 None
        """
        if not self._enabled:
            logger.warning("[AzureAdapter] Token 未配置，跳过调用")
            return None

        # 1. 精确模型名映射
        clean_model = self._normalize_model(model)
        api_model = self._OFFICIAL_MODEL_NAMES.get(clean_model, clean_model)

        # 2. 黑名单检查
        if self._is_blacklisted(clean_model):
            logger.warning(
                f"[AzureAdapter] {clean_model} 在黑名单中，跳过本次调用"
            )
            return None

        # 3. 限流
        self._rate_limit_control()

        # 4. 原生 HTTP POST（无 LiteLLM，无 api-version）
        payload = {
            "model": api_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            import requests

            self._total_requests += 1
            resp = requests.post(
                self.BASE_URL,
                headers=self._headers,
                json=payload,
                timeout=timeout or self._timeout,
            )

            status = resp.status_code

            if status == 200:
                self._total_success += 1
                self._mark_success(clean_model)
                return resp.json()

            elif status == 429:
                # 限流 → 降低 RPM 并黑名单短暂冷却
                logger.warning(
                    f"[AzureAdapter] {api_model} 429 限流 | "
                    f"RPM={self._rpm_limit}"
                )
                self._apply_rate_backoff()
                self._mark_failure(clean_model)
                return None

            elif status in (302, 301):
                # 重定向 → 模型名或路由错误
                redirect_url = resp.headers.get("Location", "unknown")
                logger.error(
                    f"[AzureAdapter] {api_model} HTTP {status} 重定向 → {redirect_url} "
                    f"| 模型名可能不匹配，请检查 _OFFICIAL_MODEL_NAMES"
                )
                self._mark_failure(clean_model)
                return None

            elif status == 404:
                logger.error(
                    f"[AzureAdapter] {api_model} HTTP 404 模型不存在 "
                    f"| 请确认模型名 {api_model} 在 GitHub Models 中可用"
                )
                self._mark_failure(clean_model)
                return None

            else:
                logger.warning(
                    f"[AzureAdapter] {api_model} HTTP {status}: "
                    f"{resp.text[:300]}"
                )
                if status >= 500:
                    self._mark_failure(clean_model)
                return None

        except requests.exceptions.Timeout:
            logger.error(
                f"[AzureAdapter] {api_model} 请求超时 ({timeout or self._timeout}s)"
            )
            self._mark_failure(clean_model)
            return None

        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"[AzureAdapter] {api_model} 连接失败: {e}"
            )
            self._mark_failure(clean_model)
            return None

        except Exception as e:
            logger.error(
                f"[AzureAdapter] {api_model} 未知异常: {type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}"
            )
            self._mark_failure(clean_model)
            return None

    # ============================================================
    # 模型名标准化
    # ============================================================

    @staticmethod
    def _normalize_model(model: str) -> str:
        """去除前缀，返回简短名"""
        model = model.strip()
        for prefix in ("github/", "azure/", "openai/"):
            if model.startswith(prefix):
                model = model[len(prefix):]
        return model

    @classmethod
    def get_api_model_name(cls, short_name: str) -> str:
        """获取 API 实际使用的模型名"""
        clean = cls._normalize_model(short_name)
        return cls._OFFICIAL_MODEL_NAMES.get(clean, clean)

    @classmethod
    def is_known_model(cls, model: str) -> bool:
        return cls._normalize_model(model) in cls._OFFICIAL_MODEL_NAMES

    @classmethod
    def get_known_models(cls) -> List[str]:
        return list(cls._OFFICIAL_MODEL_NAMES.keys())

    # ============================================================
    # 黑名单管理
    # ============================================================

    def _is_blacklisted(self, model: str) -> bool:
        until = self._blacklist.get(model, 0)
        return time.time() < until

    def _mark_success(self, model: str):
        self._error_counts.pop(model, None)
        self._blacklist.pop(model, None)

    def _mark_failure(self, model: str):
        count = self._error_counts.get(model, 0) + 1
        self._error_counts[model] = count
        if count >= self._blacklist_threshold:
            self._blacklist[model] = time.time() + self._blacklist_cooldown
            logger.warning(
                f"[AzureAdapter] {model} 连续失败 {count} 次 → "
                f"加入黑名单 {self._blacklist_cooldown}s"
            )

    def _apply_rate_backoff(self):
        old = self._rpm_limit
        self._rpm_limit = max(3, self._rpm_limit - 3)
        logger.info(
            f"[AzureAdapter] RPM 回退: {old} → {self._rpm_limit}"
        )

    # ============================================================
    # 统计与诊断
    # ============================================================

    def stats(self) -> Dict[str, Any]:
        return {
            "total_requests": self._total_requests,
            "total_success": self._total_success,
            "success_rate": (
                self._total_success / max(self._total_requests, 1)
            ),
            "current_rpm": self._rpm_limit,
            "blacklisted": {
                m: round(until - time.time(), 1)
                for m, until in self._blacklist.items()
                if time.time() < until
            },
            "error_counts": dict(self._error_counts),
        }


# ============================================================
# 全局单例
# ============================================================

_github_azure_client: Optional[GitHubAzureAdapter] = None


def get_github_azure_adapter(
    token: str = "", rpm_limit: int = 15,
) -> GitHubAzureAdapter:
    global _github_azure_client
    if _github_azure_client is None or token:
        _github_azure_client = GitHubAzureAdapter(token=token, rpm_limit=rpm_limit)
    return _github_azure_client

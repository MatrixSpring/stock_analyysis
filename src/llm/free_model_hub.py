# -*- coding: utf-8 -*-
"""
===================================
免费模型聚合中心 — FreeModelHub
===================================

聚合三大免费 LLM 提供商：
  1. GitHub Models     — GPT-4o / GPT-4o-mini (已验证通过)
  2. Groq              — Llama 3.3 70B / Llama 4 Scout / GPT-OSS-120B (超快)
  3. OpenRouter        — DeepSeek R1 / Qwen3 Coder 480B / Llama 3.3 70B 等30+模型

全部 OpenAI SDK 兼容，零成本，无需信用卡。

使用方式：
    hub = FreeModelHub()
    hub.add_github(token="ghp_xxx")
    hub.add_groq(token="gsk_xxx")
    hub.add_openrouter(token="sk-or-xxx")

    results = await hub.compare_all(stock_data, prompt)
    # 6+ 模型并行对比，自动共识分析
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

import requests

from src.llm.github_models import GitHubModelsProvider

logger = logging.getLogger(__name__)


# ============================================================
# Groq 提供商
# ============================================================

class GroqProvider:
    """
    Groq 免费 API（LPU 硬件加速，300-500 tok/s）。

    获取 Token: https://console.groq.com/keys
    免费额度: ~14,400 RPD (8B) / ~1,000 RPD (70B)
    """

    BASE_URL = "https://api.groq.com/openai/v1"

    # Groq 免费可用模型
    FREE_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-4-scout-17b-64e-instruct",
        "deepseek-r1-distill-llama-70b",
        "qwen-qwq-32b",
    ]

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._enabled = bool(api_key)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_api_key(self, key: str):
        self._api_key = key
        self._enabled = bool(key)

    @staticmethod
    def list_models(api_key: str) -> List[str]:
        """列出可用模型"""
        try:
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return [m["id"] for m in resp.json().get("data", [])]
        except Exception:
            pass
        return GroqProvider.FREE_MODELS

    async def call(
        self, model: str, messages: List[Dict], temperature: float = 0.3,
        max_tokens: int = 2048, timeout: int = 60,
    ) -> Dict[str, Any]:
        """调用 Groq 模型"""
        start = time.time()
        try:
            # 尝试用 litellm
            try:
                import litellm
                response = await litellm.acompletion(
                    model=f"groq/{model}",
                    messages=messages,
                    api_key=self._api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                content = response.choices[0].message.content
            except ImportError:
                # 直接 HTTP 调用
                resp = requests.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=timeout,
                )
                content = resp.json()["choices"][0]["message"]["content"]

            return {
                "model": f"groq/{model}", "content": content,
                "success": True, "duration_ms": round((time.time() - start) * 1000, 1),
                "error": "",
            }
        except Exception as e:
            return {
                "model": f"groq/{model}", "success": False,
                "error": str(e)[:150],
                "duration_ms": round((time.time() - start) * 1000, 1),
                "content": "",
            }


# ============================================================
# OpenRouter 提供商
# ============================================================

class OpenRouterProvider:
    """
    OpenRouter 免费 API（30+ 免费模型）。

    获取 Token: https://openrouter.ai/keys
    免费额度: 200 RPD / 20 RPM
    免费模型: 模型名加 :free 后缀，如 "deepseek/deepseek-r1:free"
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    # OpenRouter 免费模型精选
    FREE_MODELS = [
        "deepseek/deepseek-r1:free",
        "qwen/qwen3-coder:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "openai/gpt-oss-120b:free",
        "mistralai/mistral-small-3.1-24b:free",
    ]

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._enabled = bool(api_key)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_api_key(self, key: str):
        self._api_key = key
        self._enabled = bool(key)

    async def call(
        self, model: str, messages: List[Dict], temperature: float = 0.3,
        max_tokens: int = 2048, timeout: int = 60,
    ) -> Dict[str, Any]:
        """调用 OpenRouter 模型"""
        start = time.time()
        try:
            try:
                import litellm
                response = await litellm.acompletion(
                    model=f"openrouter/{model}",
                    messages=messages,
                    api_key=self._api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                content = response.choices[0].message.content
            except ImportError:
                resp = requests.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/daily-stock-analysis",
                        "X-Title": "DSA Stock Analysis",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=timeout,
                )
                content = resp.json()["choices"][0]["message"]["content"]

            return {
                "model": f"openrouter/{model}", "content": content,
                "success": True, "duration_ms": round((time.time() - start) * 1000, 1),
                "error": "",
            }
        except Exception as e:
            return {
                "model": f"openrouter/{model}", "success": False,
                "error": str(e)[:150],
                "duration_ms": round((time.time() - start) * 1000, 1),
                "content": "",
            }


# ============================================================
# 免费模型聚合中心
# ============================================================

class FreeModelHub:
    """
    统一免费模型聚合中心。

    使用方式：
        hub = FreeModelHub()
        hub.add_github(token="ghp_xxx")
        hub.add_groq(token="gsk_xxx")       # 可选
        hub.add_openrouter(token="sk-or-xxx") # 可选

        results = await hub.compare_all(stock_data, prompt)
        report = hub.build_consensus(results)
    """

    def __init__(self):
        self._github: Optional[GitHubModelsProvider] = None
        self._groq: Optional[GroqProvider] = None
        self._openrouter: Optional[OpenRouterProvider] = None
        self._all_models: List[str] = []
        self._provider_count = 0

    @property
    def enabled(self) -> bool:
        return self._provider_count > 0

    # ============================================================
    # 添加提供商
    # ============================================================

    def add_github(self, token: str = "", model_list: Optional[List[str]] = None):
        """添加 GitHub Models"""
        key = token or os.getenv("GITHUB_MODELS_TOKEN", "")
        if not key:
            return self
        self._github = GitHubModelsProvider(api_key=key, model_list=model_list)
        self._all_models.extend(self._github._model_list)
        self._provider_count += 1
        logger.info(f"[FreeModelHub] + GitHub Models ({len(self._github._model_list)} models)")
        return self

    def add_groq(self, token: str = "", model_list: Optional[List[str]] = None):
        """添加 Groq"""
        key = token or os.getenv("GROQ_API_KEY", "")
        if not key:
            return self
        self._groq = GroqProvider(api_key=key)
        self._provider_count += 1
        logger.info(f"[FreeModelHub] + Groq")
        return self

    def add_openrouter(self, token: str = "", model_list: Optional[List[str]] = None):
        """添加 OpenRouter"""
        key = token or os.getenv("OPENROUTER_API_KEY", "")
        if not key:
            return self
        self._openrouter = OpenRouterProvider(api_key=key)
        self._provider_count += 1
        logger.info(f"[FreeModelHub] + OpenRouter")
        return self

    def auto_configure(self):
        """从环境变量自动配置所有可用提供商"""
        self.add_github()
        self.add_groq()
        self.add_openrouter()
        return self

    # ============================================================
    # 并行对比
    # ============================================================

    async def compare_all(
        self, stock_context: str, prompt: str,
        max_models_per_provider: int = 2,
        temperature: float = 0.3,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        聚合所有免费模型并行对比分析。

        Returns:
            {results, consensus, stats}
        """
        all_results: List[Dict[str, Any]] = []
        tasks = []

        # GitHub Models
        if self._github and self._github.enabled:
            gh_models = self._github._model_list[:max_models_per_provider]
            tasks.append(self._github.compare(stock_context, prompt, gh_models))

        # Groq
        if self._groq and self._groq.enabled:
            groq_models = GroqProvider.FREE_MODELS[:max_models_per_provider]
            for model in groq_models:
                tasks.append(self._groq.call(
                    model,
                    [{"role": "user", "content": f"{prompt}\n\n{stock_context}"}],
                    temperature=temperature, timeout=timeout,
                ))

        # OpenRouter
        if self._openrouter and self._openrouter.enabled:
            or_models = OpenRouterProvider.FREE_MODELS[:max_models_per_provider]
            for model in or_models:
                tasks.append(self._openrouter.call(
                    model,
                    [{"role": "user", "content": f"{prompt}\n\n{stock_context}"}],
                    temperature=temperature, timeout=timeout,
                ))

        if not tasks:
            return {
                "results": [], "consensus": None,
                "stats": {"total": 0, "success": 0, "providers": 0},
            }

        # 并行执行所有调用
        all_raw = await asyncio.gather(*tasks, return_exceptions=True)

        # 展平结果
        for item in all_raw:
            if isinstance(item, list):
                all_results.extend(item)
            elif isinstance(item, dict):
                all_results.append(item)

        # 共识分析
        github_provider = self._github or GitHubModelsProvider()
        consensus = github_provider.build_consensus(all_results)

        # 统计
        success = sum(1 for r in all_results if r.get("success"))
        total_ms = sum(r.get("duration_ms", 0) for r in all_results)

        return {
            "results": all_results,
            "consensus": consensus,
            "stats": {
                "total": len(all_results),
                "success": success,
                "failed": len(all_results) - success,
                "providers": self._provider_count,
                "total_ms": round(total_ms, 1),
            },
        }

    def compare_sync(self, stock_context: str, prompt: str) -> Dict[str, Any]:
        """同步版（内部 asyncio.run）"""
        try:
            return asyncio.run(self.compare_all(stock_context, prompt))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run, self.compare_all(stock_context, prompt)
                ).result(timeout=180)

    # ============================================================
    # 状态
    # ============================================================

    def status(self) -> Dict[str, Any]:
        return {
            "providers": self._provider_count,
            "github": self._github.enabled if self._github else False,
            "groq": self._groq.enabled if self._groq else False,
            "openrouter": self._openrouter.enabled if self._openrouter else False,
            "total_models": len(self._all_models),
            "models": self._all_models,
        }

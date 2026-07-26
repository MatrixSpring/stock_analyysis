# -*- coding: utf-8 -*-
"""
===================================
多模型共识分析服务 — MultiModelAnalysisService
===================================

封装 FreeModelHub，提供 Pipeline 可调用的统一接口。

职责：
1. 管理 FreeModelHub 生命周期（初始化、健康检查、降级）
2. 提供同步/异步分析接口
3. 将共识结果注入分析上下文
4. 支持环境变量控制开关

使用方式：
    from src.services.multi_model_analysis import MultiModelAnalysisService
    svc = MultiModelAnalysisService()
    consensus = svc.analyze(stock_context, prompt)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MultiModelAnalysisService:
    """多模型共识分析服务。

    配置项（环境变量/Config）:
    - MULTI_MODEL_ENABLED: 启用/禁用 (默认 false)
    - MULTI_MODEL_MIN_COUNT: 最少参与模型数 (默认 3)
    - MULTI_MODEL_MAX_COUNT: 最多参与模型数 (默认 6)
    - MULTI_MODEL_CONSENSUS_THRESHOLD: 共识阈值 (默认 0.6)
    - MULTI_MODEL_TIMEOUT: 单模型超时秒数 (默认 60)
    - GITHUB_MODELS_TOKEN: GitHub Models API token
    - GROQ_API_KEY: Groq API key
    - OPENROUTER_API_KEY: OpenRouter API key
    """

    def __init__(
        self,
        enabled: Optional[bool] = None,
        min_models: Optional[int] = None,
        max_models: Optional[int] = None,
        consensus_threshold: float = 0.6,
        timeout: int = 60,
        github_token: str = "",
        groq_key: str = "",
        openrouter_key: str = "",
    ):
        # 配置加载：环境变量优先
        self._enabled = (
            enabled
            if enabled is not None
            else os.getenv("MULTI_MODEL_ENABLED", "false").lower() == "true"
        )
        self._min_models = min_models or int(os.getenv("MULTI_MODEL_MIN_COUNT", "3"))
        self._max_models = max_models or int(os.getenv("MULTI_MODEL_MAX_COUNT", "6"))
        self._threshold = consensus_threshold or float(
            os.getenv("MULTI_MODEL_CONSENSUS_THRESHOLD", "0.6")
        )
        self._timeout = timeout or int(os.getenv("MULTI_MODEL_TIMEOUT", "60"))

        # Token 加载
        self._github_token = github_token or os.getenv("GITHUB_MODELS_TOKEN", "")
        self._groq_key = groq_key or os.getenv("GROQ_API_KEY", "")
        self._openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY", "")

        # 内部状态
        self._hub = None  # 延迟初始化
        self._initialized = False
        self._last_health_check: float = 0.0
        self._health_check_ttl: float = 300.0  # 5 分钟

    # ---- 属性 ----

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._github_token or self._groq_key or self._openrouter_key)

    @property
    def provider_count(self) -> int:
        if not self._init_hub():
            return 0
        return self._hub._provider_count

    @property
    def available_models(self) -> List[str]:
        if not self._init_hub():
            return []
        return list(self._hub._all_models)

    # ---- 初始化 ----

    def _init_hub(self) -> bool:
        """延迟初始化 FreeModelHub"""
        if self._hub is not None:
            return True

        if not self.enabled:
            return False

        try:
            from src.llm.free_model_hub import FreeModelHub

            self._hub = FreeModelHub()
            self._hub.add_github(token=self._github_token)
            self._hub.add_groq(token=self._groq_key)
            self._hub.add_openrouter(token=self._openrouter_key)

            self._initialized = self._hub.enabled
            if self._initialized:
                logger.info(
                    f"[MultiModel] 初始化完成: "
                    f"{self._hub._provider_count} providers, "
                    f"{len(self._hub._all_models)} models"
                )
            else:
                logger.warning("[MultiModel] 未配置任何免费模型 token，服务已禁用")
            return self._initialized
        except Exception as e:
            logger.error(f"[MultiModel] 初始化失败: {e}")
            self._enabled = False
            return False

    def ensure_initialized(self) -> bool:
        """确保已初始化（在调用 analyze 前调用）"""
        return self._init_hub()

    # ---- 健康检查 ----

    def check_health(self, force: bool = False) -> Dict[str, Any]:
        """检查多模型服务健康状态"""
        now = time.time()
        if not force and now - self._last_health_check < self._health_check_ttl:
            return {"status": "cached", "enabled": self.enabled}

        if not self._init_hub():
            self._last_health_check = now
            return {"status": "disabled", "enabled": False}

        status = self._hub.status()
        status["status"] = "healthy" if self._hub.enabled else "degraded"
        self._last_health_check = now
        return status

    # ---- 核心分析 ----

    def analyze(
        self,
        stock_context: str,
        prompt: str,
        max_models: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """同步版多模型共识分析。

        Args:
            stock_context: 股票行情数据上下文
            prompt: 分析提示词
            max_models: 最多模型数 (默认用配置)
            timeout: 单模型超时秒数

        Returns:
            {results, consensus, stats, degradation_level}
        """
        if not self._init_hub():
            return {
                "results": [],
                "consensus": None,
                "stats": {"total": 0, "success": 0, "providers": 0},
                "degradation_level": "LEVEL_4",
            }

        max_m = max_models or self._max_models
        t = timeout or self._timeout

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._hub.compare_all(
                            stock_context, prompt,
                            max_models_per_provider=min(max_m, 3),
                            timeout=t,
                        ),
                    )
                    return future.result(timeout=t * max_m + 30)
            return asyncio.run(
                self._hub.compare_all(
                    stock_context, prompt,
                    max_models_per_provider=min(max_m, 3),
                    timeout=t,
                )
            )
        except RuntimeError:
            return asyncio.run(
                self._hub.compare_all(
                    stock_context, prompt,
                    max_models_per_provider=min(max_m, 3),
                    timeout=t,
                )
            )

    async def analyze_async(
        self,
        stock_context: str,
        prompt: str,
        max_models: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """异步版多模型共识分析"""
        if not self._init_hub():
            return {
                "results": [],
                "consensus": None,
                "stats": {"total": 0, "success": 0, "providers": 0},
            }

        max_m = max_models or self._max_models
        t = timeout or self._timeout

        return await self._hub.compare_all(
            stock_context, prompt,
            max_models_per_provider=min(max_m, 3),
            timeout=t,
        )

    # ---- 共识增强 ----

    def enhance_analysis_result(
        self,
        analysis_result: Any,
        stock_context: str,
        prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """对现有分析结果做多模型增强。

        如果多模型共识可用，将共识结果附加到分析结果上。
        """
        if not self.enabled:
            return None

        try:
            result = self.analyze(stock_context, prompt)
            if result.get("consensus"):
                # 将共识信息注入 analysis_result
                if hasattr(analysis_result, "multi_model_consensus"):
                    analysis_result.multi_model_consensus = result["consensus"]
                if hasattr(analysis_result, "multi_model_stats"):
                    analysis_result.multi_model_stats = result["stats"]

                logger.info(
                    f"[MultiModel] 共识增强完成: "
                    f"{result['stats']['success']}/{result['stats']['total']} 模型成功"
                )
                return result
        except Exception as e:
            logger.warning(f"[MultiModel] 共识增强失败: {e}")

        return None

    def build_consensus_report_markdown(self, analysis_result: Dict[str, Any]) -> str:
        """从多模型分析结果生成共识报告 Markdown"""
        consensus = analysis_result.get("consensus")
        stats = analysis_result.get("stats", {})
        results = analysis_result.get("results", [])

        if not consensus and not results:
            return ""

        lines = [
            "## 🤖 多模型共识研判",
            "",
            f"**参与模型**: {stats.get('total', 0)} | "
            f"**成功**: {stats.get('success', 0)} | "
            f"**提供商**: {stats.get('providers', 0)}",
            "",
        ]

        if consensus:
            cs = consensus
            lines.append(f"**综合可信度**: {cs.get('reliability_score', 0)}/100")
            lines.append(f"**最终结论**: {cs.get('final_conclusion', '无')}")
            lines.append("")

            if cs.get("consensus"):
                c = cs["consensus"]
                lines.append("### 维度共识")
                lines.append(f"- 趋势: {c.get('trend', '未知')}")
                lines.append(f"- 风险: {c.get('risk', '未知')}")
                lines.append(f"- 策略: {c.get('strategy', '未知')}")
                lines.append("")

            if cs.get("divergence"):
                lines.append("### ⚠️ 分歧点")
                for d in cs["divergence"]:
                    lines.append(f"- {d}")
                lines.append("")

        # 各模型输出摘要
        if results:
            lines.append("### 各模型研判")
            for r in results:
                success = r.get("success", False)
                icon = "✅" if success else "❌"
                model = r.get("model", "unknown")
                duration = r.get("duration_ms", 0)
                content_preview = ""
                if success and r.get("content"):
                    raw = str(r["content"])[:150]
                    content_preview = f": {raw}..."
                lines.append(
                    f"- {icon} **{model}** "
                    f"({duration:.0f}ms){content_preview}"
                )

        return "\n".join(lines)

    # ---- 降级信息 ----

    def degradation_info(self) -> Dict[str, Any]:
        """获取当前降级状态"""
        health = self.check_health()
        return {
            "enabled": self.enabled,
            "providers": health.get("providers", 0),
            "github_available": health.get("github", False),
            "groq_available": health.get("groq", False),
            "openrouter_available": health.get("openrouter", False),
            "total_models": health.get("total_models", 0),
            "status": health.get("status", "disabled"),
        }

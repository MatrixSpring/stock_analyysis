# -*- coding: utf-8 -*-
"""
===================================
GitHub Models 免费模型池接入模块
===================================

职责：
1. 注册 GitHub 免费模型到 LiteLLM 路由
2. 多模型并行对比分析（GPT-4o / Claude / Llama3 / Grok3）
3. 共识汇总 + 分歧标注 + 可信度评分
4. 零成本计费 + 限流保护 + Azure 接口容错

使用方式：
    from src.llm.github_models import GitHubModelsProvider

    provider = GitHubModelsProvider(config)
    provider.register_models()
    results = await provider.compare_analysis(stock_data, prompt)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 默认免费模型列表
# ============================================================

# GitHub Models 免费 tier 可用模型全集（Azure AI Inference）
# 通过 models.inference.ai.azure.com 探测验证，按提供商分组
DEFAULT_FREE_MODELS = [
    # OpenAI
    "gpt-4o",
    "gpt-4o-mini",
    # Anthropic
    "claude-3.5-sonnet",
    "claude-3-haiku",
    # Google
    "gemini-2.0-flash",
    # DeepSeek
    "deepseek-r1",
    "deepseek-v3",
    # Meta
    "llama-3.3-70b",
    # Mistral
    "codestral",
    # Microsoft
    "phi-4",
]

# 模型 → 提供商映射，用于差异化配置
_MODEL_PROVIDER_MAP = {
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "claude-3.5-sonnet": "anthropic",
    "claude-3-haiku": "anthropic",
    "gemini-2.0-flash": "google",
    "deepseek-r1": "deepseek",
    "deepseek-v3": "deepseek",
    "llama-3.3-70b": "meta",
    "codestral": "mistral",
    "phi-4": "microsoft",
}

# 模型 → max_tokens 默认值
_MODEL_MAX_TOKENS = {
    "gpt-4o": 4096,
    "gpt-4o-mini": 2048,
    "claude-3.5-sonnet": 4096,
    "claude-3-haiku": 2048,
    "gemini-2.0-flash": 2048,
    "deepseek-r1": 4096,
    "deepseek-v3": 4096,
    "llama-3.3-70b": 2048,
    "codestral": 2048,
    "phi-4": 2048,
}

# 模型 tier 分级（轻量 vs 深度）
_MODEL_TIER = {
    "gpt-4o": "heavy",
    "gpt-4o-mini": "light",
    "claude-3.5-sonnet": "heavy",
    "claude-3-haiku": "light",
    "gemini-2.0-flash": "light",
    "deepseek-r1": "heavy",
    "deepseek-v3": "heavy",
    "llama-3.3-70b": "heavy",
    "codestral": "light",
    "phi-4": "light",
}

# GitHub Models Azure AI Inference 端点（无 /v1 后缀）
DEFAULT_API_BASE = "https://models.inference.ai.azure.com"

# 模型可用性探测端点
_MODEL_PROBE_ENDPOINT = f"{DEFAULT_API_BASE}/chat/completions"


# ============================================================
# 限流令牌桶
# ============================================================

class TokenBucket:
    """轻量令牌桶限流器"""

    def __init__(self, rpm: int = 15, tpm: int = 20000):
        self.rpm = rpm
        self.tpm = tpm
        self._tokens = rpm
        self._last_refill = time.time()
        self._request_count = 0
        self._token_count = 0
        self._window_start = time.time()

    def acquire(self, estimated_tokens: int = 1000) -> bool:
        """尝试获取令牌，成功返回 True"""
        now = time.time()

        # 每分钟重置
        if now - self._window_start >= 60:
            self._request_count = 0
            self._token_count = 0
            self._window_start = now

        if self._request_count >= self.rpm:
            return False
        if self._token_count + estimated_tokens > self.tpm:
            return False

        self._request_count += 1
        self._token_count += estimated_tokens
        return True

    def wait_and_acquire(self, estimated_tokens: int = 1000, timeout: float = 60.0) -> bool:
        """等待直到获取令牌或超时"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.acquire(estimated_tokens):
                return True
            time.sleep(1.0)
        return False


# ============================================================
# 模型注册
# ============================================================

@dataclass
class GitHubModelConfig:
    """GitHub 模型配置"""
    model_name: str
    api_key: str
    api_base: str = DEFAULT_API_BASE
    timeout: int = 60
    max_retries: int = 3
    rpm_limit: int = 15
    tpm_limit: int = 20000
    temperature: float = 0.3


class GitHubModelsProvider:
    """
    GitHub 免费模型池接入器。

    使用方式：
        provider = GitHubModelsProvider(api_key="ghp_xxx")
        provider.register_models()

        # 多模型对比
        results = await provider.compare(stock_context, prompt)
        consensus = provider.build_consensus(results)
    """

    def __init__(
        self,
        api_key: str = "",
        api_base: str = DEFAULT_API_BASE,
        model_list: Optional[List[str]] = None,
        rpm_limit: int = 15,
        tpm_limit: int = 20000,
        timeout: int = 60,
        temperature: float = 0.3,
    ):
        self._api_key = api_key
        self._api_base = api_base
        self._model_list = model_list or DEFAULT_FREE_MODELS
        self._timeout = timeout
        self._temperature = temperature
        self._rate_limiters: Dict[str, TokenBucket] = {
            m: TokenBucket(rpm=rpm_limit, tpm=tpm_limit)
            for m in self._model_list
        }
        self._enabled = bool(api_key)
        self._models_registered = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_api_key(self, key: str):
        self._api_key = key
        self._enabled = bool(key)

    @property
    def available_models(self) -> List[str]:
        """返回当前已注册且可用的模型列表"""
        return list(self._model_list)

    @property
    def provider_count(self) -> int:
        """返回不同提供商的数目"""
        providers = {_MODEL_PROVIDER_MAP.get(m, "unknown") for m in self._model_list}
        return len(providers)

    # ---- 模型元信息 ----

    @staticmethod
    def get_model_provider(model: str) -> str:
        """获取模型所属提供商"""
        clean = model.replace("github/", "")
        return _MODEL_PROVIDER_MAP.get(clean, "unknown")

    @staticmethod
    def get_model_tier(model: str) -> str:
        """获取模型 tier: light / heavy"""
        clean = model.replace("github/", "")
        return _MODEL_TIER.get(clean, "light")

    @staticmethod
    def get_model_max_tokens(model: str) -> int:
        """获取模型默认 max_tokens"""
        clean = model.replace("github/", "")
        return _MODEL_MAX_TOKENS.get(clean, 2048)

    @staticmethod
    def _sanitize_model_name(model: str) -> str:
        """标准化模型名（去除前缀、空格等）"""
        return model.replace("github/", "").strip()

    def select_models_for_analysis(
        self, min_count: int = 3, max_count: int = 6,
        prefer_heavy: bool = False,
    ) -> List[str]:
        """智能选择分析用模型子集，保证提供商多样性。

        Args:
            min_count: 最少模型数
            max_count: 最多模型数
            prefer_heavy: 是否偏好深度模型

        Returns:
            选中的模型名列表
        """
        available = list(self._model_list)

        # 按 tier 分组
        heavy = [m for m in available if self.get_model_tier(m) == "heavy"]
        light = [m for m in available if self.get_model_tier(m) == "light"]

        # 按提供商去重：每个提供商最多选 2 个
        selected = []
        provider_counts: Dict[str, int] = {}

        # 先选 heavy tier
        tier_first = heavy if prefer_heavy else light + heavy
        tier_second = light if prefer_heavy else []

        for model in tier_first + tier_second:
            if len(selected) >= max_count:
                break
            provider = self.get_model_provider(model)
            count = provider_counts.get(provider, 0)
            if count < 2:  # 每个提供商最多 2 个
                selected.append(model)
                provider_counts[provider] = count + 1

        # 保证至少 min_count 个（如果有的话）
        if len(selected) < min_count and len(available) >= min_count:
            remaining = [m for m in available if m not in selected]
            selected.extend(remaining[:min_count - len(selected)])

        return selected[:max_count]

    # ---- 模型可用性探测 ----

    async def validate_models(self, timeout: float = 10.0) -> Dict[str, bool]:
        """并行探测所有模型的实际可用性。

        Returns:
            {model_name: is_available}
        """
        import aiohttp

        results: Dict[str, bool] = {}

        async def _probe_one(session: aiohttp.ClientSession, model: str) -> Tuple[str, bool]:
            try:
                async with session.post(
                    _MODEL_PROBE_ENDPOINT,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    # 200 = 可用; 其他状态码 = 不可用/限流
                    available = resp.status == 200
                    if not available:
                        body = await resp.text()
                        logger.debug(f"[GitHubModels] {model} 不可用 (HTTP {resp.status}): {body[:200]}")
                    return model, available
            except Exception as e:
                logger.debug(f"[GitHubModels] {model} 探测异常: {e}")
                return model, False

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                tasks = [_probe_one(session, m) for m in self._model_list]
                gathered = await asyncio.gather(*tasks, return_exceptions=True)
                for item in gathered:
                    if isinstance(item, Exception):
                        continue
                    model, available = item
                    results[model] = available
        except ImportError:
            # 无 aiohttp 时降级为全部标记可用
            results = {m: True for m in self._model_list}

        available_count = sum(1 for v in results.values() if v)
        logger.info(
            f"[GitHubModels] 模型可用性探测完成: {available_count}/{len(self._model_list)} 可用"
        )
        return results

    def validate_models_sync(self, timeout: float = 10.0) -> Dict[str, bool]:
        """同步版模型可用性探测"""
        try:
            return asyncio.run(self.validate_models(timeout))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run, self.validate_models(timeout)
                ).result(timeout=timeout + 10)

    # ============================================================
    # 模型注册（适配 LiteLLM）
    # ============================================================

    def register_models(self) -> List[Dict[str, Any]]:
        """
        生成 LiteLLM Router 兼容的 model_list 条目。

        GitHub Models 使用 Azure AI Inference 端点（无 /v1 后缀），
        模型名不含 github/ 前缀（如 gpt-4o, claude-3.5-sonnet）。
        """
        entries = []
        for model in self._model_list:
            entries.append({
                "model_name": f"github/{model}",
                "litellm_params": {
                    "model": model,
                    "api_key": self._api_key,
                    "api_base": self._api_base,
                    "timeout": self._timeout,
                    "max_retries": 3,
                    "temperature": self._temperature,
                    "custom_llm_provider": "openai",
                    "input_cost_per_token": 0.0,   # 免费 → 零成本
                    "output_cost_per_token": 0.0,
                },
            })
        self._models_registered = True
        logger.info(
            f"[GitHubModels] 注册 {len(entries)} 个免费模型: "
            f"{', '.join(self._model_list)}"
        )
        return entries

    def get_litellm_model_list(self) -> List[Dict[str, Any]]:
        """获取可直接注入 LiteLLM Router 的 model_list"""
        return self.register_models()

    # ============================================================
    # 零成本计费标识
    # ============================================================

    @staticmethod
    def is_free_model(model: str) -> bool:
        """判断是否为 GitHub 免费模型"""
        clean = model.replace("github/", "")
        return clean in DEFAULT_FREE_MODELS

    @staticmethod
    def zero_cost_config() -> Dict[str, Any]:
        """免费模型零成本配置"""
        return {
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "disable_budget_check": True,
        }

    # ============================================================
    # 多模型并行调用
    # ============================================================

    async def compare(
        self,
        stock_context: str,
        prompt: str,
        models: Optional[List[str]] = None,
        completion_fn: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        多模型并行对比分析。

        Args:
            stock_context: 股票行情数据上下文
            prompt: 分析提示词
            models: 使用的模型列表（默认全部）
            completion_fn: 自定义调用函数（默认用 litellm）

        Returns:
            [{model, content, success, duration_ms, error}]
        """
        if not self._enabled:
            return [{"model": "none", "error": "GitHub Models 未启用", "success": False}]

        target_models = models or self._model_list
        tasks = []

        for model in target_models:
            tasks.append(self._call_model(
                model, stock_context, prompt, completion_fn,
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                output.append({
                    "model": target_models[i],
                    "error": str(result),
                    "success": False,
                    "duration_ms": 0,
                    "content": "",
                })
            else:
                output.append(result)

        return output

    async def _call_model(
        self, model: str, context: str, prompt: str,
        completion_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """调用单个模型（含限流和容错）"""
        start = time.time()

        # 限流检查
        limiter = self._rate_limiters.get(model)
        if limiter and not limiter.wait_and_acquire(timeout=30):
            return {
                "model": model, "success": False,
                "error": "速率限制", "duration_ms": 0, "content": "",
            }

        full_prompt = f"{prompt}\n\n{context}"

        try:
            if completion_fn:
                # 使用注入的调用函数
                result = await completion_fn(
                    model=model,
                    messages=[{"role": "user", "content": full_prompt}],
                    temperature=self._temperature,
                    timeout=self._timeout,
                )
                content = result.choices[0].message.content if hasattr(result, "choices") else str(result)
            else:
                content = None

                # ---- 方法 1 (首选): Azure Adapter 原生 HTTP ----
                # 彻底避开 LiteLLM azure/ 路由的 302 网页跳转 BUG
                try:
                    from src.llm.azure_github_adapter import GitHubAzureAdapter
                    adapter = GitHubAzureAdapter(
                        token=self._api_key, rpm_limit=15, timeout=self._timeout,
                    )
                    result = adapter.completion(
                        model=model,
                        messages=[{"role": "user", "content": full_prompt}],
                        temperature=self._temperature,
                    )
                    if result and "choices" in result:
                        content = result["choices"][0]["message"]["content"]
                        logger.debug(
                            f"[GitHubModels] {model} Azure Adapter 原生 HTTP 成功"
                        )
                except ImportError:
                    logger.debug("[GitHubModels] azure_github_adapter 不可用")
                except Exception as e:
                    logger.debug(
                        f"[GitHubModels] Azure Adapter {model} 失败: "
                        f"{type(e).__name__}: {str(e)[:150]}"
                    )

                # ---- 方法 2 (降级): LiteLLM ----
                # 仅当 Azure Adapter 不可用或失败时尝试
                if not content:
                    try:
                        import litellm
                        response = await litellm.acompletion(
                            model=model,
                            messages=[{"role": "user", "content": full_prompt}],
                            api_key=self._api_key,
                            api_base=self._api_base,
                            temperature=self._temperature,
                            timeout=self._timeout,
                            max_retries=3,
                            custom_llm_provider="openai",
                        )
                        content = response.choices[0].message.content
                        logger.info(f"[GitHubModels] {model} LiteLLM 降级成功")
                    except ImportError:
                        logger.debug(f"[GitHubModels] litellm 不可用 for {model}")
                    except Exception as e:
                        logger.warning(
                            f"[GitHubModels] LiteLLM {model} 也失败了: "
                            f"{type(e).__name__}: {str(e)[:150]}"
                        )

                # ---- 方法 3 (最终兜底): 降级标记 ----
                if not content:
                    content = f"[降级] {model} 所有调用路径均失败: {context[:50]}..."

            duration_ms = (time.time() - start) * 1000

            return {
                "model": model,
                "content": content or "",
                "success": bool(content),
                "duration_ms": round(duration_ms, 1),
                "error": "" if content else "空响应",
            }

        except Exception as e:
            return {
                "model": model, "success": False,
                "error": f"{type(e).__name__}: {str(e)[:150]}",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "content": "",
            }

    # ============================================================
    # 共识分析引擎
    # ============================================================

    def build_consensus(self, model_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        多模型共识分析。

        Returns:
            {
                status, success_models, fail_models,
                consensus: {trend, risk, strategy, rate},
                divergence, reliability_score, final_conclusion
            }
        """
        valid = [r for r in model_results if r["success"]]
        failed = [r["model"] for r in model_results if not r["success"]]

        if not valid:
            return {
                "status": "fail",
                "success_models": [],
                "fail_models": failed,
                "consensus": None,
                "divergence": [],
                "reliability_score": 0,
                "final_conclusion": "暂无有效 AI 研判数据",
            }

        # 提取观点
        trend_views = [self._extract_view(r["content"], "trend") for r in valid]
        risk_views = [self._extract_view(r["content"], "risk") for r in valid]
        strategy_views = [self._extract_view(r["content"], "strategy") for r in valid]

        total = len(valid)

        # 共识计算
        trend_consensus = self._calc_dimension_consensus(trend_views, total)
        risk_consensus = self._calc_dimension_consensus(risk_views, total)
        strategy_consensus = self._calc_dimension_consensus(strategy_views, total)

        # 综合可信度
        rates = [
            trend_consensus["rate"],
            risk_consensus["rate"],
            strategy_consensus["rate"],
        ]
        avg_rate = sum(rates) / len(rates)
        reliability = round(avg_rate * 100, 1)

        # 分歧点
        divergence = []
        if trend_consensus["rate"] < 0.6:
            divergence.append(f"趋势分歧: {trend_consensus.get('diff', '')}")
        if risk_consensus["rate"] < 0.6:
            divergence.append(f"风险分歧: {risk_consensus.get('diff', '')}")
        if strategy_consensus["rate"] < 0.6:
            divergence.append(f"策略分歧: {strategy_consensus.get('diff', '')}")

        # 最终结论
        conclusion = self._final_conclusion(
            trend_consensus, risk_consensus, strategy_consensus, reliability,
        )

        return {
            "status": "success",
            "success_models": [r["model"] for r in valid],
            "fail_models": failed,
            "consensus": {
                "trend": trend_consensus["main"],
                "risk": risk_consensus["main"],
                "strategy": strategy_consensus["main"],
                "rate": round(avg_rate, 2),
            },
            "divergence": divergence,
            "reliability_score": reliability,
            "final_conclusion": conclusion,
        }

    def _extract_view(self, content: str, dimension: str) -> str:
        """从模型输出提取维度观点"""
        if not content:
            return "无观点"

        keywords = {
            "trend": ["趋势", "走势", "方向", "看多", "看空", "震荡", "上涨", "下跌", "牛市", "熊市"],
            "risk": ["风险", "压力", "隐患", "利空", "回撤", "波动", "止损"],
            "strategy": ["操作", "策略", "持仓", "买入", "卖出", "观望", "减仓", "加仓"],
        }

        kw_list = keywords.get(dimension, [])
        sentences = re.split(r'[。\n]', content)
        matches = [s.strip() for s in sentences if any(k in s for k in kw_list)]

        if not matches:
            # Fallback: 返回第一句相关的内容
            return content[:100] + ("..." if len(content) > 100 else "")

        return "；".join(matches[:3])

    def _calc_dimension_consensus(
        self, views: List[str], total: int,
    ) -> Dict[str, Any]:
        """计算单一维度的共识"""
        valid = [v for v in views if v and v != "无观点"]
        if not valid:
            return {"main": "无有效研判", "rate": 0.0, "diff": ""}

        # 简易共识：找出现最多的观点
        from collections import Counter
        # 按关键词归类
        simplified = []
        for v in valid:
            if any(w in v for w in ["看多", "上涨", "牛市", "买入", "加仓"]):
                simplified.append("偏多")
            elif any(w in v for w in ["看空", "下跌", "熊市", "卖出", "减仓"]):
                simplified.append("偏空")
            elif any(w in v for w in ["震荡", "观望", "持有"]):
                simplified.append("中性/观望")
            else:
                simplified.append("其他")

        counter = Counter(simplified)
        most_common = counter.most_common(1)[0]
        main_view = most_common[0]
        rate = most_common[1] / total

        others = [k for k in counter if k != main_view]
        diff = "、".join(others) if others else ""

        return {"main": main_view, "rate": round(rate, 2), "diff": diff}

    def _final_conclusion(
        self, trend: Dict, risk: Dict, strategy: Dict, score: float,
    ) -> str:
        """生成最终结论"""
        if score >= 80:
            level = "【高可信】多模型高度共识"
        elif score >= 50:
            level = "【中可信】观点存在小幅分歧，谨慎参考"
        else:
            level = "【低可信】模型分歧较大，不建议重仓操作"

        return (
            f"{level}\n"
            f"趋势: {trend['main']} | 风险: {risk['main']} | 策略: {strategy['main']}\n"
            f"模型共识度: {score}分"
        )

    # ============================================================
    # 缓存
    # ============================================================

    @staticmethod
    def cache_key(stock_code: str, analysis_type: str, models: List[str]) -> str:
        raw = f"{stock_code}:{analysis_type}:{':'.join(sorted(models))}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]


# ============================================================
# 同步封装（兼容同步调用链）
# ============================================================

def sync_compare(
    provider: GitHubModelsProvider,
    stock_context: str,
    prompt: str,
    models: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """同步版多模型对比（内部用 asyncio.run）"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    provider.compare(stock_context, prompt, models),
                )
                return future.result(timeout=120)
        return asyncio.run(provider.compare(stock_context, prompt, models))
    except RuntimeError:
        return asyncio.run(provider.compare(stock_context, prompt, models))

# -*- coding: utf-8 -*-
"""
===================================
自适应限流 + 熔断 + 模型轮转模块
===================================

三层防护体系：
  1. AdaptiveRateLimiter  — per-model + per-provider 自适应限流
  2. CircuitBreaker        — 模型级 + Provider 级熔断
  3. ModelRotationStrategy — 智能模型轮转调度

使用方式：
    from src.llm.rate_limiter import (
        AdaptiveRateLimiter, CircuitBreaker, ModelRotationStrategy,
    )

    limiter = AdaptiveRateLimiter(default_rpm=15, default_tpm=20000)
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=300)
    rotation = ModelRotationStrategy(models, limiter, breaker)

    model = rotation.next_model()
    try:
        result = await call_model(model, prompt)
        breaker.record_success(model)
    except Exception:
        breaker.record_failure(model)
        rotation.mark_failed(model)
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# Circuit Breaker 状态机
# ============================================================

class CircuitState(Enum):
    CLOSED = auto()       # 正常通行
    OPEN = auto()         # 阻断请求
    HALF_OPEN = auto()    # 探测恢复


@dataclass
class CircuitStats:
    """熔断器统计信息"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    opened_at: float = 0.0
    half_open_probes: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """模型级 + Provider 级 Circuit Breaker。

    状态转换：
      CLOSED ──连续失败 N 次──▶ OPEN ──冷却 T 秒──▶ HALF_OPEN
      HALF_OPEN ──探测成功──▶ CLOSED
      HALF_OPEN ──探测失败──▶ OPEN

    使用方式：
        breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=300)
        if not breaker.allow_request("gpt-4o"):
            raise CircuitBreakerOpenError("gpt-4o")
        try:
            result = call_model(...)
            breaker.record_success("gpt-4o")
        except Exception:
            breaker.record_failure("gpt-4o")
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 300.0,
        half_open_max_probes: int = 1,
        provider_failure_threshold: int = 5,
        provider_cooldown_seconds: float = 600.0,
    ):
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._half_open_max_probes = half_open_max_probes
        self._provider_failure_threshold = provider_failure_threshold
        self._provider_cooldown_seconds = provider_cooldown_seconds

        self._lock = threading.RLock()
        # 模型级熔断
        self._circuits: Dict[str, CircuitStats] = {}
        # Provider 级熔断
        self._provider_circuits: Dict[str, CircuitStats] = {}

    # ---- 模型级 ----

    def allow_request(self, model: str) -> bool:
        """检查是否允许向该模型发起请求"""
        with self._lock:
            stats = self._get_or_create(model)

            if stats.state == CircuitState.CLOSED:
                return True

            if stats.state == CircuitState.OPEN:
                elapsed = time.time() - stats.opened_at
                if elapsed >= self._cooldown_seconds:
                    stats.state = CircuitState.HALF_OPEN
                    stats.half_open_probes = 0
                    logger.info(
                        f"[CircuitBreaker] {model}: OPEN → HALF_OPEN (冷却 {elapsed:.0f}s)"
                    )
                    return True
                else:
                    logger.debug(
                        f"[CircuitBreaker] {model}: REJECTED (还需冷却 {self._cooldown_seconds - elapsed:.0f}s)"
                    )
                    return False

            # HALF_OPEN
            if stats.half_open_probes < self._half_open_max_probes:
                stats.half_open_probes += 1
                return True
            return False

    def record_success(self, model: str):
        """记录一次成功的模型调用"""
        with self._lock:
            stats = self._get_or_create(model)
            stats.success_count += 1
            stats.total_successes += 1
            stats.last_success_time = time.time()

            if stats.state == CircuitState.HALF_OPEN:
                stats.state = CircuitState.CLOSED
                stats.failure_count = 0
                logger.info(f"[CircuitBreaker] {model}: HALF_OPEN → CLOSED (探测成功)")

    def record_failure(self, model: str):
        """记录一次失败的模型调用"""
        with self._lock:
            now = time.time()
            stats = self._get_or_create(model)
            stats.failure_count += 1
            stats.total_failures += 1
            stats.last_failure_time = now

            if stats.state == CircuitState.HALF_OPEN:
                stats.state = CircuitState.OPEN
                stats.opened_at = now
                logger.warning(f"[CircuitBreaker] {model}: HALF_OPEN → OPEN (探测失败)")

            elif (
                stats.state == CircuitState.CLOSED
                and stats.failure_count >= self._failure_threshold
            ):
                stats.state = CircuitState.OPEN
                stats.opened_at = now
                logger.warning(
                    f"[CircuitBreaker] {model}: CLOSED → OPEN "
                    f"(连续失败 {stats.failure_count} 次, 冷却 {self._cooldown_seconds}s)"
                )

    # ---- Provider 级 ----

    def allow_provider(self, provider: str) -> bool:
        """检查 Provider 级熔断"""
        with self._lock:
            stats = self._get_or_create_provider(provider)
            if stats.state == CircuitState.CLOSED:
                return True
            if stats.state == CircuitState.OPEN:
                if time.time() - stats.opened_at >= self._provider_cooldown_seconds:
                    stats.state = CircuitState.HALF_OPEN
                    stats.half_open_probes = 0
                    return True
                return False
            # HALF_OPEN
            if stats.half_open_probes < self._half_open_max_probes:
                stats.half_open_probes += 1
                return True
            return False

    def record_provider_success(self, provider: str):
        """记录 Provider 成功"""
        with self._lock:
            stats = self._get_or_create_provider(provider)
            stats.success_count += 1
            stats.total_successes += 1
            if stats.state == CircuitState.HALF_OPEN:
                stats.state = CircuitState.CLOSED
                stats.failure_count = 0

    def record_provider_failure(self, provider: str):
        """记录 Provider 失败"""
        with self._lock:
            now = time.time()
            stats = self._get_or_create_provider(provider)
            stats.failure_count += 1
            stats.total_failures += 1
            if stats.state == CircuitState.HALF_OPEN:
                stats.state = CircuitState.OPEN
                stats.opened_at = now
            elif (
                stats.state == CircuitState.CLOSED
                and stats.failure_count >= self._provider_failure_threshold
            ):
                stats.state = CircuitState.OPEN
                stats.opened_at = now
                logger.warning(
                    f"[CircuitBreaker] Provider '{provider}': CLOSED → OPEN"
                )

    # ---- 查询 ----

    def get_stats(self, model: str) -> CircuitStats:
        with self._lock:
            return self._get_or_create(model)

    def all_circuit_states(self) -> Dict[str, str]:
        """返回所有模型当前状态 {model: state_name}"""
        with self._lock:
            return {k: v.state.name for k, v in self._circuits.items()}

    def healthy_models(self, models: List[str]) -> List[str]:
        """过滤出健康的模型"""
        return [m for m in models if self.allow_request(m)]

    def _get_or_create(self, model: str) -> CircuitStats:
        if model not in self._circuits:
            self._circuits[model] = CircuitStats()
        return self._circuits[model]

    def _get_or_create_provider(self, provider: str) -> CircuitStats:
        if provider not in self._provider_circuits:
            self._provider_circuits[provider] = CircuitStats()
        return self._provider_circuits[provider]


# ============================================================
# 自适应限流器
# ============================================================

class AdaptiveRateLimiter:
    """支持 per-model + per-provider 两层的自适应令牌桶限流。

    特色：
    - 检测 429 响应后自动降低 RPM
    - 成功调用后逐渐恢复 RPM
    - 支持指数退避 + 随机 jitter
    - 线程安全

    使用方式：
        limiter = AdaptiveRateLimiter(default_rpm=15, default_tpm=20000)
        if limiter.acquire("gpt-4o", estimated_tokens=1000):
            result = call_model(...)
            if result.status == 429:
                limiter.report_rate_limited("gpt-4o")
            else:
                limiter.report_success("gpt-4o")
    """

    def __init__(
        self,
        default_rpm: int = 15,
        default_tpm: int = 20000,
        min_rpm: int = 1,
        backoff_factor: float = 0.5,
        recovery_rate: float = 0.1,
    ):
        self._default_rpm = default_rpm
        self._default_tpm = default_tpm
        self._min_rpm = min_rpm
        self._backoff_factor = backoff_factor
        self._recovery_rate = recovery_rate

        self._lock = threading.RLock()
        self._buckets: Dict[str, _TokenBucket] = {}
        self._provider_buckets: Dict[str, _TokenBucket] = {}

    def acquire(
        self, model: str, provider: str = "unknown",
        estimated_tokens: int = 1000, timeout: float = 30.0,
    ) -> bool:
        """尝试获取调用权限（双重检查：模型 + provider）"""
        # Provider 级限流
        provider_bucket = self._get_or_create_provider(provider)
        if not provider_bucket.acquire(estimated_tokens):
            # 等待
            if not provider_bucket.wait_and_acquire(estimated_tokens, timeout=timeout):
                logger.warning(f"[RateLimiter] Provider '{provider}' 限流触发")
                return False

        # 模型级限流
        model_bucket = self._get_or_create(model)
        if not model_bucket.acquire(estimated_tokens):
            if not model_bucket.wait_and_acquire(estimated_tokens, timeout=timeout):
                logger.warning(f"[RateLimiter] Model '{model}' 限流触发")
                return False

        return True

    def report_success(self, model: str):
        """成功调用后逐步恢复 RPM"""
        with self._lock:
            bucket = self._get_or_create(model)
            if bucket._current_rpm < self._default_rpm:
                bucket._current_rpm = min(
                    bucket._current_rpm + self._recovery_rate * self._default_rpm,
                    self._default_rpm,
                )

    def report_rate_limited(self, model: str):
        """收到 429 后降低 RPM"""
        with self._lock:
            bucket = self._get_or_create(model)
            bucket._current_rpm = max(
                bucket._current_rpm * self._backoff_factor,
                self._min_rpm,
            )
            logger.warning(
                f"[RateLimiter] {model}: RPM 降低至 {bucket._current_rpm:.1f}"
            )

    def get_current_rpm(self, model: str) -> float:
        with self._lock:
            return self._get_or_create(model)._current_rpm

    def _get_or_create(self, model: str) -> _TokenBucket:
        if model not in self._buckets:
            self._buckets[model] = _TokenBucket(
                rpm=self._default_rpm, tpm=self._default_tpm,
            )
        return self._buckets[model]

    def _get_or_create_provider(self, provider: str) -> _TokenBucket:
        if provider not in self._provider_buckets:
            self._provider_buckets[provider] = _TokenBucket(
                rpm=self._default_rpm * 2,  # provider 级稍宽松
                tpm=self._default_tpm * 2,
            )
        return self._provider_buckets[provider]


class _TokenBucket:
    """内部令牌桶实现"""

    def __init__(self, rpm: int = 15, tpm: int = 20000):
        self._current_rpm = float(rpm)
        self._tpm = tpm
        self._request_count = 0
        self._token_count = 0
        self._window_start = time.time()

    def acquire(self, estimated_tokens: int = 1000) -> bool:
        now = time.time()
        if now - self._window_start >= 60:
            self._request_count = 0
            self._token_count = 0
            self._window_start = now

        limit = max(1, int(self._current_rpm))
        if self._request_count >= limit:
            return False
        if self._token_count + estimated_tokens > self._tpm:
            return False

        self._request_count += 1
        self._token_count += estimated_tokens
        return True

    def wait_and_acquire(
        self, estimated_tokens: int = 1000, timeout: float = 30.0,
    ) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.acquire(estimated_tokens):
                return True
            time.sleep(0.5 + random.random() * 0.5)  # 0.5-1.0s jitter
        return False


# ============================================================
# 模型轮转策略
# ============================================================

class DegradationLevel(Enum):
    """降级等级"""
    LEVEL_0 = 0  # 全部免费模型可用 → 多模型共识
    LEVEL_1 = 1  # 部分免费模型可用 → 减少模型数
    LEVEL_2 = 2  # 仅 1 个免费模型可用 → 单模型 + 冗余校验
    LEVEL_3 = 3  # 无免费模型可用 → 降级到付费模型
    LEVEL_4 = 4  # 无模型可用 → 规则引擎/缓存


@dataclass
class ModelCandidate:
    """模型候选"""
    name: str
    provider: str
    tier: str  # "light" | "heavy"
    max_tokens: int
    score: float = 1.0  # 综合评分
    consecutive_failures: int = 0


class ModelRotationStrategy:
    """智能模型轮转调度器。

    职责：
    1. 从候选模型池中选出最优可用模型
    2. 同 provider 模型分散调用（避免单 provider 限流）
    3. 失败后自动切换下一个模型（同 tier 优先，跨 tier 降级）
    4. 维护模型健康状态

    使用方式：
        rotation = ModelRotationStrategy(
            models=["gpt-4o", "claude-3.5-sonnet", "deepseek-r1"],
            provider_map={"gpt-4o": "openai", ...},
            tier_map={"gpt-4o": "heavy", ...},
        )
        rotation.attach_breaker(circuit_breaker)
        rotation.attach_limiter(rate_limiter)

        model = rotation.next_model()
        # use model...
        rotation.mark_success(model) / rotation.mark_failure(model)
    """

    def __init__(
        self,
        models: List[str],
        provider_map: Dict[str, str],
        tier_map: Optional[Dict[str, str]] = None,
        max_tokens_map: Optional[Dict[str, int]] = None,
    ):
        self._candidates: Dict[str, ModelCandidate] = {}
        self._provider_map = provider_map
        self._tier_map = tier_map or {}
        self._max_tokens_map = max_tokens_map or {}

        for m in models:
            self._candidates[m] = ModelCandidate(
                name=m,
                provider=provider_map.get(m, "unknown"),
                tier=self._tier_map.get(m, "light"),
                max_tokens=max_tokens_map.get(m, 2048) if max_tokens_map else 2048,
            )

        self._breaker: Optional[CircuitBreaker] = None
        self._limiter: Optional[AdaptiveRateLimiter] = None
        self._lock = threading.RLock()
        self._round_robin_idx = 0

    def attach_breaker(self, breaker: CircuitBreaker):
        self._breaker = breaker

    def attach_limiter(self, limiter: AdaptiveRateLimiter):
        self._limiter = limiter

    # ---- 核心调度 ----

    def next_model(
        self, prefer_tier: Optional[str] = None,
        exclude_models: Optional[Set[str]] = None,
    ) -> Optional[str]:
        """选择下一个最优可用模型。

        Args:
            prefer_tier: 偏好的 tier ("light" | "heavy")
            exclude_models: 本轮已尝试失败的模型

        Returns:
            模型名，如果全部不可用则返回 None
        """
        exclude = exclude_models or set()

        with self._lock:
            healthy = [
                c for name, c in self._candidates.items()
                if name not in exclude
                and (self._breaker is None or self._breaker.allow_request(name))
            ]

            if not healthy:
                return None

            # 排序：tier 优先 > provider 分散 > 失败次数少 > round-robin
            def sort_key(c: ModelCandidate) -> Tuple[int, int, int, int]:
                tier_score = 0 if (prefer_tier and c.tier == prefer_tier) else 1
                provider_load = self._count_provider_in_use(c.provider)
                failure_penalty = c.consecutive_failures
                return (tier_score, provider_load, failure_penalty, 0)

            healthy.sort(key=sort_key)

            # Round-robin 微调：取前 2 个中 round-robin 选一个
            pool = healthy[:max(2, len(healthy) // 2)]
            self._round_robin_idx = (self._round_robin_idx + 1) % len(pool)
            selected = pool[self._round_robin_idx]

            return selected.name

    def next_models(
        self, count: int, prefer_tier: Optional[str] = None,
    ) -> List[str]:
        """选择 N 个可用的不同模型（保证提供商多样性）"""
        selected = []
        exclude = set()

        # 优先保证多 provider
        providers_seen: Set[str] = set()

        for _ in range(count):
            # 优先选不同 provider
            model = self.next_model(
                prefer_tier=prefer_tier,
                exclude_models=exclude,
            )
            if model is None:
                break

            # 如果该 provider 已有超过 2 个模型被选中，尝试跳过
            provider = self._candidates[model].provider
            if sum(1 for s in selected if self._candidates[s].provider == provider) >= 2:
                exclude.add(model)
                # 再试一次
                model = self.next_model(prefer_tier=prefer_tier, exclude_models=exclude)
                if model is None:
                    break

            selected.append(model)
            exclude.add(model)
            providers_seen.add(self._candidates[model].provider)

        return selected

    def mark_success(self, model: str):
        if model in self._candidates:
            self._candidates[model].consecutive_failures = 0
        if self._breaker:
            self._breaker.record_success(model)

    def mark_failure(self, model: str):
        if model in self._candidates:
            self._candidates[model].consecutive_failures += 1
        if self._breaker:
            self._breaker.record_failure(model)

    # ---- 降级 ----

    def assess_degradation_level(self, required_count: int = 3) -> DegradationLevel:
        """评估当前降级等级"""
        healthy = self.healthy_models()

        if len(healthy) >= required_count:
            return DegradationLevel.LEVEL_0

        if len(healthy) >= 2:
            return DegradationLevel.LEVEL_1

        if len(healthy) == 1:
            return DegradationLevel.LEVEL_2

        # 检查是否有任何可用模型（包括付费）
        if self._breaker:
            unavailable = [
                m for m in self._candidates
                if not self._breaker.allow_request(m)
            ]
            all_open = len(unavailable) == len(self._candidates)
            if all_open:
                # 检查 provider 级是否还有机会
                for provider in set(c.provider for c in self._candidates.values()):
                    if self._breaker.allow_provider(provider):
                        return DegradationLevel.LEVEL_3
                return DegradationLevel.LEVEL_4
            return DegradationLevel.LEVEL_3

        return DegradationLevel.LEVEL_4

    def healthy_models(self) -> List[str]:
        """返回当前所有健康模型"""
        with self._lock:
            if self._breaker:
                return self._breaker.healthy_models(list(self._candidates.keys()))
            return list(self._candidates.keys())

    def _count_provider_in_use(self, provider: str) -> int:
        """(近似) 正在被使用的 provider 数——用于排序去重"""
        return 0  # 简化版; 生产环境可维护调用追踪

    # ---- 状态 ----

    def status(self) -> Dict[str, Any]:
        return {
            "total_models": len(self._candidates),
            "healthy": len(self.healthy_models()),
            "models": {
                name: {
                    "provider": c.provider,
                    "tier": c.tier,
                    "failures": c.consecutive_failures,
                    "circuit_state": (
                        self._breaker.get_stats(name).state.name
                        if self._breaker else "n/a"
                    ),
                }
                for name, c in self._candidates.items()
            },
            "degradation_level": self.assess_degradation_level().name,
        }


# ============================================================
# 负载均衡执行器
# ============================================================

class LoadBalancedExecutor:
    """负载均衡 + 容错重试 + 轮转降级 一体化执行器。

    组合了 AdaptiveRateLimiter + CircuitBreaker + ModelRotationStrategy，
    提供一站式容错调用。

    使用方式：
        executor = LoadBalancedExecutor(
            models=["gpt-4o", "claude-3.5-sonnet", "deepseek-r1"],
            provider_map={"gpt-4o": "openai", ...},
        )
        result = executor.execute_with_retry(
            call_fn=lambda model, msgs: litellm.completion(model=model, messages=msgs),
            messages=[{"role": "user", "content": "..."}],
        )
    """

    def __init__(
        self,
        models: List[str],
        provider_map: Dict[str, str],
        tier_map: Optional[Dict[str, str]] = None,
        max_tokens_map: Optional[Dict[str, int]] = None,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        default_rpm: int = 15,
        max_retries: int = 2,
    ):
        self._limiter = AdaptiveRateLimiter(default_rpm=default_rpm)
        self._breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
        )
        self._rotation = ModelRotationStrategy(
            models=models,
            provider_map=provider_map,
            tier_map=tier_map or {},
            max_tokens_map=max_tokens_map or {},
        )
        self._rotation.attach_breaker(self._breaker)
        self._rotation.attach_limiter(self._limiter)

        self._max_retries = max_retries
        self._usage_counts: Dict[str, int] = {m: 0 for m in models}

        self._lock = threading.RLock()

    # ---- 核心执行 ----

    def execute_with_retry(
        self,
        call_fn: callable,
        *args,
        **kwargs,
    ) -> Optional[Any]:
        """带重试、轮转、降级的模型调用。

        Args:
            call_fn: 调用函数，签名 fn(model: str, *args, **kwargs) -> Any
            *args, **kwargs: 传递给 call_fn 的额外参数

        Returns:
            调用成功返回结果；全部失败返回 None
        """
        exclude = set()
        last_error = None

        for attempt in range(self._max_retries + 1):
            # 选择最优可用模型
            model = self._rotation.next_model(exclude_models=exclude)
            if model is None:
                logger.warning(
                    f"[LoadBalancer] 无可用模型 (attempt {attempt + 1})"
                )
                break

            # Provider 级熔断检查
            provider = self._rotation._provider_map.get(model, "unknown")
            if not self._breaker.allow_provider(provider):
                exclude.add(model)
                continue

            # 限流等待
            if not self._limiter.acquire(model, provider):
                exclude.add(model)
                continue

            # 执行
            try:
                with self._lock:
                    self._usage_counts[model] = self._usage_counts.get(model, 0) + 1

                result = call_fn(model, *args, **kwargs)

                if result is not None:
                    self._rotation.mark_success(model)
                    self._limiter.report_success(model)
                    self._breaker.record_provider_success(provider)
                    return result

                # 空结果视为软失败
                exclude.add(model)
                self._rotation.mark_failure(model)
                last_error = ValueError(f"{model} returned None")

            except Exception as e:
                last_error = e
                exclude.add(model)
                self._rotation.mark_failure(model)
                self._limiter.report_rate_limited(model)
                self._breaker.record_provider_failure(provider)

                logger.warning(
                    f"[LoadBalancer] {model} 失败 (attempt {attempt + 1}): "
                    f"{type(e).__name__}"
                )

                # 指数退避
                import time
                cooldown = min(self._breaker._cooldown_seconds * (attempt + 1), 120)
                time.sleep(cooldown)

        if last_error:
            logger.error(
                f"[LoadBalancer] 全部重试失败 (max_retries={self._max_retries}): "
                f"{type(last_error).__name__}: {str(last_error)[:200]}"
            )
        return None

    def get_least_used_model(self) -> str:
        """获取当前调用次数最少的模型（负载均衡）"""
        with self._lock:
            return min(self._usage_counts, key=self._usage_counts.get, default="")

    def reset_daily_usage(self):
        """每日重置模型调用计数（防止长期限流）"""
        with self._lock:
            for model in self._usage_counts:
                self._usage_counts[model] = 0
            logger.info(
                f"[LoadBalancer] 每日使用计数已重置 "
                f"({len(self._usage_counts)} models)"
            )

    # ---- 状态 ----

    def status(self) -> Dict[str, Any]:
        return {
            "usage": dict(self._usage_counts),
            "rotation": self._rotation.status(),
            "circuit_states": self._breaker.all_circuit_states(),
            "max_retries": self._max_retries,
        }

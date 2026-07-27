# -*- coding: utf-8 -*-
"""
ProviderRouter — 数据源智能路由模块

功能：
  1. 按优先级选择主数据源
  2. 读取 Mongo crawl_metadata 判断数据源健康状态
  3. 故障自动切换备选源
  4. 统一入口向上层 service 提供数据

设计原则：不修改现有 DataFetcherManager，作为上层包装器使用。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from data_provider.provider_config import (
    PROVIDER_PRIORITY,
    RATE_LIMIT_CONFIG,
    FEATURE_FLAGS,
    TokenBucket,
)

logger = logging.getLogger(__name__)


# ============================================================
# 数据源健康追踪
# ============================================================

@dataclass
class SourceHealth:
    """单个数据源的健康状态"""
    name: str
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_success_at: float = 0.0
    last_failure_at: float = 0.0
    last_error_message: str = ""
    cooldown_until: float = 0.0
    circuit_open: bool = False

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.success_count / self.total_requests

    @property
    def is_healthy(self) -> bool:
        """判断数据源当前是否可用"""
        if self.circuit_open:
            if time.time() < self.cooldown_until:
                return False
            # 冷却期结束，半开状态
            self.circuit_open = False
        return True

    def record_success(self):
        self.total_requests += 1
        self.success_count += 1
        self.consecutive_failures = 0
        self.last_success_at = time.time()

    def record_failure(self, error_msg: str = ""):
        self.total_requests += 1
        self.failure_count += 1
        self.consecutive_failures += 1
        self.last_failure_at = time.time()
        self.last_error_message = error_msg

        threshold = RATE_LIMIT_CONFIG["circuit_failure_threshold"]
        if self.consecutive_failures >= threshold:
            self.circuit_open = True
            self.cooldown_until = time.time() + RATE_LIMIT_CONFIG["circuit_cooldown_seconds"]
            logger.warning(
                f"[ProviderRouter] {self.name} circuit OPEN — "
                f"{self.consecutive_failures} consecutive failures, "
                f"cooldown until {self.cooldown_until:.0f}"
            )


class HealthTracker:
    """全局数据源健康追踪器（单例）"""

    _instance: Optional["HealthTracker"] = None
    _sources: Dict[str, SourceHealth] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sources = {}
        return cls._instance

    def get(self, name: str) -> SourceHealth:
        if name not in self._sources:
            self._sources[name] = SourceHealth(name=name)
        return self._sources[name]

    def get_all_health(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": h.name,
                "success_rate": round(h.success_rate, 3),
                "total_requests": h.total_requests,
                "consecutive_failures": h.consecutive_failures,
                "circuit_open": h.circuit_open,
                "is_healthy": h.is_healthy,
            }
            for h in self._sources.values()
        ]

    def reset(self, name: Optional[str] = None):
        if name:
            self._sources.pop(name, None)
        else:
            self._sources.clear()


# ============================================================
# 令牌桶限流管理器
# ============================================================

class RateLimiter:
    """全局令牌桶限流管理器"""

    _buckets: Dict[str, TokenBucket] = {}

    @classmethod
    def for_source(cls, source_name: str, tier: str = "free") -> TokenBucket:
        key = f"{source_name}:{tier}"
        if key not in cls._buckets:
            rps = (
                RATE_LIMIT_CONFIG["free_tier_rps"]
                if tier == "free"
                else RATE_LIMIT_CONFIG["paid_tier_rps"]
            )
            cls._buckets[key] = TokenBucket(rate=rps, max_tokens=rps * 3)
        return cls._buckets[key]

    @classmethod
    def wait_if_needed(cls, source_name: str, tier: str = "free",
                       timeout: float = 30.0) -> bool:
        bucket = cls.for_source(source_name, tier)
        return bucket.wait_and_acquire(timeout=timeout)


# ============================================================
# ProviderRouter 核心路由
# ============================================================

FREE_TIER_SOURCES = {"efinance", "akshare", "baostock", "tencent", "pytdx"}

PAID_TIER_SOURCES = {"tushare", "tickflow", "finnhub", "alphavantage", "longbridge"}


@dataclass
class RouteResult:
    """路由结果"""
    data: Any
    source_name: str
    success: bool
    error_message: str = ""
    attempt_count: int = 0
    total_duration_ms: float = 0.0


class ProviderRouter:
    """
    数据源智能路由器。

    使用方式：
        router = ProviderRouter()
        result = router.fetch("daily_kline", fetcher_func_map, stock_code, ...)

    也可以在现有 DataFetcherManager 之上包装使用。
    """

    def __init__(self):
        self._health = HealthTracker()
        self._rate_limiter = RateLimiter()

    @property
    def health(self) -> HealthTracker:
        return self._health

    def fetch(
        self,
        data_type: str,
        fetcher_map: Dict[str, Callable],
        *args,
        max_retries: int = 2,
        **kwargs,
    ) -> RouteResult:
        """
        按优先级依次尝试数据源，直到成功或全部失败。

        Args:
            data_type: 数据类型（daily_kline/realtime_quote/chip_distribution 等）
            fetcher_map: {"efinance": callable, "akshare": callable, ...}
            *args, **kwargs: 传给 fetcher callable 的参数

        Returns:
            RouteResult
        """
        priority_list = PROVIDER_PRIORITY.get(data_type, [])
        if not priority_list:
            return RouteResult(data=None, source_name="", success=False,
                              error_message=f"Unknown data_type: {data_type}")

        if not FEATURE_FLAGS.get("enable_auto_provider_route", True):
            # 路由关闭 → 直接使用第一个可用源
            priority_list = [priority_list[0]]

        errors = []
        start_time = time.time()
        attempt_count = 0

        for source_name in priority_list:
            if source_name not in fetcher_map:
                errors.append(f"{source_name}: not in fetcher_map")
                continue

            health = self._health.get(source_name)
            if not health.is_healthy:
                errors.append(f"{source_name}: circuit open")
                continue

            # 限流检查
            tier = "paid" if source_name in PAID_TIER_SOURCES else "free"
            if not self._rate_limiter.wait_if_needed(source_name, tier, timeout=10.0):
                errors.append(f"{source_name}: rate limited")
                continue

            # 执行抓取
            attempt_count += 1
            try:
                fetcher_fn = fetcher_map[source_name]
                data = fetcher_fn(*args, **kwargs)
                health.record_success()
                duration = (time.time() - start_time) * 1000
                return RouteResult(
                    data=data, source_name=source_name, success=True,
                    attempt_count=attempt_count, total_duration_ms=duration,
                )
            except Exception as e:
                err_msg = f"{type(e).__name__}: {str(e)[:200]}"
                health.record_failure(err_msg)
                errors.append(f"{source_name}: {err_msg}")
                if attempt_count <= max_retries:
                    continue

        duration = (time.time() - start_time) * 1000
        return RouteResult(
            data=None, source_name="", success=False,
            error_message=" | ".join(errors[-3:]),
            attempt_count=attempt_count, total_duration_ms=duration,
        )

    def get_health_report(self) -> Dict[str, Any]:
        """获取所有数据源的健康报告"""
        return {
            "sources": self._health.get_all_health(),
            "priorities": PROVIDER_PRIORITY,
        }

    # ============================================================
    # 专用路由方法（Phase 1-3 新增：筹码/基本面/新闻/舆情）
    # ============================================================

    async def get_chip_distribution(
        self, code: str, market: str, trade_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """筹码分布：efinance 主源 → akshare 备选"""
        import asyncio as _asyncio
        priority = PROVIDER_PRIORITY.get("chip_distribution", ["efinance", "akshare"])
        for source_name in priority:
            result = self._try_fetch_async(source_name, "get_chip_distribution",
                                          code, market, trade_date)
            if result:
                return result
        return None

    async def get_fundamental(
        self, code: str, market: str, report_period: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """基本面：akshare 主源 → baostock → tushare"""
        priority = PROVIDER_PRIORITY.get("fundamental", ["akshare", "baostock", "tushare"])
        for source_name in priority:
            result = self._try_fetch_async(source_name, "get_fundamental",
                                          code, market, report_period)
            if result:
                return result
        return []

    async def get_stock_news(
        self, code: str, market: str, limit: int = 50,
        start_dt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """新闻资讯：akshare → tushare"""
        priority = ["akshare", "tushare"]
        for source_name in priority:
            result = self._try_fetch_async(source_name, "get_stock_news",
                                          code, market, limit, start_dt)
            if result:
                return result
        return []

    async def get_stock_sentiment(
        self, code: str, market: str, limit: int = 100,
        start_dt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """舆情评论：efinance 主源 → akshare 备选"""
        priority = PROVIDER_PRIORITY.get("chip_distribution", ["efinance", "akshare"])
        for source_name in priority:
            result = self._try_fetch_async(source_name, "get_stock_sentiment",
                                          code, market, limit, start_dt)
            if result:
                return result
        return []

    # ============================================================
    # 内部：异步调用 fetcher 方法（兼容现有同步 fetcher）
    # ============================================================

    def _try_fetch_async(self, source_name: str, method: str, *args, **kwargs) -> Any:
        """尝试从指定数据源获取数据，失败返回 None"""
        import concurrent.futures
        health = self._health.get(source_name)
        if not health.is_healthy:
            return None

        tier = "paid" if source_name in PAID_TIER_SOURCES else "free"
        if not self._rate_limiter.wait_if_needed(source_name, tier, timeout=10.0):
            return None

        try:
            # 从 DataFetcherManager 的 _fetchers_by_name 获取实例
            # 如果未注入，返回 None 触发降级
            import asyncio as _asyncio
            fetcher = self._get_fetcher_by_name(source_name)
            if fetcher is None:
                return None

            func = getattr(fetcher, method, None)
            if func is None:
                return None

            # 兼容同步/异步方法
            if _asyncio.iscoroutinefunction(func):
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(_asyncio.run, func(*args, **kwargs))
                        result = future.result(timeout=30)
                else:
                    result = loop.run_until_complete(func(*args, **kwargs))
            else:
                result = func(*args, **kwargs)

            health.record_success()
            return result
        except Exception as e:
            health.record_failure(str(e)[:200])
            return None

    def _get_fetcher_by_name(self, source_name: str) -> Any:
        """从已注册的 DataFetcherManager 查找 fetcher 实例"""
        # 延迟导入避免循环依赖
        try:
            from data_provider.base import DataFetcherManager
            manager = DataFetcherManager.get_instance()
            return manager._fetchers_by_name.get(source_name)
        except Exception:
            return None

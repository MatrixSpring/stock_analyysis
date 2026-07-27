# -*- coding: utf-8 -*-
"""
===================================
统一数据路由引擎 — RouteEngine
===================================

职责：
1. 根据时间范围智能路由：90天内热数据 → SQLite/缓存，历史 → 归档库
2. 数据源健康监控与自动故障切换
3. 统一入口，向上层屏蔽底层存储差异
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================

# 热数据窗口：默认 90 天
HOT_DATA_WINDOW_DAYS = 90

# 归档数据格式
ARCHIVE_FORMAT = "parquet"


class StorageTier(Enum):
    """存储层级"""
    HOT = "hot"          # 热数据：SQLite + 内存缓存
    WARM = "warm"        # 温数据：本地文件缓存
    COLD = "cold"        # 冷数据：归档 Parquet / 按需拉取
    EXTERNAL = "external"  # 外部实时 API


@dataclass
class RouteDecision:
    """路由决策结果"""
    tier: StorageTier
    reason: str
    backend_name: str = ""
    fallback_available: bool = False


@dataclass
class SourceHealth:
    """数据源健康状态"""
    name: str
    healthy: bool = True
    last_check_at: float = 0.0
    consecutive_failures: int = 0
    total_requests: int = 0
    success_count: int = 0
    avg_latency_ms: float = 0.0
    circuit_open: bool = False
    cooldown_until: float = 0.0

    def record_success(self, latency_ms: float = 0.0):
        self.total_requests += 1
        self.success_count += 1
        self.consecutive_failures = 0
        self.healthy = True
        if self.avg_latency_ms == 0.0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = self.avg_latency_ms * 0.9 + latency_ms * 0.1

    def record_failure(self):
        self.total_requests += 1
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.circuit_open = True
            self.cooldown_until = time.time() + 30.0
            self.healthy = False


class RouteEngine:
    """
    统一数据路由引擎。

    职责：
    - 根据查询参数（日期范围、数据类型）决定从哪个存储层读取
    - 热数据优先走 SQLite / 内存缓存
    - 历史数据走归档层 / 外部 API 按需拉取
    - 监控各存储后端的健康状态，自动熔断/恢复

    使用方式：
        engine = RouteEngine(db_manager=db, archive_dir=Path("./data/archive"))
        decision = engine.decide(data_type="daily_kline", start_date="2024-01-01")
        data = engine.fetch(decision, stock_code="600519")
    """

    def __init__(
        self,
        db_manager: Any = None,
        archive_dir: Optional[str] = None,
        hot_window_days: int = HOT_DATA_WINDOW_DAYS,
    ):
        self._db = db_manager
        self._archive_dir = archive_dir
        self._hot_window = timedelta(days=hot_window_days)
        self._health: Dict[str, SourceHealth] = {}
        self._fetchers: Dict[str, Callable] = {}

    # ============================================================
    # 路由决策
    # ============================================================

    def decide(
        self,
        data_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> RouteDecision:
        """
        根据数据类型和日期范围做出路由决策。

        Args:
            data_type: 数据类型（daily_kline / realtime_quote / fundamental / news 等）
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            RouteDecision 包含目标层级和原因说明
        """
        # 实时行情始终走外部 API
        if data_type in ("realtime_quote", "realtime_snapshot", "intraday"):
            return RouteDecision(
                tier=StorageTier.EXTERNAL,
                reason="实时行情数据始终从外部 API 获取",
                backend_name="realtime_api",
                fallback_available=True,
            )

        # 无日期范围 → 默认热数据
        if start_date is None:
            return RouteDecision(
                tier=StorageTier.HOT,
                reason="未指定日期范围，默认查询热数据层",
                backend_name="sqlite_hot",
                fallback_available=True,
            )

        # 判断是否完全在热数据窗口内
        now = datetime.now(timezone.utc)
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return RouteDecision(
                tier=StorageTier.HOT,
                reason=f"无法解析开始日期 {start_date}，默认热数据层",
                backend_name="sqlite_hot",
                fallback_available=True,
            )

        hot_cutoff = now - self._hot_window

        if start_dt >= hot_cutoff:
            return RouteDecision(
                tier=StorageTier.HOT,
                reason=f"查询范围在热数据窗口内（{self._hot_window.days}天）",
                backend_name="sqlite_hot",
                fallback_available=True,
            )

        # 部分在窗口内 → 热数据 + 归档混合查询
        if start_dt < hot_cutoff:
            end_dt = hot_cutoff
            try:
                if end_date:
                    end_dt = min(
                        datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                        hot_cutoff,
                    )
            except (ValueError, TypeError):
                pass

            return RouteDecision(
                tier=StorageTier.COLD,
                reason=f"查询范围超出热数据窗口（{start_date} < {hot_cutoff.strftime('%Y-%m-%d')}），路由到归档层",
                backend_name="archive_parquet",
                fallback_available=True,
            )

        return RouteDecision(
            tier=StorageTier.HOT,
            reason="默认路由到热数据层",
            backend_name="sqlite_hot",
            fallback_available=True,
        )

    # ============================================================
    # 数据获取
    # ============================================================

    def fetch(
        self,
        decision: RouteDecision,
        *args,
        fallback_enabled: bool = True,
        **kwargs,
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        根据路由决策获取数据，支持自动降级。

        Returns:
            (data, error_message): 成功时 error_message 为 None
        """
        backend = decision.backend_name

        # 1. 检查主后端健康状况
        health = self._get_health(backend)
        if health.circuit_open and time.time() < health.cooldown_until:
            if fallback_enabled and decision.fallback_available:
                fallback = self._find_fallback(decision)
                if fallback:
                    logger.warning(
                        f"[RouteEngine] {backend} 熔断中，降级到 {fallback}"
                    )
                    return self._try_fetch(fallback, *args, **kwargs)
            return None, f"后端 {backend} 已熔断"

        # 2. 检查主后端是否已注册
        fetcher = self._fetchers.get(backend)
        if fetcher is None:
            if fallback_enabled and decision.fallback_available:
                fallback = self._find_fallback(decision)
                if fallback:
                    logger.warning(
                        f"[RouteEngine] {backend} 未注册，降级到 {fallback}"
                    )
                    return self._try_fetch(fallback, *args, **kwargs)
            return None, f"未找到后端 {backend} 的抓取器"

        return self._try_fetch(backend, *args, **kwargs)

    def register_fetcher(self, backend_name: str, fetcher_fn: Callable):
        """注册数据后端抓取器"""
        self._fetchers[backend_name] = fetcher_fn
        logger.info(f"[RouteEngine] 注册后端: {backend_name}")

    # ============================================================
    # 健康检查
    # ============================================================

    def get_health_report(self) -> Dict[str, Any]:
        """获取所有后端健康报告"""
        return {
            name: {
                "healthy": h.healthy,
                "circuit_open": h.circuit_open,
                "success_rate": (
                            round(h.success_count / h.total_requests, 3)
                            if h.total_requests > 0 else 1.0
                ),
                "avg_latency_ms": round(h.avg_latency_ms, 1),
                "consecutive_failures": h.consecutive_failures,
            }
            for name, h in self._health.items()
        }

    def reset_circuit(self, backend_name: Optional[str] = None):
        """重置熔断状态"""
        if backend_name:
            h = self._health.get(backend_name)
            if h:
                h.circuit_open = False
                h.consecutive_failures = 0
                h.healthy = True
        else:
            for h in self._health.values():
                h.circuit_open = False
                h.consecutive_failures = 0
                h.healthy = True

    # ============================================================
    # 内部方法
    # ============================================================

    def _get_health(self, backend_name: str) -> SourceHealth:
        if backend_name not in self._health:
            self._health[backend_name] = SourceHealth(name=backend_name)
        return self._health[backend_name]

    def _try_fetch(self, backend_name: str, *args, **kwargs) -> Tuple[Optional[Any], Optional[str]]:
        fetcher = self._fetchers.get(backend_name)
        if fetcher is None:
            return None, f"未找到后端 {backend_name}"

        health = self._get_health(backend_name)
        start = time.time()

        try:
            data = fetcher(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            health.record_success(elapsed)
            return data, None
        except Exception as e:
            health.record_failure()
            err_msg = f"{backend_name}: {type(e).__name__}: {str(e)[:200]}"
            logger.error(f"[RouteEngine] {err_msg}")
            return None, err_msg

    def _find_fallback(self, decision: RouteDecision) -> Optional[str]:
        """为给定决策查找备选后端"""
        fallback_map = {
            "sqlite_hot": "archive_parquet",
            "archive_parquet": "external_api",
            "realtime_api": "sqlite_hot",
            "external_api": None,
        }
        return fallback_map.get(decision.backend_name)

    @property
    def hot_window_days(self) -> int:
        return self._hot_window.days

    @hot_window_days.setter
    def hot_window_days(self, days: int):
        self._hot_window = timedelta(days=max(1, days))

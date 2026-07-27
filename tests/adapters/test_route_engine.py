# -*- coding: utf-8 -*-
"""RouteEngine 单元测试"""

import pytest
from unittest.mock import MagicMock
from src.adapters.route_engine import (
    RouteEngine,
    RouteDecision,
    StorageTier,
    SourceHealth,
    HOT_DATA_WINDOW_DAYS,
)


class TestRouteDecision:
    """路由决策测试"""

    def test_realtime_routes_to_external(self):
        """实时行情始终路由到外部 API"""
        engine = RouteEngine()
        decision = engine.decide("realtime_quote")
        assert decision.tier == StorageTier.EXTERNAL
        assert decision.reason == "实时行情数据始终从外部 API 获取"

    def test_intraday_routes_to_external(self):
        engine = RouteEngine()
        decision = engine.decide("intraday")
        assert decision.tier == StorageTier.EXTERNAL

    def test_no_date_defaults_to_hot(self):
        """无日期范围默认路由到热数据"""
        engine = RouteEngine()
        decision = engine.decide("daily_kline")
        assert decision.tier == StorageTier.HOT

    def test_recent_date_routes_to_hot(self):
        """最近日期在热数据窗口内"""
        engine = RouteEngine(hot_window_days=90)
        # 使用今天的日期，肯定在热窗口内
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        decision = engine.decide("daily_kline", start_date=today)
        assert decision.tier == StorageTier.HOT

    def test_old_date_routes_to_cold(self):
        """旧日期路由到归档层"""
        engine = RouteEngine(hot_window_days=30)
        decision = engine.decide("daily_kline", start_date="2020-01-01")
        assert decision.tier == StorageTier.COLD
        assert "归档" in decision.reason

    def test_custom_hot_window(self):
        """自定义热数据窗口"""
        engine = RouteEngine(hot_window_days=7)
        from datetime import datetime, timedelta
        eight_days_ago = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")
        decision = engine.decide("daily_kline", start_date=eight_days_ago)
        assert decision.tier == StorageTier.COLD

    def test_invalid_date_defaults_to_hot(self):
        """无法解析的日期默认热数据"""
        engine = RouteEngine()
        decision = engine.decide("daily_kline", start_date="not-a-date")
        assert decision.tier == StorageTier.HOT


class TestSourceHealth:
    """数据源健康状态测试"""

    def test_initial_healthy(self):
        h = SourceHealth(name="test")
        assert h.healthy is True
        assert h.circuit_open is False

    def test_success_updates_stats(self):
        h = SourceHealth(name="test")
        h.record_success(latency_ms=50.0)
        assert h.total_requests == 1
        assert h.success_count == 1
        assert h.consecutive_failures == 0
        assert h.avg_latency_ms == 50.0

    def test_consecutive_failures_open_circuit(self):
        h = SourceHealth(name="test")
        for _ in range(3):
            h.record_failure()
        assert h.circuit_open is True
        assert h.healthy is False

    def test_circuit_cooldown(self):
        h = SourceHealth(name="test")
        for _ in range(3):
            h.record_failure()
        assert h.circuit_open is True
        # cooldown 时间设置为 future
        import time
        h.cooldown_until = time.time() + 100
        assert h.circuit_open is True  # cooldown 未过


class TestRouteEngineFetch:
    """路由引擎数据获取测试"""

    def test_fetch_returns_data(self):
        """注册 fetcher 后可正常获取数据"""
        engine = RouteEngine()

        def my_fetcher(code):
            return {"code": code, "data": [1, 2, 3]}

        engine.register_fetcher("sqlite_hot", my_fetcher)
        decision = RouteDecision(
            tier=StorageTier.HOT,
            reason="test",
            backend_name="sqlite_hot",
        )
        data, err = engine.fetch(decision, "600519")
        assert err is None
        assert data == {"code": "600519", "data": [1, 2, 3]}

    def test_fetch_unknown_backend(self):
        engine = RouteEngine()
        decision = RouteDecision(
            tier=StorageTier.HOT,
            reason="test",
            backend_name="nonexistent",
        )
        data, err = engine.fetch(decision)
        assert data is None
        assert "未找到后端" in err

    def test_fetch_circuit_open_falls_back(self):
        engine = RouteEngine()

        def fallback_fetcher(code):
            return {"from": "fallback", "code": code}

        engine.register_fetcher("archive_parquet", fallback_fetcher)

        # 手动设置熔断状态
        import time
        health = engine._get_health("sqlite_hot")
        health.circuit_open = True
        health.cooldown_until = time.time() + 3600

        decision = RouteDecision(
            tier=StorageTier.HOT,
            reason="test",
            backend_name="sqlite_hot",
            fallback_available=True,
        )
        data, err = engine.fetch(decision, "600519")
        # 应该降级到 archive_parquet
        assert err is None
        assert data is not None


class TestRouteEngineHealth:
    """健康报告测试"""

    def test_health_report(self):
        engine = RouteEngine()
        engine._get_health("sqlite_hot").record_success()
        report = engine.get_health_report()
        assert "sqlite_hot" in report
        assert report["sqlite_hot"]["healthy"] is True

    def test_reset_circuit(self):
        engine = RouteEngine()
        health = engine._get_health("sqlite_hot")
        health.circuit_open = True
        engine.reset_circuit("sqlite_hot")
        assert health.circuit_open is False
        assert health.healthy is True

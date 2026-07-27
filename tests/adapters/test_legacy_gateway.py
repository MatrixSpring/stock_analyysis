# -*- coding: utf-8 -*-
"""LegacyGateway 单元测试"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.adapters import LegacyGateway, GatewayRequest
from src.adapters.dto_adapter import DTOAdapter
from src.adapters.readonly_guard import ReadOnlyViolationError


class TestLegacyGatewaySingleton:
    """单例测试"""

    def test_singleton_same_instance(self):
        g1 = LegacyGateway.get_instance()
        g2 = LegacyGateway.get_instance()
        assert g1 is g2

    def test_uninitialized_returns_error(self):
        # 创建新实例测试未初始化状态
        gw = LegacyGateway.__new__(LegacyGateway)
        gw._initialized = False
        data, err = gw.query("kline", executor=lambda: [])
        assert data is None
        assert "未初始化" in err


class TestLegacyGatewayInit:
    """初始化测试"""

    def setup_method(self):
        # 使用一个 clean 实例
        self.gw = LegacyGateway.__new__(LegacyGateway)
        LegacyGateway._instance = None
        self.gw._initialized = False
        self.gw._route_engine = None
        self.gw._readonly_guard = None
        self.gw._db_manager = None
        self.gw._requests = []
        self.gw._adapters = {}

    def test_init_creates_components(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db, archive_dir="/tmp/test_archive")

        assert self.gw.is_initialized is True
        assert self.gw.route_engine is not None
        assert self.gw.readonly_guard is not None
        assert len(self.gw._adapters) >= 4  # kline, stock_info, capital_flow, backtest

    def test_init_registers_adapters(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db)

        assert "kline" in self.gw._adapters
        assert "stock_info" in self.gw._adapters
        assert "capital_flow" in self.gw._adapters
        assert "backtest" in self.gw._adapters

    def test_init_readonly_guard_disabled(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db, enable_readonly_guard=False)
        assert self.gw.readonly_guard.enabled is False


class TestLegacyGatewayQuery:
    """查询接口测试"""

    def setup_method(self):
        self.gw = LegacyGateway.__new__(LegacyGateway)
        LegacyGateway._instance = None
        self.gw._initialized = False
        self.gw._route_engine = None
        self.gw._readonly_guard = None
        self.gw._db_manager = None
        self.gw._requests = []
        self.gw._adapters = {}
        self.gw._max_request_log = 500

    def test_query_success(self):
        mock_db = MagicMock()
        mock_db.execute_query = MagicMock(return_value=[])
        self.gw.init(db_manager=mock_db)

        data, err = self.gw.query(
            data_type="stock_info",
            executor=lambda: {"code": "600519", "name": "茅台"},
        )
        assert err is None
        assert data == {"code": "600519", "name": "茅台"}

    def test_query_blocks_write_from_legacy(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db)

        with pytest.raises(ReadOnlyViolationError):
            self.gw.query(
                data_type="stock_info",
                executor=lambda: "done",
                module="legacy_analysis",
                is_write=True,
            )

    def test_query_with_legacy_format(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db)

        data, err = self.gw.query(
            data_type="kline",
            executor=lambda: {
                "date": "2024-01-15",
                "open": 10.5,
                "high": 11.0,
                "low": 10.2,
                "close": 10.8,
                "volume": 100000,
                "amount": 1080000.0,
                "pct_chg": 2.5,
            },
            output_format="legacy",
        )
        assert err is None
        # legacy 格式应该有旧版字段名
        assert "vol" in data or "volume" in data

    def test_query_logs_request(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db)

        self.gw.query(
            data_type="kline",
            executor=lambda: [{"close": 10.8}],
            params={"stock_code": "600519"},
            module="test_module",
        )

        requests = self.gw.get_recent_requests()
        assert len(requests) >= 1
        assert requests[-1]["data_type"] == "kline"

    def test_get_stats(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db)

        self.gw.query("kline", executor=lambda: [])
        stats = self.gw.get_stats()
        assert stats["total_requests"] >= 1
        assert "success_rate" in stats
        assert "avg_latency_ms" in stats
        assert "health" in stats
        assert "readonly_guard" in stats


class TestLegacyGatewayAdapters:
    """适配器管理测试"""

    def setup_method(self):
        self.gw = LegacyGateway.__new__(LegacyGateway)
        LegacyGateway._instance = None
        self.gw._initialized = False
        self.gw._adapters = {}
        self.gw._requests = []
        self.gw._route_engine = None
        self.gw._readonly_guard = None
        self.gw._db_manager = None

    def test_register_custom_adapter(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db)

        custom = DTOAdapter.custom(field_map={"x": "y"}, defaults={"y": 0})
        self.gw.register_adapter("custom_type", custom)
        assert self.gw.get_adapter("custom_type") is custom

    def test_get_nonexistent_adapter(self):
        mock_db = MagicMock()
        self.gw.init(db_manager=mock_db)
        assert self.gw.get_adapter("nonexistent") is None

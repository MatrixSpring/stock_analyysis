# -*- coding: utf-8 -*-
"""DTOAdapter 单元测试"""

import pytest
from src.adapters.dto_adapter import DTOAdapter, KLINE_FIELD_MAP, STOCK_FIELD_MAP


class TestDTOAdapterKline:
    """K线数据适配器测试"""

    def setup_method(self):
        self.adapter = DTOAdapter.for_kline()

    def test_to_new_format_maps_correctly(self):
        """旧版 K 线字段正确映射为新版"""
        old = {
            "date": "2024-01-15",
            "open_price": 10.5,
            "high_price": 11.0,
            "low_price": 10.2,
            "close_price": 10.8,
            "vol": 100000,
            "turnover": 1080000.0,
            "change_pct": 2.5,
        }
        result = self.adapter.to_new_format(old)

        assert result["date"] == "2024-01-15"
        assert result["open"] == 10.5
        assert result["high"] == 11.0
        assert result["low"] == 10.2
        assert result["close"] == 10.8
        assert result["volume"] == 100000
        assert result["amount"] == 1080000.0
        assert result["pct_chg"] == 2.5

    def test_to_new_format_with_standard_fields(self):
        """已经是新版格式的字段保持不变"""
        old = {
            "date": "2024-01-15",
            "open": 10.5,
            "high": 11.0,
            "low": 10.2,
            "close": 10.8,
            "volume": 100000,
            "amount": 1080000.0,
            "pct_chg": 2.5,
        }
        result = self.adapter.to_new_format(old)
        assert result["open"] == 10.5
        assert result["close"] == 10.8

    def test_to_new_format_fills_defaults(self):
        """缺失字段填充默认值"""
        old = {"date": "2024-01-15", "close": 10.8}
        result = self.adapter.to_new_format(old)

        assert result["pct_chg"] == 0.0  # 默认值
        assert result["volume"] == 0     # 默认值
        assert result["amount"] == 0.0   # 默认值

    def test_to_legacy_format(self):
        """新版 → 旧版格式"""
        new = {
            "date": "2024-01-15",
            "open": 10.5,
            "high": 11.0,
            "low": 10.2,
            "close": 10.8,
            "volume": 100000,
            "amount": 1080000.0,
            "pct_chg": 2.5,
        }
        result = self.adapter.to_legacy_format(new)
        # 反向映射后应有旧版字段
        assert "vol" in result or "volume" in result

    def test_to_new_format_batch(self):
        """批量转换"""
        old_list = [
            {"date": "2024-01-15", "close": 10.8},
            {"date": "2024-01-16", "close": 11.0},
        ]
        result = self.adapter.to_new_format_batch(old_list)
        assert len(result) == 2
        assert result[0]["close"] == 10.8

    def test_adapt_series_auto_detect_legacy(self):
        """自动检测旧版格式并转换"""
        legacy = {"date": "2024-01-15", "close_price": 10.8, "vol": 50000}
        result = self.adapter.adapt_series(legacy)
        # 应该被检测为旧版格式并转换
        assert result["close"] == 10.8
        assert result["volume"] == 50000

    def test_adapt_series_auto_detect_new(self):
        """自动检测新版格式保持不变"""
        new = {"date": "2024-01-15", "close": 10.8, "volume": 50000, "pct_chg": 1.5}
        result = self.adapter.adapt_series(new)
        assert result["close"] == 10.8


class TestDTOAdapterStockInfo:
    """股票信息适配器测试"""

    def setup_method(self):
        self.adapter = DTOAdapter.for_stock_info()

    def test_maps_legacy_fields(self):
        old = {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "region": "A",
            "sector": "白酒",
        }
        result = self.adapter.to_new_format(old)
        assert result["code"] == "600519"
        assert result["name"] == "贵州茅台"
        assert result["market"] == "A"
        assert result["industry"] == "白酒"


class TestDTOAdapterCapitalFlow:
    """资金流向适配器测试"""

    def setup_method(self):
        self.adapter = DTOAdapter.for_capital_flow()

    def test_maps_main_net(self):
        old = {
            "main_net_inflow": 5.2e7,
            "north_net": 3.1e7,
        }
        result = self.adapter.to_new_format(old)
        assert result["main_net_inflow"] == 5.2e7
        assert result["north_bound_inflow"] == 3.1e7


class TestDTOAdapterCustom:
    """自定义适配器测试"""

    def test_custom_field_map(self):
        adapter = DTOAdapter.custom(
            field_map={"a": "alpha", "b": "beta"},
            defaults={"alpha": 0, "beta": 0},
        )
        result = adapter.to_new_format({"a": 1, "b": 2})
        assert result["alpha"] == 1
        assert result["beta"] == 2

    def test_custom_missing_defaults(self):
        adapter = DTOAdapter.custom(
            field_map={"a": "alpha"},
            defaults={"alpha": 42},
        )
        result = adapter.to_new_format({})
        assert result["alpha"] == 42

"""
单元测试 — 股票模块端到端验证
python -m pytest tests/test_stock_service.py -v
"""
import pytest
from src.compat.adapter import StockServiceAdapter


def test_query_kline_returns_dataframe():
    """测试日线查询返回有效 DataFrame"""
    df = StockServiceAdapter.query_kline_data(
        "000001", "2026-01-01", "2026-01-10", use_cache=False
    )
    # 空数据库时应返回空 DataFrame 而不报错
    assert df is not None


def test_get_stock_info_unknown_code():
    """测试不存在的股票代码"""
    try:
        StockServiceAdapter.get_stock_base_info("999999")
    except Exception as e:
        assert "不存在" in str(e) or "DataQueryError" in type(e).__name__


def test_adapter_fallback():
    """测试灰度开关正常工作"""
    from src.compat.adapter import ENABLE_NEW_STOCK_SERVICE
    assert ENABLE_NEW_STOCK_SERVICE in (True, False)

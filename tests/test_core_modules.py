# -*- coding: utf-8 -*-
"""
===================================
核心模块单元测试 — tests/test_core_modules.py
===================================

覆盖：GlobalState, MessageBus, DataCleaner, TimeUtils,
      ExceptionHandler, QuantScorer, StockSelector,
      BacktestEngine, Storage, EventAnalyzer, ChainSimulator

运行：pytest tests/test_core_modules.py -v
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_kline():
    """生成标准 K 线测试数据"""
    np.random.seed(42)
    n = 120
    returns = np.random.normal(0.0005, 0.015, n)
    close = 100 * np.cumprod(1 + returns)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="B"),
        "open": np.round(close * 0.998, 2),
        "high": np.round(close * 1.01, 2),
        "low": np.round(close * 0.99, 2),
        "close": np.round(close, 2),
        "volume": np.random.randint(100000, 1000000, n),
    })


@pytest.fixture
def clean_global_state():
    """每个测试前重置 GlobalState"""
    from core.global_state import GlobalState
    GlobalState.reset_instance()
    yield GlobalState.get_instance()
    GlobalState.reset_instance()


# ============================================================
# 1. GlobalState
# ============================================================

class TestGlobalState:
    def test_update_stock_state(self, clean_global_state):
        gs = clean_global_state
        gs.update_stock_state("600519", name="贵州茅台", support_price=1800, resistance_price=2000)
        s = gs.get_stock("600519")
        assert s.name == "贵州茅台"
        assert s.support_price == 1800
        assert s.resistance_price == 2000

    def test_get_or_create_stock(self, clean_global_state):
        gs = clean_global_state
        s = gs.get_stock("000001")
        assert s.code == "000001"
        assert s.name == ""

    def test_event_lifecycle(self, clean_global_state):
        from core.global_state import EventItem
        gs = clean_global_state
        event = EventItem(
            event_id="evt_001", title="测试事件",
            source_type="新闻", direction="positive", strength=7,
            audit_status="pending",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        gs.add_event(event)
        assert len(gs.get_pending_events()) == 1
        gs.confirm_event("evt_001")
        assert len(gs.get_confirmed_events()) == 1

    def test_snapshot_roundtrip(self, clean_global_state):
        gs = clean_global_state
        gs.update_stock_state("600519", name="茅台")
        gs.update_capital_state(margin_risk_level="low")
        snap = gs.get_all_state()
        assert "stock_state" in snap
        assert snap["stock_state"]["600519"]["name"] == "茅台"

    def test_subscriber_notification(self, clean_global_state):
        gs = clean_global_state
        called = []

        def callback(group, data):
            called.append((group, data))

        gs.subscribe("stock", callback)
        gs.update_stock_state("000001", name="平安银行")
        assert len(called) == 1
        assert called[0][0] == "stock"


# ============================================================
# 2. MessageBus
# ============================================================

class TestMessageBus:
    def test_handler_registration(self):
        from core.message_bus import MessageBus
        bus = MessageBus()
        called = []

        @bus.on("test")
        def handler(payload):
            called.append(payload)
            return {"ok": True}

        ack = bus.receive_from_js('{"msg_id":"1","action":"test","payload":{"k":"v"}}')
        ack_data = json.loads(ack)
        assert ack_data["payload"]["data"]["ok"] is True
        assert len(called) == 1
        assert called[0]["k"] == "v"

    def test_unknown_action(self):
        from core.message_bus import MessageBus
        bus = MessageBus()
        ack = bus.receive_from_js('{"msg_id":"1","action":"nonexistent","payload":{}}')
        ack_data = json.loads(ack)
        assert ack_data["payload"]["error"] is not None

    def test_send_to_js(self):
        from core.message_bus import MessageBus
        bus = MessageBus()
        msg = bus.send_to_js("state_sync", {"stocks": 5})
        data = json.loads(msg)
        assert data["action"] == "state_sync"
        assert data["payload"]["stocks"] == 5


# ============================================================
# 3. Time Utils
# ============================================================

class TestTimeUtils:
    def test_standard_timezone(self):
        from utils.time_utils import standard_timezone, SH_TZ
        df = pd.DataFrame({"date": ["2026-07-28 14:00:00"]})
        df["date"] = pd.to_datetime(df["date"])
        result = standard_timezone(df)
        assert result["date"].iloc[0].tzinfo is not None
        assert str(result["date"].iloc[0].tzinfo) == str(SH_TZ)

    def test_get_today_str(self):
        from utils.time_utils import get_today_str
        today = get_today_str()
        assert len(today) == 8
        assert today.startswith("2026")

    def test_tzless_input(self):
        from utils.time_utils import standard_timezone
        df = pd.DataFrame({"date": pd.date_range("2026-07-01", periods=5, freq="D")})
        result = standard_timezone(df)
        assert result["date"].iloc[0].tzinfo is not None


# ============================================================
# 4. Exception Handler
# ============================================================

class TestExceptionHandler:
    def test_biz_exception(self):
        from utils.exception_handler import BizException, ErrorCode
        exc = BizException(ErrorCode.PARAM_INVALID, "test error")
        assert exc.code == 1001
        assert "test error" in str(exc)

    def test_data_source_error(self):
        from utils.exception_handler import DataSourceError
        exc = DataSourceError("timeout", source="akshare")
        assert exc.code == 2001
        assert "akshare" in exc.msg

    def test_success_response(self):
        from utils.exception_handler import create_success_response
        resp = create_success_response({"key": "val"})
        assert resp["code"] == 0
        assert resp["data"]["key"] == "val"

    def test_error_response(self):
        from utils.exception_handler import create_error_response
        resp = create_error_response(500, "内错")
        assert resp["code"] == 500
        assert "内错" in resp["msg"]


# ============================================================
# 5. Quant Score
# ============================================================

class TestQuantScorer:
    def test_single_score(self, sample_kline):
        from core.quant_score import QuantScorer
        scorer = QuantScorer()
        result = scorer.score(sample_kline, code="600519", name="茅台")
        assert 0 <= result.total_score <= 1
        assert 0 <= result.trend_score <= 1
        assert 0 <= result.capital_score <= 1
        assert result.code == "600519"

    def test_trend_label(self, sample_kline):
        from core.quant_score import QuantScorer
        scorer = QuantScorer()
        result = scorer.score(sample_kline)
        assert result.trend_label in ("强势", "偏多", "震荡", "偏空", "弱势")

    def test_risk_detection(self, sample_kline):
        from core.quant_score import QuantScorer
        scorer = QuantScorer()
        result = scorer.score(sample_kline)
        assert isinstance(result.risk_tags, list)

    def test_empty_data(self):
        from core.quant_score import QuantScorer
        scorer = QuantScorer()
        result = scorer.score(pd.DataFrame(), code="xxx")
        assert result.total_score == 0.0

    def test_batch_score(self, sample_kline):
        from core.quant_score import QuantScorer
        scorer = QuantScorer()
        results = scorer.batch_score({"A": sample_kline, "B": sample_kline})
        assert len(results) == 2
        assert results[0].total_score >= results[1].total_score


# ============================================================
# 6. Stock Selector
# ============================================================

class TestStockSelector:
    def test_screen(self, sample_kline):
        from core.stock_selector import StockSelector
        sel = StockSelector()
        results = sel.screen(
            {"000001": sample_kline, "600519": sample_kline, "300750": sample_kline},
            top_n=2,
            name_map={"000001": "平安银行", "600519": "茅台", "300750": "宁德时代"},
        )
        assert len(results) <= 2
        assert results[0].total_score >= results[-1].total_score

    def test_min_score_filter(self, sample_kline):
        from core.stock_selector import StockSelector
        sel = StockSelector()
        results = sel.screen(
            {"000001": sample_kline}, top_n=5, min_score=0.99,
        )
        assert len(results) == 0  # all below 0.99

    def test_sector_ranking(self, sample_kline):
        from core.stock_selector import StockSelector
        ranking = StockSelector.sector_ranking(
            {"A": sample_kline, "B": sample_kline},
            sector_map={"A": "银行", "B": "消费"},
            top_n=5,
        )
        assert len(ranking) <= 5
        for r in ranking:
            assert "sector" in r
            assert "avg_score" in r

    def test_export_snapshot(self, sample_kline):
        from core.stock_selector import StockSelector
        sel = StockSelector()
        results = sel.screen({"000001": sample_kline}, top_n=1)
        snap = sel.export_snapshot(results)
        assert snap["total_picks"] == len(results)
        assert "picks" in snap


# ============================================================
# 7. Backtest Engine
# ============================================================

class TestBacktestEngine:
    def test_ma_crossover(self):
        from core.backtest import BacktestEngine
        np.random.seed(1)
        n = 200
        close = 100 * np.cumprod(1 + np.random.normal(0.0003, 0.012, n))
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=n, freq="B").strftime("%Y-%m-%d"),
            "open": close * 0.998, "high": close * 1.005,
            "low": close * 0.995, "close": close,
        })
        df["ma5"] = df["close"].rolling(5).mean()
        df["ma20"] = df["close"].rolling(20).mean()
        df["signal"] = 0
        df.loc[df["ma5"] > df["ma20"], "signal"] = 1
        df.loc[df["ma5"] < df["ma20"], "signal"] = -1
        df = df.dropna()

        engine = BacktestEngine()
        result = engine.run(df)
        assert result["performance"] is not None
        p = result["performance"]
        assert "sharpe_ratio" in p
        assert "max_drawdown" in p
        assert p["trade_count"] >= 0

    def test_snapshot_save_load(self):
        from core.backtest import BacktestEngine
        np.random.seed(2)
        n = 100
        close = 100 * np.cumprod(1 + np.random.normal(0, 0.01, n))
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=n, freq="B").strftime("%Y-%m-%d"),
            "open": close, "high": close, "low": close, "close": close,
            "signal": [1 if i % 25 == 0 else (-1 if i % 25 == 12 else 0) for i in range(n)],
        })
        engine = BacktestEngine()
        result = engine.run(df, name="snapshot_test")
        sid = result["snapshot_id"]
        snap = engine.load_snapshot(sid)
        assert snap is not None
        assert snap["name"] == "snapshot_test"

    def test_future_function_detection(self):
        from core.backtest import BacktestEngine
        n = 50
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=n, freq="B").strftime("%Y-%m-%d"),
            "open": np.ones(n)*100, "high": np.ones(n)*100,
            "low": np.ones(n)*100, "close": 100 * np.cumprod(1 + np.random.normal(0, 0.01, n)),
            "signal": 0,
        })
        # Inject future-looking signal
        df["signal"] = (df["close"].shift(-1) > df["close"]).astype(int)
        df = df.dropna()
        engine = BacktestEngine()
        result = engine.run(df)
        assert len(result["warnings"]) > 0


# ============================================================
# 8. Storage
# ============================================================

class TestStorage:
    @pytest.fixture
    def storage(self):
        from core.storage import Storage
        db = Path(tempfile.gettempdir()) / f"test_storage_{os.getpid()}.db"
        store = Storage(db_path=db)
        yield store
        if db.exists():
            db.unlink()

    def test_save_load_delete(self, storage, clean_global_state):
        clean_global_state.update_stock_state("000001", name="test")
        assert storage.save_snapshot("test")
        snapshots = storage.list_snapshots()
        assert len(snapshots) >= 1
        assert storage.delete_snapshot("test")

    def test_audit_log(self, storage):
        storage.log_audit("evt_x", "confirm", operator="tester", detail="ok")
        history = storage.get_audit_history("evt_x")
        assert len(history) >= 1
        assert history[0]["action"] == "confirm"


# ============================================================
# 9. EventAnalyzer + ChainSimulator
# ============================================================

class TestEventPipeline:
    def test_parse_and_simulate(self, clean_global_state):
        from core.event_analyzer import EventAnalyzer
        from core.chain_simulation import ChainSimulator
        from core.global_state import EventItem
        from core.utils import generate_id

        gs = clean_global_state
        analyzer = EventAnalyzer()
        event_id = generate_id("evt")

        event = EventItem(
            event_id=event_id, title="央行降准",
            source_type="政策", direction="positive", strength=8,
            time_cycle="short", audit_status="confirmed",
            parsed_json={
                "event_meta": {"event_title": "央行降准", "overall_direction": "positive", "impact_strength": 8},
                "transfer_chain": [
                    {"from_node": "央行", "to_node": "招商银行", "transfer_logic": "流动性宽松", "direction": "positive", "strength": 8},
                    {"from_node": "招商银行", "to_node": "万科A", "transfer_logic": "信贷放宽", "direction": "positive", "strength": 6},
                ],
            },
            created_at=datetime.now().isoformat(), updated_at=datetime.now().isoformat(),
        )
        gs.add_event(event)
        link_ids = analyzer._build_transfer_graph(event_id, event.parsed_json["transfer_chain"])
        event.transfer_links = link_ids
        for lid in link_ids:
            gs.update_transfer_link(lid, audit_status="confirmed")

        sim = ChainSimulator()
        result = sim.simulate(event_id)
        assert "stock_impacts" in result
        impacts = result["stock_impacts"]
        assert len(impacts) >= 1
        for code, imp in impacts.items():
            assert "score" in imp
            assert "paths" in imp


# ============================================================
# 10. Data Cleaner
# ============================================================

class TestDataCleaner:
    def test_clean_removes_zeros(self):
        from core.data_cleaner import clean_stock_data
        df = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=10, freq="D"),
            "open": [100] * 10, "high": [105] * 10,
            "low": [95] * 9 + [0], "close": [100] * 10,
            "volume": range(10),
        })
        clean = clean_stock_data(df)
        assert len(clean) < 10  # row with low=0 removed

    def test_detect_missing(self):
        from core.data_cleaner import detect_data_missing
        df = pd.DataFrame({"date": pd.to_datetime(["2026-07-01", "2026-07-03", "2026-07-07"])})
        missing = detect_data_missing(df)
        assert len(missing) > 0

    def test_quality_score(self):
        from core.data_cleaner import validate_data_quality
        df = pd.DataFrame({
            "open": [100]*5, "high": [105]*5,
            "low": [95]*5, "close": [100]*5,
        })
        q = validate_data_quality(df)
        assert q["score"] > 0.5


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# -*- coding: utf-8 -*-
"""P3 模块测试: 快照 + 事件传导 + 向量化回测"""

import pytest
import tempfile, os
import numpy as np
from src.snapshot import MarketSnapshot, SnapshotStore, SnapshotPoint
from src.event_graph import EventPropagationGraph, EventNode
from src.vector_bt import VectorBacktester, BacktestResult, PortfolioResult


# ============================================================
# SnapshotStore
# ============================================================

class TestSnapshotStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = SnapshotStore(os.path.join(self.tmpdir, "snaps"))

    def test_capture_and_save(self):
        snap = self.store.capture(
            "600519", "贵州茅台", "2024-06-15",
            price_data=[
                {"date": "2024-06-14", "close": 1800.0, "volume": 5000000,
                 "open": 1790, "high": 1810, "low": 1785, "amount": 9e9,
                 "pct_chg": 1.5, "ma5": 1790, "ma10": 1780, "ma20": 1770},
            ],
            capital_flow={"score": 65.0, "north_net": "+3.2亿"},
            sentiment={"overall": "positive"},
            macro={"risk_score": 35.0},
        )
        self.store.save(snap)
        assert snap.stock_code == "600519"
        assert snap.stock_name == "贵州茅台"

    def test_load_snapshot(self):
        self.store.capture("000001", "平安银行", "2024-06-15",
                           price_data=[{"date": "2024-06-14", "close": 12.0, "volume": 1000000,
                                        "open": 11.9, "high": 12.1, "low": 11.8, "amount": 1.2e8,
                                        "pct_chg": 0.5, "ma5": 11.9, "ma10": 11.8, "ma20": 11.7}])
        snap = self.store.capture("000001", "平安银行", "2024-06-16",
                                  price_data=[{"date": "2024-06-15", "close": 12.2, "volume": 1200000,
                                               "open": 12.0, "high": 12.3, "low": 11.9, "amount": 1.5e8,
                                               "pct_chg": 1.0, "ma5": 12.0, "ma10": 11.9, "ma20": 11.8}])
        self.store.save(snap)
        # List should include it
        snaps = self.store.list_snapshots("000001")
        assert len(snaps) >= 1

    def test_digest(self):
        snap = self.store.capture(
            "600519", price_data=[
                {"date": "2024-06-14", "close": 1800.0, "volume": 5000000,
                 "open": 1790, "high": 1810, "low": 1785, "amount": 9e9,
                 "pct_chg": 1.5, "ma5": 1790, "ma10": 1780, "ma20": 1770},
            ],
        )
        digest = snap.digest()
        assert "600519" in digest
        assert "1800" in digest

    def test_compare(self):
        self.store.capture("600519", price_data=[{"date": "2024-01-01", "close": 1700, "volume": 1000000,
                                                   "open": 1695, "high": 1710, "low": 1690, "amount": 1.7e9,
                                                   "pct_chg": 0.3, "ma5": 1695, "ma10": 1690, "ma20": 1685}])
        s = self.store.capture("600519", "茅台", "2024-01-15",
                               price_data=[{"date": "2024-01-14", "close": 1750, "volume": 1000000,
                                            "open": 1740, "high": 1760, "low": 1735, "amount": 1.75e9,
                                            "pct_chg": 1.0, "ma5": 1740, "ma10": 1730, "ma20": 1720}])
        self.store.save(s)


# ============================================================
# EventPropagationGraph
# ============================================================

class TestEventGraph:
    def setup_method(self):
        self.graph = EventPropagationGraph()

    def test_add_node_and_edge(self):
        self.graph.add_node("e1", "事件1")
        self.graph.add_node("e2", "事件2")
        self.graph.add_edge("e1", "e2", strength=0.8)
        assert self.graph.count()["nodes"] == 2
        assert self.graph.count()["edges"] == 1

    def test_find_paths(self):
        self.graph.add_node("fed", "美联储加息")
        self.graph.add_node("rmb", "人民币贬值")
        self.graph.add_node("export", "出口受益")
        self.graph.add_edge("fed", "rmb", strength=0.9, mechanism="利差扩大")
        self.graph.add_edge("rmb", "export", strength=0.7, mechanism="本币贬值")

        paths = self.graph.find_paths("fed")
        assert len(paths) >= 1
        assert any("人民币贬值" in p["path"] for p in paths)

    def test_find_affected_stocks(self):
        self.graph.add_node("chip_ban", "芯片禁令")
        self.graph.add_node("supply", "供应短缺", level="industry")
        self.graph.add_node("smic", "中芯国际", level="stock")
        self.graph.add_edge("chip_ban", "supply", strength=0.85)
        self.graph.add_edge("supply", "smic", strength=0.5)

        affected = self.graph.find_affected_stocks("chip_ban")
        assert len(affected) >= 1

    def test_impact_assessment(self):
        self.graph.add_node("fed_hike", "美联储加息", category="policy")
        self.graph.add_node("broker", "券商板块", level="industry")
        self.graph.add_edge("fed_hike", "broker", strength=0.6)

        report = self.graph.impact_assessment("fed_hike")
        assert "event" in report
        assert report["event"] == "美联储加息"

    def test_load_presets(self):
        self.graph.load_preset_chains()
        assert self.graph.count()["nodes"] >= 10
        # Test finding paths from a preset event
        paths = self.graph.find_paths("fed_hike")
        assert len(paths) >= 1


# ============================================================
# VectorBacktester
# ============================================================

class TestVectorBacktester:
    def setup_method(self):
        self.vb = VectorBacktester(initial_capital=100000)

    def _random_prices(self, n: int = 252, seed: int = 42) -> np.ndarray:
        np.random.seed(seed)
        rets = np.random.normal(0.0005, 0.015, n)
        return 100.0 * np.cumprod(1 + rets)

    def test_single_stock_buy_hold(self):
        prices = self._random_prices(252)
        signals = np.ones(len(prices))
        result = self.vb.run_single(prices, signals)
        assert result.total_return != 0
        assert result.sharpe_ratio != 0
        assert 0 <= result.win_rate <= 1

    def test_portfolio_backtest(self):
        prices = {
            "stock_a": self._random_prices(252, 42),
            "stock_b": self._random_prices(252, 123),
        }
        result = self.vb.run(prices)
        assert len(result.stock_results) == 2
        assert result.equity_curve[0] == 100000
        assert 0 <= result.max_drawdown <= 1

    def test_backtest_basic_metrics(self):
        prices = self._random_prices(252)
        signals = np.ones(len(prices))
        result = self.vb.run_single(prices, signals)
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe_ratio, float)
        assert 0 <= result.max_drawdown <= 1

    def test_param_scan(self):
        prices = self._random_prices(252)

        def gen_signal(threshold):
            rets = np.diff(prices) / prices[:-1]
            return np.concatenate([[0], (rets > threshold).astype(int)])

        results = self.vb.param_scan(
            prices, "threshold", [0.0, 0.005, 0.01], gen_signal,
        )
        assert len(results) == 3

    def test_optimize(self):
        prices = self._random_prices(100)

        def gen_signal(ma_window):
            window = int(ma_window)
            if window < 2:
                window = 2
            ma = np.convolve(prices, np.ones(window)/window, mode='same')
            signals = (prices > ma).astype(int)
            return signals

        result = self.vb.optimize(
            prices,
            {"ma_window": [5.0, 10.0, 20.0]},
            gen_signal,
            objective="sharpe",
        )
        assert "best_params" in result
        assert result["best_params"]["ma_window"] in [5.0, 10.0, 20.0]

    def test_attribution(self):
        prices = {
            "stock_a": self._random_prices(252, 42),
            "stock_b": self._random_prices(252, 123),
        }
        result = self.vb.run(prices)
        assert "stock_contributions" in result.attribution
        assert len(result.attribution["stock_contributions"]) == 2

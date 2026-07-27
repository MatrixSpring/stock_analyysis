# -*- coding: utf-8 -*-
"""最终模块测试: DataPipeline + AlphaFactors + MultiAgent + StressTest"""

import pytest
import numpy as np
from src.data_pipeline import DataPipeline
from src.alpha_factors import AlphaLibrary
from src.multi_agent import (
    MultiAgentOrchestrator, DualModelRouter, AgentReport, ModelRoute,
)
from src.stress_test import (
    MonteCarloSimulator, NumbaBacktester, HAS_NUMBA,
)


# ============================================================
# DataPipeline
# ============================================================

class TestDataPipeline:
    def setup_method(self):
        self.pipe = DataPipeline()

    def test_fill_missing(self):
        data = np.array([[1.0, np.nan], [np.nan, 2.0], [3.0, np.nan]], dtype=float)
        result = self.pipe.fill_missing(data)
        assert not np.isnan(result[-1, 1])  # last row filled

    def test_remove_outliers(self):
        data = np.random.normal(0, 1, (100, 2))
        data[0, 0] = 100.0  # outlier
        result = self.pipe.remove_outliers(data)
        assert result[0, 0] < 100.0  # clipped

    def test_zscore(self):
        data = np.random.normal(5, 2, (100, 2))
        result = self.pipe.zscore_normalize(data)
        assert abs(np.mean(result[:, 0])) < 0.1  # near zero mean

    def test_full_pipeline(self):
        data = np.random.normal(0, 1, (100, 3))
        data[5, :] = np.nan
        data[10, 0] = 50  # outlier
        result = self.pipe.run(data, skip_neutralize=True)
        assert result.shape == data.shape
        assert self.pipe.get_summary()["steps"]


# ============================================================
# AlphaLibrary
# ============================================================

class TestAlphaFactors:
    def setup_method(self):
        self.lib = AlphaLibrary()
        n = 252
        np.random.seed(42)
        self.close = 100 * np.cumprod(1 + np.random.normal(0.0005, 0.015, n))
        self.volume = np.random.randint(1e6, 1e7, n).astype(float)
        self.open_p = self.close * (1 + np.random.normal(0, 0.002, n))

    def test_ret_1d(self):
        f = AlphaLibrary.ret_1d(self.close)
        assert len(f) == len(self.close)

    def test_ma_cross(self):
        f = AlphaLibrary.ma_cross(self.close, 5, 20)
        assert len(f) == len(self.close)

    def test_rsi_14d(self):
        f = AlphaLibrary.rsi_14d(self.close)
        assert np.all((f >= 0) & (f <= 100))

    def test_compute_all(self):
        factors = self.lib.compute_all(
            self.open_p, self.close * 1.01, self.close * 0.99,
            self.close, self.volume, self.close * self.volume,
        )
        assert len(factors) >= 10
        assert "ret_1d" in factors
        assert "rsi_14d" in factors

    def test_list_factors(self):
        names = self.lib.list_factors()
        assert "ret_1d" in names


# ============================================================
# MultiAgent + DualModel
# ============================================================

class TestMultiAgent:
    def test_orchestrator(self):
        orch = MultiAgentOrchestrator(parallel=False)

        def tech_agent(code, ctx):
            return AgentReport("technical", conclusion="bullish", score=70,
                               key_signals=["MA金叉"], confidence=0.8)

        def capital_agent(code, ctx):
            return AgentReport("capital", conclusion="bullish", score=65,
                               key_signals=["北向流入"], confidence=0.7)

        orch.register("technical", tech_agent)
        orch.register("capital", capital_agent)

        report = orch.analyze("600519")
        assert report.consensus == "bullish"
        assert report.consensus_score > 60

    def test_consensus_divergent(self):
        orch = MultiAgentOrchestrator(parallel=False)

        orch.register("a", lambda c, ctx: AgentReport("a", "bullish", score=80))
        orch.register("b", lambda c, ctx: AgentReport("b", "bearish", score=20))
        orch.register("c", lambda c, ctx: AgentReport("c", "bearish", score=25))

        report = orch.analyze("test")
        assert report.consensus in ("bearish", "neutral", "divergent")

    def test_to_markdown(self):
        orch = MultiAgentOrchestrator(parallel=False)
        orch.register("tech", lambda c, ctx: AgentReport("tech", "bullish", score=70))
        report = orch.analyze("AAPL")
        md = orch.to_markdown(report)
        assert "AAPL" in md

    def test_agent_report_fields(self):
        r = AgentReport("test", conclusion="neutral")
        assert r.score == 50.0
        assert r.confidence == 0.5


class TestDualModelRouter:
    def setup_method(self):
        self.router = DualModelRouter()

    def test_light_route(self):
        route = self.router.route("quick_scan")
        assert route.tier == "light"
        assert route.max_tokens == 1024

    def test_heavy_route(self):
        route = self.router.route("full_analysis")
        assert route.tier == "heavy"
        assert route.max_tokens == 4096

    def test_large_context_forces_heavy(self):
        route = self.router.route("quick_scan", context_size=5000)
        assert route.tier == "heavy"

    def test_estimate_cost(self):
        route = ModelRoute(tier="light", model_name="deepseek-chat",
                          max_tokens=1024, temperature=0.3, reason="test")
        cost = self.router.estimate_cost(route, 1000)
        assert cost > 0


# ============================================================
# StressTest / MonteCarlo / Numba
# ============================================================

class TestMonteCarlo:
    def test_run(self):
        sim = MonteCarloSimulator(seed=42)
        returns = np.random.normal(0.0005, 0.015, 500)
        result = sim.run(returns, n_simulations=500, horizon=100)
        assert result.mean_return != 0
        assert result.var_95 >= 0
        assert 0 <= result.ruin_probability <= 1

    def test_historical_stress(self):
        sim = MonteCarloSimulator()
        returns = np.random.normal(0.0005, 0.015, 500)
        stress = sim.historical_stress(returns)
        assert "2008_financial_crisis" in stress

    def test_distributions(self):
        sim = MonteCarloSimulator(seed=123)
        returns = np.random.normal(0.0005, 0.02, 252)
        result = sim.run(returns, n_simulations=200, horizon=252)
        assert len(result.return_distribution) == 200
        assert len(result.drawdown_distribution) == 200


class TestNumbaBacktester:
    def test_run(self):
        nb = NumbaBacktester()
        np.random.seed(42)
        rets = np.random.normal(0.0005, 0.015, 500).astype(np.float64)
        sigs = np.ones(500, dtype=np.float64)
        result = nb.run(sigs, rets)
        assert result["total_return"] != 0
        assert len(result["equity_curve"]) == 501
        assert result["total_trades"] >= 0

    def test_speed_test(self):
        result = NumbaBacktester.speed_test(n_iterations=1000)
        assert result["iterations"] == 1000

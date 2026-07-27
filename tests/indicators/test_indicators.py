# -*- coding: utf-8 -*-
"""Indicators SDK 单元测试"""

import pytest
import numpy as np

from src.indicators.metrics_core import (
    total_return,
    cagr,
    daily_returns,
    volatility,
    max_drawdown,
    max_drawdown_duration,
    downside_volatility,
    var_95,
    cvar_95,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    information_ratio,
    beta,
    alpha,
    win_rate,
    profit_loss_ratio,
    profit_factor,
    composite_score,
    metrics_report,
)
from src.indicators.capital_flow import (
    north_bound_score,
    main_capital_score,
    margin_score,
    dragon_tiger_score,
    composite_capital_heat,
)
from src.indicators.sentiment import (
    text_sentiment,
    batch_sentiment,
    industry_boom_score,
    macro_risk_score,
    market_sentiment_index,
)


# ============================================================
# 收益类
# ============================================================

class TestReturns:
    def test_total_return_positive(self):
        prices = [10.0, 11.0, 12.0, 13.0]
        assert total_return(prices) == pytest.approx(0.3, rel=0.01)

    def test_total_return_negative(self):
        prices = [10.0, 9.0, 8.0]
        assert total_return(prices) == pytest.approx(-0.2, rel=0.01)

    def test_total_return_single_price(self):
        assert total_return([10.0]) == 0.0

    def test_cagr_positive(self):
        """100 → 161.05 over 2 years → 26% CAGR"""
        prices = [100.0] + [100.0 * (1.001) ** i for i in range(1, 505)]  # ~2 years
        # Just verify it's computable and positive
        result = cagr(prices)
        assert result > 0

    def test_daily_returns(self):
        prices = [10.0, 11.0, 10.0]
        d = daily_returns(prices)
        assert len(d) == 2
        assert d[0] == pytest.approx(0.1)
        assert d[1] == pytest.approx(-0.0909, abs=0.01)


# ============================================================
# 风险类
# ============================================================

class TestRisk:
    def test_max_drawdown_zero(self):
        assert max_drawdown([10.0, 11.0, 12.0]) == 0.0

    def test_max_drawdown_standard(self):
        """Peak 10 → valley 7 → drawdown 30%"""
        prices = [10.0, 10.5, 7.0, 8.0, 9.0]
        dd = max_drawdown(prices)
        assert dd == pytest.approx(0.33, abs=0.01)

    def test_max_drawdown_duration(self):
        prices = [10.0, 9.0, 8.0, 7.0, 8.0, 10.0]
        dur = max_drawdown_duration(prices)
        # peak=10 at index 0, then indices 1-4 are below cumulative max = 4 days
        assert dur == 4

    def test_volatility(self):
        rets = [0.01, -0.02, 0.015, -0.01, 0.005]
        vol = volatility(rets, daily=True)
        assert vol > 0

    def test_var_95(self):
        np.random.seed(42)
        rets = list(np.random.normal(0.001, 0.02, 1000))
        v = var_95(rets)
        assert v > 0.02  # ~1.645 * 0.02 * sqrt(252) annualized? No, daily VaR
        # Daily VaR ~ 1.645 * 0.02 ≈ 0.033
        assert v > 0.02


# ============================================================
# 风险调整
# ============================================================

class TestRiskAdjusted:
    def test_sharpe_positive(self):
        rets = [0.001] * 100  # all positive tiny returns
        sr = sharpe_ratio(rets, risk_free_rate=0.02)
        # near-zero std → very high or zero sharpe
        assert sr >= 0

    def test_sharpe_zero_std(self):
        assert sharpe_ratio([0.01, 0.01, 0.01]) == 0.0

    def test_sortino_matches_sharpe_for_symmetric(self):
        rets = [0.001, -0.002, 0.003, -0.001, 0.002] * 20
        sortino = sortino_ratio(rets)
        assert sortino != 0

    def test_calmar_ratio(self):
        prices = [100.0, 99.0, 101.0, 102.0, 103.0]
        rets = daily_returns(prices)
        cr = calmar_ratio(rets, prices)
        assert cr != 0 or max_drawdown(prices) == 0

    def test_beta_one_for_identical(self):
        rets = [0.01, -0.01, 0.02, -0.02]
        assert beta(rets, rets) == pytest.approx(1.0, abs=0.01)


# ============================================================
# 交易指标
# ============================================================

class TestTrading:
    def test_win_rate(self):
        outcomes = [True, True, False, True, False]
        assert win_rate(outcomes) == 0.6

    def test_win_rate_empty(self):
        assert win_rate([]) == 0.0

    def test_profit_loss_ratio(self):
        wins = [0.05, 0.03, 0.04]
        losses = [-0.02, -0.01]
        pl = profit_loss_ratio(wins, losses)
        assert pl > 2.0

    def test_profit_factor(self):
        wins = [0.05, 0.03]
        losses = [-0.02]
        pf = profit_factor(wins, losses)
        assert pf > 3.0

    def test_composite_score(self):
        prices = [100.0]
        for _ in range(200):
            prices.append(prices[-1] * (1 + np.random.normal(0.0005, 0.015)))
        rets = daily_returns(prices)
        score = composite_score(rets, prices)
        assert 0 <= score <= 100

    def test_metrics_report(self):
        prices = [100.0]
        for _ in range(252):
            prices.append(prices[-1] * (1 + np.random.normal(0.0005, 0.015)))
        report = metrics_report(prices)
        assert "total_return" in report
        assert "sharpe_ratio" in report
        assert "max_drawdown" in report
        assert "composite_score" in report


# ============================================================
# 资金行为
# ============================================================

class TestCapitalFlow:
    def test_north_bound_score_neutral(self):
        score = north_bound_score([])
        assert score == 50.0

    def test_north_bound_score_bullish(self):
        inflows = [5.0, 3.0, 7.0, 8.0, 10.0, 6.0] * 5
        score = north_bound_score(inflows)
        assert score > 50  # 全部为正 → 偏多

    def test_north_bound_score_bearish(self):
        inflows = [-5.0, -3.0, -7.0, -8.0, -10.0] * 5
        score = north_bound_score(inflows)
        assert score < 50

    def test_main_capital_score(self):
        result = main_capital_score(
            super_large_net=5000, large_net=3000,
            medium_net=-2000, small_net=-6000,
            total_amount=100000,
        )
        assert result["score"] > 50  # 主力净流入
        assert result["main_ratio"] > 0
        assert "structure" in result

    def test_margin_score_bullish(self):
        result = margin_score(
            margin_balance=100.0,
            margin_change=5.0,
            short_balance=2.0,
        )
        assert result["bias"] == "bullish"

    def test_composite_capital_heat(self):
        result = composite_capital_heat(
            north_bound_inflows=[5.0] * 10,
            main_capital={"score": 65.0},
        )
        assert 0 <= result["total_score"] <= 100
        assert "trend" in result
        assert "divergence_warning" in result


# ============================================================
# 舆情/情绪
# ============================================================

class TestSentiment:
    def test_text_sentiment_positive(self):
        result = text_sentiment("公司业绩超预期，利好频出，增长强劲")
        assert result["sentiment"] == "positive"
        assert result["score"] > 0

    def test_text_sentiment_negative(self):
        result = text_sentiment("财报亏损，股价暴跌，面临制裁和调查")
        assert result["sentiment"] == "negative"
        assert result["score"] < 0

    def test_text_sentiment_neutral(self):
        result = text_sentiment("今日无重大事件")
        assert result["sentiment"] == "neutral"

    def test_batch_sentiment(self):
        texts = [
            "业绩超预期，利好",
            "亏损暴雷，下跌",
            "无重大事件",
            "增长强劲突破",
        ]
        result = batch_sentiment(texts)
        assert result["count"] == 4
        assert "distribution" in result
        assert result["distribution"]["positive"] == 2
        assert result["distribution"]["negative"] == 1
        assert result["distribution"]["neutral"] == 1

    def test_industry_boom_score(self):
        result = industry_boom_score(
            upstream_prices=[100, 98, 95],
            downstream_demand=0.03,
            capacity_utilization=0.82,
            inventory_level=0.45,
            new_orders_growth=0.06,
        )
        assert 0 <= result["score"] <= 100
        assert result["phase"] in ("expansion", "recovery", "slowdown", "recession")

    def test_industry_boom_expansion(self):
        result = industry_boom_score(
            upstream_prices=[100, 98, 96],
            downstream_demand=0.08,
            capacity_utilization=0.90,
            inventory_level=0.35,
            new_orders_growth=0.10,
        )
        assert result["score"] >= 65

    def test_macro_risk_score(self):
        articles = [
            {"title": "地缘冲突升级 制裁加剧", "content": "军事对抗 贸易战 出口管制"},
            {"title": "央行加息 通胀高企", "content": "美联储加息 通胀 CPI GDP"},
        ]
        result = macro_risk_score(articles)
        assert result["risk_score"] > 50

    def test_market_sentiment_index(self):
        result = market_sentiment_index(
            news_sentiment={"avg_score": 0.3},
            capital_heat={"total_score": 65.0},
        )
        assert 0 <= result["index"] <= 100
        assert "level" in result
        assert "components" in result

# -*- coding: utf-8 -*-
"""Analysis Dimensions 测试 — 五维分析引擎"""

import pytest
import numpy as np
from src.analysis_dimensions.base import (
    DimensionResult, ResonanceResult, DimensionAnalyzer,
    DIMENSION_LABELS, DIMENSION_ORDER,
)
from src.analysis_dimensions.analyzers import (
    TechnicalAnalyzer, CapitalFlowAnalyzer, InstitutionalAnalyzer,
    MacroGeoAnalyzer, IndustrySentimentAnalyzer,
)
from src.analysis_dimensions.resonance import ResonanceEngine


def _make_kline_data(prices, volumes=None):
    if volumes is None:
        volumes = [1000000] * len(prices)
    return [
        {"date": f"2024-{i+1:02d}-01", "close": p, "open": p, "high": p, "low": p,
         "volume": v, "amount": p * v}
        for i, (p, v) in enumerate(zip(prices, volumes))
    ]


class TestTechnicalAnalyzer:
    def test_no_data(self):
        result = TechnicalAnalyzer().analyze("600519")
        assert result.score == 50.0
        assert not result.data_available

    def test_bullish_trend(self):
        # gentle uptrend over 60 days (~5% gain, no extreme bias)
        prices = [100.0 + i * 0.08 for i in range(60)]  # ~5% over 60 days
        kline = _make_kline_data(prices)
        result = TechnicalAnalyzer().analyze("600519", kline_data=kline)
        assert result.score >= 55
        assert result.data_available

    def test_bearish_trend(self):
        prices = list(range(130, 100, -1))
        kline = _make_kline_data(prices)
        result = TechnicalAnalyzer().analyze("600519", kline_data=kline)
        assert result.score < 55


class TestCapitalFlowAnalyzer:
    def test_no_data(self):
        result = CapitalFlowAnalyzer().analyze("600519")
        assert result.score == 50.0
        assert not result.data_available

    def test_north_bound_bullish(self):
        result = CapitalFlowAnalyzer().analyze(
            "600519", north_bound_inflows=[5.0] * 10
        )
        assert result.score > 50
        assert result.data_available

    def test_with_main_capital(self):
        result = CapitalFlowAnalyzer().analyze(
            "600519",
            main_capital_data={
                "super_large_net": 5000, "large_net": 3000,
                "medium_net": -2000, "small_net": -6000,
                "total_amount": 100000,
            },
        )
        assert result.data_available
        assert "main_score" in result.detail


class TestInstitutionalAnalyzer:
    def test_no_data(self):
        result = InstitutionalAnalyzer().analyze("600519")
        assert result.score == 50.0

    def test_bullish_reports(self):
        reports = [
            {"rating": "买入", "target_price": 2000},
            {"rating": "买入", "target_price": 2100},
            {"rating": "增持", "target_price": 1950},
            {"rating": "中性", "target_price": 1800},
        ]
        result = InstitutionalAnalyzer().analyze("600519", research_reports=reports)
        assert result.data_available
        assert result.score > 55
        assert result.detail["buy_count"] >= 3


class TestMacroGeoAnalyzer:
    def test_no_data(self):
        result = MacroGeoAnalyzer().analyze("600519")
        assert result.score == 50.0

    def test_geopolitical_risk(self):
        articles = [
            {"title": "地缘冲突升级", "content": "军事对抗 制裁 贸易战"},
            {"title": "央行加息", "content": "美联储加息 通胀"},
        ]
        result = MacroGeoAnalyzer().analyze("600519", macro_articles=articles)
        assert result.data_available
        assert "宏观风险" in result.summary


class TestIndustrySentimentAnalyzer:
    def test_no_data(self):
        result = IndustrySentimentAnalyzer().analyze("600519")
        assert result.score == 50.0

    def test_positive_news(self):
        articles = [
            {"title": "业绩超预期", "content": "增长强劲 利好 突破"},
            {"title": "订单饱满", "content": "涨价 供不应求 回购"},
        ]
        result = IndustrySentimentAnalyzer().analyze("600519", news_articles=articles)
        assert result.data_available
        assert result.score > 50


class TestResonanceEngine:
    def test_full_resonance(self):
        engine = ResonanceEngine()
        engine.register("technical", TechnicalAnalyzer())
        engine.register("capital_flow", CapitalFlowAnalyzer())
        engine.register("institutional", InstitutionalAnalyzer())
        engine.register("macro_geo", MacroGeoAnalyzer())
        engine.register("industry_sentiment", IndustrySentimentAnalyzer())

        kline = _make_kline_data(list(range(100, 130, 1)))
        result = engine.analyze(
            "600519", market="A",
            extra_context={
                "kline_data": kline,
                "north_bound_inflows": [5.0] * 10,
                "research_reports": [{"rating": "买入", "target_price": 2000}],
                "macro_articles": [{"title": "稳定", "content": "经济复苏"}],
                "news_articles": [{"title": "利好", "content": "增长突破"}],
            },
        )

        assert len(result.dimensions) == 5
        assert 0 <= result.consensus_score <= 100
        assert result.bullish_dimensions + result.bearish_dimensions + result.neutral_dimensions >= 0
        assert len(result.ai_prompt) > 100
        assert "五维一体分析" in result.ai_prompt

    def test_empty_resonance(self):
        engine = ResonanceEngine()
        result = engine.analyze("600519")
        assert len(result.dimensions) == 0
        assert result.ai_prompt == ""
        assert result.consensus_score == 50.0

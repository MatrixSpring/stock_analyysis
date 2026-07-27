# -*- coding: utf-8 -*-
"""
===================================
五维一体分析维度引擎
===================================

五大维度：
  1. 技术面 (TechnicalAnalyzer)
  2. 资金行为 (CapitalFlowAnalyzer)
  3. 机构观点 (InstitutionalAnalyzer)
  4. 宏观博弈 (MacroGeoAnalyzer)
  5. 产业链舆情 (IndustrySentimentAnalyzer)

使用方式：
    from src.analysis_dimensions import ResonanceEngine, TechnicalAnalyzer, CapitalFlowAnalyzer

    engine = ResonanceEngine()
    engine.register("technical", TechnicalAnalyzer())
    engine.register("capital_flow", CapitalFlowAnalyzer())
    # ...

    result = engine.analyze("600519", market="A",
                            kline_data=data, north_bound_inflows=inflows)
"""

from src.analysis_dimensions.base import (
    DimensionAnalyzer,
    DimensionResult,
    ResonanceResult,
    DIMENSION_TECHNICAL,
    DIMENSION_CAPITAL_FLOW,
    DIMENSION_INSTITUTIONAL,
    DIMENSION_MACRO_GEO,
    DIMENSION_INDUSTRY_SENTIMENT,
    DIMENSION_LABELS,
    DIMENSION_ORDER,
)
from src.analysis_dimensions.analyzers import (
    TechnicalAnalyzer,
    CapitalFlowAnalyzer,
    InstitutionalAnalyzer,
    MacroGeoAnalyzer,
    IndustrySentimentAnalyzer,
)
from src.analysis_dimensions.resonance import ResonanceEngine

__all__ = [
    "DimensionAnalyzer",
    "DimensionResult",
    "ResonanceResult",
    "ResonanceEngine",
    "TechnicalAnalyzer",
    "CapitalFlowAnalyzer",
    "InstitutionalAnalyzer",
    "MacroGeoAnalyzer",
    "IndustrySentimentAnalyzer",
    "DIMENSION_TECHNICAL",
    "DIMENSION_CAPITAL_FLOW",
    "DIMENSION_INSTITUTIONAL",
    "DIMENSION_MACRO_GEO",
    "DIMENSION_INDUSTRY_SENTIMENT",
    "DIMENSION_LABELS",
    "DIMENSION_ORDER",
]

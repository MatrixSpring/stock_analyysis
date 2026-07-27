# -*- coding: utf-8 -*-
"""
===================================
五维分析框架 — DimensionBase
===================================

五大分析维度：
  维度1: 技术面 (Technical)        — K线、趋势、量价、形态
  维度2: 资金行为 (CapitalFlow)    — 北向、主力、融资融券、龙虎榜
  维度3: 机构观点 (Institutional)   — 研报评级、目标价、一致性预期
  维度4: 宏观博弈 (MacroGeo)       — 地缘、政策、汇率、外部风险
  维度5: 产业链舆情 (IndustrySentiment) — 上下游、景气度、舆情情感

每个维度的输出结构：
{
  score: 0-100,           # 该维度综合评分
  signals: [...],         # 关键信号列表
  risk_flags: [...],      # 风险标记
  summary: "...",         # AI 可用的中文摘要
  detail: {...},          # 子指标详情
}
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================
# 统一输出结构
# ============================================================

@dataclass
class DimensionResult:
    """单维度分析结果"""
    dimension: str                # 维度名称
    score: float = 50.0           # 0-100
    label: str = ""               # 中文标签
    signals: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    summary: str = ""             # AI 可用的摘要
    detail: Dict[str, Any] = field(default_factory=dict)
    data_available: bool = False  # 是否有数据支撑
    confidence: float = 0.5       # 置信度 0-1


@dataclass
class ResonanceResult:
    """五维共振分析结果"""
    dimensions: Dict[str, DimensionResult] = field(default_factory=dict)
    consensus_score: float = 50.0   # 共振评分
    bullish_dimensions: int = 0
    bearish_dimensions: int = 0
    neutral_dimensions: int = 0
    dominant_dimension: str = ""    # 主导维度
    divergence_warning: bool = False  # 维度背离
    ai_prompt: str = ""             # 拼接好的 AI 分析 Prompt


# ============================================================
# 维度假名
# ============================================================

DIMENSION_TECHNICAL = "technical"
DIMENSION_CAPITAL_FLOW = "capital_flow"
DIMENSION_INSTITUTIONAL = "institutional"
DIMENSION_MACRO_GEO = "macro_geo"
DIMENSION_INDUSTRY_SENTIMENT = "industry_sentiment"

DIMENSION_LABELS: Dict[str, str] = {
    DIMENSION_TECHNICAL: "技术面",
    DIMENSION_CAPITAL_FLOW: "资金行为",
    DIMENSION_INSTITUTIONAL: "机构观点",
    DIMENSION_MACRO_GEO: "宏观博弈",
    DIMENSION_INDUSTRY_SENTIMENT: "产业链舆情",
}

# 分析顺序：自上而下（宏观 → 行业 → 机构 → 资金 → 技术）
DIMENSION_ORDER = [
    DIMENSION_MACRO_GEO,
    DIMENSION_INDUSTRY_SENTIMENT,
    DIMENSION_INSTITUTIONAL,
    DIMENSION_CAPITAL_FLOW,
    DIMENSION_TECHNICAL,
]


# ============================================================
# 基类
# ============================================================

class DimensionAnalyzer(ABC):
    """维度分析器基类"""

    dimension: str = ""
    label: str = ""

    @abstractmethod
    def analyze(
        self,
        stock_code: str,
        market: str = "A",
        **kwargs,
    ) -> DimensionResult:
        """
        执行本维度分析。

        Args:
            stock_code: 股票代码
            market: 市场 (A/HK/US)
            **kwargs: 额外上下文数据

        Returns:
            DimensionResult
        """
        ...

    def _result(
        self,
        score: float = 50.0,
        signals: Optional[List[str]] = None,
        risk_flags: Optional[List[str]] = None,
        summary: str = "",
        detail: Optional[Dict[str, Any]] = None,
        data_available: bool = False,
        confidence: float = 0.5,
    ) -> DimensionResult:
        return DimensionResult(
            dimension=self.dimension,
            score=round(float(score), 1),
            label=self.label,
            signals=signals or [],
            risk_flags=risk_flags or [],
            summary=summary,
            detail=detail or {},
            data_available=data_available,
            confidence=round(confidence, 2),
        )

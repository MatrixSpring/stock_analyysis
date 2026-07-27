# -*- coding: utf-8 -*-
"""
===================================
五维共振分析引擎 — ResonanceEngine
===================================

职责：
1. 调度五大维度分析器依次执行
2. 检测维度间背离/共振信号
3. 计算综合评分
4. 生成多维度 AI 分析 Prompt
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.analysis_dimensions.base import (
    DimensionResult,
    ResonanceResult,
    DIMENSION_ORDER,
    DIMENSION_LABELS,
    DIMENSION_TECHNICAL,
    DIMENSION_CAPITAL_FLOW,
    DIMENSION_INSTITUTIONAL,
    DIMENSION_MACRO_GEO,
    DIMENSION_INDUSTRY_SENTIMENT,
    DimensionAnalyzer,
)

logger = logging.getLogger(__name__)


class ResonanceEngine:
    """
    五维共振分析引擎。

    使用方式：
        engine = ResonanceEngine()
        engine.register(DIMENSION_TECHNICAL, technical_analyzer)
        engine.register(DIMENSION_CAPITAL_FLOW, capital_flow_analyzer)
        ...
        result = engine.analyze("600519", market="A")
    """

    def __init__(self):
        self._analyzers: Dict[str, DimensionAnalyzer] = {}

    def register(self, dimension: str, analyzer: DimensionAnalyzer):
        self._analyzers[dimension] = analyzer
        logger.info(f"[ResonanceEngine] 注册维度: {dimension} → {analyzer.__class__.__name__}")

    def analyze(
        self,
        stock_code: str,
        market: str = "A",
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> ResonanceResult:
        """
        执行五维分析并生成共振报告。

        Args:
            stock_code: 股票代码
            market: 市场
            extra_context: 额外上下文（预先获取的行情/新闻等）

        Returns:
            ResonanceResult
        """
        dimensions: Dict[str, DimensionResult] = {}
        context = extra_context or {}
        errors: List[str] = []

        # 按自上而下顺序执行
        for dim in DIMENSION_ORDER:
            analyzer = self._analyzers.get(dim)
            if analyzer is None:
                continue
            try:
                result = analyzer.analyze(stock_code, market=market, **context)
                dimensions[dim] = result
            except Exception as e:
                logger.error(f"[ResonanceEngine] {dim} 分析失败: {e}")
                dimensions[dim] = DimensionResult(
                    dimension=dim,
                    label=DIMENSION_LABELS.get(dim, dim),
                    summary=f"分析失败: {e}",
                    data_available=False,
                )
                errors.append(f"{dim}: {e}")

        # 空维度检查
        if not dimensions:
            return ResonanceResult(
                dimensions={},
                consensus_score=50.0,
                bullish_dimensions=0,
                bearish_dimensions=0,
                neutral_dimensions=0,
                dominant_dimension="",
                divergence_warning=False,
                ai_prompt="",
            )

        # 计算共振
        resonance = self._compute_resonance(dimensions)

        # 生成 AI Prompt
        ai_prompt = self._build_ai_prompt(stock_code, market, dimensions, resonance)

        return ResonanceResult(
            dimensions=dimensions,
            consensus_score=resonance["score"],
            bullish_dimensions=resonance["bullish"],
            bearish_dimensions=resonance["bearish"],
            neutral_dimensions=resonance["neutral"],
            dominant_dimension=resonance["dominant"],
            divergence_warning=resonance["divergence"],
            ai_prompt=ai_prompt,
        )

    # ============================================================
    # 共振计算
    # ============================================================

    def _compute_resonance(self, dimensions: Dict[str, DimensionResult]) -> Dict[str, Any]:
        """
        计算五维共振指标。

        规则：
        - 4+ 维同向 → 强共振
        - 3 维同向 → 弱共振
        - 维度间分数标准差 > 20 → 背离警告
        """
        scores = [d.score for d in dimensions.values() if d.data_available]
        if not scores:
            return {"score": 50.0, "bullish": 0, "bearish": 0, "neutral": len(dimensions),
                    "dominant": "", "divergence": False}

        bullish = sum(1 for s in scores if s >= 60)
        bearish = sum(1 for s in scores if s <= 40)
        neutral = len(scores) - bullish - bearish

        # 加权综合分：宏观 25% + 行业 20% + 机构 20% + 资金 20% + 技术 15%
        weights = {
            DIMENSION_MACRO_GEO: 0.25,
            DIMENSION_INDUSTRY_SENTIMENT: 0.20,
            DIMENSION_INSTITUTIONAL: 0.20,
            DIMENSION_CAPITAL_FLOW: 0.20,
            DIMENSION_TECHNICAL: 0.15,
        }
        weighted = sum(
            dimensions[dim].score * weights.get(dim, 0.2)
            for dim in dimensions
            if dim in weights
        )
        total_weight = sum(
            weights.get(dim, 0.2)
            for dim in dimensions
            if dim in weights
        )
        consensus = weighted / max(total_weight, 0.01) if total_weight > 0 else 50.0

        # 背离检测
        import statistics
        stdev = statistics.stdev(scores) if len(scores) >= 2 else 0
        divergence = stdev > 20

        # 主导维度
        max_gap = 0
        dominant = ""
        for dim, r in dimensions.items():
            gap = abs(r.score - 50)
            if gap > max_gap:
                max_gap = gap
                dominant = dim

        return {
            "score": round(consensus, 1),
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "dominant": dominant,
            "divergence": divergence,
            "stdev": round(stdev, 1),
        }

    # ============================================================
    # AI Prompt 生成
    # ============================================================

    def _build_ai_prompt(
        self,
        stock_code: str,
        market: str,
        dimensions: Dict[str, DimensionResult],
        resonance: Dict[str, Any],
    ) -> str:
        """生成五维融合 AI 分析 Prompt"""

        lines = [
            f"## 五维一体分析：{stock_code} ({market})",
            "",
            f"### 共振评分: {resonance['score']}/100",
            f"看多维度: {resonance['bullish']} | 看空维度: {resonance['bearish']} | 中性: {resonance['neutral']}",
        ]

        if resonance["divergence"]:
            lines.append("⚠️ **维度背离警告**: 不同维度信号分歧显著，需谨慎判断")
        if resonance["dominant"]:
            dom_label = DIMENSION_LABELS.get(resonance["dominant"], resonance["dominant"])
            lines.append(f"主导维度: {dom_label}")

        lines.append("")
        lines.append("---")
        lines.append("")

        # 各维度详情（按自上而下顺序）
        for dim in DIMENSION_ORDER:
            r = dimensions.get(dim)
            if r is None:
                continue
            lines.append(f"### {r.label} ({r.score}/100)" +
                        (f" 置信度:{r.confidence:.0%}" if r.data_available else " ⚠️数据不足"))
            if r.summary:
                lines.append(r.summary)
            if r.signals:
                lines.append("**信号**: " + "、".join(r.signals))
            if r.risk_flags:
                lines.append("**风险**: " + "、".join(r.risk_flags))
            if r.detail:
                for k, v in r.detail.items():
                    if isinstance(v, (int, float)):
                        lines.append(f"  - {k}: {v}")
            lines.append("")

        lines.append("---")
        lines.append("请基于以上五维数据，给出：")
        lines.append("1. 综合研判结论（看多/看空/中性）")
        lines.append("2. 各维度关键矛盾点")
        lines.append("3. 建议操作方向和仓位建议")

        return "\n".join(lines)

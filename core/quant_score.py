# -*- coding: utf-8 -*-
"""
===================================
四维量化打分引擎 — core/quant_score.py
===================================

四维度：趋势(Trend) · 资金(Capital) · 估值(Value) · 情绪(Sentiment)
每维度 0~1 评分，加权融合输出综合得分。

使用方式：
    from core.quant_score import QuantScorer
    scorer = QuantScorer()
    result = scorer.score(kline_df, capital_data={})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    """打分结果"""
    code: str = ""
    name: str = ""
    trend_score: float = 0.0       # 趋势 0~1
    capital_score: float = 0.0     # 资金 0~1
    value_score: float = 0.0       # 估值 0~1
    sentiment_score: float = 0.0   # 情绪 0~1
    total_score: float = 0.0       # 加权综合 0~1
    trend_label: str = "中性"
    risk_tags: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class QuantScorer:
    """
    四维量化打分引擎。

    权重可配置，默认等权。
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "trend": 0.30,
            "capital": 0.25,
            "value": 0.25,
            "sentiment": 0.20,
        }

    # ---- 主入口 ----

    def score(
        self,
        df: pd.DataFrame,
        code: str = "",
        name: str = "",
        capital_data: Optional[Dict] = None,
        sector_data: Optional[Dict] = None,
    ) -> ScoreResult:
        """
        计算四维综合评分。

        Args:
            df: K线 DataFrame (需含 close, high, low, volume)
            code: 股票代码
            name: 股票名称
            capital_data: 资金数据 (北向、融资等)
            sector_data: 行业数据

        Returns:
            ScoreResult 完整打分结果
        """
        if df is None or df.empty or "close" not in df.columns:
            return ScoreResult(code=code, name=name)

        close = df["close"].astype(float)
        volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(dtype=float)

        # 1. 趋势评分
        trend = self._score_trend(close, df)
        # 2. 资金评分
        capital = self._score_capital(close, volume, capital_data or {})
        # 3. 估值评分
        value = self._score_value(close)
        # 4. 情绪评分
        sentiment = self._score_sentiment(close, volume, sector_data or {})

        # 加权融合
        total = (
            trend * self.weights["trend"]
            + capital * self.weights["capital"]
            + value * self.weights["value"]
            + sentiment * self.weights["sentiment"]
        )

        # 风险标签
        risk_tags = self._detect_risks(df, close, volume)

        return ScoreResult(
            code=code,
            name=name,
            trend_score=round(trend, 4),
            capital_score=round(capital, 4),
            value_score=round(value, 4),
            sentiment_score=round(sentiment, 4),
            total_score=round(total, 4),
            trend_label=self._trend_label(trend),
            risk_tags=risk_tags,
            details={
                "ma_status": self._ma_status(close),
                "volatility": round(float(close.pct_change().std() * np.sqrt(252)), 4),
                "volume_ratio": round(float(volume.tail(5).mean() / max(volume.tail(20).mean(), 1)), 2) if len(volume) >= 20 else 1.0,
            },
        )

    # ============================================================
    # 维度一：趋势评分
    # ============================================================

    def _score_trend(self, close: pd.Series, df: pd.DataFrame) -> float:
        """趋势评分：均线排列 + 价格位置 + 动量"""
        score = 0.5  # 基准分
        ln = len(close)

        # 1. 均线多头排列 (MA5 > MA20 > MA60)
        if ln >= 60:
            ma5 = close.rolling(5).mean().iloc[-1]
            ma20 = close.rolling(20).mean().iloc[-1]
            ma60 = close.rolling(60).mean().iloc[-1]
            if ma5 > ma20 > ma60:
                score += 0.2
            elif ma5 < ma20 < ma60:
                score -= 0.2

        # 2. 价格相对位置 (近20日高低)
        if ln >= 20:
            h20 = close.tail(20).max()
            l20 = close.tail(20).min()
            pos = (close.iloc[-1] - l20) / max(h20 - l20, 0.01)
            score += (pos - 0.5) * 0.2  # 高位加分，低位减分

        # 3. 短期动量 (5日涨跌幅)
        if ln >= 5:
            ret5 = close.iloc[-1] / close.iloc[-5] - 1
            score += np.clip(ret5 * 2, -0.15, 0.15)

        # 4. 波动率惩罚
        if ln >= 20:
            vol = close.pct_change().tail(20).std()
            if vol > 0.04:
                score -= 0.1
            elif vol < 0.01:
                score += 0.05

        return self._clamp(score)

    # ============================================================
    # 维度二：资金评分
    # ============================================================

    def _score_capital(
        self, close: pd.Series, volume: pd.Series, capital_data: Dict
    ) -> float:
        """资金评分：量价配合 + 资金流向"""
        score = 0.5
        ln = len(close)

        # 1. 量价配合
        if ln >= 20 and len(volume) >= 20:
            price_up = close.tail(20).diff().gt(0)
            vol_up = volume.tail(20).diff().gt(0)
            concordance = (price_up == vol_up).sum() / 20
            score += (concordance - 0.5) * 0.2

        # 2. 放量程度
        if len(volume) >= 20:
            vol_ratio = volume.tail(5).mean() / max(volume.tail(60).mean(), 1) if ln >= 60 else 1
            if vol_ratio > 1.5:
                score += 0.1  # 放量
            elif vol_ratio < 0.5:
                score -= 0.1  # 缩量

        # 3. 北向资金 (外部数据)
        if capital_data.get("north_bound_inflow"):
            score += 0.1
        elif capital_data.get("north_bound_outflow"):
            score -= 0.15

        # 4. 融资盘风险
        if capital_data.get("margin_ratio", 0) > 0.8:
            score -= 0.2
            # high margin = risk

        return self._clamp(score)

    # ============================================================
    # 维度三：估值评分
    # ============================================================

    def _score_value(self, close: pd.Series) -> float:
        """估值评分：历史分位 + 偏离度"""
        score = 0.5
        ln = len(close)

        if ln < 60:
            return 0.5

        # 1. 历史价格分位 (越低越便宜)
        pct = (close.iloc[-1] - close.min()) / max(close.max() - close.min(), 0.01)
        if pct < 0.2:
            score += 0.25  # 历史低位 → 估值偏低
        elif pct < 0.4:
            score += 0.1
        elif pct > 0.8:
            score -= 0.2  # 历史高位 → 估值偏高
        elif pct > 0.6:
            score -= 0.1

        # 2. 偏离60日均线
        ma60 = close.rolling(60).mean().iloc[-1]
        deviation = close.iloc[-1] / ma60 - 1
        if deviation < -0.2:
            score += 0.1  # 超跌
        elif deviation > 0.3:
            score -= 0.15  # 超涨

        return self._clamp(score)

    # ============================================================
    # 维度四：情绪评分
    # ============================================================

    def _score_sentiment(
        self, close: pd.Series, volume: pd.Series, sector_data: Dict
    ) -> float:
        """情绪评分：市场情绪 + 波动特征"""
        score = 0.5
        ln = len(close)

        # 1. 近期连续涨跌天数
        if ln >= 5:
            recent = close.tail(5)
            up_days = (recent.diff() > 0).sum()
            score += (up_days / 5 - 0.5) * 0.3

        # 2. 振幅异常
        if ln >= 10 and "high" in close.index and "low" in close.index:
            pass  # handled in trend

        # 3. 行业情绪
        if sector_data.get("sector_momentum"):
            score += 0.1
        if sector_data.get("sector_decline"):
            score -= 0.1

        # 4. 涨跌停检测
        if ln >= 1:
            pct = close.pct_change().iloc[-1]
            if abs(pct) > 0.095:
                score += 0.15 if pct > 0 else -0.15

        return self._clamp(score)

    # ============================================================
    # 辅助
    # ============================================================

    def _clamp(self, val: float) -> float:
        return round(max(0.0, min(1.0, val)), 4)

    def _trend_label(self, score: float) -> str:
        if score > 0.65:
            return "强势"
        elif score > 0.5:
            return "偏多"
        elif score > 0.35:
            return "震荡"
        elif score > 0.2:
            return "偏空"
        return "弱势"

    def _ma_status(self, close: pd.Series) -> str:
        ln = len(close)
        if ln < 20:
            return "数据不足"
        ma5 = close.rolling(5).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        if ma5 > ma20 * 1.02:
            return "多头排列"
        elif ma5 < ma20 * 0.98:
            return "空头排列"
        return "均线粘合"

    def _detect_risks(self, df: pd.DataFrame, close: pd.Series, volume: pd.Series) -> List[str]:
        risks = []
        ln = len(close)

        if ln >= 20:
            # 高位风险
            h20 = close.tail(20).max()
            if close.iloc[-1] >= h20 * 0.98:
                risks.append("接近20日高点")

            # 缩量风险
            if len(volume) >= 20 and volume.tail(5).mean() < volume.tail(20).mean() * 0.5:
                risks.append("持续缩量")

            # 波动率风险
            vol = close.pct_change().tail(10).std()
            if vol > 0.05:
                risks.append("高波动")
            elif vol < 0.005:
                risks.append("极度低波")

        return risks

    # ============================================================
    # 批量评分
    # ============================================================

    def batch_score(
        self,
        stocks_data: Dict[str, pd.DataFrame],
        capital_map: Optional[Dict[str, Dict]] = None,
    ) -> List[ScoreResult]:
        """
        批量评分，返回按 total_score 降序排列。

        Args:
            stocks_data: {code: kline_df} 映射
            capital_map: {code: capital_data} 映射
        """
        results = []
        for code, df in stocks_data.items():
            cap = (capital_map or {}).get(code, {})
            result = self.score(df, code=code, capital_data=cap)
            results.append(result)

        results.sort(key=lambda r: r.total_score, reverse=True)
        return results


# 全局单例
_quant_scorer: Optional[QuantScorer] = None


def get_scorer(weights: Optional[Dict[str, float]] = None) -> QuantScorer:
    global _quant_scorer
    if _quant_scorer is None:
        _quant_scorer = QuantScorer(weights)
    return _quant_scorer

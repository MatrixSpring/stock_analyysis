# -*- coding: utf-8 -*-
"""
===================================
多模型共识预测引擎 — core/multi_model_forecast.py
===================================

三大子模型：
- 时序预测 (ARIMA/趋势外推)
- 资金模型 (量价关系/北向)
- 舆情模型 (情绪/事件)

加权融合 → 多周期推演 (1周/15天/1月/半年)

使用方式：
    from core.multi_model_forecast import MultiModelForecastEngine, ForecastCycle
    engine = MultiModelForecastEngine()
    result = engine.forecast("600519", kline_df, ForecastCycle.DAY_15)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core.utils import clamp, safe_execute

logger = logging.getLogger(__name__)


class ForecastCycle(Enum):
    WEEK_1 = ("1周", 5)
    DAY_15 = ("15天", 15)
    MONTH_1 = ("1个月", 22)
    HALF_YEAR = ("半年", 126)

    @property
    def label(self) -> str:
        return self.value[0]

    @property
    def days(self) -> int:
        return self.value[1]


class MultiModelForecastEngine:
    """
    多模型融合预测引擎。

    三大子模型独立推演 → 加权共识 → 置信度评估
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "time_series": 0.40,
            "capital": 0.35,
            "sentiment": 0.25,
        }

    # ---- 主入口 ----

    def forecast(
        self,
        stock_code: str,
        df_kline: pd.DataFrame,
        cycle: ForecastCycle = ForecastCycle.DAY_15,
        capital_data: Optional[Dict] = None,
        event_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        多模型共识预测。

        Returns:
            {
                "stock_code": str,
                "cycle": str,
                "consensus_score": float 0~1,
                "trend": "up/down/oscillation",
                "confidence": float,
                "price_range": {"optimistic": float, "base": float, "pessimistic": float},
                "sub_models": {...},
                "risk_warnings": [...]
            }
        """
        if df_kline is None or df_kline.empty or "close" not in df_kline.columns:
            return self._empty_result(stock_code, cycle)

        close = df_kline["close"].astype(float)
        ln = len(close)
        if ln < 20:
            return self._empty_result(stock_code, cycle, error="K线数据不足(需≥20条)")

        last_price = float(close.iloc[-1])

        # 1. 时序预测
        ts = self._time_series_predict(close, cycle)

        # 2. 资金模型
        cap = self._capital_predict(df_kline, stock_code, capital_data or {})

        # 3. 舆情模型
        sent = self._sentiment_predict(stock_code, event_data or {})

        # 4. 加权共识
        consensus_score = (
            ts["score"] * self.weights["time_series"]
            + cap["score"] * self.weights["capital"]
            + sent["score"] * self.weights["sentiment"]
        )

        # 5. 趋势判定
        if consensus_score > 0.55:
            trend = "up"
        elif consensus_score < 0.45:
            trend = "down"
        else:
            trend = "oscillation"

        # 6. 置信度
        confidence = self._calc_confidence(ts, cap, sent)

        # 7. 价格区间
        volatility = float(close.pct_change().tail(20).std() * np.sqrt(cycle.days))
        base_move = (consensus_score - 0.5) * 2 * volatility
        base_price = round(last_price * (1 + base_move), 2)
        optimistic = round(last_price * (1 + base_move + volatility * 0.5), 2)
        pessimistic = round(last_price * (1 + base_move - volatility * 0.5), 2)

        # 8. 风险警告
        risks = self._detect_forecast_risks(ts, cap, sent, volatility)

        return {
            "stock_code": stock_code,
            "cycle": cycle.label,
            "cycle_days": cycle.days,
            "consensus_score": round(consensus_score, 4),
            "trend": trend,
            "confidence": round(confidence, 4),
            "current_price": last_price,
            "price_range": {
                "optimistic": max(optimistic, last_price * 0.9),
                "base": base_price,
                "pessimistic": max(pessimistic, last_price * 0.85),
            },
            "sub_models": {
                "time_series": {"score": ts["score"], "label": ts["label"], "detail": ts.get("detail", "")},
                "capital": {"score": cap["score"], "label": cap["label"], "detail": cap.get("detail", "")},
                "sentiment": {"score": sent["score"], "label": sent["label"], "detail": sent.get("detail", "")},
            },
            "risk_warnings": risks,
        }

    # ============================================================
    # 子模型 1: 时序预测
    # ============================================================

    def _time_series_predict(self, close: pd.Series, cycle: ForecastCycle) -> Dict:
        """基于趋势 + 动量的时序外推"""
        ln = len(close)
        ma5 = close.rolling(5).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        last = close.iloc[-1]

        # 短期动量
        mom5 = close.iloc[-1] / close.iloc[-5] - 1 if ln >= 5 else 0
        mom20 = close.iloc[-1] / close.iloc[-20] - 1 if ln >= 20 else 0

        # 趋势强度
        trend_score = 0.5
        if ma5 > ma20:
            trend_score += 0.15
        else:
            trend_score -= 0.1

        # 动量和周期权重
        cycle_weight = min(cycle.days / 30, 1.0)
        momentum = mom5 * (1 - cycle_weight) + mom20 * cycle_weight
        trend_score += clamp(momentum * 2, -0.15, 0.15)

        label = "看多" if trend_score > 0.55 else ("看空" if trend_score < 0.45 else "震荡")

        return {
            "score": clamp(trend_score, 0.05, 0.95),
            "label": label,
            "detail": f"MA5={ma5:.1f} MA20={ma20:.1f} mom5={mom5*100:.1f}%",
        }

    # ============================================================
    # 子模型 2: 资金模型
    # ============================================================

    def _capital_predict(self, df: pd.DataFrame, code: str, capital_data: Dict) -> Dict:
        """基于量价 + 资金流预测"""
        close = df["close"].astype(float)
        volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(dtype=float)
        ln = len(close)

        score = 0.5

        # 量价配合
        if len(volume) >= 20:
            price_up = close.tail(20).diff().gt(0)
            vol_up = volume.tail(20).diff().gt(0)
            concordance = (price_up == vol_up).sum() / 20
            score += (concordance - 0.5) * 0.2

        # 放量程度
        if len(volume) >= 60:
            vol_ratio = volume.tail(5).mean() / max(volume.tail(60).mean(), 1)
            if vol_ratio > 1.8:
                score += 0.1
            elif vol_ratio < 0.4:
                score -= 0.1

        # 外部资金数据
        if capital_data.get("north_bound_in"):
            score += 0.1
        if capital_data.get("margin_ratio", 0) > 0.7:
            score -= 0.15

        label = "资金流入" if score > 0.55 else ("资金流出" if score < 0.45 else "中性")

        return {
            "score": clamp(score, 0.05, 0.95),
            "label": label,
            "detail": f"vol_ratio={vol_ratio:.1f}" if len(volume) >= 60 else "",
        }

    # ============================================================
    # 子模型 3: 舆情模型
    # ============================================================

    def _sentiment_predict(self, code: str, event_data: Dict) -> Dict:
        """基于事件/舆情的情绪预测"""
        score = 0.5

        events = event_data.get("events", [])
        if not events:
            return {"score": 0.5, "label": "中性", "detail": "无事件数据"}

        positive = sum(1 for e in events if e.get("direction") == "positive")
        negative = sum(1 for e in events if e.get("direction") == "negative")
        total = len(events)

        if total > 0:
            net = (positive - negative) / total
            score += net * 0.3

        # 事件强度加权
        strengths = [e.get("strength", 5) for e in events]
        avg_strength = sum(strengths) / len(strengths) if strengths else 5
        score += (avg_strength - 5) / 50

        label = "正面" if score > 0.55 else ("负面" if score < 0.45 else "中性")

        return {
            "score": clamp(score, 0.05, 0.95),
            "label": label,
            "detail": f"利好{positive} 利空{negative} 总{total}",
        }

    # ============================================================
    # 置信度 + 风险
    # ============================================================

    def _calc_confidence(self, ts: Dict, cap: Dict, sent: Dict) -> float:
        """模型一致性越高，置信度越高"""
        scores = [ts["score"], cap["score"], sent["score"]]
        variance = float(np.var(scores))
        # 方差小 → 一致性强 → 置信度高
        conf = clamp(1.0 - variance * 5, 0.1, 0.95)
        return round(conf, 4)

    def _detect_forecast_risks(
        self, ts: Dict, cap: Dict, sent: Dict, volatility: float
    ) -> List[str]:
        risks = []
        if volatility > 0.05:
            risks.append(f"高波动({volatility*100:.1f}%) → 预测区间较宽")
        if abs(ts["score"] - cap["score"]) > 0.3:
            risks.append("时序与资金模型分歧大 → 信号矛盾")
        if abs(ts["score"] - sent["score"]) > 0.3:
            risks.append("时序与舆情模型分歧大 → 待确认信号")
        if ts["score"] < 0.3 and cap["score"] < 0.3:
            risks.append("多模型一致悲观 → 下行风险高")
        return risks

    def _empty_result(self, code: str, cycle: ForecastCycle, error: str = "数据不足") -> Dict:
        return {
            "stock_code": code,
            "cycle": cycle.label,
            "consensus_score": 0.5,
            "trend": "oscillation",
            "confidence": 0,
            "current_price": 0,
            "price_range": {"optimistic": 0, "base": 0, "pessimistic": 0},
            "sub_models": {},
            "risk_warnings": [error],
        }

    # ---- 批量预测 ----

    def batch_forecast(
        self,
        stocks_kline: Dict[str, pd.DataFrame],
        cycle: ForecastCycle = ForecastCycle.DAY_15,
    ) -> pd.DataFrame:
        """
        批量多周期预测。

        Returns:
            DataFrame: code, score, trend, confidence, optimistic, base, pessimistic
        """
        rows = []
        for code, df in stocks_kline.items():
            result = self.forecast(code, df, cycle)
            price = result.get("price_range", {})
            rows.append({
                "code": code,
                "score": result["consensus_score"],
                "trend": result["trend"],
                "confidence": result["confidence"],
                "optimistic": price.get("optimistic", 0),
                "base": price.get("base", 0),
                "pessimistic": price.get("pessimistic", 0),
                "risks": "; ".join(result.get("risk_warnings", [])),
            })
        df = pd.DataFrame(rows)
        return df.sort_values("score", ascending=False)


# 全局单例
_forecast_engine: Optional[MultiModelForecastEngine] = None


def get_forecast_engine() -> MultiModelForecastEngine:
    global _forecast_engine
    if _forecast_engine is None:
        _forecast_engine = MultiModelForecastEngine()
    return _forecast_engine

# -*- coding: utf-8 -*-
"""
===================================
五大维度分析器实现
===================================

每个分析器实现 DimensionAnalyzer 接口，返回 DimensionResult。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from src.analysis_dimensions.base import (
    DimensionAnalyzer,
    DimensionResult,
    DIMENSION_TECHNICAL,
    DIMENSION_CAPITAL_FLOW,
    DIMENSION_INSTITUTIONAL,
    DIMENSION_MACRO_GEO,
    DIMENSION_INDUSTRY_SENTIMENT,
)
from src.indicators.metrics_core import (
    total_return, volatility, max_drawdown, sharpe_ratio,
    daily_returns, win_rate,
)
from src.indicators.capital_flow import (
    north_bound_score, main_capital_score, margin_score,
    dragon_tiger_score, composite_capital_heat,
)
from src.indicators.sentiment import (
    text_sentiment, batch_sentiment, industry_boom_score,
    macro_risk_score, market_sentiment_index,
)


# ============================================================
# 维度1: 技术面分析
# ============================================================

class TechnicalAnalyzer(DimensionAnalyzer):
    """技术面分析：K线趋势、量价、形态、支撑压力"""

    dimension = DIMENSION_TECHNICAL
    label = "技术面"

    def analyze(
        self,
        stock_code: str,
        market: str = "A",
        kline_data: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> DimensionResult:
        if not kline_data:
            return self._result(
                score=50.0,
                summary="技术面数据缺失，无法评估。",
            )

        closes = [bar.get("close", 0) for bar in kline_data]
        volumes = [bar.get("volume", 0) for bar in kline_data]
        signals: List[str] = []
        risks: List[str] = []
        detail: Dict[str, Any] = {}

        if len(closes) < 5:
            return self._result(50.0, summary="K线数据不足（<5 根），无法评估。")

        arr = np.array(closes, dtype=np.float64)
        vol_arr = np.array(volumes, dtype=np.float64)

        # 1. 趋势评分 (0-30)
        ma5 = np.mean(arr[-5:]) if len(arr) >= 5 else arr[-1]
        ma10 = np.mean(arr[-10:]) if len(arr) >= 10 else ma5
        ma20 = np.mean(arr[-20:]) if len(arr) >= 20 else ma10
        current = arr[-1]

        trend_score = 15.0
        if ma5 > ma10 > ma20:
            trend_score = 25.0
            signals.append("多头排列")
        elif ma5 < ma10 < ma20:
            trend_score = 5.0
            risks.append("空头排列")
        elif abs(current - ma20) / ma20 < 0.02:
            trend_score = 15.0
            signals.append("均线粘合")

        detail["ma5"] = round(float(ma5), 2)
        detail["ma10"] = round(float(ma10), 2)
        detail["ma20"] = round(float(ma20), 2)

        # 2. 乖离率 (0-15)
        if ma20 > 0:
            bias = (current - ma20) / ma20
            detail["bias_pct"] = round(float(bias * 100), 2)
            if bias > 0.05:
                risks.append(f"乖离率偏高({bias*100:.1f}%)，追高风险")
                trend_score -= 5
            elif bias < -0.05:
                signals.append(f"超跌({bias*100:.1f}%)，可能反弹")
                trend_score += 2

        # 3. 量价配合 (0-20)
        if len(vol_arr) >= 5:
            avg_vol = np.mean(vol_arr[-20:]) if len(vol_arr) >= 20 else np.mean(vol_arr)
            recent_vol = np.mean(vol_arr[-5:])
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
            detail["vol_ratio"] = round(float(vol_ratio), 2)
            if vol_ratio > 1.5 and current > arr[-6] if len(arr) >= 6 else False:
                signals.append("放量上涨")
                trend_score += 8
            elif vol_ratio < 0.5:
                signals.append("缩量整理")
                trend_score += 3
            elif vol_ratio > 1.5:
                risks.append("放量下跌")
                trend_score -= 5

        # 4. 动量指标
        if len(arr) >= 20:
            rets = daily_returns(closes)
            vol = volatility(rets, daily=True)
            detail["volatility"] = round(vol, 4)
            if vol > 0.5:
                risks.append(f"波动率偏高({vol:.1%})")

            sharpe = sharpe_ratio(rets, daily=True)
            detail["sharpe"] = round(sharpe, 2)

            dd = max_drawdown(closes)
            detail["max_drawdown"] = round(dd, 4)
            if dd > 0.2:
                risks.append(f"近期回撤较大({dd:.1%})")

        total_ret = total_return(closes)
        detail["total_return"] = round(total_ret, 4)

        total_score = np.clip(trend_score + 30, 0, 100)

        return self._result(
            score=total_score,
            signals=signals,
            risk_flags=risks,
            summary=f"当前{'多头' if total_score > 55 else '震荡' if total_score > 45 else '空头'}格局，"
                     f"MA5={ma5:.2f} MA20={ma20:.2f}，"
                     f"{'放量' if detail.get('vol_ratio', 1) > 1.2 else '缩量'}运行。",
            detail=detail,
            data_available=True,
            confidence=min(len(closes) / 60, 1.0),
        )


# ============================================================
# 维度2: 资金行为分析
# ============================================================

class CapitalFlowAnalyzer(DimensionAnalyzer):
    """资金行为分析：北向、主力、融资融券、龙虎榜"""

    dimension = DIMENSION_CAPITAL_FLOW
    label = "资金行为"

    def analyze(
        self,
        stock_code: str,
        market: str = "A",
        north_bound_inflows: Optional[List[float]] = None,
        main_capital_data: Optional[Dict[str, Any]] = None,
        margin_data: Optional[Dict[str, Any]] = None,
        dragon_tiger_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> DimensionResult:
        has_any_data = any([
            north_bound_inflows,
            main_capital_data,
            margin_data,
            dragon_tiger_data,
        ])

        if not has_any_data:
            return self._result(
                score=50.0,
                summary="资金数据缺失，无法评估资金行为。",
            )

        # 北向
        nb_score = 50.0
        if north_bound_inflows:
            nb_score = north_bound_score(north_bound_inflows)

        # 主力
        mc_result = {"score": 50.0, "structure": "", "main_ratio": 0}
        if main_capital_data:
            mc_result = main_capital_score(**main_capital_data)

        # 融资融券
        margin_result = {"score": 50.0, "bias": "neutral"}
        if margin_data:
            margin_result = margin_score(**margin_data)

        # 综合
        heat = composite_capital_heat(
            north_bound_inflows=north_bound_inflows,
            main_capital=mc_result,
            margin_data=margin_result,
            dragon_tiger_data=dragon_tiger_data,
        )

        signals = []
        risks = []

        if heat["total_score"] >= 65:
            signals.append("资金面整体偏多")
        elif heat["total_score"] <= 35:
            risks.append("资金面整体偏空")

        if heat["divergence_warning"]:
            risks.append("北向与主力资金背离")

        trend_map = {
            "strong_inflow": "资金大幅流入",
            "moderate_inflow": "资金温和流入",
            "neutral": "资金中性",
            "moderate_outflow": "资金温和流出",
            "strong_outflow": "资金大幅流出",
        }

        return self._result(
            score=heat["total_score"],
            signals=signals,
            risk_flags=risks,
            summary=f"{trend_map.get(heat['trend'], '资金中性')}。"
                     f"北向评分{nb_score:.0f}，主力评分{mc_result.get('score', 50):.0f}。",
            detail={
                "north_score": round(nb_score, 1),
                "main_score": round(mc_result.get("score", 50.0), 1),
                "margin_score": round(margin_result.get("score", 50.0), 1),
                "structure": mc_result.get("structure", "N/A"),
            },
            data_available=True,
            confidence=0.7 if north_bound_inflows else 0.4,
        )


# ============================================================
# 维度3: 机构观点分析
# ============================================================

class InstitutionalAnalyzer(DimensionAnalyzer):
    """机构观点分析：研报评级、目标价、一致性预期、分歧度"""

    dimension = DIMENSION_INSTITUTIONAL
    label = "机构观点"

    def analyze(
        self,
        stock_code: str,
        market: str = "A",
        research_reports: Optional[List[Dict[str, Any]]] = None,
        consensus_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> DimensionResult:
        if not research_reports and not consensus_data:
            return self._result(
                score=50.0,
                summary="暂无机构研报和目标价数据。",
            )

        score = 50.0
        signals = []
        risks = []
        detail: Dict[str, Any] = {}

        # 研报分析
        if research_reports:
            ratings = [r.get("rating", "") for r in research_reports]
            targets = [r.get("target_price", 0) for r in research_reports if r.get("target_price")]

            # 评级分布
            buy_count = sum(1 for r in ratings if "buy" in r.lower() or "买入" in r or "增持" in r or "推荐" in r)
            hold_count = sum(1 for r in ratings if "hold" in r.lower() or "中性" in r or "持有" in r)
            sell_count = len(ratings) - buy_count - hold_count

            detail["buy_count"] = buy_count
            detail["hold_count"] = hold_count
            detail["sell_count"] = sell_count
            detail["total_reports"] = len(research_reports)

            if len(ratings) > 0:
                buy_ratio = buy_count / len(ratings)
                if buy_ratio >= 0.7:
                    score += 20
                    signals.append(f"机构一致看多({buy_count}/{len(ratings)})")
                elif buy_ratio <= 0.3:
                    score -= 15
                    risks.append("机构普遍偏空")
                else:
                    score += 5
                    signals.append(f"机构存在分歧(买入{buy_count} 中性{hold_count})")

            # 平均目标价
            if targets:
                avg_target = np.mean(targets)
                detail["avg_target_price"] = round(float(avg_target), 2)

        # 一致性预期
        if consensus_data:
            eps_est = consensus_data.get("eps_estimate")
            pe_est = consensus_data.get("pe_estimate")
            if eps_est is not None:
                detail["eps_estimate"] = round(float(eps_est), 2)
                if eps_est > 0:
                    signals.append(f"EPS 预期 {eps_est:.2f}")
            if pe_est is not None:
                detail["pe_estimate"] = round(float(pe_est), 2)

        return self._result(
            score=np.clip(score, 0, 100),
            signals=signals,
            risk_flags=risks,
            summary=f"共{detail.get('total_reports', 0)}份研报，"
                     f"买入{detail.get('buy_count', 0)} "
                     f"中性{detail.get('hold_count', 0)} "
                     f"卖出{detail.get('sell_count', 0)}。",
            detail=detail,
            data_available=bool(research_reports or consensus_data),
            confidence=0.6 if research_reports else 0.3,
        )


# ============================================================
# 维度4: 宏观博弈分析
# ============================================================

class MacroGeoAnalyzer(DimensionAnalyzer):
    """宏观博弈分析：地缘政治、政策、汇率、外部风险"""

    dimension = DIMENSION_MACRO_GEO
    label = "宏观博弈"

    def analyze(
        self,
        stock_code: str,
        market: str = "A",
        macro_articles: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> DimensionResult:
        if not macro_articles:
            return self._result(
                score=50.0,
                summary="宏观事件数据缺失。",
            )

        risk = macro_risk_score(macro_articles)

        # 风险反转 → 利好评分
        score = 100.0 - risk["risk_score"]

        signals = []
        risks_list = []

        if risk["geopolitics_level"] == "elevated":
            risks_list.append("地缘政治风险升高")
        if risk["macro_tightness"] == "tight":
            risks_list.append("宏观政策偏紧")
        if score >= 60:
            signals.append("宏观环境相对友好")
        elif score <= 40:
            risks_list.append("宏观风险偏高")

        key_events = risk.get("key_events", [])

        return self._result(
            score=round(score, 1),
            signals=signals,
            risk_flags=risks_list,
            summary=f"宏观风险评分{risk['risk_score']:.0f}/100，"
                     f"地缘风险{'偏高' if risk['geopolitics_level'] == 'elevated' else '正常'}，"
                     f"政策环境{'偏紧' if risk['macro_tightness'] == 'tight' else '中性'}。"
                     + (f" 关注: {'; '.join(key_events[:3])}" if key_events else ""),
            detail={
                "macro_risk_score": risk["risk_score"],
                "geopolitics_level": risk["geopolitics_level"],
                "macro_tightness": risk["macro_tightness"],
                "key_events": key_events,
            },
            data_available=True,
            confidence=min(len(macro_articles) / 20, 0.8),
        )


# ============================================================
# 维度5: 产业链舆情分析
# ============================================================

class IndustrySentimentAnalyzer(DimensionAnalyzer):
    """产业链舆情分析：上下游、景气度、舆情情感"""

    dimension = DIMENSION_INDUSTRY_SENTIMENT
    label = "产业链舆情"

    def analyze(
        self,
        stock_code: str,
        market: str = "A",
        news_articles: Optional[List[Dict[str, str]]] = None,
        industry_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> DimensionResult:
        has_news = bool(news_articles)
        has_industry = bool(industry_data)

        if not has_news and not has_industry:
            return self._result(
                score=50.0,
                summary="产业链舆情数据缺失。",
            )

        score = 50.0
        signals = []
        risks = []
        detail: Dict[str, Any] = {}

        # 舆情情感
        if news_articles:
            texts = [
                f"{a.get('title', '')} {a.get('content', '')}"
                for a in news_articles
            ]
            sentiment = batch_sentiment(texts)
            detail["sentiment"] = sentiment

            pos = sentiment["distribution"].get("positive", 0)
            neg = sentiment["distribution"].get("negative", 0)
            total = sentiment["count"]

            if total > 0:
                if pos > neg * 2:
                    score += 15
                    signals.append(f"舆情偏正面(正面{pos} 负面{neg})")
                elif neg > pos * 2:
                    score -= 15
                    risks.append(f"舆情偏负面(正面{pos} 负面{neg})")
                else:
                    signals.append(f"舆情中性(正面{pos} 负面{neg})")

        # 行业景气度
        if industry_data:
            boom = industry_boom_score(**industry_data)
            detail["industry_boom"] = boom

            phase_map = {
                "expansion": ("行业扩张期", 20),
                "recovery": ("行业复苏期", 10),
                "slowdown": ("行业放缓期", -5),
                "recession": ("行业衰退期", -15),
            }
            phase_info = phase_map.get(boom["phase"], ("未知", 0))
            signals.append(phase_info[0])
            score += phase_info[1]

            if boom["signals"]:
                for s in boom["signals"]:
                    if "旺盛" in s or "改善" in s or "加速" in s or "满产" in s:
                        signals.append(s)
                    else:
                        risks.append(s)

        return self._result(
            score=np.clip(score, 0, 100),
            signals=signals,
            risk_flags=risks,
            summary=f"舆情{detail.get('sentiment', {}).get('overall_sentiment', '未知')}，"
                     f"行业{detail.get('industry_boom', {}).get('phase', '未知')}。",
            detail=detail,
            data_available=bool(has_news or has_industry),
            confidence=0.5 + (0.2 if has_news else 0) + (0.2 if has_industry else 0),
        )

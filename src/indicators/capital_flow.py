# -*- coding: utf-8 -*-
"""
===================================
资金行为指标 — CapitalFlowIndicators
===================================

职责：
1. 资金热度评分：北向 + 主力 + 融资融券 + 龙虎榜 + 大宗交易
2. 单一数据源资金指标
3. 资金背离检测
4. 主力意图研判辅助

全项目唯一真源，所有模块统一调用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# 单一维度指标
# ============================================================

def north_bound_score(
    daily_inflows: List[float],
    consecutive_days: int = 20,
) -> float:
    """
    北向资金热度评分 (0-100)。

    维度：连续流入趋势 + 累计流入规模 + 近期加速

    Args:
        daily_inflows: 每日北向净流入（亿元）
        consecutive_days: 计算窗口

    Returns:
        float: 0-100 评分
    """
    if not daily_inflows:
        return 50.0

    arr = np.array(daily_inflows[-consecutive_days:], dtype=np.float64)
    score = 50.0

    # 1. 趋势项 (0-30)
    recent = arr[-5:]
    pos_days = float(np.sum(recent > 0))
    score += pos_days / 5.0 * 15  # 近5日净流入天数
    if len(arr) >= 10:
        longer = arr[-10:]
        score += float(np.sum(longer > 0)) / 10.0 * 15  # 近10日

    # 2. 规模项 (-20 ~ +20)
    total = float(np.sum(arr[-5:]))
    score += np.clip(total / 50.0, -1.0, 1.0) * 20  # 5日累计，允许负分

    # 3. 加速项 (0-10，前5日 vs 前10日)
    if len(arr) >= 10:
        recent_sum = float(np.sum(arr[-5:]))
        prior_sum = float(np.sum(arr[-10:-5]))
        if recent_sum > prior_sum:
            score += min((recent_sum - prior_sum) / max(abs(prior_sum), 1) * 5, 10)

    return float(np.clip(score, 0, 100))


def main_capital_score(
    super_large_net: float = 0.0,
    large_net: float = 0.0,
    medium_net: float = 0.0,
    small_net: float = 0.0,
    total_amount: float = 1.0,
) -> Dict[str, Any]:
    """
    主力资金分析评分。

    Args:
        super_large_net: 超大单净流入
        large_net: 大单净流入
        medium_net: 中单净流入
        small_net: 小单净流入
        total_amount: 总成交额

    Returns:
        dict: {
            main_net: 主力净流入,
            main_ratio: 主力净占比,
            retail_net: 散户净流入,
            score: 资金评分 0-100,
            structure: 资金结构描述
        }
    """
    total = max(total_amount, 1.0)
    main_net = super_large_net + large_net
    retail_net = medium_net + small_net

    main_ratio = main_net / total

    # 评分：主力净占比 + 超大单权重
    score = 50.0
    score += np.clip(main_ratio * 500, -25, 25)  # 主力占比 ±25
    score += np.clip(super_large_net / total * 300, -15, 15)  # 超大单偏重
    score += 10.0 if main_net > 0 and retail_net < 0 else 0  # 主力吃散户

    # 结构描述
    if main_ratio > 0.05:
        structure = "主力大幅流入"
    elif main_ratio > 0.02:
        structure = "主力温和流入"
    elif main_ratio > -0.02:
        structure = "主力观望"
    elif main_ratio > -0.05:
        structure = "主力温和流出"
    else:
        structure = "主力大幅流出"

    return {
        "main_net": round(main_net, 2),
        "main_ratio": round(main_ratio, 4),
        "retail_net": round(retail_net, 2),
        "super_large_ratio": round(super_large_net / total, 4),
        "score": round(float(np.clip(score, 0, 100)), 1),
        "structure": structure,
    }


def margin_score(
    margin_balance: float,
    margin_change: float,
    short_balance: Optional[float] = None,
) -> Dict[str, Any]:
    """
    融资融券多空博弈评分。

    Args:
        margin_balance: 融资余额（亿元）
        margin_change: 融资余额变化
        short_balance: 融券余额（可选）

    Returns:
        dict: {score, bias, leverage_change}
    """
    score = 50.0

    # 融资变化
    if margin_balance > 0:
        change_pct = margin_change / margin_balance
        score += np.clip(change_pct * 500, -20, 20)

    # 融券判断
    bias = "neutral"
    if short_balance is not None and margin_balance > 0:
        short_ratio = short_balance / margin_balance
        if short_ratio > 0.3:
            bias = "bearish"  # 融券占比高 → 偏空
            score -= 15
        elif short_ratio < 0.05:
            bias = "bullish"  # 融券占比低 → 偏多
            score += 10

    return {
        "score": round(float(np.clip(score, 0, 100)), 1),
        "bias": bias,
        "leverage_change": round(margin_change, 2),
    }


def dragon_tiger_score(
    buy_amount: float,
    sell_amount: float,
    institution_buy: float = 0.0,
    institution_sell: float = 0.0,
) -> Dict[str, Any]:
    """
    龙虎榜活跃度评分。

    Returns:
        dict: {score, net, institution_net, activity}
    """
    net = buy_amount - sell_amount
    inst_net = institution_buy - institution_sell
    total = buy_amount + sell_amount

    score = 50.0
    if total > 0:
        score += np.clip(net / total * 30, -20, 20)
        score += np.clip(inst_net / total * 20, -15, 15)

    activity = "quiet"
    if total > 1e10:
        activity = "extremely_active"
    elif total > 5e9:
        activity = "active"
    elif total > 1e9:
        activity = "moderate"

    return {
        "score": round(float(np.clip(score, 0, 100)), 1),
        "net": round(net, 2),
        "institution_net": round(inst_net, 2),
        "activity": activity,
    }


# ============================================================
# 综合资金热度
# ============================================================

def composite_capital_heat(
    north_bound_inflows: Optional[List[float]] = None,
    main_capital: Optional[Dict[str, Any]] = None,
    margin_data: Optional[Dict[str, Any]] = None,
    dragon_tiger_data: Optional[Dict[str, Any]] = None,
    block_trade_premium: Optional[float] = None,
) -> Dict[str, Any]:
    """
    综合资金热度评分 (0-100)。

    权重：北向 30% + 主力 25% + 融资融券 20% + 龙虎榜 15% + 大宗 10%

    Returns:
        dict: {
            total_score, north_score, main_score, margin_score,
            dragon_score, block_score, trend, divergence_warning
        }
    """
    scores: Dict[str, float] = {}
    weights = {
        "north": 0.30,
        "main": 0.25,
        "margin": 0.20,
        "dragon": 0.15,
        "block": 0.10,
    }

    # 北向
    if north_bound_inflows:
        scores["north"] = north_bound_score(north_bound_inflows)
    else:
        scores["north"] = 50.0

    # 主力
    if main_capital:
        scores["main"] = main_capital.get("score", 50.0)
    else:
        scores["main"] = 50.0

    # 融资融券
    if margin_data:
        scores["margin"] = margin_data.get("score", 50.0)
    else:
        scores["margin"] = 50.0

    # 龙虎榜
    if dragon_tiger_data:
        scores["dragon"] = dragon_tiger_data.get("score", 50.0)
    else:
        scores["dragon"] = 50.0

    # 大宗交易
    if block_trade_premium is not None:
        scores["block"] = 50.0 + np.clip(block_trade_premium * 100, -20, 20)
    else:
        scores["block"] = 50.0

    total = sum(scores[k] * weights[k] for k in weights)

    # 趋势判定
    if total >= 70:
        trend = "strong_inflow"
    elif total >= 55:
        trend = "moderate_inflow"
    elif total >= 45:
        trend = "neutral"
    elif total >= 30:
        trend = "moderate_outflow"
    else:
        trend = "strong_outflow"

    # 背离检测
    divergence_warning = False
    if scores["north"] > 70 and scores["main"] < 30:
        divergence_warning = True  # 北向大量流入但主力流出

    return {
        "total_score": round(total, 1),
        "north_score": round(scores["north"], 1),
        "main_score": round(scores["main"], 1),
        "margin_score": round(scores["margin"], 1),
        "dragon_score": round(scores["dragon"], 1),
        "block_score": round(scores["block"], 1),
        "trend": trend,
        "divergence_warning": divergence_warning,
    }

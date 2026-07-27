# -*- coding: utf-8 -*-
"""
===================================
舆情与行业景气度指标 — SentimentIndicators
===================================

职责：
1. 舆情情感评分：新闻 / 社交媒体 / 公告
2. 行业景气度评分：上下游产业链
3. 宏观事件风险评分
4. 综合市场情绪指数

全项目唯一真源，所有模块统一调用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import re
import math

import numpy as np


# ============================================================
# 关键词词典
# ============================================================

POSITIVE_WORDS = {
    "利好", "增长", "突破", "创新高", "翻倍", "暴涨", "获批", "超预期",
    "复苏", "回暖", "政策支持", "补贴", "降息", "放量", "业绩预增",
    "订单饱满", "满产", "涨价", "供不应求", "新品发布", "技术突破",
    "回购", "增持", "分红", "中标", "签约", "合作", "获牌",
}

NEGATIVE_WORDS = {
    "利空", "下跌", "暴跌", "违约", "暴雷", "退市", "制裁", "调查",
    "处罚", "停产", "亏损", "下滑", "萎缩", "收紧", "通胀",
    "减持", "质押", "爆仓", "诉讼", "失信", "整改", "限产",
    "降价", "过剩", "需求疲软", "砍单", "裁员", "关停",
}

GEOPOLITICAL_WORDS = {
    "地缘", "冲突", "制裁", "军事", "海峡", "同盟", "G20", "北约",
    "联合国", "外交", "关税", "出口管制", "贸易战", "供应链安全",
    "稀土", "芯片禁令", "实体清单", "脱钩", "去风险",
}

MACRO_WORDS = {
    "降准", "降息", "加息", "通胀", "CPI", "PPI", "PMI", "GDP",
    "美联储", "央行", "MLF", "LPR", "逆回购", "社融", "M2",
    "财政", "赤字", "国债", "汇率", "人民币", "美元指数",
}

INDUSTRY_WORDS = {
    "产业链", "供应链", "产能", "开工率", "库存", "订单", "出货",
    "排产", "装机", "交付", "投产", "扩产", "供需", "景气",
    "景气度", "行业周期", "上下游",
}


# ============================================================
# 文本情感分析
# ============================================================

def text_sentiment(text: str) -> Dict[str, Any]:
    """
    单文本情感分析。

    Returns:
        dict: {sentiment, score, positive_count, negative_count}
    """
    pos_count = sum(1 for w in POSITIVE_WORDS if w in text)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in text)

    if pos_count > neg_count:
        sentiment = "positive"
        score = min(0.5 + (pos_count - neg_count) * 0.15, 1.0)
    elif neg_count > pos_count:
        sentiment = "negative"
        score = max(-0.5 - (neg_count - pos_count) * 0.15, -1.0)
    else:
        sentiment = "neutral"
        score = 0.0

    return {
        "sentiment": sentiment,
        "score": round(score, 3),
        "positive_count": pos_count,
        "negative_count": neg_count,
    }


def batch_sentiment(texts: List[str]) -> Dict[str, Any]:
    """
    批量文本情感分析。

    Returns:
        dict: {overall_sentiment, avg_score, distribution, count}
    """
    if not texts:
        return {"overall_sentiment": "neutral", "avg_score": 0.0,
                "distribution": {}, "count": 0}

    results = [text_sentiment(t) for t in texts]
    scores = [r["score"] for r in results]

    pos_count = sum(1 for r in results if r["sentiment"] == "positive")
    neg_count = sum(1 for r in results if r["sentiment"] == "negative")
    neu_count = len(results) - pos_count - neg_count

    avg = float(np.mean(scores)) if scores else 0.0
    overall = "positive" if avg > 0.1 else ("negative" if avg < -0.1 else "neutral")

    return {
        "overall_sentiment": overall,
        "avg_score": round(avg, 3),
        "distribution": {
            "positive": pos_count,
            "negative": neg_count,
            "neutral": neu_count,
        },
        "count": len(results),
    }


# ============================================================
# 行业景气度
# ============================================================

def industry_boom_score(
    upstream_prices: Optional[List[float]] = None,
    downstream_demand: Optional[float] = None,
    capacity_utilization: Optional[float] = None,
    inventory_level: Optional[float] = None,
    new_orders_growth: Optional[float] = None,
) -> Dict[str, Any]:
    """
    行业景气度综合评分 (0-100)。

    维度：
    - 上游价格趋势 (20%)
    - 下游需求 (25%)
    - 产能利用率 (20%)
    - 库存水平 (20%)
    - 新订单增速 (15%)

    Returns:
        dict: {score, phase, signals}
    """
    scores_parts: Dict[str, float] = {}
    signals: List[str] = []

    # 1. 上游价格趋势：价格上涨 → 成本压力 ↑
    if upstream_prices is not None and len(upstream_prices) >= 2:
        price_change = (upstream_prices[-1] - upstream_prices[0]) / max(upstream_prices[0], 0.01)
        if -0.05 <= price_change <= 0.05:
            scores_parts["upstream"] = 15
        elif price_change > 0:  # 上游涨价 → 成本压力
            scores_parts["upstream"] = max(15 - price_change * 100, 0)
            signals.append(f"上游原材料上涨{price_change:.1%}")
        else:  # 上游降价 → 成本改善
            scores_parts["upstream"] = min(15 + abs(price_change) * 100, 20)
            signals.append("上游成本改善")
    else:
        scores_parts["upstream"] = 10

    # 2. 下游需求
    if downstream_demand is not None:
        demand_score = 50.0 + downstream_demand * 100
        scores_parts["downstream"] = np.clip(demand_score * 0.25, 0, 25)
        if downstream_demand > 0.05:
            signals.append("下游需求旺盛")
        elif downstream_demand < -0.05:
            signals.append("下游需求疲软")
    else:
        scores_parts["downstream"] = 12.5

    # 3. 产能利用率
    if capacity_utilization is not None:
        scores_parts["capacity"] = np.clip(capacity_utilization * 20, 0, 20)
        if capacity_utilization < 0.6:
            signals.append("产能利用率偏低")
        elif capacity_utilization > 0.85:
            signals.append("接近满产")
    else:
        scores_parts["capacity"] = 10

    # 4. 库存水平
    if inventory_level is not None:
        # 库存低位 > 健康 > 库存高位
        if 0.3 <= inventory_level <= 0.7:
            scores_parts["inventory"] = 20
        elif inventory_level < 0.3:
            scores_parts["inventory"] = 16
            signals.append("库存偏低")
        else:
            scores_parts["inventory"] = max(20 - inventory_level * 15, 0)
            signals.append("库存偏高")
    else:
        scores_parts["inventory"] = 10

    # 5. 新订单增速
    if new_orders_growth is not None:
        scores_parts["orders"] = np.clip(7.5 + new_orders_growth * 75, 0, 15)
        if new_orders_growth > 0.05:
            signals.append("新订单加速")
    else:
        scores_parts["orders"] = 7.5

    total = sum(scores_parts.values())

    # 阶段判定
    if total >= 70:
        phase = "expansion"  # 扩张
    elif total >= 50:
        phase = "recovery"   # 复苏
    elif total >= 30:
        phase = "slowdown"   # 放缓
    else:
        phase = "recession"  # 衰退

    return {
        "score": round(total, 1),
        "phase": phase,
        "detail": {k: round(v, 1) for k, v in scores_parts.items()},
        "signals": signals,
    }


# ============================================================
# 宏观事件风险
# ============================================================

def macro_risk_score(
    articles: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    宏观事件风险评分 (0-100，越高风险越大)。

    分析文章列表中的地缘政治/宏观事件关键词密度。

    Returns:
        dict: {risk_score, geopolitics_level, macro_tightness, key_events}
    """
    if not articles:
        return {"risk_score": 50.0, "geopolitics_level": "normal",
                "macro_tightness": "neutral", "key_events": []}

    geo_count = 0
    macro_count = 0
    key_events: List[str] = []

    for article in articles:
        text = f"{article.get('title', '')} {article.get('content', '')}"
        geo = sum(1 for w in GEOPOLITICAL_WORDS if w in text)
        mac = sum(1 for w in MACRO_WORDS if w in text)
        geo_count += geo
        macro_count += mac
        if geo + mac >= 3:
            key_events.append(article.get("title", "")[:80])

    # 归一化评分
    geo_score = min(geo_count / max(len(articles), 1) * 25, 50)
    macro_score = min(macro_count / max(len(articles), 1) * 25, 50)
    risk = 20.0 + geo_score + macro_score

    geo_level = "elevated" if geo_score > 25 else "normal"
    macro_tightness = "tight" if macro_score > 25 else "neutral"

    return {
        "risk_score": round(float(np.clip(risk, 0, 100)), 1),
        "geopolitics_level": geo_level,
        "macro_tightness": macro_tightness,
        "key_events": key_events[:5],
    }


# ============================================================
# 综合市场情绪
# ============================================================

def market_sentiment_index(
    news_sentiment: Optional[Dict[str, Any]] = None,
    social_sentiment: Optional[Dict[str, Any]] = None,
    capital_heat: Optional[Dict[str, Any]] = None,
    macro_risk: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    综合市场情绪指数 (0-100，50=中性)。

    权重：舆情 30% + 社媒 20% + 资金热度 30% + 宏观风险(反向) 20%
    """
    parts: Dict[str, float] = {}

    # 舆情
    if news_sentiment:
        parts["news"] = (news_sentiment.get("avg_score", 0.0) + 1) * 25
    else:
        parts["news"] = 50.0

    # 社媒
    if social_sentiment:
        parts["social"] = (social_sentiment.get("avg_score", 0.0) + 1) * 25
    else:
        parts["social"] = 50.0

    # 资金热度
    if capital_heat:
        parts["capital"] = capital_heat.get("total_score", 50.0)
    else:
        parts["capital"] = 50.0

    # 宏观风险（反向：风险越高 → 情绪越低）
    if macro_risk:
        parts["macro"] = 100.0 - macro_risk.get("risk_score", 50.0)
    else:
        parts["macro"] = 50.0

    weight_map = {"news": 0.30, "social": 0.20, "capital": 0.30, "macro": 0.20}
    total = sum(parts[k] * weight_map[k] for k in weight_map)

    # 定性判定
    if total >= 70:
        level = "greedy"       # 贪婪
    elif total >= 55:
        level = "optimistic"    # 乐观
    elif total >= 45:
        level = "neutral"       # 中性
    elif total >= 30:
        level = "fearful"       # 恐惧
    else:
        level = "panic"         # 恐慌

    return {
        "index": round(total, 1),
        "level": level,
        "components": {k: round(v, 1) for k, v in parts.items()},
    }

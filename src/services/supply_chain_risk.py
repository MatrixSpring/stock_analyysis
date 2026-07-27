# -*- coding: utf-8 -*-
"""
供应链风险评估引擎 — 从 ai_mark 子系统融合

基于 GDELT 全球事件 + 申万产业链映射，评估：
  1. 供应链中断风险等级
  2. 受影响的关键节点（上游原材料/中游制造/下游物流）
  3. 替代供应方案建议

原始来源：ai_mark/services/supply_chain_risk.py
"""

import logging
from typing import Any, Dict, List, Optional

from src.data.shenwan_chain_ledger import find_affected_chains, get_chains_by_factor

logger = logging.getLogger(__name__)

# ============================================================
# 风险事件类型定义
# ============================================================

RISK_EVENT_TYPES = {
    "geopolitical_conflict": {
        "label": "地缘冲突",
        "factors": ["地缘政治", "交通运输"],
        "affected_stages": ["midstream", "downstream"],
        "default_risk_level": "high",
    },
    "trade_restriction": {
        "label": "贸易限制/制裁",
        "factors": ["地缘政治", "汇率波动", "技术壁垒"],
        "affected_stages": ["upstream", "midstream"],
        "default_risk_level": "high",
    },
    "natural_disaster": {
        "label": "自然灾害/极端天气",
        "factors": ["气象灾害", "交通运输"],
        "affected_stages": ["upstream", "downstream"],
        "default_risk_level": "medium",
    },
    "logistics_disruption": {
        "label": "物流中断",
        "factors": ["交通运输"],
        "affected_stages": ["downstream"],
        "default_risk_level": "medium",
    },
    "raw_material_shortage": {
        "label": "原材料短缺",
        "factors": ["原材料", "供需格局"],
        "affected_stages": ["upstream"],
        "default_risk_level": "medium",
    },
    "regulatory_change": {
        "label": "政策监管变化",
        "factors": ["政策监管", "环保双碳"],
        "affected_stages": ["upstream", "midstream", "downstream"],
        "default_risk_level": "medium",
    },
    "supplier_bankruptcy": {
        "label": "核心供应商破产/停产",
        "factors": ["企业管理", "金融资金"],
        "affected_stages": ["upstream", "midstream"],
        "default_risk_level": "high",
    },
}

# 供应链阶段定义
SUPPLY_CHAIN_STAGES = {
    "upstream": "上游（原材料/初级产品）",
    "midstream": "中游（制造/加工/组装）",
    "downstream": "下游（分销/物流/终端）",
}


# ============================================================
# 风险评估引擎
# ============================================================

def classify_risk_event(title: str, content: str) -> Optional[Dict[str, Any]]:
    """
    将新闻事件分类为供应链风险类型。

    Args:
        title: 新闻标题
        content: 新闻内容

    Returns:
        风险分类结果，或 None
    """
    text = f"{title} {content}".lower()

    type_keywords = {
        "geopolitical_conflict": ["conflict", "war", "military", "invasion", "attack",
                                   "冲突", "战争", "军事", "入侵"],
        "trade_restriction": ["sanction", "tariff", "export control", "ban", "restrict",
                              "制裁", "关税", "出口管制", "限制", "禁令"],
        "natural_disaster": ["earthquake", "flood", "hurricane", "drought", "tsunami",
                             "地震", "洪水", "飓风", "干旱", "海啸", "台风"],
        "logistics_disruption": ["port congestion", "canal blockage", "shipping delay",
                                 "港口拥堵", "运河堵塞", "航运延误", "苏伊士", "巴拿马"],
        "raw_material_shortage": ["shortage", "supply deficit", "price surge",
                                  "短缺", "供应不足", "涨价", "减产"],
        "regulatory_change": ["regulation", "policy change", "ban", "compliance",
                              "监管", "政策", "新规", "合规"],
        "supplier_bankruptcy": ["bankruptcy", "shutdown", "insolvent",
                                "破产", "关闭", "停产", "清算"],
    }

    for rtype, kws in type_keywords.items():
        for kw in kws:
            if kw in text:
                event = RISK_EVENT_TYPES[rtype]
                return {
                    "risk_type": rtype,
                    "label": event["label"],
                    "factors": event["factors"],
                    "affected_stages": event["affected_stages"],
                    "default_risk_level": event["default_risk_level"],
                    "matched_keyword": kw,
                }

    return None


def assess_chain_risk(gdelt_articles: List[Dict[str, Any]],
                      stock_list: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    评估供应链风险 — 基于 GDELT 事件数据。

    Args:
        gdelt_articles: GDELT 抓取的标准化文章列表
        stock_list: 关注的股票列表（用于查找其所属产业链）

    Returns:
        风险评估报告
    """
    risks: List[Dict] = []
    affected_chains_all: List[Dict] = []
    stage_risks: Dict[str, int] = {"upstream": 0, "midstream": 0, "downstream": 0}

    for article in gdelt_articles:
        title = article.get("title", "")
        content = article.get("content", "")

        # 事件分类
        event = classify_risk_event(title, content)
        if not event:
            continue

        # 查找受影响的产业链
        keywords = title.split() + content[:300].split()
        affected = find_affected_chains(keywords, top_n=5)

        risk_item = {
            "title": title[:150],
            "risk_type": event["label"],
            "risk_level": event["default_risk_level"],
            "factors": event["factors"],
            "affected_stages": event["affected_stages"],
            "affected_chains": [
                {"code": c["code"], "name": f"{c['l1']}→{c['l2']}→{c['l3']}"}
                for c in affected
            ],
        }
        risks.append(risk_item)
        affected_chains_all.extend(affected)

        # 累计各阶段风险
        for stage in event["affected_stages"]:
            level_weight = {"low": 1, "medium": 2, "high": 3}
            stage_risks[stage] += level_weight.get(event["default_risk_level"], 1)

    # 去重产业链
    seen_codes = set()
    unique_chains = []
    for c in affected_chains_all:
        if c["code"] not in seen_codes:
            seen_codes.add(c["code"])
            unique_chains.append(c)

    # 最高风险阶段
    max_stage = max(stage_risks, key=stage_risks.get)  # type: ignore[arg-type]
    overall_level = "high" if stage_risks[max_stage] >= 6 else (
        "medium" if stage_risks[max_stage] >= 3 else "low"
    )

    # 如果指定了股票列表，查找其所属产业链风险
    stock_chain_risks: List[Dict] = []
    if stock_list:
        for stock_code in stock_list:
            # 通过申万台账查找该股票可能涉及的产业链
            matching = [c for c in unique_chains
                       for l in c.get("leaders", [])
                       if stock_code in l.get("name", "")]
            if matching:
                stock_chain_risks.append({
                    "code": stock_code,
                    "affected_chain": f"{matching[0]['l1']}→{matching[0]['l3']}",
                })

    return {
        "total_risk_events": len(risks),
        "overall_risk_level": overall_level,
        "highest_risk_stage": {
            "stage": max_stage,
            "label": SUPPLY_CHAIN_STAGES.get(max_stage, max_stage),
            "score": stage_risks[max_stage],
        },
        "stage_scores": stage_risks,
        "risk_events": risks[:10],  # Top 10
        "affected_chains_count": len(unique_chains),
        "affected_chains": unique_chains[:10],
        "stock_chain_risks": stock_chain_risks,
    }


def format_supply_chain_risk_for_prompt(risk_report: Dict[str, Any]) -> str:
    """
    将供应链风险评估格式化为 LLM prompt 上下文。

    Args:
        risk_report: assess_chain_risk() 的返回结果

    Returns:
        prompt 片段
    """
    if not risk_report or risk_report.get("total_risk_events", 0) == 0:
        return ""

    level_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    level = risk_report.get("overall_risk_level", "low")
    emoji = level_emoji.get(level, "⚪")

    lines = [
        f"## {emoji} 全球供应链风险预警（GDELT 事件监测）",
        "",
        f"- **综合风险等级**: {level.upper()}",
        f"- **风险事件数**: {risk_report.get('total_risk_events', 0)}",
        f"- **最高风险阶段**: {risk_report.get('highest_risk_stage', {}).get('label', 'N/A')}",
        f"- **受影响的申万产业链**: {risk_report.get('affected_chains_count', 0)} 条",
        "",
    ]

    # 各阶段风险
    stage_scores = risk_report.get("stage_scores", {})
    if stage_scores:
        lines.append("### 供应链各阶段风险评分")
        for stage, score in stage_scores.items():
            label = SUPPLY_CHAIN_STAGES.get(stage, stage)
            bar = "█" * min(score, 20)
            lines.append(f"- {label}: {bar} ({score})")
        lines.append("")

    # 高风险事件
    events = risk_report.get("risk_events", [])[:5]
    if events:
        lines.append("### 近期风险事件")
        for i, e in enumerate(events, 1):
            level_tag = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(e.get("risk_level", ""), "")
            lines.append(f"{i}. {level_tag} [{e.get('risk_type', '')}] {e.get('title', '')[:100]}")
            chains = [c["name"] for c in e.get("affected_chains", [])[:3]]
            if chains:
                lines.append(f"   - 影响产业链: {', '.join(chains)}")
        lines.append("")

    lines.append("> 数据来源：GDELT 全球事件数据库 + 申万产业链台账")
    return "\n".join(lines)

# -*- coding: utf-8 -*-
"""
新闻→产业链影响分析引擎 — 从 ai_mark 子系统融合

对每条情报文章自动分析：
  1. 利好哪些行业 / 利空哪些行业
  2. 影响程度 (high/medium/low)
  3. 传导路径 (上游→中游→下游)
  4. 生成行业影响聚合概览

原始来源：ai_mark/services/impact_analyzer.py
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from src.data.shenwan_chain_ledger import find_affected_chains, format_chain_context_for_prompt

# ============================================================
# 产业链关键词映射表（核心产业链 × 多级关键词）
# ============================================================

INDUSTRY_KEYWORD_MAP: Dict[str, Dict[str, Any]] = {
    "新能源汽车": {
        "keywords": ["新能源车", "电动车", "EV", "电动汽车", "充电桩", "换电", "动力电池",
                     "锂电池", "锂电", "宁德时代", "比亚迪", "蔚来", "小鹏", "理想汽车",
                     "正极材料", "负极材料", "电解液", "隔膜", "锂矿", "钴", "镍"],
        "l2_chains": ["动力电池", "整车制造", "充电桩", "锂矿", "电解液", "隔膜"],
        "sentiment": {
            "positive": ["渗透率", "补贴", "免税", "规划", "放量", "突破", "量产", "里程碑"],
            "negative": ["关税", "反补贴", "加征", "限制", "退坡", "涨价", "短缺", "事故"],
        },
    },
    "半导体": {
        "keywords": ["芯片", "半导体", "集成电路", "IC", "晶圆", "光刻", "刻蚀", "封测",
                     "大基金", "中芯国际", "台积电", "海光", "寒武纪", "华为", "EDA",
                     "硅片", "光刻胶", "氮化镓", "碳化硅", "RISC-V", "ARM"],
        "l2_chains": ["芯片设计", "晶圆代工", "封测", "半导体设备", "光刻胶", "硅片"],
        "sentiment": {
            "positive": ["突破", "大基金", "国产替代", "自给率", "量产", "扩产", "绿色通道"],
            "negative": ["出口管制", "实体清单", "断供", "限制", "暂停", "禁令", "脱钩"],
        },
    },
    "光伏产业": {
        "keywords": ["光伏", "太阳能", "硅料", "硅片", "电池片", "组件", "逆变器",
                     "隆基", "通威", "晶澳", "天合", "BC电池", "TOPCon", "HJT"],
        "l2_chains": ["硅料", "光伏玻璃", "电池片", "逆变器", "电站", "储能"],
        "sentiment": {
            "positive": ["效率突破", "降本", "放量", "并网", "装机", "补贴", "规划"],
            "negative": ["关税", "反倾销", "过剩", "价格战", "限电", "弃光"],
        },
    },
    "AI算力": {
        "keywords": ["AI", "人工智能", "大模型", "GPU", "算力", "数据中心", "服务器",
                     "光模块", "CPO", "液冷", "英伟达", "寒武纪", "海光",
                     "训练", "推理", "ChatGPT", "Copilot"],
        "l2_chains": ["光模块/CPO", "AI服务器", "AI芯片", "液冷散热"],
        "sentiment": {
            "positive": ["突破", "发布", "合作", "订单", "放量", "落地", "规划"],
            "negative": ["监管", "限制", "备案", "安全评估", "能耗", "涨价"],
        },
    },
    "医药生物": {
        "keywords": ["医药", "创新药", "生物药", "疫苗", "医疗器械", "CXO", "原料药",
                     "恒瑞", "药明", "迈瑞", "医保", "集采", "FDA", "临床"],
        "l2_chains": ["原料药", "化学制药", "生物制药", "医药流通", "医疗器械"],
        "sentiment": {
            "positive": ["获批", "上市", "突破", "临床成功", "纳入医保", "出海", "授权"],
            "negative": ["集采", "降价", "医保控费", "临床失败", "召回", "处罚"],
        },
    },
    "人形机器人": {
        "keywords": ["机器人", "人形机器人", "具身智能", "减速器", "伺服电机", "传感器",
                     "特斯拉Bot", "优必选", "汇川", "绿的谐波", "灵巧手"],
        "l2_chains": ["减速器", "伺服电机", "控制器", "传感器", "整机"],
        "sentiment": {
            "positive": ["发布", "量产", "突破", "融资", "合作", "订单", "规划"],
            "negative": ["延迟", "召回", "事故", "限制", "禁令"],
        },
    },
}


# ============================================================
# 影响分析引擎
# ============================================================

def analyze_article_impact(article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    分析单篇文章的产业链影响。

    Args:
        article: 标准化文章字典（含 title/content）

    Returns:
        影响分析结果，或 None（无匹配产业链时）
    """
    title = article.get("title", "")
    content = article.get("content", "")
    text = f"{title} {content}"

    impacts = []
    for industry, imap in INDUSTRY_KEYWORD_MAP.items():
        # 关键词匹配
        kw_matches = [kw for kw in imap["keywords"] if kw in text]
        if not kw_matches:
            continue

        # 情感判断
        pos = sum(1 for kw in imap["sentiment"]["positive"] if kw in text)
        neg = sum(1 for kw in imap["sentiment"]["negative"] if kw in text)

        if pos > neg:
            direction = "positive"
            impact_score = min(pos * 0.15, 1.0)
        elif neg > pos:
            direction = "negative"
            impact_score = min(neg * 0.15, 1.0)
        else:
            direction = "neutral"
            impact_score = 0.1

        # 影响程度
        if impact_score >= 0.6:
            level = "high"
        elif impact_score >= 0.3:
            level = "medium"
        else:
            level = "low"

        impacts.append({
            "industry": industry,
            "direction": direction,
            "level": level,
            "score": round(impact_score, 2),
            "matched_keywords": kw_matches[:5],
            "affected_l2_chains": imap["l2_chains"],
        })

    if not impacts:
        return None

    # 寻找申万产业链中的关联
    all_kw = title.split() + content[:200].split()
    shenwan_chains = find_affected_chains(all_kw, top_n=5)

    return {
        "article_title": title,
        "impacts": impacts,
        "shenwan_chains": shenwan_chains,
        "dominant_direction": _dominant_direction(impacts),
        "affected_industries": [i["industry"] for i in impacts],
    }


def aggregate_impacts(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    聚合多篇文章的产业链影响。

    Args:
        articles: 标准化文章列表

    Returns:
        聚合影响概览
    """
    industry_scores: Dict[str, Dict] = defaultdict(lambda: {
        "positive": 0, "negative": 0, "neutral": 0,
        "article_count": 0, "total_score": 0.0,
        "details": [],
    })

    for article in articles:
        impact = analyze_article_impact(article)
        if not impact:
            continue

        for imp in impact["impacts"]:
            ind = imp["industry"]
            industry_scores[ind][imp["direction"]] += 1
            industry_scores[ind]["article_count"] += 1
            industry_scores[ind]["total_score"] += imp["score"]
            industry_scores[ind]["details"].append({
                "title": impact["article_title"][:100],
                "direction": imp["direction"],
                "level": imp["level"],
            })

    # 计算各行业净影响
    summary = []
    for ind, scores in industry_scores.items():
        net = scores["positive"] - scores["negative"]
        if net > 2:
            net_label = "利好"
            net_direction = "positive"
        elif net < -2:
            net_label = "利空"
            net_direction = "negative"
        else:
            net_label = "中性"
            net_direction = "neutral"

        summary.append({
            "industry": ind,
            "net_label": net_label,
            "net_direction": net_direction,
            "net_score": net,
            "article_count": scores["article_count"],
            "avg_impact_score": round(scores["total_score"] / max(scores["article_count"], 1), 2),
        })

    summary.sort(key=lambda x: abs(x["net_score"]), reverse=True)

    return {
        "industries_affected": len(summary),
        "summary": summary,
    }


def format_impact_for_prompt(articles: List[Dict[str, Any]],
                             max_industries: int = 5) -> str:
    """
    将产业链影响分析格式化为 LLM prompt 上下文。

    Args:
        articles: 标准化文章列表
        max_industries: 最多展示行业数

    Returns:
        prompt 片段
    """
    aggregated = aggregate_impacts(articles)
    if not aggregated["summary"]:
        return ""

    lines = ["## 新闻→产业链影响分析", ""]
    lines.append("| 行业 | 净影响 | 文章数 | 平均影响分 |")
    lines.append("|------|--------|--------|-----------|")

    for s in aggregated["summary"][:max_industries]:
        emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(s["net_direction"], "⚪")
        lines.append(
            f"| {s['industry']} | {emoji} {s['net_label']} ({s['net_score']:+d}) "
            f"| {s['article_count']} | {s['avg_impact_score']:.2f} |"
        )

    lines.append("")
    lines.append(f"> 分析覆盖 {aggregated['industries_affected']} 个行业")

    # 附申万产业链上下文
    top_impacts = aggregated["summary"][:3]
    for s in top_impacts:
        imap = INDUSTRY_KEYWORD_MAP.get(s["industry"], {})
        if imap:
            lines.append(f"\n### {s['industry']}")
            lines.append(f"- 涉及子链: {', '.join(imap.get('l2_chains', [])[:5])}")
            kw_sample = imap.get("keywords", [])[:8]
            lines.append(f"- 关注标的: {', '.join(kw_sample)}")

    return "\n".join(lines)


def _dominant_direction(impacts: List[Dict]) -> str:
    """判断主要影响方向"""
    pos_count = sum(1 for i in impacts if i["direction"] == "positive")
    neg_count = sum(1 for i in impacts if i["direction"] == "negative")
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"

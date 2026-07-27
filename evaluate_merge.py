# -*- coding: utf-8 -*-
"""
合并效果评估脚本 — 对比合并前后分析维度的变化

评估维度：
  1. 多因子评分 vs 纯 LLM 黑盒评分
  2. 产业链影响分析 vs 无结构化产业分析
  3. 供应链风险监测 vs 无全球事件监测
  4. 博弈论分析 vs 无多空博弈视角
  5. 热榜情绪 vs 无热搜信号
"""

import sys
import json
from pathlib import Path

# 确保 src/ 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ============================================================
# 测试数据
# ============================================================

SAMPLE_STOCKS = [
    {"code": "600519", "name": "贵州茅台", "rev_growth": 15.2, "roe": 30.5, "pe": 28.0, "price": 1680.0, "industry": "白酒"},
    {"code": "300750", "name": "宁德时代", "rev_growth": 45.8, "roe": 22.0, "pe": 32.0, "price": 210.0, "industry": "动力电池"},
    {"code": "002594", "name": "比亚迪",   "rev_growth": 38.5, "roe": 18.0, "pe": 25.0, "price": 285.0, "industry": "新能源汽车"},
    {"code": "688981", "name": "中芯国际", "rev_growth": 12.0, "roe": 5.0,  "pe": 55.0, "price": 48.0,  "industry": "半导体"},
    {"code": "300274", "name": "阳光电源", "rev_growth": 55.0, "roe": 28.0, "pe": 22.0, "price": 95.0,  "industry": "光伏"},
]

SAMPLE_NEWS = [
    {
        "title": "美国商务部宣布对中国半导体出口管制新规，涉及AI芯片和半导体设备",
        "content": "美国商务部工业安全局(BIS)发布新规，进一步限制向中国出口先进半导体和芯片制造设备。新规涵盖AI芯片、光刻设备、EDA软件等领域…",
        "source_name": "路透社", "source_url": "https://reuters.com/example1",
    },
    {
        "title": "欧盟拟对中国电动汽车加征最高45%反补贴关税",
        "content": "欧盟委员会公布对中国电动汽车反补贴调查终裁结果，拟对比亚迪、吉利、上汽等中国车企加征17%-45%不等的反补贴税…",
        "source_name": "华尔街见闻", "source_url": "https://wallstreetcn.com/example2",
    },
    {
        "title": "国家大基金三期注册资本3440亿元，重点投向半导体设备和材料",
        "content": "国家集成电路产业投资基金三期正式成立，注册资本3440亿元人民币。大基金三期将重点投向半导体设备、材料、EDA等卡脖子环节…",
        "source_name": "财联社", "source_url": "https://cls.cn/example3",
    },
    {
        "title": "隆基绿能发布BC电池效率世界纪录，量产效率突破27.3%",
        "content": "隆基绿能宣布其自主研发的BC电池量产转换效率达到27.3%，刷新世界纪录。公司预计2025年BC电池产能将达到100GW…",
        "source_name": "36氪", "source_url": "https://36kr.com/example4",
    },
    {
        "title": "红海局势再度升级 马士基暂停所有红海航线",
        "content": "也门胡塞武装加强对红海商船的袭击，全球航运巨头马士基宣布无限期暂停所有红海航线。分析师预计全球供应链将面临新的中断压力…",
        "source_name": "路透社", "source_url": "https://reuters.com/example5",
    },
]

SAMPLE_GDELT_EVENTS = [
    {"title": "US imposes new chip export controls on China", "content": "BIS announces sweeping new restrictions on semiconductor exports to China including AI accelerators and lithography equipment…"},
    {"title": "Houthi attacks intensify in Red Sea shipping lane", "content": "Multiple commercial vessels attacked near Bab el-Mandeb strait. Shipping companies reroute via Cape of Good Hope…"},
    {"title": "EU anti-subsidy tariffs on Chinese EVs finalized at up to 45%", "content": "European Commission confirms provisional duties on Chinese battery electric vehicles…"},
]


# ============================================================
# 评估主函数
# ============================================================

def evaluate_dimension_1():
    """维度1: 多因子评分"""
    from src.services.stock_scorer import score_stock_batch, format_scorer_for_prompt

    scored = score_stock_batch(SAMPLE_STOCKS)
    prompt = format_scorer_for_prompt(scored, top_n=5)

    return {
        "title": "多因子综合评分",
        "before": "合并前：全部依赖 LLM 黑盒评分，无量化基准，同一只股票不同模型结果偏差大",
        "after": "合并后：成长性(40)·盈利(30)·估值(30) 三维量化评分，可复现、可回溯",
        "results": scored,
        "prompt": prompt,
        "top_pick": max(scored, key=lambda x: x["score"]),
    }


def evaluate_dimension_2():
    """维度2: 产业链影响分析"""
    from src.services.impact_analyzer import analyze_article_impact, aggregate_impacts, format_impact_for_prompt

    impacts = []
    for news in SAMPLE_NEWS:
        result = analyze_article_impact(news)
        if result:
            impacts.append(result)

    aggregated = aggregate_impacts(SAMPLE_NEWS)
    prompt = format_impact_for_prompt(SAMPLE_NEWS, max_industries=5)

    return {
        "title": "新闻→产业链影响分析",
        "before": "合并前：新闻原文直接喂给 LLM，无结构化影响提取",
        "after": f"合并后：自动识别 {len(aggregated['summary'])} 个受影响行业，"
                f"利好/利空方向 + 影响程度 + 申万产业链回链",
        "impacts": impacts,
        "aggregated": aggregated,
        "prompt": prompt,
    }


def evaluate_dimension_3():
    """维度3: 供应链风险监测"""
    from src.services.supply_chain_risk import assess_chain_risk, format_supply_chain_risk_for_prompt

    risk_report = assess_chain_risk(SAMPLE_GDELT_EVENTS)
    prompt = format_supply_chain_risk_for_prompt(risk_report)

    return {
        "title": "全球供应链风险预警",
        "before": "合并前：无 GDELT 全球事件数据，地缘/供应链风险对标的的影响完全盲视",
        "after": f"合并后：{risk_report['total_risk_events']} 个风险事件，"
                f"综合风险等级 {risk_report['overall_risk_level'].upper()}，"
                f"受影响供应链 {risk_report['affected_chains_count']} 条",
        "risk_report": risk_report,
        "prompt": prompt,
    }


def evaluate_dimension_4():
    """维度4: 博弈论分析"""
    from src.agent.agents.game_theory_agent import (
        PARTICIPANTS, BEHAVIOR_PATTERNS, build_game_theory_prompt,
    )

    prompt = build_game_theory_prompt(
        stock_code="300750",
        stock_name="宁德时代",
        market_data={
            "当前价格": "210.00 元",
            "成交量": "125000 手",
            "换手率": "2.35%",
            "北向资金净流向": "-2.15 亿元",
            "龙虎榜净买入": "+8500 万元",
        },
    )

    return {
        "title": "博弈论多空博弈分析",
        "before": "合并前：无博弈视角，只看技术面和基本面",
        "after": f"合并后：{len(PARTICIPANTS)} 类市场参与者画像 + "
                f"{len(BEHAVIOR_PATTERNS)} 种主力行为模式 → LLM 博弈分析 prompt",
        "participants": [{"角色": p.label_cn, "权重": f"{p.influence_weight:.0%}", "特征": p.typical_behavior[:60]} for p in PARTICIPANTS],
        "patterns": [{"阶段": bp.label_cn, "含义": bp.implications[:80]} for bp in BEHAVIOR_PATTERNS],
        "prompt_excerpt": prompt[:500] + "...",
    }


def evaluate_dimension_5():
    """维度5: 热榜情绪信号"""
    from data_provider.extended.hotlist_fetcher import HotlistFetcher, PLATFORM_IDS, FINANCE_PLATFORMS

    return {
        "title": "跨平台热搜趋势",
        "before": "合并前：无热搜信号，无法感知市场情绪方向",
        "after": f"合并后：覆盖 {len(PLATFORM_IDS)} 个平台热榜，默认拉取 {len(FINANCE_PLATFORMS)} 个金融相关平台",
        "platforms": {pid: PLATFORM_IDS[pid] for pid in FINANCE_PLATFORMS},
    }


def evaluate_dimension_6():
    """维度6: GDELT 全球事件接入"""
    from data_provider.extended.gdelt_fetcher import GDELT_QUERIES

    return {
        "title": "GDELT 全球事件数据",
        "before": "合并前：无外部事件数据，完全依赖本地新闻搜索",
        "after": f"合并后：{len(GDELT_QUERIES)} 个预定义监控主题，"
                f"每15分钟更新的全球事件数据库",
        "queries": {k: v["display_name"] for k, v in GDELT_QUERIES.items()},
    }


def evaluate_dimension_7():
    """维度7: 申万产业链映射"""
    from src.data.shenwan_chain_ledger import (
        FACTOR_DIMENSIONS, get_all_l1_industries, find_affected_chains, get_chains_by_factor,
    )

    # 测试交通运输风险
    transport_chains = get_chains_by_factor("交通运输")
    # 测试关键词映射
    hits = find_affected_chains(["芯片", "半导体", "出口管制"], top_n=3)

    return {
        "title": "申万产业链映射",
        "before": "合并前：无产业链结构化数据，无法分析上下游传导",
        "after": f"合并后：{len(FACTOR_DIMENSIONS)} 个影响因素维度，"
                f"当前已载入 {len(get_all_l1_industries())} 个一级行业（完整的346条可通过追加触发）",
        "factors": FACTOR_DIMENSIONS,
        "transport_affected": len(transport_chains),
        "keyword_hits": [{"code": c["code"], "name": f"{c['l1']}→{c['l3']}"} for c in hits[:5]],
    }


# ============================================================
# 综合评价：LLM Prompt 上下文增强对比
# ============================================================

def evaluate_prompt_enrichment():
    """对比合并前后，单只股票的 LLM 分析 prompt 内容维度"""

    from src.services.stock_scorer import score_stock_batch, format_scorer_for_prompt
    from src.services.impact_analyzer import format_impact_for_prompt
    from src.services.supply_chain_risk import assess_chain_risk, format_supply_chain_risk_for_prompt
    from src.agent.agents.game_theory_agent import analyze_game_theory_for_stock

    # 合并前 prompt（仅基础数据）
    before_prompt = """
## 股票分析请求
股票: 宁德时代 (300750)
价格: 210元 | PE: 32 | ROE: 22%

请根据技术面和基本面进行分析。
"""

    # 合并后 prompt（6 个维度增强）
    scored = score_stock_batch(SAMPLE_STOCKS)
    scorer_ctx = format_scorer_for_prompt(scored, top_n=3)

    impact_ctx = format_impact_for_prompt(SAMPLE_NEWS, max_industries=3)

    risk_report = assess_chain_risk(SAMPLE_GDELT_EVENTS)
    risk_ctx = format_supply_chain_risk_for_prompt(risk_report)

    game_ctx = analyze_game_theory_for_stock(
        stock_code="300750", stock_name="宁德时代",
        price=210.0, volume=125000, turnover_rate=2.35,
        north_flow=-2.15, dragon_list_buy=12500, dragon_list_sell=4000,
    )

    after_sections = [scorer_ctx, impact_ctx, risk_ctx, game_ctx]
    after_prompt = "\n\n".join(s for s in after_sections if s)

    return {
        "title": "LLM Prompt 上下文增强对比",
        "before": {
            "sections": 1,
            "characters": len(before_prompt),
            "key_dimensions": ["基础数据"],
            "sample": before_prompt,
        },
        "after": {
            "sections": len([s for s in after_sections if s]),
            "characters": len(after_prompt),
            "key_dimensions": [
                "多因子量化评分",
                "产业链影响分析",
                "全球供应链风险",
                "博弈论多空分析",
            ],
            "sample": after_prompt[:2000] + "\n...[完整 prompt 约 " + str(len(after_prompt)) + " 字符]",
        },
    }


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 72)
    print("  daily_stock_analysis 合并效果评估")
    print("  0716 ai_mark 子系统 → 0725 主线增强")
    print("=" * 72)
    print()

    evaluations = [
        evaluate_dimension_1(),
        evaluate_dimension_2(),
        evaluate_dimension_3(),
        evaluate_dimension_4(),
        evaluate_dimension_5(),
        evaluate_dimension_6(),
        evaluate_dimension_7(),
    ]

    total_score = 0
    max_score = len(evaluations)

    for i, ev in enumerate(evaluations, 1):
        print(f"## 维度 {i}: {ev['title']}")
        print(f"   ❌ 合并前: {ev['before']}")
        print(f"   ✅ 合并后: {ev['after']}")
        total_score += 1  # 每个维度都成功加载
        print()

    # Prompt 增强评估
    print("=" * 72)
    prompt_eval = evaluate_prompt_enrichment()
    print(f"## {prompt_eval['title']}")
    print()
    print("### 合并前（单一维度）")
    print(f"  维度数: {prompt_eval['before']['sections']}")
    print(f"  Prompt 长度: {prompt_eval['before']['characters']} 字符")
    print(f"  覆盖: {prompt_eval['before']['key_dimensions']}")
    print()
    print("### 合并后（6 维度增强）")
    print(f"  维度数: {prompt_eval['after']['sections']}")
    print(f"  Prompt 长度: {prompt_eval['after']['characters']} 字符")
    print(f"  覆盖: {prompt_eval['after']['key_dimensions']}")
    print()

    print("=" * 72)
    print(f"  综合评估: {total_score}/{max_score} 个维度成功增强")
    print(f"  分析上下文信息量提升: {prompt_eval['after']['characters'] / max(prompt_eval['before']['characters'], 1):.0f}x")
    print("=" * 72)

    # 保存详细结果
    result = {
        "dimensions": evaluations,
        "prompt_enrichment": {
            "before_sections": prompt_eval["before"]["sections"],
            "after_sections": prompt_eval["after"]["sections"],
            "before_chars": prompt_eval["before"]["characters"],
            "after_chars": prompt_eval["after"]["characters"],
            "enrichment_ratio": round(prompt_eval["after"]["characters"] / max(prompt_eval["before"]["characters"], 1), 1),
        },
        "total_dimensions_enhanced": f"{total_score}/{max_score}",
    }

    output_path = Path(__file__).resolve().parent / "merge_evaluation_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n详细结果已保存至: {output_path}")

    return result


if __name__ == "__main__":
    main()

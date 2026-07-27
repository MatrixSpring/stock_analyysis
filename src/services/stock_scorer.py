# -*- coding: utf-8 -*-
"""
股票多因子综合评分模型 — 从 ai_mark 子系统融合

评分维度 (0-100):
  - 成长性 (40分): 营收增长率
  - 盈利能力 (30分): ROE
  - 估值合理性 (30分): PE 倒数

评级:
  >70: ⭐ 强烈推荐
  50-70: ✅ 推荐关注
  30-50: 👀 观察
  <30: ⚠️ 谨慎

原始来源：ai_mark/services/stock_scorer.py
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================
# 评分配置
# ============================================================

@dataclass
class ScorerConfig:
    """多因子评分配置"""
    growth_weight: float = 40.0       # 成长性权重
    profit_weight: float = 30.0       # 盈利能力权重
    valuation_weight: float = 30.0    # 估值合理性权重
    technical_weight: float = 0.0     # 技术面加分（默认关闭，由 LLM Agent 负责）
    sentiment_weight: float = 0.0     # 情绪面加分（默认关闭）
    min_rev_growth: float = -50.0     # 营收增长率下限 (%)
    max_rev_growth: float = 200.0     # 营收增长率上限 (%)
    max_pe_for_scoring: float = 60.0  # PE 评分区间上限
    benchmark_roe: float = 30.0       # ROE 基准值 (%)


DEFAULT_SCORER_CONFIG = ScorerConfig()


# ============================================================
# 评分引擎
# ============================================================

def calculate_score(
    rev_growth: float = 0.0,
    roe: float = 0.0,
    pe: float = 0.0,
    config: Optional[ScorerConfig] = None,
    extra_weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    综合评分 (0-100)。

    Args:
        rev_growth: 营收增长率 (%)
        roe: ROE (%)
        pe: PE 市盈率
        config: 评分配置
        extra_weights: 自定义权重 {"growth": 40, "profit": 30, "valuation": 30}

    Returns:
        综合评分 (0-100)
    """
    cfg = config or DEFAULT_SCORER_CONFIG
    w = extra_weights or {
        "growth": cfg.growth_weight,
        "profit": cfg.profit_weight,
        "valuation": cfg.valuation_weight,
    }

    # 成长性得分：增长率映射到 [0, w[growth]]
    growth_clipped = max(cfg.min_rev_growth, min(rev_growth, cfg.max_rev_growth))
    growth_score = max(0, growth_clipped / 100 * w["growth"])

    # 盈利能力得分：ROE 相对基准
    profit_score = min((roe / cfg.benchmark_roe) * w["profit"], w["profit"]) if roe > 0 else 0

    # 估值得分：PE 越低越好
    if 0 < pe < cfg.max_pe_for_scoring:
        valuation_score = max(0, (cfg.max_pe_for_scoring - pe) / cfg.max_pe_for_scoring * w["valuation"])
    else:
        valuation_score = 0

    return round(growth_score + profit_score + valuation_score, 1)


def get_rating(score: float) -> Dict[str, str]:
    """评分→评级"""
    if score > 70:
        return {"level": "strong_buy", "label": "强烈推荐", "emoji": "⭐", "color": "#10B981"}
    elif score >= 50:
        return {"level": "buy", "label": "推荐关注", "emoji": "✅", "color": "#3B82F6"}
    elif score >= 30:
        return {"level": "hold", "label": "观察", "emoji": "👀", "color": "#F59E0B"}
    else:
        return {"level": "caution", "label": "谨慎", "emoji": "⚠️", "color": "#EF4444"}


def classify_strategy(score: float, rev_growth: float, roe: float, pe: float) -> str:
    """
    根据评分和基本面特征自动推荐策略类型。

    Returns:
        策略标签: short_term / mid_term / value / dividend / watch
    """
    if rev_growth > 50 and pe < 35 and score > 35:
        return "short_term"
    elif 20 <= rev_growth <= 50 and roe > 15 and score > 30:
        return "mid_term"
    elif pe < 15 and roe > 12 and score > 25:
        return "value"
    elif roe > 15 and pe < 25:
        return "dividend"
    return "watch"


STRATEGY_LABELS: Dict[str, str] = {
    "short_term": "短线成长",
    "mid_term": "中线稳健",
    "value": "价值低估",
    "dividend": "红利防御",
    "watch": "观望",
}


def score_stock_batch(stocks: List[Dict[str, Any]],
                      config: Optional[ScorerConfig] = None) -> List[Dict[str, Any]]:
    """
    批量评分。

    Args:
        stocks: 股票列表，每条含 {"name", "code", "rev_growth", "roe", "pe"}
        config: 评分配置

    Returns:
        评分后的股票列表（按评分降序）
    """
    results = []
    for s in stocks:
        score = calculate_score(
            rev_growth=float(s.get("rev_growth", 0) or 0),
            roe=float(s.get("roe", 0) or 0),
            pe=float(s.get("pe", 0) or 0),
            config=config,
        )
        rating = get_rating(score)
        strategy = classify_strategy(
            score,
            float(s.get("rev_growth", 0) or 0),
            float(s.get("roe", 0) or 0),
            float(s.get("pe", 0) or 0),
        )
        results.append({
            **s,
            "score": score,
            "rating_level": rating["level"],
            "rating_label": f"{rating['emoji']} {rating['label']}",
            "rating_color": rating["color"],
            "strategy_type": strategy,
            "strategy_label": STRATEGY_LABELS.get(strategy, strategy),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def format_scorer_for_prompt(scored_stocks: List[Dict[str, Any]],
                             top_n: int = 10) -> str:
    """
    将多因子评分结果格式化为 LLM prompt 上下文。

    Args:
        scored_stocks: score_stock_batch() 的返回结果
        top_n: 展示前 N 只

    Returns:
        prompt 片段
    """
    if not scored_stocks:
        return ""

    lines = [
        "## 多因子综合评分（成长性·盈利能力·估值合理性）",
        "",
        "| # | 股票 | 评分 | 评级 | 策略建议 | 营收增长 | ROE | PE |",
        "|---|------|------|------|---------|----------|-----|----|",
    ]

    for i, s in enumerate(scored_stocks[:top_n], 1):
        name = s.get("name", s.get("code", "N/A"))
        lines.append(
            f"| {i} | {name} | **{s['score']:.1f}** | {s['rating_label']} "
            f"| {s['strategy_label']} "
            f"| {s.get('rev_growth', 'N/A')}% "
            f"| {s.get('roe', 'N/A')}% "
            f"| {s.get('pe', 'N/A')} |"
        )

    lines.append("")
    lines.append("> 评分维度: 成长性(40分) + 盈利能力(30分) + 估值合理性(30分)")
    lines.append("> 以上评分仅作研究参考，不构成任何投资建议。")

    return "\n".join(lines)


def generate_trading_prompt(scored_stocks: List[Dict[str, Any]]) -> str:
    """生成 TradingAgents 风格的完整分析 prompt"""
    stock_list = "\n".join([
        f"{i+1}. {s.get('name', s.get('code', 'N/A'))}: "
        f"价格={s.get('price','N/A')}元, "
        f"PE={s.get('pe','N/A')}, ROE={s.get('roe','N/A')}%, "
        f"增长={s.get('rev_growth','N/A')}%, "
        f"行业={s.get('industry','')}, "
        f"评分={s.get('score','N/A')}分 ({s.get('rating_label','')})"
        for i, s in enumerate(scored_stocks)
    ])

    return f"""## 候选股票池（来自 daily_stock_analysis 多因子评分筛选）

{stock_list}

## 评分维度
- 成长性(40分): 营收增长率越高越好
- 盈利能力(30分): ROE越高越好
- 估值合理性(30分): PE越低越好(0-60区间)

请从以下角度分析:
1. 哪些标的具有最佳风险收益比？
2. 行业配置是否合理？
3. 需要规避哪些风险点？

以上分析仅作研究参考，不构成任何投资建议。"""

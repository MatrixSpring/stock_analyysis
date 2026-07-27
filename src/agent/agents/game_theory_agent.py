# -*- coding: utf-8 -*-
"""
博弈论多空博弈分析 Agent — 从 ai_mark 子系统融合并 LLM 化

将 ai_mark/services/game_engine.py 的规则模拟重构为 LLM Agent：
  - 分析多空力量对比（散户/游资/机构/北向资金/产业资本）
  - 识别主力资金行为模式（吸筹/洗盘/拉升/出货）
  - 输出博弈态势评估，注入 DecisionAgent 的决策 prompt

原始来源：ai_mark/services/game_engine.py (规则模拟)
重构方向：LLM Agent（利用 0725 的 LLM 路由 + Agent 框架）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 市场参与者类型定义
# ============================================================

@dataclass
class MarketParticipant:
    """市场参与者画像"""
    role: str                          # retail / hot_money / fund / north_money / corp
    label_cn: str                      # 中文标签
    typical_behavior: str              # 典型行为特征
    signal_indicators: List[str]       # 可通过数据观察的信号指标
    influence_weight: float            # 对股价的影响力权重


PARTICIPANTS: List[MarketParticipant] = [
    MarketParticipant(
        role="retail",
        label_cn="散户",
        typical_behavior="追涨杀跌，情绪驱动，羊群效应明显。"
                         "成交量放大时往往在顶部追入，缩量下跌时恐慌卖出。",
        signal_indicators=["成交量放大", "融资金额变化", "新增开户数", "百度搜索指数"],
        influence_weight=0.10,
    ),
    MarketParticipant(
        role="hot_money",
        label_cn="游资/热钱",
        typical_behavior="短线快进快出，追逐题材热点，制造高位换手。"
                         "龙虎榜席位频繁出现，涨停板封单快速变化。",
        signal_indicators=["龙虎榜净买入", "涨停板封单", "换手率异常", "题材热度"],
        influence_weight=0.20,
    ),
    MarketParticipant(
        role="fund",
        label_cn="公募/机构",
        typical_behavior="基本面驱动，长期持有，左侧布局。"
                         "季报持仓变化缓慢，偏好大盘蓝筹和成长白马。",
        signal_indicators=["机构持仓变化", "大宗交易", "基金季报", "北向资金"],
        influence_weight=0.35,
    ),
    MarketParticipant(
        role="north_money",
        label_cn="北向资金",
        typical_behavior="外资风格，偏好消费/金融/新能源龙头。"
                         "持续净流入/流出反映外资对 A 股的系统性看法。",
        signal_indicators=["北向资金净流向", "汇率变动", "AH 溢价", "MSCI 调整"],
        influence_weight=0.25,
    ),
    MarketParticipant(
        role="corp_capital",
        label_cn="产业资本",
        typical_behavior="增减持、回购、股权激励。"
                         "大股东增持是强信心信号，减持则需警惕。",
        signal_indicators=["大股东增减持", "公司回购", "股权激励计划", "解禁预告"],
        influence_weight=0.10,
    ),
]


# ============================================================
# 资金行为模式
# ============================================================

@dataclass
class BehaviorPattern:
    """主力资金行为模式"""
    pattern: str                       # accumulation / washout / markup / distribution
    label_cn: str
    description: str
    typical_signals: List[str]
    implications: str                  # 对投资者的含义


BEHAVIOR_PATTERNS: List[BehaviorPattern] = [
    BehaviorPattern(
        pattern="accumulation",
        label_cn="吸筹阶段",
        description="主力在低位区域缓慢建仓，成交量温和放大但不张扬，"
                    "股价在窄幅区间震荡。散户因长期横盘失去耐心而割肉。",
        typical_signals=["缩量横盘后放量拉升", "低位筹码集中度提升",
                        "大宗交易折价率收窄", "大股东增持"],
        implications="逢低布局窗口，可跟随主力分批建仓。"
                     "注意：主力吸筹可能持续数周到数月，需要耐心。",
    ),
    BehaviorPattern(
        pattern="washout",
        label_cn="洗盘阶段",
        description="主力通过快速打压制造恐慌，清洗浮动筹码。"
                    "特征是急跌后快速收回，成交量放大但价格未有效跌破支撑。",
        typical_signals=["盘中急跌后收回", "支撑位不破", "散户融资余额下降",
                        "龙虎榜出现买一卖一均为机构"],
        implications="不要被洗出局。如果基本面和技术面支撑未变，"
                     "洗盘是加仓机会而非止损信号。",
    ),
    BehaviorPattern(
        pattern="markup",
        label_cn="拉升阶段",
        description="主力开始主动推升股价，成交量持续放大，"
                    "突破关键阻力位。市场关注度上升，散户开始跟风。",
        typical_signals=["放量突破前高", "均线多头排列", "龙虎榜净买入",
                        "媒体/大V 开始推荐"],
        implications="顺势持有，但需要设定移动止盈。"
                     "拉升末期往往伴随巨量换手，注意高位放量滞涨信号。",
    ),
    BehaviorPattern(
        pattern="distribution",
        label_cn="出货阶段",
        description="主力在高位区域逐步减仓，利用散户追涨心理完成筹码转移。"
                    "特征：高位放量滞涨、利好不涨、龙虎榜净卖出。",
        typical_signals=["高位放量阴线", "利好不涨反跌", "筹码集中度下降",
                        "大股东减持公告", "北向资金转为净流出"],
        implications="危险信号！应考虑减仓或清仓。不要在高位接盘。",
    ),
]


# ============================================================
# 博弈态势分析 Prompt 构建
# ============================================================

def build_game_theory_prompt(
    stock_code: str,
    stock_name: str,
    market_data: Dict[str, Any],
) -> str:
    """
    构建博弈论分析 prompt（用于注入 LLM Agent）。

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        market_data: 市场数据（价格/成交量/北向/龙虎榜/筹码分布等）

    Returns:
        博弈分析 prompt 片段
    """
    # 构建参与者画像
    participants_desc = "\n".join([
        f"- **{p.label_cn}**（权重 {p.influence_weight:.0%}）：{p.typical_behavior}"
        for p in PARTICIPANTS
    ])

    # 构建行为模式参考
    patterns_desc = "\n".join([
        f"- **{bp.label_cn}**：{bp.description[:120]}..."
        for bp in BEHAVIOR_PATTERNS
    ])

    # 市场数据摘要
    data_lines = []
    for key, val in market_data.items():
        if val is not None:
            data_lines.append(f"- {key}: {val}")
    data_section = "\n".join(data_lines) if data_lines else "- 暂无实时数据"

    return f"""## 博弈论多空博弈分析

### 分析标的
- 代码: {stock_code}
- 名称: {stock_name}

### 当前市场数据
{data_section}

### 市场参与者画像
{participants_desc}

### 主力资金行为模式
{patterns_desc}

### 分析要求
请基于以上数据和参与者画像，从博弈论角度分析：

1. **多空力量对比**：当前哪类参与者主导定价权？多空力量比如何？
2. **主力行为判断**：当前处于吸筹/洗盘/拉升/出货哪个阶段？依据是什么？
3. **散户情绪定位**：散户目前处于恐慌/犹豫/乐观/狂热哪个阶段？是否反向指标？
4. **博弈策略建议**：
   - 如果你是散户，当前应该如何应对主力的行为？
   - 如果你是主力，你的对手盘（其他主力 + 散户）会如何反应？
5. **关键博弈节点**：未来 1-2 周内可能触发博弈格局变化的关键价位/事件是什么？

⚠️ 以上分析仅作研究参考，不构成任何投资建议。"""


def build_game_theory_summary(
    stock_code: str,
    llm_analysis: str,
) -> Dict[str, Any]:
    """
    从 LLM 分析结果中提取结构化博弈摘要。

    Args:
        stock_code: 股票代码
        llm_analysis: LLM 返回的博弈分析文本

    Returns:
        结构化博弈摘要
    """
    return {
        "stock_code": stock_code,
        "analysis_timestamp": None,  # 由调用方填充
        "raw_analysis": llm_analysis,
        "detected_pattern": _detect_pattern_from_text(llm_analysis),
        "risk_level": _detect_risk_from_text(llm_analysis),
    }


def _detect_pattern_from_text(text: str) -> Optional[str]:
    """从 LLM 分析文本中检测资金行为模式"""
    for bp in BEHAVIOR_PATTERNS:
        if bp.label_cn in text or bp.pattern in text.lower():
            return bp.pattern
    return None


def _detect_risk_from_text(text: str) -> str:
    """从 LLM 分析文本中检测博弈风险等级"""
    high_risk_keywords = ["出货", "高位", "见顶", "恐慌", "踩踏", "崩盘"]
    medium_risk_keywords = ["洗盘", "分歧", "震荡", "不确定", "博弈激烈"]
    low_risk_keywords = ["吸筹", "拉升", "一致看多", "筹码集中"]

    text_lower = text.lower()
    high_count = sum(1 for kw in high_risk_keywords if kw in text)
    medium_count = sum(1 for kw in medium_risk_keywords if kw in text)
    low_count = sum(1 for kw in low_risk_keywords if kw in text)

    if high_count > medium_count and high_count > low_count:
        return "high"
    elif medium_count > low_count:
        return "medium"
    return "low"


# ============================================================
# 便捷函数：一键生成博弈分析 prompt
# ============================================================

def analyze_game_theory_for_stock(
    stock_code: str,
    stock_name: str,
    price: float,
    volume: float,
    turnover_rate: Optional[float] = None,
    north_flow: Optional[float] = None,
    margin_balance: Optional[float] = None,
    dragon_list_buy: Optional[float] = None,
    dragon_list_sell: Optional[float] = None,
    insider_trade: Optional[str] = None,
    chip_concentration: Optional[float] = None,
) -> str:
    """
    一键构建单只股票的博弈分析 prompt。

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        price: 当前价格
        volume: 成交量（手）
        turnover_rate: 换手率 (%)
        north_flow: 北向资金净流向（亿元）
        margin_balance: 融资余额变化
        dragon_list_buy: 龙虎榜买入（万元）
        dragon_list_sell: 龙虎榜卖出（万元）
        insider_trade: 大股东增减持情况
        chip_concentration: 筹码集中度

    Returns:
        博弈分析 prompt
    """
    market_data = {
        "当前价格": f"{price:.2f} 元" if price else None,
        "成交量": f"{volume:.0f} 手" if volume else None,
        "换手率": f"{turnover_rate:.2f}%" if turnover_rate else None,
        "北向资金净流向": f"{north_flow:+.2f} 亿元" if north_flow else None,
        "融资余额变化": f"{margin_balance:+.2f} 亿元" if margin_balance else None,
        "龙虎榜净买入": f"{dragon_list_buy - dragon_list_sell:+.0f} 万元"
        if dragon_list_buy and dragon_list_sell else None,
        "大股东动向": insider_trade,
        "筹码集中度": f"{chip_concentration:.1f}%" if chip_concentration else None,
    }
    market_data = {k: v for k, v in market_data.items() if v is not None}

    return build_game_theory_prompt(stock_code, stock_name, market_data)

# -*- coding: utf-8 -*-
"""
舆情三大因子量化策略 — 固化阈值 & 组合交易规则

三大因子（值域标准化）：
  1. sentiment_score [-1, 1]  情绪得分 → 涨跌倾向
  2. heat_momentum   [0, 1]   热度动量 → 题材强度
  3. divergence_index [0, 1]  分歧度    → 反转信号

五个组合交易信号：
  BUY        短线做多入场
  ADD        趋势加速加仓
  SELL       高位止盈离场
  STOP       风控止损/空仓
  REVERSAL   低位反转埋伏
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================
# 阈值常量
# ============================================================

class SentimentLevel(str, Enum):
    EXTREME_BULLISH = "extreme_bullish"    # >= 0.6
    BULLISH = "bullish"                    # [0.2, 0.6)
    NEUTRAL = "neutral"                    # (-0.2, 0.2)
    BEARISH = "bearish"                    # (-0.6, -0.2]
    EXTREME_BEARISH = "extreme_bearish"    # <= -0.6


class MomentumLevel(str, Enum):
    TOP_HOT = "top_hot"         # >= 0.8  顶级热点
    ACTIVE = "active"           # [0.4, 0.8) 有效活跃
    LOW = "low"                 # [0.1, 0.4) 低度冷门
    DEAD = "dead"               # < 0.1   极致冷门


class DivergenceLevel(str, Enum):
    CONSENSUS = "consensus"      # <= 0.3  高度一致
    NORMAL = "normal"            # (0.3, 0.7) 正常博弈
    EXTREME = "extreme"          # >= 0.7  极高分歧（反转拐点）


class TradeSignal(str, Enum):
    BUY = "buy"                  # 短线做多入场
    ADD = "add"                  # 趋势加速加仓
    SELL = "sell"                # 高位止盈离场
    STOP = "stop"                # 风控止损/空仓
    REVERSAL = "reversal"       # 低位反转埋伏
    HOLD = "hold"               # 持仓观望


# ============================================================
# 因子数据
# ============================================================

@dataclass
class SentimentFactors:
    """舆情三因子快照"""
    code: str
    sentiment_score: float      # [-1, 1]
    heat_momentum: float        # [0, 1]
    divergence_index: float     # [0, 1]
    window_type: str = "24h"
    post_count: int = 0
    hot_keywords: List[str] = field(default_factory=list)
    is_spike: bool = False
    spike_detail: str = ""

    @property
    def sentiment_level(self) -> SentimentLevel:
        s = self.sentiment_score
        if s >= 0.6: return SentimentLevel.EXTREME_BULLISH
        if s >= 0.2: return SentimentLevel.BULLISH
        if s > -0.2: return SentimentLevel.NEUTRAL
        if s > -0.6: return SentimentLevel.BEARISH
        return SentimentLevel.EXTREME_BEARISH

    @property
    def momentum_level(self) -> MomentumLevel:
        m = self.heat_momentum
        if m >= 0.8: return MomentumLevel.TOP_HOT
        if m >= 0.4: return MomentumLevel.ACTIVE
        if m >= 0.1: return MomentumLevel.LOW
        return MomentumLevel.DEAD

    @property
    def divergence_level(self) -> DivergenceLevel:
        d = self.divergence_index
        if d <= 0.3: return DivergenceLevel.CONSENSUS
        if d < 0.7: return DivergenceLevel.NORMAL
        return DivergenceLevel.EXTREME


@dataclass
class TradeSignalResult:
    """交易信号输出"""
    signal: TradeSignal
    label: str                     # 中文标签
    direction: str                 # long / short / flat
    urgency: str                   # high / medium / low
    reason: str
    factors: SentimentFactors
    timestamp: str = ""


# ============================================================
# 策略引擎
# ============================================================

class SentimentStrategyEngine:
    """舆情三因子量化策略引擎 — 纯规则、无主观、可直接回测"""

    @staticmethod
    def evaluate(factors: SentimentFactors) -> TradeSignalResult:
        """
        按优先级依次匹配交易规则，返回第一个命中的信号。
        规则优先级：STOP > SELL > REVERSAL > ADD > BUY > HOLD
        """
        s = factors.sentiment_score
        m = factors.heat_momentum
        d = factors.divergence_index

        # ----- Rule 5: 低位反转（优先于 STOP，极端分歧下的超跌反弹信号）-----
        if s <= -0.6 and d >= 0.7:
            return TradeSignalResult(
                signal=TradeSignal.REVERSAL,
                label="低位反转埋伏",
                direction="long",
                urgency="medium",
                reason=f"极致利空(s={s:.2f})+分歧加大(d={d:.2f})=利空出尽反转窗口",
                factors=factors,
            )

        # ----- Rule 4: 风控止损/空仓 -----
        if s <= -0.2 or m < 0.4:
            return TradeSignalResult(
                signal=TradeSignal.STOP,
                label="风控止损/空仓",
                direction="flat",
                urgency="high",
                reason=f"情绪转弱(s={s:.2f})或热度不足(m={m:.2f})",
                factors=factors,
            )

        # ----- Rule 3: 高位止盈 -----
        if s >= 0.6 and m >= 0.8 and d >= 0.7:
            return TradeSignalResult(
                signal=TradeSignal.SELL,
                label="高位止盈离场",
                direction="short",
                urgency="high",
                reason=f"情绪极致(s={s:.2f})+热度顶级(m={m:.2f})+分歧剧烈(d={d:.2f})=见顶信号",
                factors=factors,
            )

        # ----- Rule 2: 趋势加速加仓 -----
        if s >= 0.6 and m >= 0.8 and d <= 0.3:
            return TradeSignalResult(
                signal=TradeSignal.ADD,
                label="趋势加速加仓",
                direction="long",
                urgency="high",
                reason=f"情绪极致(s={s:.2f})+顶级热度(m={m:.2f})+高度一致(d={d:.2f})=主升浪",
                factors=factors,
            )

        # ----- Rule 1: 短线做多 -----
        if s >= 0.2 and m >= 0.4 and d < 0.7:
            return TradeSignalResult(
                signal=TradeSignal.BUY,
                label="短线做多入场",
                direction="long",
                urgency="medium",
                reason=f"正向情绪(s={s:.2f})+活跃热度(m={m:.2f})+无极端分歧(d={d:.2f})",
                factors=factors,
            )

        # ----- Default: 持仓观望 -----
        return TradeSignalResult(
            signal=TradeSignal.HOLD,
            label="持仓观望",
            direction="flat",
            urgency="low",
            reason=f"信号未触发(s={s:.2f}, m={m:.2f}, d={d:.2f})",
            factors=factors,
        )

    @staticmethod
    def compute_heat_momentum(post_count: int, total_interact: int,
                              max_expected_posts: int = 200) -> float:
        """从原始指标计算热度动量（0~1 标准化）"""
        if post_count == 0:
            return 0.0
        post_score = min(post_count / max_expected_posts, 1.0) * 0.6
        interact_score = min(total_interact / (max_expected_posts * 10), 1.0) * 0.4
        return round(post_score + interact_score, 3)

    @staticmethod
    def factors_from_agg_window(agg: Any) -> SentimentFactors:
        """从 SentimentAggWindow 提取三因子"""
        momentum = SentimentStrategyEngine.compute_heat_momentum(
            getattr(agg, "post_count", 0),
            getattr(agg, "total_interact", 0),
        )
        return SentimentFactors(
            code=getattr(agg, "code", ""),
            sentiment_score=getattr(agg, "avg_sentiment_score", 0.0),
            heat_momentum=momentum,
            divergence_index=getattr(agg, "divergence_index", 0.0),
            window_type=getattr(agg, "window_type", "24h"),
            post_count=getattr(agg, "post_count", 0),
            hot_keywords=getattr(agg, "hot_keywords", []),
            is_spike=getattr(agg, "is_sentiment_spike", False),
            spike_detail=getattr(agg, "spike_detail", ""),
        )

    @staticmethod
    def format_for_agent(result: TradeSignalResult) -> str:
        """生成 Agent prompt 可用的三因子分析文本"""
        f = result.factors
        signal_emoji = {
            TradeSignal.BUY: "🟢", TradeSignal.ADD: "🔥",
            TradeSignal.SELL: "🔴", TradeSignal.STOP: "⛔",
            TradeSignal.REVERSAL: "🔄", TradeSignal.HOLD: "⚪",
        }
        return (
            f"## 舆情三因子交易信号 {signal_emoji.get(result.signal, '')}\n"
            f"- 信号：**{result.label}**（{result.urgency}优先级）\n"
            f"- 情绪得分：{f.sentiment_score:+.2f}（{f.sentiment_level.value}）\n"
            f"- 热度动量：{f.heat_momentum:.2f}（{f.momentum_level.value}）\n"
            f"- 分歧度：{f.divergence_index:.2f}（{f.divergence_level.value}）\n"
            f"- 逻辑：{result.reason}"
        )


# 全局引擎
sentiment_strategy_engine = SentimentStrategyEngine()

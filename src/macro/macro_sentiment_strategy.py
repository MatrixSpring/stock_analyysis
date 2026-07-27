# -*- coding: utf-8 -*-
"""
宏观+舆情联动策略 — P0 核心优化版
新增：动态仓位 + 四重共振过滤 + 反转强度判定 + 地缘风险强制风控

核心理念：
  宏观定仓位 → 舆情定买卖 → 地缘定风险偏好
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.macro.macro_liquidity_monitor import MacroFactorResult, macro_monitor
from src.services.sentiment_strategy import SentimentFactors, sentiment_strategy_engine

logger = logging.getLogger(__name__)


@dataclass
class FinalTradeSignal:
    signal: str              # BUY / ADD / SELL / REVERSAL / HOLD / AVOID
    level: str               # high / medium / low
    confidence: float = 0.5
    position_ratio: float = 0.0
    macro_override: bool = False
    macro_reason: str = ""
    stock_reason: str = ""
    timestamp: str = ""


class MacroSentimentStrategy:
    """宏观+舆情联动策略引擎（P0版）"""

    @staticmethod
    def calc_reversal_strength(factors: SentimentFactors) -> float:
        """
        反转强度 [0, 1]
        条件：高分歧 + 情绪极值 + 热度企稳 = 强反转
        """
        if factors.divergence_index < 0.7:
            return 0.0
        emo_extreme = abs(factors.sentiment_score)
        heat_adj = min(factors.heat_momentum + 0.2, 1.0)
        return round(emo_extreme * factors.divergence_index * heat_adj, 3)

    def get_signal(self, stock_factors: SentimentFactors,
                   macro: Optional[MacroFactorResult] = None) -> FinalTradeSignal:
        """
        宏观+个股联动最终交易信号。

        Args:
            stock_factors: 舆情三因子
            macro: 宏观研判（可选，不传自动获取缓存）

        Returns:
            FinalTradeSignal
        """
        if macro is None:
            macro = macro_monitor.get_macro_overall()

        pos = macro.position_ratio
        rev_strength = self.calc_reversal_strength(stock_factors)
        stock_result = sentiment_strategy_engine.evaluate(stock_factors)
        ts = datetime.now(timezone.utc).isoformat()

        # ============================================================
        # 🔴 地缘风控：geo_risk > 0.8 强制空仓
        # ============================================================
        if macro.geo_risk > 0.8:
            return FinalTradeSignal(
                signal="AVOID", level="极低", confidence=0.05,
                position_ratio=0.0, macro_override=True,
                macro_reason=f"地缘风险极端({macro.geo_risk:.2f})，风险偏好崩塌，全面空仓",
                stock_reason="所有做多信号被地缘风控覆盖",
                timestamp=ts,
            )

        # ============================================================
        # 🔴 系统性熊市：全面规避
        # ============================================================
        if macro.market_trend == "bear" or macro.risk_level == "high":
            # 极端利空+高分歧反转 → 轻仓试探（仅当非极端地缘）
            if stock_result.signal.value == "reversal" and rev_strength > 0.5 and macro.geo_risk < 0.5:
                return FinalTradeSignal(
                    signal="REVERSAL", level="medium", confidence=0.4,
                    position_ratio=0.1, macro_override=False,
                    macro_reason=f"宏观偏紧但反转信号强(rev={rev_strength:.2f})",
                    stock_reason=stock_result.reason,
                    timestamp=ts,
                )
            return FinalTradeSignal(
                signal="AVOID", level="低", confidence=0.1,
                position_ratio=0.0, macro_override=True,
                macro_reason=f"系统性风控: {macro.reason}",
                stock_reason=f"个股信号被覆盖({stock_result.signal.value})",
                timestamp=ts,
            )

        # ============================================================
        # 🟢 牛市：积极做多
        # ============================================================
        if macro.market_trend == "bull":
            if stock_result.signal.value in ("buy", "add"):
                return FinalTradeSignal(
                    signal=stock_result.signal.value.upper(), level="高",
                    confidence=0.8, position_ratio=pos,
                    macro_override=False,
                    macro_reason=f"牛市共振，仓位{pos:.0%}",
                    stock_reason=stock_result.reason,
                    timestamp=ts,
                )
            if stock_result.signal.value == "sell":
                return FinalTradeSignal(
                    signal="SELL", level="高", confidence=0.75,
                    position_ratio=0.0,
                    macro_reason="牛市高位分歧止盈",
                    stock_reason=stock_result.reason,
                    timestamp=ts,
                )

        # ============================================================
        # 🟡 震荡：精选反转 + 强势题材
        # ============================================================
        if macro.market_trend == "oscillate":
            if stock_result.signal.value == "reversal" and rev_strength > 0.4:
                return FinalTradeSignal(
                    signal="REVERSAL", level="中高", confidence=0.55,
                    position_ratio=0.25,
                    macro_reason=f"震荡反转(rev={rev_strength:.2f})",
                    stock_reason=stock_result.reason,
                    timestamp=ts,
                )
            if stock_result.signal.value == "buy":
                return FinalTradeSignal(
                    signal="BUY", level="中", confidence=0.5,
                    position_ratio=pos * 0.5,
                    macro_reason="震荡市中性仓位",
                    stock_reason=stock_result.reason,
                    timestamp=ts,
                )

        # ============================================================
        # 默认观望
        # ============================================================
        return FinalTradeSignal(
            signal="HOLD", level="中", confidence=0.35,
            position_ratio=pos * 0.5,
            macro_reason=macro.reason,
            stock_reason=stock_result.reason,
            timestamp=ts,
        )

    def format_for_agent(self, signal: FinalTradeSignal,
                         macro: MacroFactorResult,
                         stock_factors: SentimentFactors) -> str:
        macro_text = macro_monitor.format_for_agent(macro)
        stock_text = sentiment_strategy_engine.format_for_agent(
            sentiment_strategy_engine.evaluate(stock_factors))
        override = "⚠️ 宏观覆盖" if signal.macro_override else "✅ 宏观共振"
        emoji = {"BUY": "🟢", "ADD": "🔥", "SELL": "🔴", "REVERSAL": "🔄", "HOLD": "⚪", "AVOID": "🚫"}
        return (
            f"{macro_text}\n\n{stock_text}\n\n"
            f"## {emoji.get(signal.signal, '')} 最终决策（{override}）\n"
            f"- 信号：{signal.signal} | 置信度：{signal.confidence:.0%}"
            f" | 仓位：{signal.position_ratio:.0%}\n"
            f"- 宏观：{signal.macro_reason}\n"
            f"- 个股：{signal.stock_reason}"
        )


macro_sent_strategy = MacroSentimentStrategy()

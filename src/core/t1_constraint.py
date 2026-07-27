# -*- coding: utf-8 -*-
"""
A股 T+1 交易约束 + 复权口径 + 动态滑点 + 信号校验

在不修改现有 backtest_engine.py 的前提下，作为外层 wrapper 提供增强能力。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# T+1 约束
# ============================================================

class T1Constraint:
    """
    A股 T+1 交易规则强制校验。

    规则：
      - 当日买入的股票，最早下一个交易日才能卖出
      - 回测中禁止同一交易日内对同一标的出现 buy→sell 序列
    """

    def __init__(self):
        self._holdings: Dict[str, date] = {}  # code → 买入日期

    def can_sell(self, code: str, trade_date: date) -> bool:
        """检查是否允许卖出"""
        buy_date = self._holdings.get(code)
        if buy_date is None:
            return True  # 未持有，可以卖出(虽然逻辑上不应发生)
        return trade_date > buy_date

    def record_buy(self, code: str, trade_date: date):
        self._holdings[code] = trade_date

    def record_sell(self, code: str):
        self._holdings.pop(code, None)

    def validate_trade(self, code: str, action: str,
                       trade_date: date) -> Tuple[bool, str]:
        """
        校验单笔交易是否符合 T+1 规则。

        Returns:
            (是否合法, 违规原因)
        """
        if action == "buy":
            self.record_buy(code, trade_date)
            return True, ""
        if action == "sell":
            if not self.can_sell(code, trade_date):
                buy_date = self._holdings.get(code)
                return False, (
                    f"T+1违规: {code} 于 {buy_date} 买入, "
                    f"{trade_date} 同日卖出"
                )
            self.record_sell(code)
            return True, ""
        return True, ""

    def reset(self):
        self._holdings.clear()


# 全局实例
t1_constraint = T1Constraint()


# ============================================================
# 动态滑点模型
# ============================================================

class DynamicSlippage:
    """
    基于当日波动率动态计算滑点。

    公式：slippage = base_bps + volatility * vol_multiplier
    """

    def __init__(self, base_bps: float = 2.0, vol_multiplier: float = 0.5):
        self.base_bps = base_bps        # 基础滑点 (bps)
        self.vol_multiplier = vol_multiplier

    def calc_buy_slippage(self, daily_range_pct: float) -> float:
        """买入滑点（正数=实际成交价高于信号价）"""
        return (self.base_bps + daily_range_pct * self.vol_multiplier * 100) / 10000

    def calc_sell_slippage(self, daily_range_pct: float) -> float:
        """卖出滑点（正数=实际成交价低于信号价）"""
        return (self.base_bps + daily_range_pct * self.vol_multiplier * 100) / 10000

    @staticmethod
    def daily_range_pct(high: float, low: float, prev_close: float) -> float:
        """日内波动幅度（相对于前收盘）"""
        if prev_close <= 0:
            return 0.0
        return abs(high - low) / prev_close


# 全局实例
dynamic_slippage = DynamicSlippage()


# ============================================================
# 复权模式统一管理
# ============================================================

@dataclass
class AdjustMode:
    """复权模式"""
    mode: str = "forward"  # forward / backward / none
    label: str = "前复权"


ADJUST_MODES = {
    "forward": AdjustMode("forward", "前复权"),
    "backward": AdjustMode("backward", "后复权"),
    "none": AdjustMode("none", "不复权"),
}


def get_adjust_mode(mode: str = "forward") -> AdjustMode:
    return ADJUST_MODES.get(mode, ADJUST_MODES["forward"])


# ============================================================
# 回测信号后验校验
# ============================================================

class SignalValidator:
    """
    回测信号后验校验。

    检测项：
      - 未来函数：收盘前使用当日 close 生成信号
      - 涨跌停不可交易
      - ST 股流动性限制
    """

    @staticmethod
    def validate_no_future_leak(
        signal_time: str,      # "open" / "close"
        used_price: str,       # 信号使用的价格类型
    ) -> Tuple[bool, str]:
        """
        检测未来函数：禁止在开盘时使用当日收盘价。

        规则：
          - bar_open 时只能使用 open/昨收
          - bar_close 时可以使用当日所有价格
        """
        if signal_time == "open" and used_price in ("close", "high", "low"):
            return False, f"未来函数: 开盘信号使用了当日{used_price}价"
        return True, ""

    @staticmethod
    def validate_limit_trade(
        action: str,       # buy / sell
        pct_chg: float,    # 涨跌幅
        is_st: bool = False,
    ) -> Tuple[bool, str]:
        """
        涨跌停交易可行性校验。
        - 涨停(>=9.9%)：买入不可执行
        - 跌停(<=-9.9%)：卖出不可执行
        - ST 股涨跌幅 5%
        """
        limit = 5.0 if is_st else 9.9
        if action == "buy" and pct_chg >= limit * 0.99:
            return False, f"涨停({pct_chg:.1f}%)不可买入"
        if action == "sell" and pct_chg <= -limit * 0.99:
            return False, f"跌停({pct_chg:.1f}%)不可卖出"
        return True, ""


signal_validator = SignalValidator()

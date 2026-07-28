# -*- coding: utf-8 -*-
"""
===================================
回测绩效指标计算 — core/backtest/metrics.py
===================================

完整量化绩效指标：
- 累计收益、年化收益
- 最大回撤（MDD）
- 夏普比率、索提诺比率
- 胜率、盈亏比
- 卡玛比率
- 波动率
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any


class PerformanceMetrics:
    """量化绩效指标计算器"""

    @staticmethod
    def compute(
        asset_df: pd.DataFrame,
        risk_free_rate: float = 0.025,
        trading_days: int = 252,
    ) -> Dict[str, Any]:
        """
        计算完整绩效指标。

        Args:
            asset_df: 包含 date, asset 列的资产曲线
            risk_free_rate: 无风险利率（默认 2.5%）
            trading_days: 年交易日数

        Returns:
            绩效指标 dict
        """
        if asset_df is None or asset_df.empty:
            return _empty_performance()

        df = asset_df.copy()
        if "asset" not in df.columns:
            return _empty_performance()

        df["asset"] = pd.to_numeric(df["asset"], errors="coerce")
        df = df.dropna(subset=["asset"])

        if len(df) < 2:
            return _empty_performance()

        df["return"] = df["asset"].pct_change().fillna(0)

        init = float(df["asset"].iloc[0])
        final = float(df["asset"].iloc[-1])
        total_return = (final - init) / init

        # 年化收益
        years = len(df) / trading_days if trading_days > 0 else 1
        annual_return = (final / init) ** (1 / max(years, 0.01)) - 1

        # 最大回撤
        df["peak"] = df["asset"].cummax()
        df["drawdown"] = (df["asset"] - df["peak"]) / df["peak"]
        max_drawdown = float(df["drawdown"].min())

        # 夏普比率
        excess = df["return"] - risk_free_rate / trading_days
        daily_std = float(df["return"].std())
        sharpe = float(excess.mean() / daily_std * np.sqrt(trading_days)) if daily_std > 0 else 0

        # 索提诺比率（下行波动率）
        downside = df.loc[df["return"] < 0, "return"]
        downside_std = float(downside.std()) if len(downside) > 1 else 0
        sortino = float(excess.mean() / downside_std * np.sqrt(trading_days)) if downside_std > 0 else 0

        # 卡玛比率
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 胜率（正收益日占比）
        win_days = int((df["return"] > 0).sum())
        total_days = len(df)
        win_rate = win_days / total_days if total_days > 0 else 0

        # 盈亏比
        avg_win = float(df.loc[df["return"] > 0, "return"].mean()) if win_days > 0 else 0
        avg_loss = abs(float(df.loc[df["return"] < 0, "return"].mean())) if total_days - win_days > 0 else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 波动率
        volatility = float(daily_std * np.sqrt(trading_days))

        return {
            "initial_capital": round(init, 2),
            "final_capital": round(final, 2),
            "total_return": round(total_return, 4),
            "total_return_pct": f"{round(total_return * 100, 2)}%",
            "annual_return": round(annual_return, 4),
            "annual_return_pct": f"{round(annual_return * 100, 2)}%",
            "max_drawdown": round(max_drawdown, 4),
            "max_drawdown_pct": f"{round(max_drawdown * 100, 2)}%",
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "calmar_ratio": round(calmar, 3),
            "win_rate": round(win_rate, 4),
            "win_rate_pct": f"{round(win_rate * 100, 1)}%",
            "profit_loss_ratio": round(profit_loss_ratio, 2),
            "volatility": round(volatility, 4),
            "trading_days": total_days,
            "win_days": win_days,
        }


def _empty_performance() -> Dict[str, Any]:
    return {
        "initial_capital": 0, "final_capital": 0,
        "total_return": 0, "total_return_pct": "0%",
        "annual_return": 0, "annual_return_pct": "0%",
        "max_drawdown": 0, "max_drawdown_pct": "0%",
        "sharpe_ratio": 0, "sortino_ratio": 0, "calmar_ratio": 0,
        "win_rate": 0, "win_rate_pct": "0%",
        "profit_loss_ratio": 0, "volatility": 0,
        "trading_days": 0, "win_days": 0,
    }

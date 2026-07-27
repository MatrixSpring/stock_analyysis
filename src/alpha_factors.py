# -*- coding: utf-8 -*-
"""
===================================
Alpha 因子库 — AlphaLibrary
===================================

对齐 Qlib Alpha158 核心因子体系，提供：
- 量价因子 (K线、均线、波动)
- 动量因子 (收益率动量、反转)
- 流动性因子 (换手率、成交量)
- 质量因子 (ROE、毛利率)

所有因子经预处理后使用，支持因子有效性检测。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class AlphaLibrary:
    """
    Alpha 因子库。

    使用方式:
        lib = AlphaLibrary()
        factors = lib.compute_all(open, high, low, close, volume, amount)
        # factors is {name: np.ndarray}
    """

    def __init__(self):
        self._factor_names: List[str] = []

    # ============================================================
    # 量价因子
    # ============================================================

    @staticmethod
    def ret_1d(close: np.ndarray) -> np.ndarray:
        """1日收益率"""
        r = np.diff(close) / (close[:-1] + 1e-10)
        return np.pad(r, (1, 0), constant_values=0)

    @staticmethod
    def ret_5d(close: np.ndarray) -> np.ndarray:
        """5日收益率"""
        r = np.zeros_like(close)
        r[5:] = close[5:] / (close[:-5] + 1e-10) - 1
        return r

    @staticmethod
    def ret_20d(close: np.ndarray) -> np.ndarray:
        """20日收益率"""
        r = np.zeros_like(close)
        r[20:] = close[20:] / (close[:-20] + 1e-10) - 1
        return r

    @staticmethod
    def ma_gap(close: np.ndarray, window: int = 5) -> np.ndarray:
        """均线偏离: (close - MA) / MA"""
        ma = AlphaLibrary._rolling_mean(close, window)
        return np.where(ma > 0, (close - ma) / ma, 0)

    @staticmethod
    def ma_cross(close: np.ndarray, fast: int = 5, slow: int = 20) -> np.ndarray:
        """均线交叉信号"""
        ma_fast = AlphaLibrary._rolling_mean(close, fast)
        ma_slow = AlphaLibrary._rolling_mean(close, slow)
        return np.where(ma_slow > 0, (ma_fast - ma_slow) / ma_slow, 0)

    @staticmethod
    def volatility_20d(close: np.ndarray) -> np.ndarray:
        """20日波动率"""
        rets = AlphaLibrary.ret_1d(close)
        return AlphaLibrary._rolling_std(rets, 20) * np.sqrt(252)

    @staticmethod
    def rsi_14d(close: np.ndarray) -> np.ndarray:
        """14日RSI"""
        delta = np.diff(close)
        delta = np.pad(delta, (1, 0), constant_values=0)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = AlphaLibrary._rolling_mean(gain, 14)
        avg_loss = AlphaLibrary._rolling_mean(loss, 14)
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - 100 / (1 + rs)

    @staticmethod
    def bollinger_position(close: np.ndarray, window: int = 20) -> np.ndarray:
        """布林带位置: (close - lower) / (upper - lower)"""
        ma = AlphaLibrary._rolling_mean(close, window)
        std = AlphaLibrary._rolling_std(close, window)
        upper = ma + 2 * std
        lower = ma - 2 * std
        denom = upper - lower + 1e-10
        return np.clip((close - lower) / denom, 0, 1)

    # ============================================================
    # 动量/反转因子
    # ============================================================

    @staticmethod
    def momentum_12m1m(close: np.ndarray) -> np.ndarray:
        """12月-1月动量 (需要 > 252 根K线)"""
        r = np.zeros_like(close)
        n = len(close)
        if n < 253:
            return r  # 数据不足
        r[252:] = close[252:] / (close[:-252] + 1e-10) - \
                  close[21:n-252+21] / (close[:n-252] + 1e-10)
        return r

    @staticmethod
    def reversal_5d(close: np.ndarray) -> np.ndarray:
        """5日反转: -ret_5d"""
        return -AlphaLibrary.ret_5d(close)

    @staticmethod
    def max_drawdown_60d(close: np.ndarray) -> np.ndarray:
        """60日最大回撤"""
        result = np.zeros(len(close))
        for i in range(60, len(close)):
            window = close[i-60:i+1]
            peak = np.maximum.accumulate(window)
            dd = (peak - window) / (peak + 1e-10)
            result[i] = np.max(dd)
        return result

    # ============================================================
    # 流动性因子
    # ============================================================

    @staticmethod
    def turnover_5d(volume: np.ndarray, float_shares: float = 1.0) -> np.ndarray:
        """5日平均换手率"""
        shares = max(float_shares, 1.0)
        avg_vol = AlphaLibrary._rolling_mean(volume, 5)
        return avg_vol / shares

    @staticmethod
    def volume_ratio(volume: np.ndarray, window: int = 20) -> np.ndarray:
        """量比: 近5日均量 / 20日均量"""
        vol5 = AlphaLibrary._rolling_mean(volume, 5)
        vol20 = AlphaLibrary._rolling_mean(volume, window)
        return np.where(vol20 > 0, vol5 / vol20, 1.0)

    @staticmethod
    def illiquidity(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """Amihud非流动性: |ret| / amount"""
        ret = AlphaLibrary.ret_1d(close)
        amount = close * volume
        return np.where(amount > 0, np.abs(ret) / amount * 1e8, 0)

    # ============================================================
    # 质量因子 (截面/基本面数据留接口)
    # ============================================================

    @staticmethod
    def roe_factor(roe: np.ndarray) -> np.ndarray:
        """ROE 因子（标准化后使用）"""
        return roe

    @staticmethod
    def gross_margin(revenue: np.ndarray, cost: np.ndarray) -> np.ndarray:
        """毛利率"""
        return np.where(revenue > 0, (revenue - cost) / revenue, 0)

    # ============================================================
    # 批量计算
    # ============================================================

    def compute_all(
        self, open_p: np.ndarray, high: np.ndarray, low: np.ndarray,
        close: np.ndarray, volume: np.ndarray, amount: np.ndarray,
        float_shares: float = 1.0,
    ) -> Dict[str, np.ndarray]:
        """计算全部因子"""
        factors = {
            "ret_1d": self.ret_1d(close),
            "ret_5d": self.ret_5d(close),
            "ret_20d": self.ret_20d(close),
            "ma_gap_5": self.ma_gap(close, 5),
            "ma_gap_20": self.ma_gap(close, 20),
            "ma_cross": self.ma_cross(close, 5, 20),
            "volatility_20d": self.volatility_20d(close),
            "rsi_14d": self.rsi_14d(close),
            "bollinger_pos": self.bollinger_position(close, 20),
            "reversal_5d": self.reversal_5d(close),
            "momentum_12m1m": self.momentum_12m1m(close),
            "max_drawdown_60d": self.max_drawdown_60d(close),
            "volume_ratio": self.volume_ratio(volume),
            "illiquidity": self.illiquidity(close, volume),
        }
        self._factor_names = list(factors.keys())
        return factors

    def factor_matrix(self, **factor_kwargs) -> np.ndarray:
        """因子矩阵 (T, N_factors)"""
        factors = self.compute_all(**factor_kwargs)
        # 对齐到最短长度
        min_len = min(len(v) for v in factors.values())
        return np.column_stack([
            list(factors.values())[i][-min_len:]
            for i in range(len(factors))
        ])

    def list_factors(self) -> List[str]:
        return self._factor_names or [
            "ret_1d", "ret_5d", "ret_20d", "ma_gap_5", "ma_gap_20",
            "ma_cross", "volatility_20d", "rsi_14d", "bollinger_pos",
            "reversal_5d", "momentum_12m1m", "max_drawdown_60d",
            "volume_ratio", "illiquidity",
        ]

    # ============================================================
    # 因子有效性检测
    # ============================================================

    @staticmethod
    def factor_ic(factor: np.ndarray, forward_return: np.ndarray) -> float:
        """Rank IC (Spearman): 因子值与下期收益的秩相关系数"""
        valid = ~(np.isnan(factor) | np.isnan(forward_return))
        if valid.sum() < 10:
            return 0.0
        f = factor[valid]
        r = forward_return[valid]
        # Spearman = Pearson on ranks
        from scipy.stats import spearmanr
        ic, _ = spearmanr(f, r)
        return float(ic) if not np.isnan(ic) else 0.0

    @staticmethod
    def factor_ir(factor: np.ndarray, forward_returns: np.ndarray) -> float:
        """信息比率: mean(IC) / std(IC)"""
        ics = []
        for t in range(1, len(factor)):
            if t + 1 >= len(forward_returns):
                break
            ic = AlphaLibrary.factor_ic(factor[:t], forward_returns[1:t+1])
            ics.append(ic)
        if len(ics) < 5:
            return 0.0
        return float(np.mean(ics) / max(np.std(ics), 1e-10))

    # ============================================================
    # 工具
    # ============================================================

    @staticmethod
    def _rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
        result = np.zeros_like(x)
        cumsum = np.cumsum(np.insert(x, 0, 0))
        result[window-1:] = (cumsum[window:] - cumsum[:-window]) / window
        result[:window-1] = np.mean(x[:window]) if window > 0 else 0
        return result

    @staticmethod
    def _rolling_std(x: np.ndarray, window: int) -> np.ndarray:
        result = np.zeros_like(x)
        for i in range(window - 1, len(x)):
            result[i] = np.std(x[i-window+1:i+1])
        return result

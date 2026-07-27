# -*- coding: utf-8 -*-
"""
===================================
向量化回测引擎 — VectorBacktester
===================================

职责：
1. NumPy 向量化批量回测（对标 VectorBT 核心能力）
2. 组合级指标：收益率、夏普、回撤、胜率
3. 多股票并行测试，性能优于逐股循环
4. 绩效归因：因子暴露 + 收益分解

核心优化：
- 用 NumPy 向量化操作代替 Python 循环
- 单次矩阵运算处理全部股票的完整回测周期
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """回测结果"""
    stock_code: str = ""
    total_return: float = 0.0
    cagr: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_return: float = 0.0
    final_equity: float = 1.0
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PortfolioResult:
    """组合级回测结果"""
    total_return: float = 0.0
    cagr: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    equity_curve: np.ndarray = field(default_factory=lambda: np.array([]))
    stock_results: List[BacktestResult] = field(default_factory=list)
    correlation_matrix: np.ndarray = field(default_factory=lambda: np.array([]))
    attribution: Dict[str, Any] = field(default_factory=dict)


class VectorBacktester:
    """
    向量化回测引擎。

    使用方式：
        vb = VectorBacktester()
        prices = {"600519": np.array([...]), "000001": np.array([...])}
        signals = {"600519": np.array([1, 0, -1, ...]), ...}
        result = vb.run(prices, signals)
    """

    def __init__(self, initial_capital: float = 100000.0,
                 commission: float = 0.0003,  # 万三
                 slippage: float = 0.001):     # 0.1%
        self._capital = initial_capital
        self._commission = commission
        self._slippage = slippage

    # ============================================================
    # 核心回测方法
    # ============================================================

    def run(
        self, prices: Dict[str, np.ndarray],
        signals: Optional[Dict[str, np.ndarray]] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> PortfolioResult:
        """
        向量化回测。

        Args:
            prices: {stock_code: price_array (T,)}
            signals: {stock_code: signal_array (T,)}  1=long, -1=short, 0=flat
            weights: {stock_code: weight}  组合权重

        Returns:
            PortfolioResult
        """
        if not prices:
            return PortfolioResult()

        stock_codes = list(prices.keys())
        n_stocks = len(stock_codes)
        n_periods = min(len(p) for p in prices.values())

        # 对齐所有价格序列
        price_matrix = np.zeros((n_periods, n_stocks))
        for i, code in enumerate(stock_codes):
            price_matrix[:, i] = prices[code][:n_periods]

        # 生成信号矩阵（若无信号则 buy & hold）
        if signals is None:
            signal_matrix = np.ones((n_periods, n_stocks))
        else:
            signal_matrix = np.zeros((n_periods, n_stocks))
            for i, code in enumerate(stock_codes):
                sig = signals.get(code)
                if sig is not None:
                    signal_matrix[:len(sig), i] = sig[:n_periods]

        # 生成权重矩阵
        if weights is None:
            weight_array = np.ones(n_stocks) / n_stocks
        else:
            weight_array = np.array([weights.get(c, 0.0) for c in stock_codes])
            weight_array = weight_array / weight_array.sum() if weight_array.sum() > 0 else weight_array

        # ---- 向量化回测核心 ----
        # 日收益率矩阵
        returns_matrix = np.diff(price_matrix, axis=0) / (price_matrix[:-1] + 1e-10)

        # 策略收益（考虑信号）
        strategy_returns = returns_matrix * signal_matrix[:-1]

        # 扣除手续费和滑点
        trades = np.diff(signal_matrix, axis=0)
        trade_count = np.sum(np.abs(trades), axis=1)
        cost = trade_count * (self._commission + self._slippage) / n_stocks

        # 加权组合收益
        portfolio_returns = np.sum(strategy_returns * weight_array, axis=1) - cost

        # ---- 绩效计算 ----
        equity = self._capital * np.cumprod(1 + portfolio_returns)
        equity = np.insert(equity, 0, self._capital)

        total_ret = (equity[-1] / self._capital - 1)
        cagr = self._calc_cagr(equity)
        vol = float(np.std(portfolio_returns) * np.sqrt(252)) if len(portfolio_returns) > 1 else 0
        sharpe = (
            float(np.mean(portfolio_returns) / max(np.std(portfolio_returns), 1e-10) * np.sqrt(252))
            if len(portfolio_returns) > 1 else 0
        )
        mdd = self._calc_max_drawdown(equity)
        wr = float(np.sum(portfolio_returns > 0) / max(len(portfolio_returns), 1))

        # ---- 个股回测 ----
        stock_results = []
        for i, code in enumerate(stock_codes):
            stock_rets = returns_matrix[:, i] * signal_matrix[:-1, i]
            stock_equity = self._capital * np.cumprod(1 + stock_rets)
            stock_equity = np.insert(stock_equity, 0, self._capital)

            stock_results.append(BacktestResult(
                stock_code=code,
                total_return=float(stock_equity[-1] / self._capital - 1),
                cagr=self._calc_cagr(stock_equity),
                volatility=float(np.std(stock_rets) * np.sqrt(252)),
                sharpe_ratio=float(np.mean(stock_rets) / max(np.std(stock_rets), 1e-10) * np.sqrt(252)),
                max_drawdown=self._calc_max_drawdown(stock_equity),
                win_rate=float(np.sum(stock_rets > 0) / max(len(stock_rets), 1)),
                equity_curve=stock_equity.tolist(),
            ))

        # ---- 相关矩阵 ----
        corr = np.corrcoef(returns_matrix.T) if n_stocks > 1 else np.eye(1)

        # ---- 归因 ----
        attribution = self._attribution(returns_matrix, signal_matrix[:-1], stock_codes)

        return PortfolioResult(
            total_return=round(total_ret, 4),
            cagr=round(cagr, 4),
            volatility=round(vol, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(mdd, 4),
            win_rate=round(wr, 4),
            equity_curve=equity,
            stock_results=stock_results,
            correlation_matrix=corr,
            attribution=attribution,
        )

    def run_single(
        self, prices: np.ndarray, signals: np.ndarray,
    ) -> BacktestResult:
        """单股票快速回测"""
        result = self.run(
            {"stock": prices}, {"stock": signals},
        )
        if result.stock_results:
            return result.stock_results[0]
        return BacktestResult()

    # ============================================================
    # 参数扫描
    # ============================================================

    def param_scan(
        self, prices: np.ndarray,
        param_name: str, param_values: List[float],
        signal_generator,
    ) -> List[Dict[str, Any]]:
        """
        参数扫描：测试不同参数的回测表现。

        Returns:
            [{param_value, sharpe, max_dd, total_return}]
        """
        results = []
        for val in param_values:
            sigs = signal_generator(val)
            bt = self.run_single(prices, sigs)
            results.append({
                param_name: val,
                "sharpe": bt.sharpe_ratio,
                "max_drawdown": bt.max_drawdown,
                "total_return": bt.total_return,
                "win_rate": bt.win_rate,
            })
        return results

    def optimize(
        self, prices: np.ndarray,
        param_ranges: Dict[str, List[float]],
        signal_generator,
        objective: str = "sharpe",
    ) -> Dict[str, Any]:
        """
        网格搜索最优参数。

        Args:
            param_ranges: {param_name: [values]}
            objective: "sharpe" | "return" | "calmar"
        """
        import itertools
        keys = list(param_ranges.keys())
        best_params = None
        best_score = -float("inf")

        for combo in itertools.product(*param_ranges.values()):
            params = dict(zip(keys, combo))
            sigs = signal_generator(**params)
            bt = self.run_single(prices, sigs)
            score = getattr(bt, f"{objective}_ratio", bt.sharpe_ratio) if objective != "return" else bt.total_return
            if score > best_score:
                best_score = score
                best_params = {**params, "score": round(score, 4)}

        return {
            "best_params": best_params,
            "objective": objective,
            "scanned_combinations": len(list(itertools.product(*param_ranges.values()))),
        }

    # ============================================================
    # 绩效归因
    # ============================================================

    def _attribution(
        self, returns: np.ndarray, signals: np.ndarray, codes: List[str],
    ) -> Dict[str, Any]:
        """简单绩效归因"""
        n_stocks = returns.shape[1]
        if n_stocks == 0:
            return {}

        stock_contributions = {}
        for i, code in enumerate(codes):
            stock_ret = np.sum(returns[:, i] * signals[:, i]) if signals.shape[0] == returns.shape[0] else 0
            stock_contributions[code] = round(float(stock_ret), 4)

        total = sum(abs(v) for v in stock_contributions.values()) or 1
        return {
            "stock_contributions": stock_contributions,
            "top_contributors": sorted(
                stock_contributions.items(), key=lambda x: -x[1]
            )[:5],
            "concentration": round(
                sum(v**2 for v in stock_contributions.values()) / total**2, 4
            ) if total > 0 else 1.0,
        }

    # ============================================================
    # 工具
    # ============================================================

    @staticmethod
    def _calc_cagr(equity: np.ndarray) -> float:
        n = len(equity) - 1
        if n <= 0 or equity[0] <= 0:
            return 0.0
        years = n / 252.0
        if years <= 0:
            return 0.0
        return float((equity[-1] / equity[0]) ** (1.0 / years) - 1.0)

    @staticmethod
    def _calc_max_drawdown(equity: np.ndarray) -> float:
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        return float(np.max(dd))

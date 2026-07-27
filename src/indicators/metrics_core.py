# -*- coding: utf-8 -*-
"""
===================================
全局唯一指标计算核心 — MetricsCore
===================================

职责：
1. 全项目唯一真源的指标计算实现
2. 所有模块（旧版/新版/回测/AI）统一调用，消除数据不一致
3. 所有计算均为纯函数，无副作用，可复现

覆盖指标：
- 收益类: 总收益、年化收益(CAGR)、日/周/月收益率序列
- 风险类: 波动率、最大回撤、下行波动率、VaR、CVaR
- 风险调整: 夏普比率、索提诺比率、卡玛比率、信息比率
- 交易类: 胜率、盈亏比、平均持仓天数
- 综合类: 综合评分
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np


# ============================================================
# 类型别名
# ============================================================

NumericArray = Union[List[float], np.ndarray, Sequence[float]]
ReturnSeries = Union[List[float], np.ndarray]


# ============================================================
# 工具函数
# ============================================================

def _to_array(values: NumericArray) -> np.ndarray:
    """统一转为 numpy array"""
    if isinstance(values, np.ndarray):
        return values.astype(np.float64)
    return np.array(values, dtype=np.float64)


def _annual_factor(daily: bool = True) -> float:
    """年化因子：日线 ≈252，非日线 → 1"""
    return 252.0 if daily else 1.0


# ============================================================
# 收益类指标
# ============================================================

def total_return(close_prices: NumericArray) -> float:
    """
    总收益率。

    Args:
        close_prices: 收盘价序列

    Returns:
        float: 总收益率（小数形式）
    """
    arr = _to_array(close_prices)
    if len(arr) < 2 or arr[0] == 0:
        return 0.0
    return float((arr[-1] / arr[0]) - 1.0)


def cagr(close_prices: NumericArray, daily: bool = True) -> float:
    """
    年化复合增长率 (CAGR)。

    Args:
        close_prices: 收盘价序列
        daily: 是否日线数据

    Returns:
        float: CAGR（小数形式）
    """
    arr = _to_array(close_prices)
    if len(arr) < 2 or arr[0] <= 0:
        return 0.0

    total = total_return(arr)
    periods = len(arr) - 1
    if periods <= 0:
        return 0.0

    years = periods / 252.0 if daily else periods
    if years <= 0:
        return 0.0

    return float((1 + total) ** (1.0 / years) - 1.0)


def daily_returns(close_prices: NumericArray) -> np.ndarray:
    """计算日收益率序列"""
    arr = _to_array(close_prices)
    if len(arr) < 2:
        return np.array([])
    return (arr[1:] - arr[:-1]) / arr[:-1]


def cumulative_returns(close_prices: NumericArray) -> np.ndarray:
    """计算累计收益率序列"""
    arr = _to_array(close_prices)
    if len(arr) < 2 or arr[0] <= 0:
        return np.array([])
    return arr / arr[0] - 1.0


def excess_returns(
    returns: ReturnSeries,
    benchmark_returns: ReturnSeries,
) -> np.ndarray:
    """计算超额收益率序列"""
    r = _to_array(returns)
    b = _to_array(benchmark_returns)
    min_len = min(len(r), len(b))
    return r[:min_len] - b[:min_len]


# ============================================================
# 风险类指标
# ============================================================

def volatility(returns: ReturnSeries, daily: bool = True) -> float:
    """
    年化波动率。

    Args:
        returns: 收益率序列
        daily: 是否为日频

    Returns:
        float: 年化波动率（小数形式）
    """
    r = _to_array(returns)
    if len(r) < 2:
        return 0.0
    std = float(np.std(r, ddof=1))
    return std * math.sqrt(_annual_factor(daily))


def max_drawdown(close_prices: NumericArray) -> float:
    """
    最大回撤。

    Args:
        close_prices: 收盘价序列

    Returns:
        float: 最大回撤（非负小数，0.25 = 25%）
    """
    arr = _to_array(close_prices)
    if len(arr) < 2:
        return 0.0

    cumulative_max = np.maximum.accumulate(arr)
    drawdowns = (cumulative_max - arr) / cumulative_max
    return float(np.max(drawdowns))


def max_drawdown_duration(close_prices: NumericArray) -> int:
    """
    最长回撤持续期（天数）。

    Args:
        close_prices: 收盘价序列

    Returns:
        int: 最长连续回撤天数
    """
    arr = _to_array(close_prices)
    if len(arr) < 2:
        return 0

    cumulative_max = np.maximum.accumulate(arr)
    in_drawdown = cumulative_max > arr

    max_duration = 0
    current = 0
    for v in in_drawdown:
        if v:
            current += 1
            max_duration = max(max_duration, current)
        else:
            current = 0
    return max_duration


def downside_volatility(returns: ReturnSeries, daily: bool = True) -> float:
    """
    下行波动率（只计算负收益的标准差）。

    Args:
        returns: 收益率序列
        daily: 是否为日频

    Returns:
        float: 年化下行波动率
    """
    r = _to_array(returns)
    negative = r[r < 0]
    if len(negative) < 2:
        return 0.0
    std = float(np.std(negative, ddof=1))
    return std * math.sqrt(_annual_factor(daily))


def var_95(returns: ReturnSeries) -> float:
    """
    95% 置信度 VaR (Value at Risk)。

    Returns:
        float: 非负值，表示最大亏损比例（小数形式）
    """
    r = _to_array(returns)
    if len(r) < 5:
        return 0.0
    return float(-np.percentile(r, 5))


def cvar_95(returns: ReturnSeries) -> float:
    """
    95% 置信度 CVaR (Conditional VaR / Expected Shortfall)。

    Returns:
        float: 尾部期望损失（非负小数）
    """
    r = _to_array(returns)
    if len(r) < 5:
        return 0.0
    var = np.percentile(r, 5)
    tail = r[r <= var]
    if len(tail) == 0:
        return 0.0
    return float(-np.mean(tail))


# ============================================================
# 风险调整指标
# ============================================================

def sharpe_ratio(returns: ReturnSeries, risk_free_rate: float = 0.02, daily: bool = True) -> float:
    """
    夏普比率。

    Formula: (mean_return - rf) / std_return * sqrt(annual_factor)

    Args:
        returns: 收益率序列
        risk_free_rate: 年化无风险利率（默认 2%）
        daily: 是否为日频

    Returns:
        float: 年化夏普比率
    """
    r = _to_array(returns)
    if len(r) < 2:
        return 0.0

    mean_ret = float(np.mean(r))
    std_ret = float(np.std(r, ddof=1))
    if std_ret == 0:
        return 0.0

    ann_factor = _annual_factor(daily)
    rf_daily = risk_free_rate / ann_factor
    return float((mean_ret - rf_daily) / std_ret * math.sqrt(ann_factor))


def sortino_ratio(returns: ReturnSeries, risk_free_rate: float = 0.02, daily: bool = True) -> float:
    """
    索提诺比率（下行风险调整收益）。

    Formula: (mean_return - rf) / downside_std * sqrt(annual_factor)
    """
    r = _to_array(returns)
    if len(r) < 2:
        return 0.0

    mean_ret = float(np.mean(r))
    down_vol = downside_volatility(r, daily=False)
    if down_vol == 0:
        return 0.0

    ann_factor = _annual_factor(daily)
    rf_daily = risk_free_rate / ann_factor
    return float((mean_ret - rf_daily) / down_vol * math.sqrt(ann_factor))


def calmar_ratio(returns: ReturnSeries, close_prices: NumericArray, daily: bool = True) -> float:
    """
    卡玛比率 (CAGR / Max Drawdown)。
    """
    c = cagr(close_prices, daily=daily)
    dd = max_drawdown(close_prices)
    if dd == 0:
        return 0.0
    return c / dd


def information_ratio(
    returns: ReturnSeries,
    benchmark_returns: ReturnSeries,
    daily: bool = True,
) -> float:
    """
    信息比率（超额收益 / 跟踪误差）。
    """
    ex = excess_returns(returns, benchmark_returns)
    if len(ex) < 2:
        return 0.0

    mean_ex = float(np.mean(ex))
    std_ex = float(np.std(ex, ddof=1))
    if std_ex == 0:
        return 0.0

    return float(mean_ex / std_ex * math.sqrt(_annual_factor(daily)))


def beta(returns: ReturnSeries, benchmark_returns: ReturnSeries) -> float:
    """
    Beta 系数（相对于基准的系统性风险）。
    """
    r = _to_array(returns)
    b = _to_array(benchmark_returns)
    min_len = min(len(r), len(b))
    if min_len < 2:
        return 1.0

    r = r[:min_len]
    b = b[:min_len]

    cov = np.cov(r, b, ddof=1)[0, 1]
    var = np.var(b, ddof=1)
    if var == 0:
        return 1.0
    return float(cov / var)


def alpha(returns: ReturnSeries, benchmark_returns: ReturnSeries,
          risk_free_rate: float = 0.02, daily: bool = True) -> float:
    """
    Jensen's Alpha（超额收益中不能被 Beta 解释的部分）。
    """
    r = _to_array(returns)
    b = _to_array(benchmark_returns)
    min_len = min(len(r), len(b))
    if min_len < 2:
        return 0.0

    r = r[:min_len]
    b = b[:min_len]

    _beta = beta(r, b)
    ann_factor = _annual_factor(daily)
    rf_daily = risk_free_rate / ann_factor

    mean_rf_excess = float(np.mean(r - rf_daily))
    mean_bm_excess = float(np.mean(b - rf_daily))

    return float(mean_rf_excess - _beta * mean_bm_excess) * ann_factor


# ============================================================
# 交易类指标
# ============================================================

def win_rate(
    outcomes: Union[List[bool], List[int]],
) -> float:
    """
    胜率。

    Args:
        outcomes: 布尔列表（True=赢）或 0/1 列表（1=赢）

    Returns:
        float: 胜率（小数形式）
    """
    if not outcomes:
        return 0.0
    wins = sum(1 for o in outcomes if o is True or o == 1)
    return wins / len(outcomes)


def profit_loss_ratio(
    winning_returns: NumericArray,
    losing_returns: NumericArray,
) -> float:
    """
    盈亏比（平均盈利 / 平均亏损）。

    Returns:
        float: 盈亏比
    """
    w = _to_array(winning_returns)
    l = _to_array(losing_returns)

    avg_win = float(np.mean(w)) if len(w) > 0 else 0.0
    avg_loss = float(np.mean(np.abs(l))) if len(l) > 0 else 1.0

    if avg_loss == 0:
        return 0.0
    return avg_win / avg_loss


def profit_factor(
    winning_returns: NumericArray,
    losing_returns: NumericArray,
) -> float:
    """
    盈利因子（总盈利 / 总亏损）。
    """
    total_win = float(np.sum(_to_array(winning_returns)))
    total_loss = float(np.sum(np.abs(_to_array(losing_returns))))
    if total_loss == 0:
        return 0.0 if total_win == 0 else float("inf")
    return total_win / total_loss


def avg_holding_days(holding_periods: NumericArray) -> float:
    """平均持仓天数"""
    arr = _to_array(holding_periods)
    if len(arr) == 0:
        return 0.0
    return float(np.mean(arr))


def turnover_rate(trades_count: int, periods: int) -> float:
    """
    换手率（年化）。

    Args:
        trades_count: 总交易次数
        periods: 总交易天数

    Returns:
        float: 年化换手率
    """
    if periods <= 0:
        return 0.0
    return trades_count / periods * 252.0


# ============================================================
# 综合评分
# ============================================================

def composite_score(
    returns: ReturnSeries,
    close_prices: NumericArray,
    benchmark_returns: Optional[ReturnSeries] = None,
    risk_free_rate: float = 0.02,
    daily: bool = True,
) -> float:
    """
    综合绩效评分 (0-100)。

    评分维度：夏普(25%) + 最大回撤(25%) + 胜率(20%) + 盈亏比(15%) + Alpha(15%)
    """
    r = _to_array(returns)
    if len(r) < 2:
        return 0.0

    scores: List[float] = []

    # 1. 夏普 (0-25)
    sr = sharpe_ratio(r, risk_free_rate, daily)
    sr_score = min(max(sr / 3.0, 0), 1.0) * 25
    scores.append(sr_score)

    # 2. 最大回撤 (0-25)：回撤 < 10% → 满分
    dd = max_drawdown(close_prices)
    dd_score = max(1.0 - dd / 0.4, 0) * 25
    scores.append(dd_score)

    # 3. 胜率 (0-20)
    wr = win_rate([(ret > 0) for ret in r])
    wr_score = max(wr - 0.3, 0) / 0.7 * 20
    scores.append(max(min(wr_score, 20), 0))

    # 4. 盈亏比 (0-15)
    winning = r[r > 0]
    losing = r[r < 0]
    pl = profit_loss_ratio(winning, losing)
    pl_score = min(pl / 3.0, 1.0) * 15
    scores.append(pl_score)

    # 5. Alpha (0-15)
    if benchmark_returns is not None:
        a = alpha(r, benchmark_returns, risk_free_rate, daily)
        a_score = max(min(a / 0.2 + 0.5, 1.0), 0) * 15
        scores.append(a_score)
    else:
        scores.append(7.5)  # 无基准时给中性分

    return round(sum(scores), 1)


# ============================================================
# 诊断
# ============================================================

def metrics_report(
    close_prices: NumericArray,
    returns: Optional[ReturnSeries] = None,
    benchmark_returns: Optional[ReturnSeries] = None,
    risk_free_rate: float = 0.02,
    daily: bool = True,
) -> dict:
    """
    生成完整的指标报告。

    Returns:
        dict: 包含所有核心指标的字典
    """
    if returns is None:
        returns = daily_returns(close_prices).tolist() if len(close_prices) > 1 else []

    r = _to_array(returns)
    cp = _to_array(close_prices)

    report = {
        # 收益
        "total_return": round(total_return(cp), 4),
        "cagr": round(cagr(cp, daily), 4),
        "mean_daily_return": round(float(np.mean(r)), 6),

        # 风险
        "volatility": round(volatility(r, daily), 4),
        "max_drawdown": round(max_drawdown(cp), 4),
        "max_drawdown_duration": max_drawdown_duration(cp),
        "downside_volatility": round(downside_volatility(r, daily), 4),
        "var_95": round(var_95(r), 4),
        "cvar_95": round(cvar_95(r), 4),

        # 风险调整
        "sharpe_ratio": round(sharpe_ratio(r, risk_free_rate, daily), 4),
        "sortino_ratio": round(sortino_ratio(r, risk_free_rate, daily), 4),
        "calmar_ratio": round(calmar_ratio(r, cp, daily), 4),
    }

    # 相对基准指标
    if benchmark_returns is not None:
        bm = _to_array(benchmark_returns)
        report["information_ratio"] = round(information_ratio(r, bm, daily), 4)
        report["beta"] = round(beta(r, bm), 4)
        report["alpha"] = round(alpha(r, bm, risk_free_rate, daily), 4)

    # 交易指标
    winning = r[r > 0]
    losing = r[r < 0]
    report["win_rate"] = round(len(winning) / max(len(r), 1), 4)
    report["profit_loss_ratio"] = (
        round(profit_loss_ratio(winning, losing), 4)
        if len(losing) > 0 else None
    )
    report["profit_factor"] = (
        round(profit_factor(winning, losing), 4)
        if len(losing) > 0 else None
    )

    # 综合
    report["composite_score"] = composite_score(r, cp, benchmark_returns, risk_free_rate, daily)

    return report

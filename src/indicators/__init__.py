# -*- coding: utf-8 -*-
"""
===================================
全局唯一指标计算 SDK
===================================

职责：
全项目唯一真源的指标计算实现。所有模块（旧版/新版/回测/AI/报表）统一调用，
彻底消除新旧页面数据不一致问题。

模块：
- metrics_core  — 收益/风险/风险调整/交易指标 + 综合评分
- capital_flow  — 资金行为指标（北向/主力/融资融券/龙虎榜/大宗）
- sentiment     — 舆情情感/行业景气度/宏观风险/市场情绪指数

使用方式：
    from src.indicators import (
        sharpe_ratio, max_drawdown, win_rate, composite_score,
        north_bound_score, composite_capital_heat,
        text_sentiment, industry_boom_score, market_sentiment_index,
        metrics_report,
    )
"""

from src.indicators.metrics_core import (
    # 收益
    total_return,
    cagr,
    daily_returns,
    cumulative_returns,
    excess_returns,
    # 风险
    volatility,
    max_drawdown,
    max_drawdown_duration,
    downside_volatility,
    var_95,
    cvar_95,
    # 风险调整
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    information_ratio,
    beta,
    alpha,
    # 交易
    win_rate,
    profit_loss_ratio,
    profit_factor,
    avg_holding_days,
    turnover_rate,
    # 综合
    composite_score,
    metrics_report,
)

from src.indicators.capital_flow import (
    north_bound_score,
    main_capital_score,
    margin_score,
    dragon_tiger_score,
    composite_capital_heat,
)

from src.indicators.sentiment import (
    text_sentiment,
    batch_sentiment,
    industry_boom_score,
    macro_risk_score,
    market_sentiment_index,
)

__all__ = [
    # 收益
    "total_return",
    "cagr",
    "daily_returns",
    "cumulative_returns",
    "excess_returns",
    # 风险
    "volatility",
    "max_drawdown",
    "max_drawdown_duration",
    "downside_volatility",
    "var_95",
    "cvar_95",
    # 风险调整
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "information_ratio",
    "beta",
    "alpha",
    # 交易
    "win_rate",
    "profit_loss_ratio",
    "profit_factor",
    "avg_holding_days",
    "turnover_rate",
    # 综合
    "composite_score",
    "metrics_report",
    # 资金
    "north_bound_score",
    "main_capital_score",
    "margin_score",
    "dragon_tiger_score",
    "composite_capital_heat",
    # 舆情/情绪
    "text_sentiment",
    "batch_sentiment",
    "industry_boom_score",
    "macro_risk_score",
    "market_sentiment_index",
]

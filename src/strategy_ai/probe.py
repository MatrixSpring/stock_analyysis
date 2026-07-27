# -*- coding: utf-8 -*-
"""策略探针 — 识别策略表现不佳的时段和原因"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np

@dataclass
class WeaknessPoint:
    period: str; metric: str; severity: float; description: str
    possible_causes: List[str] = field(default_factory=list)

@dataclass
class ProbeReport:
    strategy_id: str; overall_weaknesses: List[WeaknessPoint] = field(default_factory=list)
    performance_breakdown: Dict[str, float] = field(default_factory=dict)
    stability_score: float = 0.0; robustness_score: float = 0.0
    sample_size: int = 0; warning: Optional[str] = None

class StrategyProbe:
    def __init__(self, backtest_engine=None):
        self._backtest = backtest_engine
        self._phases = {
            "bull": ("2020-04-01","2021-02-01"),
            "bear": ("2022-01-01","2022-10-01"),
            "consolidation": ("2021-03-01","2021-12-01"),
        }

    def probe(self, strategy: Dict[str, Any], backtest_fn=None) -> ProbeReport:
        fid = strategy.get("version_id", strategy.get("id", "unknown"))
        # Full backtest result from caller or stored
        full_result = strategy.get("evaluation_results", {})
        trades = full_result.get("trades", [])
        trade_count = full_result.get("total_trades", len(trades))

        weaknesses: List[WeaknessPoint] = []
        phase_returns: Dict[str, float] = {}
        full_return = full_result.get("total_return", 0)

        for phase, (start, end) in self._phases.items():
            phase_ret = full_result.get(f"phase_{phase}_return", full_return)
            phase_returns[phase] = phase_ret
            if phase_ret < full_return * 0.5 and phase_ret < 0:
                severity = min(1.0, abs(phase_ret - full_return) / max(abs(full_return), 1))
                causes = []
                if full_result.get("max_drawdown", 0) > full_result.get("max_drawdown_base", 0) * 1.5:
                    causes.append("回撤控制失效")
                if full_result.get("win_rate", 0) < full_result.get("win_rate_base", 0) * 0.6:
                    causes.append("胜率大幅下降")
                weaknesses.append(WeaknessPoint(
                    period=phase, metric="total_return", severity=severity,
                    description=f"{phase}阶段表现不佳", possible_causes=causes or ["市场环境不匹配"],
                ))

        stability = self._calc_stability(phase_returns)
        robustness = max(0, 1.0 - abs(min(phase_returns.values())) / 20) if phase_returns else 0.5
        warning = None
        if trade_count < 30: warning = f"样本量不足({trade_count}笔)"
        elif trade_count < 100: warning = f"样本量偏小({trade_count}笔)"

        return ProbeReport(strategy_id=fid, overall_weaknesses=weaknesses,
                          performance_breakdown=phase_returns,
                          stability_score=stability, robustness_score=robustness,
                          sample_size=trade_count, warning=warning)

    def _calc_stability(self, returns: Dict) -> float:
        vals = list(returns.values())
        if not vals or sum(vals) == 0: return 0.5
        cv = float(np.std(vals)) / (abs(np.mean(vals)) + 0.001)
        return max(0, 1.0 - min(1.0, cv))

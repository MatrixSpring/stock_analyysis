# -*- coding: utf-8 -*-
"""决策网关 — 严格控制策略准入"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
import numpy as np
from scipy import stats

@dataclass
class GateDecision:
    accepted: bool; score: float = 0.0
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)

class StrategyGateKeeper:
    def __init__(self, min_trades: int = 100, min_sharpe: float = 0.5,
                 max_dd: float = 0.3, sig_level: float = 0.05, oos_ratio: float = 0.3):
        self._min_trades = min_trades; self._min_sharpe = min_sharpe
        self._max_dd = max_dd; self._sig = sig_level; self._oos = oos_ratio

    def evaluate(self, version, backtest: Dict) -> GateDecision:
        passed, failed, reasons = [], [], []
        # 1. Sample size
        trades = backtest.get("total_trades", 0)
        (passed if trades >= self._min_trades else failed).append(f"样本量({trades})")
        if trades < self._min_trades: reasons.append("交易次数不足")
        # 2. Overfit
        ofs = self._detect_overfit(backtest)
        (passed if ofs < 0.3 else failed).append(f"过拟合({ofs:.2f})")
        if ofs >= 0.3: reasons.append("过拟合风险高")
        # 3. Significance
        sig = self._test_sig(backtest)
        (passed if sig else failed).append("显著性")
        if not sig: reasons.append("绩效统计不显著")
        # 4. Sharpe
        sr = backtest.get("sharpe_ratio", 0)
        (passed if sr >= self._min_sharpe else failed).append(f"夏普({sr:.2f})")
        if sr < self._min_sharpe: reasons.append("风险调整收益不足")
        # 5. Drawdown
        dd = backtest.get("max_drawdown", 0) / 100 if backtest.get("max_drawdown", 0) > 1 else backtest.get("max_drawdown", 0)
        (passed if dd <= self._max_dd else failed).append(f"回撤({dd:.1%})")
        if dd > self._max_dd: reasons.append("回撤超限")
        # Score
        total = len(passed) + len(failed)
        score = (len(passed) / max(1, total)) * 100
        actions = self._actions(failed)
        return GateDecision(accepted=len(failed) == 0, score=score,
                           checks_passed=passed, checks_failed=failed,
                           reasons=reasons, suggested_actions=actions)

    def _detect_overfit(self, results: Dict) -> float:
        trades = results.get("trades", [])
        if len(trades) < 30: return 0.5
        s = int(len(trades) * (1 - self._oos))
        ins = sum(t.get("return", 0) for t in trades[:s])
        out = sum(t.get("return", 0) for t in trades[s:])
        if abs(ins) < 0.001: return 0.5
        return min(1.0, abs(out / ins - 1))

    def _test_sig(self, results: Dict) -> bool:
        trades = results.get("trades", [])
        if len(trades) < 30: return False
        rets = [t.get("return", 0) for t in trades]
        means = [np.mean(np.random.choice(rets, len(rets))) for _ in range(500)]
        se = np.std(means) or 0.001
        return stats.norm.cdf(np.mean(rets) / se) > (1 - self._sig)

    def _actions(self, failed: List) -> List[str]:
        actions = []
        for f in failed:
            if "样本量" in f: actions.append("扩展回测区间")
            elif "过拟合" in f: actions.append("简化策略逻辑")
            elif "显著" in f: actions.append("寻找更强信号")
            elif "夏普" in f: actions.append("增加风控机制")
            elif "回撤" in f: actions.append("增加止损逻辑")
        return list(set(actions))

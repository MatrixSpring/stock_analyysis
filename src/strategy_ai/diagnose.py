# -*- coding: utf-8 -*-
"""策略诊断 — 分析策略失效的根本原因"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.strategy_ai.probe import ProbeReport

@dataclass
class DiagnosisResult:
    root_causes: List[str] = field(default_factory=list)
    factor_contributions: Dict[str, float] = field(default_factory=dict)
    regime_sensitivity: Dict[str, float] = field(default_factory=dict)
    stability_analysis: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    confidence_score: float = 0.5

class StrategyDiagnoser:
    def __init__(self, market_data_provider=None):
        self._market = market_data_provider

    def diagnose(self, strategy: Dict, probe: ProbeReport, backtest: Dict) -> DiagnosisResult:
        config = strategy.get("config", {})
        factors = config.get("factors", {"momentum": 0.3, "mean_reversion": 0.3, "quality": 0.2, "value": 0.2})
        regime = {p: r for p, r in probe.performance_breakdown.items()}
        root_causes: List[str] = []
        max_factor = max(factors.values()) if factors else 0
        if max_factor > 0.7: root_causes.append("因子过于集中，分散化不足")
        if probe.sample_size < 50: root_causes.append(f"样本量不足({probe.sample_size}笔)")
        if probe.stability_score < 0.4: root_causes.append("策略稳定性差")
        if not root_causes: root_causes.append("未检测到明显缺陷")
        recs = self._make_recommendations(root_causes, factors)
        stability = {"score": probe.stability_score, "robustness": probe.robustness_score}
        conf = min(1.0, 0.5 + (0.3 if probe.sample_size >= 200 else 0.1 if probe.sample_size >= 50 else 0) + (0.1 if probe.stability_score > 0.7 else 0) + (0.1 if probe.robustness_score > 0.7 else 0))
        return DiagnosisResult(root_causes=root_causes, factor_contributions=factors,
                               regime_sensitivity=regime, stability_analysis=stability,
                               recommendations=recs, confidence_score=conf)

    def _make_recommendations(self, causes: List, factors: Dict) -> List[str]:
        recs = []
        for c in causes:
            if "因子集中" in c: recs.extend(["增加因子维度", "使用因子正交化"])
            elif "样本量" in c: recs.extend(["扩展回测周期", "Bootstrap验证"])
            elif "稳定性" in c: recs.extend(["增加市场过滤", "动态参数调整"])
        return recs or ["策略表现稳定，继续监控"]

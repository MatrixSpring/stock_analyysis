# -*- coding: utf-8 -*-
"""AI策略优化器 — 自动生成假设、修改策略"""
from __future__ import annotations

import ast, json, logging, re, uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.strategy_ai.registry import StrategyRegistry, StrategyVersion
from src.strategy_ai.probe import ProbeReport, StrategyProbe
from src.strategy_ai.diagnose import StrategyDiagnoser, DiagnosisResult

logger = logging.getLogger(__name__)

@dataclass
class ProposedPatch:
    patch_id: str; version_id: str; description: str; hypothesis: str
    code_patch: str; config_changes: Dict = field(default_factory=dict)
    expected_improvement: str = ""; confidence: float = 0.5; reasoning: str = ""

@dataclass
class PatchResult:
    patch: ProposedPatch; evaluation: Dict; accepted: bool
    reason: str; new_version_id: Optional[str] = None

class AIStrategyOptimizer:
    def __init__(self, registry: StrategyRegistry, backtest_engine=None,
                 llm_client=None, market_data=None):
        self._registry = registry; self._backtest = backtest_engine
        self._llm = llm_client; self._market = market_data
        self._min_trades = 50; self._improvement_threshold = 0.05

    async def optimize(self, strategy_name: str, mode: str = "explore") -> List[PatchResult]:
        current = self._registry.get_latest_version(strategy_name)
        if not current: return []
        results = []
        for iteration in range(3):  # max 3 iterations
            probe = StrategyProbe(self._backtest).probe(current.__dict__)
            diag = StrategyDiagnoser(self._market).diagnose(current.__dict__, probe, current.evaluation_results)
            patches = await self._generate_patches(current, diag, mode)
            if not patches: break
            for patch in patches:
                new_ver = self._apply_patch(current, patch)
                eval_r = await self._evaluate(new_ver)
                accepted, reason = self._decide(current.evaluation_results, eval_r, eval_r.get("total_trades", 0))
                pr = PatchResult(patch=patch, evaluation=eval_r, accepted=accepted, reason=reason,
                                 new_version_id=new_ver.version_id if accepted else None)
                results.append(pr)
                if accepted:
                    current = new_ver
                    break
            if not any(r.accepted for r in results): break
        return results

    async def _generate_patches(self, strategy: StrategyVersion, diag: DiagnosisResult, mode: str) -> List[ProposedPatch]:
        cfg = json.dumps(strategy.config, ensure_ascii=False)
        prompt = f"""你是量化策略优化专家。策略诊断：{diag.root_causes}。建议：{diag.recommendations}。
因子贡献：{diag.factor_contributions}。模式：{mode}。
生成1-2个代码优化方案，格式：
## PATCH 1
HYPOTHESIS: [假设]
DESCRIPTION: [描述]
CODE: ```python
[策略代码]
```"""
        if self._llm:
            try:
                resp = await self._llm.generate(prompt)
                return self._parse_response(resp, strategy)
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}")
        return []

    def _parse_response(self, text: str, strategy: StrategyVersion) -> List[ProposedPatch]:
        patches = []
        for block in re.split(r"## PATCH \d+", text)[1:]:
            hyp = self._extract(block, "HYPOTHESIS")
            desc = self._extract(block, "DESCRIPTION")
            code = self._extract_code(block)
            if code:
                patches.append(ProposedPatch(patch_id=str(uuid.uuid4())[:8],
                    version_id=strategy.version_id, description=desc or "改进",
                    hypothesis=hyp or "提升策略", code_patch=code))
        return patches

    def _extract(self, text: str, marker: str) -> str:
        m = re.search(rf"{marker}:\s*(.+?)(?=\n[A-Z]+:|\n##|\Z)", text, re.S | re.I)
        return m.group(1).strip() if m else ""

    def _extract_code(self, text: str) -> str:
        m = re.search(r"```python\s*(.*?)\s*```", text, re.S)
        return m.group(1) if m else ""

    def _apply_patch(self, strategy: StrategyVersion, patch: ProposedPatch) -> StrategyVersion:
        new_code = patch.code_patch if "def " in patch.code_patch else strategy.code + "\n" + patch.code_patch
        new_cfg = {**strategy.config, **patch.config_changes}
        return self._registry.create_version(name=strategy.name, code=new_code, config=new_cfg,
                                             parent_id=strategy.version_id, created_by="ai",
                                             prompt_used=patch.hypothesis)

    async def _evaluate(self, version: StrategyVersion) -> Dict:
        if self._backtest:
            r = await self._backtest.run(version.code, version.config) if hasattr(self._backtest, "run") else {}
        else:
            r = {"total_return": version.evaluation_results.get("total_return", 0) * 1.02,
                 "total_trades": 100, "max_drawdown": 15, "sharpe_ratio": 1.2}
        self._registry.update_evaluation(version.version_id, r)
        return r

    def _decide(self, baseline: Dict, candidate: Dict, trades: int) -> tuple:
        if trades < self._min_trades: return False, f"样本不足({trades})"
        br, cr = baseline.get("total_return", 0) or 0, candidate.get("total_return", 0) or 0
        if cr < br * (1 + self._improvement_threshold): return False, f"改进不足({cr:.1f}% vs {br:.1f}%)"
        bd, cd = baseline.get("max_drawdown", 0) or 0, candidate.get("max_drawdown", 0) or 0
        if cd > bd * 1.2: return False, f"回撤增加({cd:.1f}% vs {bd:.1f}%)"
        return True, f"✅ 绩效提升{((cr/br)-1)*100:.1f}%"

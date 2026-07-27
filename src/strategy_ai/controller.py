# -*- coding: utf-8 -*-
"""
AI 策略研发主控制器
Probe → Diagnose → Propose → Patch → Evaluate → Decide
"""
from __future__ import annotations

import asyncio, logging, uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.strategy_ai.registry import StrategyRegistry
from src.strategy_ai.probe import StrategyProbe, ProbeReport
from src.strategy_ai.diagnose import StrategyDiagnoser, DiagnosisResult
from src.strategy_ai.optimizer import AIStrategyOptimizer, ProposedPatch, PatchResult
from src.strategy_ai.gatekeeper import StrategyGateKeeper, GateDecision

logger = logging.getLogger(__name__)

@dataclass
class EvolutionSession:
    session_id: str; strategy_id: str; start_version: str
    end_version: Optional[str] = None; iterations: int = 0
    patches_attempted: int = 0; patches_accepted: int = 0
    current_score: float = 0.0; status: str = "running"
    history: List[Dict] = field(default_factory=list)

class AIStrategyController:
    def __init__(self, registry: StrategyRegistry, backtest_engine=None,
                 llm_client=None, market_data=None, max_iterations: int = 5):
        self._registry = registry; self._backtest = backtest_engine
        self._llm = llm_client; self._market = market_data
        self._max_iter = max_iterations
        self._probe = StrategyProbe(backtest_engine)
        self._diagnoser = StrategyDiagnoser(market_data)
        self._optimizer = AIStrategyOptimizer(registry, backtest_engine, llm_client, market_data)
        self._gatekeeper = StrategyGateKeeper()
        self._sessions: Dict[str, EvolutionSession] = {}

    async def evolve(self, strategy_name: str, mode: str = "explore",
                     max_iterations: int = None) -> EvolutionSession:
        current = self._registry.get_latest_version(strategy_name)
        if not current: raise ValueError(f"Strategy '{strategy_name}' not found")

        sid = str(uuid.uuid4())[:8]
        session = EvolutionSession(session_id=sid, strategy_id=strategy_name,
                                   start_version=current.version_id, status="running")
        self._sessions[sid] = session
        max_iter = max_iterations or self._max_iter
        logger.info(f"Evolution session {sid} started for {strategy_name}")

        for i in range(max_iter):
            session.iterations = i + 1
            try:
                probe = self._probe.probe(current.__dict__)
                diag = self._diagnoser.diagnose(current.__dict__, probe, current.evaluation_results)
                patches = await self._optimizer._generate_patches(current, diag, mode)
                if not patches: break
                session.patches_attempted += len(patches)
                for patch in patches:
                    new_ver = self._optimizer._apply_patch(current, patch)
                    eval_r = await self._optimizer._evaluate(new_ver)
                    gd = self._gatekeeper.evaluate(new_ver, eval_r)
                    session.history.append({
                        "iteration": i + 1, "patch_id": patch.patch_id,
                        "hypothesis": patch.hypothesis, "evaluation": eval_r,
                        "gate_decision": gd.__dict__,
                    })
                    if gd.accepted:
                        current = new_ver; session.patches_accepted += 1
                        session.current_score = gd.score
                        session.end_version = current.version_id
                        logger.info(f"Patch {patch.patch_id} accepted: score={gd.score:.0f}")
                        break
                    logger.info(f"Patch {patch.patch_id} rejected: {gd.reasons}")
                if session.current_score >= 90: break
            except Exception as e:
                logger.error(f"Iteration {i+1} failed: {e}")
                session.status = "failed"
                return session

        session.status = "completed"
        session.end_version = session.end_version or current.version_id
        logger.info(f"Evolution complete: {session.patches_accepted}/{session.patches_attempted} accepted")
        return session

    def get_session(self, sid: str) -> Optional[EvolutionSession]:
        return self._sessions.get(sid)

    def list_sessions(self) -> List[Dict]:
        return [{"id": s.session_id, "strategy": s.strategy_id, "status": s.status,
                 "iterations": s.iterations, "accepted": s.patches_accepted,
                 "score": s.current_score} for s in self._sessions.values()]

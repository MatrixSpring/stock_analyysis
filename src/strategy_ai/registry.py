# -*- coding: utf-8 -*-
"""策略注册表 — 版本管理与血缘追踪"""
from __future__ import annotations

import json, logging, uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class StrategyVersion:
    version_id: str; parent_id: Optional[str] = None; name: str = ""
    code: str = ""; config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""; created_by: str = "human"
    generation: int = 1; prompt_used: Optional[str] = None
    evaluation_results: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StrategyBloodline:
    root_id: str = ""; current_id: str = ""
    lineage: List[str] = field(default_factory=list)
    improvements: List[Dict[str, Any]] = field(default_factory=list)

class StrategyRegistry:
    def __init__(self, mongo_db=None, redis_client=None):
        self._mongo, self._redis = mongo_db, redis_client
        self._versions: Dict[str, StrategyVersion] = {}
        self._bloodlines: Dict[str, StrategyBloodline] = {}
        self._by_name: Dict[str, List[str]] = {}

    def create_version(self, name: str, code: str, config: Dict,
                       parent_id: str = None, created_by: str = "human",
                       prompt_used: str = None) -> StrategyVersion:
        gen = self._versions[parent_id].generation + 1 if parent_id and parent_id in self._versions else 1
        v = StrategyVersion(version_id=str(uuid.uuid4())[:8], parent_id=parent_id,
                           name=name, code=code, config=config,
                           created_at=datetime.utcnow().isoformat(),
                           created_by=created_by, generation=gen, prompt_used=prompt_used)
        self._versions[v.version_id] = v
        self._by_name.setdefault(name, []).append(v.version_id)
        if parent_id: self._update_bloodline(parent_id, v.version_id)
        else: self._bloodlines[v.version_id] = StrategyBloodline(
            root_id=v.version_id, current_id=v.version_id, lineage=[v.version_id])
        return v

    def update_evaluation(self, version_id: str, results: Dict):
        v = self._versions.get(version_id)
        if v: v.evaluation_results = results
        bl = self._find_bloodline(version_id)
        if bl: bl.improvements.append({"version_id": version_id, "metrics": results,
                                       "timestamp": datetime.utcnow().isoformat()})

    def get_latest_version(self, name: str) -> Optional[StrategyVersion]:
        ids = self._by_name.get(name, [])
        if not ids: return None
        vs = sorted([self._versions[i] for i in ids if i in self._versions],
                    key=lambda x: x.generation, reverse=True)
        return vs[0] if vs else None

    def get_version(self, vid: str) -> Optional[StrategyVersion]:
        return self._versions.get(vid)

    def get_bloodline(self, root_id: str) -> Optional[StrategyBloodline]:
        return self._bloodlines.get(root_id)

    def compare_versions(self, a: str, b: str) -> Dict:
        va, vb = self._versions.get(a), self._versions.get(b)
        if not va or not vb: return {"error": "not found"}
        delta = {}
        for m in ("total_return","sharpe_ratio","max_drawdown","win_rate"):
            av = va.evaluation_results.get(m,0) or 0
            bv = vb.evaluation_results.get(m,0) or 0
            if av: delta[m] = {"from":av,"to":bv,"pct":round((bv-av)/abs(av)*100,1)}
        return {"version_a":a,"version_b":b,"performance_delta":delta}

    def _find_bloodline(self, vid: str) -> Optional[StrategyBloodline]:
        for bl in self._bloodlines.values():
            if bl.current_id == vid: return bl
        for bl in self._bloodlines.values():
            if vid in bl.lineage: return bl
        return None

    def _update_bloodline(self, pid: str, cid: str):
        bl = self._find_bloodline(pid)
        if bl: bl.current_id = cid; bl.lineage.append(cid)
        else: self._bloodlines[cid] = StrategyBloodline(root_id=pid, current_id=cid, lineage=[pid,cid])

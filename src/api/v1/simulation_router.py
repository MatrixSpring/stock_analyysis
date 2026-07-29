"""冲击推演 API — BFS 传导路径计算 + 事件管理"""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/simulation", tags=["冲击推演"])

# ---- 内置产业链数据 ----
INDUSTRY_EDGES = [
    {"source": "li_ore", "target": "carbonate", "edgeType": "COST_TRANSFER", "coeff": 0.82, "time_lag": "1~2月", "time_lag_days": 45},
    {"source": "cobalt", "target": "ternary", "edgeType": "COST_TRANSFER", "coeff": 0.75, "time_lag": "1~2月", "time_lag_days": 40},
    {"source": "carbonate", "target": "ternary", "edgeType": "COST_TRANSFER", "coeff": 0.68, "time_lag": "20~40天", "time_lag_days": 30},
    {"source": "ternary", "target": "battery", "edgeType": "COST_TRANSFER", "coeff": 0.55, "time_lag": "15天", "time_lag_days": 15},
    {"source": "battery", "target": "ev", "edgeType": "COST_TRANSFER", "coeff": 0.42, "time_lag": "1个月", "time_lag_days": 30},
    {"source": "ev", "target": "battery", "edgeType": "DEMAND_DRIVE", "coeff": 0.76, "time_lag": "1~3月", "time_lag_days": 60},
]

EVENTS = [
    {"event_id": "sim001", "title": "澳洲锂矿出口限制加剧", "event_type": "geopolitics", "direction": "negative", "target_node": "li_ore"},
    {"event_id": "sim002", "title": "新能源车刺激政策落地", "event_type": "policy", "direction": "positive", "target_node": "ev"},
    {"event_id": "sim003", "title": "市场流动性收紧", "event_type": "liquidity", "direction": "negative", "target_node": "ev"},
]


class SimulateRequest(BaseModel):
    rootNodeId: str = "li_ore"
    baseStrength: float = Field(0.8, ge=0, le=1)
    minCoeffFilter: float = Field(0.15, ge=0, le=1)
    maxLevel: int = Field(6, ge=1, le=10)


class SpreadRecord(BaseModel):
    root_id: str = ""
    source_id: str
    target_id: str
    edge_type: str
    single_coeff: float
    total_coeff: float
    final_impact_strength: float
    total_lag_days: int
    step: int


@router.post("/calcPath", response_model=List[SpreadRecord])
def calc_path(req: SimulateRequest):
    """BFS 传导路径计算 — 按 total_lag_days 排序"""
    adj = {}
    for e in INDUSTRY_EDGES:
        adj.setdefault(e["source"], []).append(e)
        adj.setdefault(e["target"], [])

    results, visited = [], {req.rootNodeId}
    queue = [(req.rootNodeId, 0, 1.0, 0)]

    while queue:
        current, step, total_c, total_d = queue.pop(0)
        if step >= req.maxLevel:
            continue
        for edge in adj.get(current, []):
            nxt = edge["target"]
            if nxt in visited:
                continue
            visited.add(nxt)
            new_c = total_c * edge["coeff"]
            new_d = total_d + edge.get("time_lag_days", 30)
            if new_c < req.minCoeffFilter:
                continue
            results.append(SpreadRecord(
                root_id=req.rootNodeId, source_id=current, target_id=nxt,
                edge_type=edge["edgeType"], single_coeff=edge["coeff"],
                total_coeff=round(new_c, 4),
                final_impact_strength=round(req.baseStrength * new_c, 4),
                total_lag_days=new_d, step=step + 1,
            ))
            queue.append((nxt, step + 1, new_c, new_d))

    results.sort(key=lambda r: r.total_lag_days)
    return results


@router.get("/event_root")
def get_event_root(eventId: str):
    for ev in EVENTS:
        if ev["event_id"] == eventId:
            return {"nodeId": ev["target_node"], "nodeName": ev["title"]}
    raise HTTPException(status_code=404)


@router.get("/events")
def list_events():
    return EVENTS


class FactorRequest(BaseModel):
    event_title: str = "美国芯片出口限制升级"
    target_node: str = "n_upstream_GPU芯片"
    factors: dict = Field(default_factory=lambda: {"policy": 8, "game": 3, "sentiment": 5, "capital": 4, "geo": 7})
    chain_name: str = "AI算力"


@router.post("/factor/analyze")
def factor_analyze(req: FactorRequest):
    """多因子加权传导分析 — 返回溯源日志+三级穿透"""
    from src.service.chain_factor_engine import get_factor_engine
    engine = get_factor_engine()
    result = engine.calculate(req.event_title, req.target_node, req.factors, req.chain_name)
    return {
        "steps": [
            {"type": s.type, "title": s.title, "detail": s.detail,
             "impact": s.impact, "coeff": s.coeff, "time": s.time}
            for s in result.steps
        ],
        "tier1_nodes": result.tier1_nodes,
        "tier2_sectors": result.tier2_sectors,
        "tier3_stocks": result.tier3_stocks,
        "total_impact": result.total_impact,
        "dominant_factor": result.dominant_factor,
    }

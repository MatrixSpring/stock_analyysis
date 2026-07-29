"""
产业链冲击推演沙盘 — FastAPI + Neo4j (SQLite 降级)
启动: uvicorn sim_backend.main:app --port 8001 --reload
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sim_backend.config import settings

app = FastAPI(title="产业链冲击推演沙盘后端")

# ============================================================
# Neo4j 驱动（按需初始化）
# ============================================================
_neo4j_driver = None


def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None and settings.USE_NEO4J:
        try:
            from neo4j import GraphDatabase, basic_auth
            _neo4j_driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=basic_auth(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        except Exception:
            _neo4j_driver = None
    return _neo4j_driver


# ============================================================
# SQLite 内置产业链数据（降级模式，无需 Neo4j）
# ============================================================

INDUSTRY_NODES = [
    {"id": "li_ore", "label": "锂矿", "nodeType": "upstream", "marketScale": "约890亿", "pricingPower": "强",
     "middleFactor": None},
    {"id": "cobalt", "label": "钴矿", "nodeType": "upstream", "marketScale": "约420亿", "pricingPower": "中",
     "middleFactor": None},
    {"id": "carbonate", "label": "碳酸锂", "nodeType": "midstream", "marketScale": "2100亿", "pricingPower": "强",
     "middleFactor": {"name": "碳酸锂现货价格", "indicator": "上涨18%"}},
    {"id": "ternary", "label": "三元正极", "nodeType": "midstream", "marketScale": "3600亿", "pricingPower": "中",
     "middleFactor": None},
    {"id": "battery", "label": "动力电池", "nodeType": "midstream", "marketScale": "8500亿", "pricingPower": "中",
     "middleFactor": None},
    {"id": "ev", "label": "新能源整车", "nodeType": "downstream", "marketScale": "3.2万亿", "pricingPower": "分化",
     "middleFactor": None},
]

COMPANY_NODES = [
    {"id": "CATL", "label": "宁德时代", "stock_code": "300750", "belongs_to": "battery"},
    {"id": "BYD", "label": "比亚迪", "stock_code": "002594", "belongs_to": "ev"},
]

INDUSTRY_EDGES = [
    {"source": "li_ore", "target": "carbonate", "edgeType": "COST_TRANSFER", "coeff": 0.82, "time_lag": "1~2月",
     "time_lag_days": 45},
    {"source": "cobalt", "target": "ternary", "edgeType": "COST_TRANSFER", "coeff": 0.75, "time_lag": "1~2月",
     "time_lag_days": 40},
    {"source": "carbonate", "target": "ternary", "edgeType": "COST_TRANSFER", "coeff": 0.68, "time_lag": "20~40天",
     "time_lag_days": 30},
    {"source": "ternary", "target": "battery", "edgeType": "COST_TRANSFER", "coeff": 0.55, "time_lag": "15天",
     "time_lag_days": 15},
    {"source": "battery", "target": "ev", "edgeType": "COST_TRANSFER", "coeff": 0.42, "time_lag": "1个月",
     "time_lag_days": 30},
    {"source": "ev", "target": "battery", "edgeType": "DEMAND_DRIVE", "coeff": 0.76, "time_lag": "1~3月",
     "time_lag_days": 60},
]

EVENTS = [
    {"event_id": "sim001", "title": "澳洲锂矿出口限制加剧", "event_type": "geopolitics", "direction": "negative",
     "target_node": "li_ore"},
    {"event_id": "sim002", "title": "新能源车刺激政策落地", "event_type": "policy", "direction": "positive",
     "target_node": "ev"},
    {"event_id": "sim003", "title": "市场流动性收紧", "event_type": "liquidity", "direction": "negative",
     "target_node": "ev"},
]


# ============================================================
# Pydantic 模型
# ============================================================

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


# ============================================================
# 接口 1: 产业链图谱数据
# ============================================================

@app.get("/api/industry/chain")
def get_chain_data(chainId: str = "li_battery"):
    nodes = [dict(n) for n in INDUSTRY_NODES]
    for c in COMPANY_NODES:
        nodes.append({"id": c["id"], "label": c["label"], "nodeType": "company", "events": []})
    edges = [
        {"source": e["source"], "target": e["target"],
         "edgeType": _edge_type_label(e["edgeType"]),
         "coeff": e["coeff"], "timeLag": e["time_lag"]}
        for e in INDUSTRY_EDGES
    ]
    for c in COMPANY_NODES:
        edges.append({"source": c["id"], "target": c["belongs_to"], "edgeType": "", "coeff": 0, "timeLag": ""})
    return {"nodes": nodes, "edges": edges}


def _edge_type_label(t: str) -> str:
    m = {"COST_TRANSFER": "cost", "DEMAND_DRIVE": "demand", "SUBSTITUTE": "substitute",
         "SUPPLY_CONSTRAINT": "supply"}
    return m.get(t, "")


# ============================================================
# 接口 2: 冲击推演路径计算 ⭐核心
# ============================================================

@app.post("/api/simulation/calcPath", response_model=List[SpreadRecord])
def calc_simulation_path(req: SimulateRequest):
    driver = get_neo4j_driver()
    if driver:
        return _calc_neo4j(req)
    return _calc_sqlite(req)


def _calc_neo4j(req: SimulateRequest) -> List[SpreadRecord]:
    """Neo4j + APOC 路径遍历"""
    driver = get_neo4j_driver()
    if not driver:
        return []
    cypher = """
    MATCH startNode:Industry{id:$rootId}
    CALL apoc.path.expandConfig(startNode,{
        relationshipFilter:"COST_TRANSFER>|DEMAND_DRIVE>|SUBSTITUTE>|SUPPLY_CONSTRAINT>",
        maxLevel:$maxLevel, uniqueness:"NODE_GLOBAL"
    }) YIELD path
    WITH path, relationships(path) AS rels, nodes(path) AS nodes
    WITH nodes[-2] AS src, nodes[-1] AS tgt, rels[-1] AS e, length(path) AS step,
         reduce(tc=1.0, r IN rels | tc * r.coeff) AS total_c,
         reduce(td=0, r IN rels | td + r.time_lag_days) AS total_d
    WHERE total_c > $minCoeff
    RETURN startNode.id AS root_id, src.id AS source_id, tgt.id AS target_id,
           type(e) AS edge_type, e.coeff AS single_coeff, total_c AS total_coeff,
           $baseStrength * total_c AS final_impact_strength, total_d AS total_lag_days, step
    ORDER BY total_lag_days
    """
    params = {"rootId": req.rootNodeId, "maxLevel": req.maxLevel,
              "minCoeff": req.minCoeffFilter, "baseStrength": req.baseStrength}
    with driver.session() as session:
        rows = session.run(cypher, params)
        return [SpreadRecord(root_id=r["root_id"], source_id=r["source_id"], target_id=r["target_id"],
                             edge_type=r["edge_type"], single_coeff=r["single_coeff"],
                             total_coeff=r["total_coeff"],
                             final_impact_strength=r["final_impact_strength"],
                             total_lag_days=r["total_lag_days"], step=r["step"]) for r in rows]


def _calc_sqlite(req: SimulateRequest) -> List[SpreadRecord]:
    """SQLite 降级：BFS 在图数据内存中计算"""
    adj = {}
    for e in INDUSTRY_EDGES:
        adj.setdefault(e["source"], []).append(e)
        adj.setdefault(e["target"], [])

    results = []
    visited = {req.rootNodeId}
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


# ============================================================
# 接口 3: 事件查询冲击起点
# ============================================================

@app.get("/api/simulation/event_root")
def get_event_impact_node(eventId: str):
    for ev in EVENTS:
        if ev["event_id"] == eventId:
            return {"nodeId": ev["target_node"], "nodeName": ev["title"]}
    raise HTTPException(status_code=404, detail="事件不存在")


# ============================================================
# 接口 4: 事件列表
# ============================================================

@app.get("/api/simulation/events")
def list_events():
    return [{
        "event_id": e["event_id"], "title": e["title"],
        "event_type": e["event_type"], "direction": e["direction"],
        "target_node": e["target_node"],
    } for e in EVENTS]


@app.on_event("shutdown")
def close():
    global _neo4j_driver
    if _neo4j_driver:
        _neo4j_driver.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("sim_backend.main:app", host="0.0.0.0", port=8001, reload=True)

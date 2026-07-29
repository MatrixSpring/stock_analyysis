"""产业链图谱 API — G6/ECharts 图数据接口"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List
from src.api.response import ApiResp
from src.service.chain_graph_engine import ImpactEvent, get_graph_engine

router = APIRouter(prefix="/graph", tags=["产业链图谱"])

engine = get_graph_engine()


class ImpactEventRequest(BaseModel):
    title: str
    category: str = "舆情事件"
    direction: str = "negative"
    strength: float = 5.0
    target_nodes: List[str] = []
    credibility: float = 0.8


@router.get("/data/{chain_name}", summary="获取产业链图数据 (nodes+edges)")
async def get_graph(chain_name: str):
    data = engine.get_graph_data(chain_name)
    return ApiResp.ok(data=data)


@router.post("/impact/{chain_name}", summary="应用外部事件冲击 → 返回动画帧")
async def apply_impact(chain_name: str, req: ImpactEventRequest):
    event = ImpactEvent(
        event_id=f"evt_{__import__('time').time()}",
        title=req.title,
        category=req.category,
        direction=req.direction,
        strength=req.strength,
        target_nodes=req.target_nodes,
        credibility=req.credibility,
    )
    engine.add_event(event)
    result = engine.apply_event_impact(chain_name, event)
    return ApiResp.ok(data=result)


@router.get("/events", summary="获取外部事件列表")
async def list_events(category: str = ""):
    return ApiResp.ok(data=engine.list_events(category))


@router.get("/snapshot/{chain_name}", summary="导出图谱快照 JSON")
async def export_snapshot(chain_name: str):
    return ApiResp.ok(data={"json": engine.export_snapshot(chain_name)})

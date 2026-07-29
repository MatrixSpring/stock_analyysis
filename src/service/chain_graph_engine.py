"""
产业链图谱引擎 — Graph Schema + 外部事件融合 + 传导动画数据
对标: Wind产业链 / 同花顺iFinD / MSCI供应链图谱
输出: G6/ECharts 兼容的 {nodes, edges} 结构
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.cache import cache
from src.core.tracer import trace_cost

logger = logging.getLogger(__name__)

CHAIN_DATA_FILE = Path("data/industry_chains.json")

# ============================================================
# Graph Schema — 四类实体 + 传导边
# ============================================================

# 连线视觉映射
EDGE_STYLE_MAP = {
    "成本传导": {"lineType": "solid", "color": "#6096FF", "label": "C"},
    "需求拉动": {"lineType": "solid", "color": "#36CFC9", "label": "D"},
    "替代竞争": {"lineType": "dashed", "color": "#FF7D00", "label": "S"},
    "供给约束": {"lineType": "solid", "color": "#F53F3F", "label": "Sup", "lineWidth": 3},
}

# 节点类型视觉
NODE_STYLE_MAP = {
    "industry": {"shape": "rect", "size": 60},
    "company": {"shape": "circle", "size": 30},
    "impact_factor": {"shape": "diamond", "size": 40},
    "intermediate": {"shape": "roundRect", "size": 20},
}


@dataclass
class GraphNode:
    id: str
    name: str
    node_type: str  # industry / company / impact_factor / intermediate
    segment: str = ""  # upstream / midstream / downstream
    props: Dict[str, Any] = field(default_factory=dict)
    x: Optional[float] = None
    y: Optional[float] = None
    impact_score: float = 0.0  # 冲击影响值 (-10 ~ +10)
    style: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)  # 🆕 外部事件标记

    def to_dict(self) -> dict:
        style = NODE_STYLE_MAP.get(self.node_type, {})
        color = "#22c55e" if self.impact_score > 3 else ("#ef4444" if self.impact_score < -3 else "#64748B")
        if self.impact_score == 0:
            color = style.get("color", "#94A3B8")
        return {
            "id": self.id, "name": self.name, "type": self.node_type,
            "segment": self.segment, "x": self.x, "y": self.y,
            "impact_score": self.impact_score,
            "style": {
                "fill": color, "stroke": color,
                "shape": style.get("shape", "rect"),
                "size": style.get("size", 50),
                **self.style,
            },
            "props": self.props,
            "events": self.events,  # 🆕
        }


@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    edge_type: str  # 成本传导 / 需求拉动 / 替代竞争 / 供给约束
    direction: str = "正向"
    transmission_coeff: float = 0.5
    time_lag: str = "3~15个交易日"
    description: str = ""
    is_impact_path: bool = False  # 冲击传播路径高亮

    def to_dict(self) -> dict:
        style = EDGE_STYLE_MAP.get(self.edge_type, {})
        return {
            "id": self.id, "source": self.source, "target": self.target,
            "edge_type": self.edge_type, "direction": self.direction,
            "transmission_coeff": self.transmission_coeff,
            "time_lag": self.time_lag, "description": self.description,
            "is_impact_path": self.is_impact_path,
            "style": {
                "stroke": style.get("color", "#666"),
                "lineWidth": style.get("lineWidth", 2),
                "lineDash": [8, 4] if style.get("lineType") == "dashed" else None,
                "label": style.get("label", ""),
            },
        }


@dataclass
class ImpactEvent:
    """外部冲击因子"""
    event_id: str
    title: str
    category: str  # 产业政策 / 舆情事件 / 宏观资金 / 地缘政治
    direction: str  # positive / negative
    strength: float  # 1-10
    target_nodes: List[str] = field(default_factory=list)
    source_url: str = ""
    credibility: float = 0.8
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id, "title": self.title,
            "category": self.category, "direction": self.direction,
            "strength": self.strength, "target_nodes": self.target_nodes,
            "credibility": self.credibility, "timestamp": self.timestamp,
        }


# ============================================================
# 图引擎
# ============================================================

class ChainGraphEngine:
    """产业链图谱引擎 — 构建 nodes/edges + 事件传导"""

    def __init__(self):
        self._chains: Dict[str, dict] = {}
        self._events: List[ImpactEvent] = []
        self._load()

    def _load(self):
        if CHAIN_DATA_FILE.exists():
            try:
                self._chains = json.loads(CHAIN_DATA_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._chains = {}

    def _build_default_edges(self, chain: dict) -> List[GraphEdge]:
        """从链的上下游关系自动构建边"""
        edges = []
        nodes = chain.get("nodes", {})

        # 上游 → 中游
        upstream = [nid for nid, n in nodes.items() if n.get("segment") == "upstream"]
        midstream = [nid for nid, n in nodes.items() if n.get("segment") == "midstream"]
        downstream = [nid for nid, n in nodes.items() if n.get("segment") == "downstream"]

        for u in upstream:
            for m in midstream:
                edges.append(GraphEdge(
                    id=f"e_{u}_{m}", source=u, target=m,
                    edge_type="成本传导", transmission_coeff=0.8,
                    description="上游→中游成本传导",
                ))
        for m in midstream:
            for d in downstream:
                edges.append(GraphEdge(
                    id=f"e_{m}_{d}", source=m, target=d,
                    edge_type="需求拉动", transmission_coeff=0.6,
                    description="中游→下游需求拉动",
                ))
        return edges

    def _ensure_nodes_format(self, chain: dict) -> dict:
        """兼容旧格式：从 upstream/midstream/downstream 列表自动生成 nodes"""
        if chain.get("nodes"):
            return chain
        key_stocks = chain.get("key_stocks", {})
        nodes = {}
        for seg in ("upstream", "midstream", "downstream"):
            for name in chain.get(seg, []):
                nid = f"n_{seg}_{name}"
                nodes[nid] = {
                    "name": name, "segment": seg,
                    "stock_codes": key_stocks.get(name, []), "weight": 1.0,
                }
        chain["nodes"] = nodes
        return chain

    @trace_cost("get_graph_data")
    def get_graph_data(self, chain_name: str) -> dict:
        """获取完整图数据 — G6/ECharts 直接消费"""
        chain = self._chains.get(chain_name, {})
        if not chain:
            return {"nodes": [], "edges": []}
        chain = self._ensure_nodes_format(chain)

        nodes = []
        seg_x = {"upstream": 200, "midstream": 500, "downstream": 800}
        seg_y_base = {"upstream": 100, "midstream": 100, "downstream": 100}
        seg_count = {"upstream": 0, "midstream": 0, "downstream": 0}

        for nid, n in chain.get("nodes", {}).items():
            seg = n.get("segment", "midstream")
            y = seg_y_base[seg] + seg_count[seg] * 80
            seg_count[seg] += 1
            nodes.append(GraphNode(
                id=nid, name=n.get("name", nid),
                node_type="industry", segment=seg,
                props={"stocks": n.get("stock_codes", []), "weight": n.get("weight", 1.0)},
                x=seg_x[seg], y=y,
            ))

        edges = self._build_default_edges(chain)
        # 追加自定义边
        for e in chain.get("custom_edges", []):
            edges.append(GraphEdge(**e))

        return {
            "chain_name": chain_name,
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def apply_event_impact(self, chain_name: str, event: ImpactEvent) -> dict:
        """将外部事件应用到图谱 — BFS 传导 + 返回动画帧"""
        graph = self.get_graph_data(chain_name)
        if not graph["nodes"]:
            return graph

        node_map = {n["id"]: n for n in graph["nodes"]}
        edge_map: Dict[str, list] = {}
        for e in graph["edges"]:
            edge_map.setdefault(e["source"], []).append(e)

        # BFS 传导
        frames = []  # 动画帧序列
        visited = set()
        queue = [(tid, 0, event.strength) for tid in event.target_nodes if tid in node_map]

        while queue:
            current, depth, strength = queue.pop(0)
            if current in visited or depth > 3:
                continue
            visited.add(current)
            decay = (1 - 0.2) ** depth
            impact = strength * decay * (1 if event.direction == "positive" else -1)

            node_map[current]["impact_score"] = round(impact, 2)
            frames.append({
                "node_id": current,
                "depth": depth,
                "impact": round(impact, 2),
                "timestamp_ms": depth * 800,  # 每层延迟 800ms
            })

            for edge in edge_map.get(current, []):
                edge["is_impact_path"] = True
                target = edge["target"]
                if target not in visited:
                    queue.append((target, depth + 1, strength))

        graph["impact_event"] = event.to_dict()
        graph["animation_frames"] = frames
        graph["benefited"] = [n["id"] for n in graph["nodes"] if n["impact_score"] > 1]
        graph["damaged"] = [n["id"] for n in graph["nodes"] if n["impact_score"] < -1]
        return graph

    def add_event(self, event: ImpactEvent):
        self._events.append(event)

    def list_events(self, category: str = "") -> List[dict]:
        events = self._events
        if category:
            events = [e for e in events if e.category == category]
        return [e.to_dict() for e in events]

    def export_snapshot(self, chain_name: str) -> str:
        """导出图谱快照 JSON"""
        return json.dumps(self.get_graph_data(chain_name), ensure_ascii=False, indent=2)


# 单例
_engine: Optional[ChainGraphEngine] = None


def get_graph_engine() -> ChainGraphEngine:
    global _engine
    if _engine is None:
        _engine = ChainGraphEngine()
    return _engine

"""
产业链管理服务 — 节点 CRUD + 外部事件影响力计算 + 传导推演
业界方案：ECharts tree 显示 + 图数据库存储 + LLM 事件引擎
"""

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
# 数据模型
# ============================================================

@dataclass
class ChainNode:
    """产业链节点"""
    id: str                                    # 唯一标识
    name: str                                  # 显示名
    segment: str                               # upstream / midstream / downstream
    parent_id: Optional[str] = None            # 父节点 ID
    stock_codes: List[str] = field(default_factory=list)
    weight: float = 1.0                        # 节点权重
    description: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "segment": self.segment,
            "parent_id": self.parent_id, "stock_codes": self.stock_codes,
            "weight": self.weight, "description": self.description,
            "custom_fields": self.custom_fields,
        }


@dataclass
class ExternalEvent:
    """外部影响事件"""
    event_id: str
    title: str
    direction: str              # positive / negative
    impact_strength: float      # 1-10
    target_nodes: List[str]     # 受影响的节点 ID 列表
    impact_radius: int = 1      # 传导层级数（1=直接, 2=间接, 3=全链）
    decay_rate: float = 0.2     # 每层衰减率
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = ""            # 事件来源

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id, "title": self.title,
            "direction": self.direction, "impact_strength": self.impact_strength,
            "target_nodes": self.target_nodes, "impact_radius": self.impact_radius,
            "decay_rate": self.decay_rate, "timestamp": self.timestamp, "source": self.source,
        }


@dataclass
class ImpactResult:
    """传导计算结果"""
    node_id: str
    node_name: str
    final_impact: float          # 最终影响力（经过衰减）
    distance: int                # 距事件源的距离
    intermediate_path: List[str] = field(default_factory=list)
    affected_stocks: List[str] = field(default_factory=list)


# ============================================================
# 产业链服务
# ============================================================

class IndustryChainService:
    """
    产业链管理 + 外部事件传导引擎。

    使用方式:
        svc = IndustryChainService()
        chain = svc.load_chain("光伏")
        svc.add_node(chain, ChainNode(...))
        results = svc.calculate_event_impact(chain, event)
    """

    def __init__(self):
        self._chains: Dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        if CHAIN_DATA_FILE.exists():
            try:
                self._chains = json.loads(CHAIN_DATA_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._chains = {}

    def _save_all(self):
        CHAIN_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHAIN_DATA_FILE.write_text(json.dumps(self._chains, ensure_ascii=False, indent=2))

    # ---- 链管理 ----

    def list_chains(self) -> List[str]:
        return list(self._chains.keys())

    def load_chain(self, name: str) -> Optional[dict]:
        return deepcopy(self._chains.get(name))

    @trace_cost("save_chain")
    def save_chain(self, name: str, chain: dict):
        self._chains[name] = chain
        self._save_all()
        cache.delete(f"chain:{name}")
        logger.info(f"[Chain] 已保存: {name}")

    def create_chain(self, name: str, description: str = "") -> dict:
        chain = {
            "name": name, "description": description,
            "upstream": [], "midstream": [], "downstream": [],
            "nodes": {}, "key_stocks": {},
            "created_at": datetime.now().isoformat(),
        }
        self._chains[name] = chain
        self._save_all()
        return chain

    # ---- 节点 CRUD ----

    def add_node(self, chain_name: str, node: ChainNode) -> dict:
        chain = self.load_chain(chain_name) or self.create_chain(chain_name)
        # 同步到旧格式（兼容） + 新格式（nodes 字典）
        chain["nodes"][node.id] = node.to_dict()
        if node.segment in ("upstream", "midstream", "downstream"):
            seg_list = chain.setdefault(node.segment, [])
            if node.name not in seg_list:
                seg_list.append(node.name)
        if node.stock_codes:
            chain.setdefault("key_stocks", {})[node.name] = node.stock_codes
        self.save_chain(chain_name, chain)
        return chain

    def update_node(self, chain_name: str, node_id: str, updates: dict) -> Optional[dict]:
        chain = self.load_chain(chain_name)
        if not chain or node_id not in chain.get("nodes", {}):
            return None
        chain["nodes"][node_id].update(updates)
        # 同步 name → segment list
        node = chain["nodes"][node_id]
        if node.get("stock_codes"):
            chain.setdefault("key_stocks", {})[node["name"]] = node["stock_codes"]
        self.save_chain(chain_name, chain)
        return chain

    def delete_node(self, chain_name: str, node_id: str) -> bool:
        chain = self.load_chain(chain_name)
        if not chain or node_id not in chain.get("nodes", {}):
            return False
        node = chain["nodes"].pop(node_id)
        for seg in ("upstream", "midstream", "downstream"):
            if node["name"] in chain.get(seg, []):
                chain[seg].remove(node["name"])
        chain.get("key_stocks", {}).pop(node["name"], None)
        # 清理孤儿引用
        for n in chain["nodes"].values():
            if n.get("parent_id") == node_id:
                n["parent_id"] = None
        self.save_chain(chain_name, chain)
        return True

    def reorder_node(self, chain_name: str, node_id: str, new_segment: str):
        """移动节点到不同的区段"""
        chain = self.load_chain(chain_name)
        if not chain or node_id not in chain.get("nodes", {}):
            return None
        node = chain["nodes"][node_id]
        old_seg = node["segment"]
        if old_seg in chain:
            chain[old_seg] = [x for x in chain.get(old_seg, []) if x != node["name"]]
        node["segment"] = new_segment
        chain.setdefault(new_segment, []).append(node["name"])
        self.save_chain(chain_name, chain)
        return chain

    # ---- 外部事件传导引擎（核心） ----

    @trace_cost("event_impact")
    def calculate_event_impact(
        self, chain_name: str, event: ExternalEvent
    ) -> List[ImpactResult]:
        """
        计算外部事件沿产业链的传导影响力。

        算法：BFS 从目标节点出发，每层衰减 decay_rate。
        上游冲击 → 中游衰减 20% → 下游衰减 40%

        Args:
            chain_name: 产业链名称
            event: 外部事件

        Returns:
            各节点的最终影响力列表
        """
        chain = self.load_chain(chain_name)
        if not chain:
            return []

        nodes = chain.get("nodes", {})
        # 构建邻接表
        adj: Dict[str, List[str]] = {}
        for nid, n in nodes.items():
            adj.setdefault(nid, [])
            pid = n.get("parent_id")
            if pid and pid in nodes:
                adj.setdefault(pid, []).append(nid)

        results = []
        visited = set()

        # BFS 从每个目标节点出发
        for target_id in event.target_nodes:
            if target_id not in nodes:
                continue
            queue = [(target_id, 0, [target_id])]  # (node_id, distance, path)
            while queue:
                current, dist, path = queue.pop(0)
                if current in visited:
                    continue
                if dist > event.impact_radius:
                    continue
                visited.add(current)

                # 计算衰减后的影响力
                node = nodes[current]
                decay = (1 - event.decay_rate) ** dist
                impact = event.impact_strength * decay * node.get("weight", 1.0)
                if event.direction == "negative":
                    impact = -impact

                results.append(ImpactResult(
                    node_id=current,
                    node_name=node["name"],
                    final_impact=round(impact, 2),
                    distance=dist,
                    intermediate_path=path,
                    affected_stocks=node.get("stock_codes", []),
                ))

                # BFS 下一层
                for neighbor in adj.get(current, []):
                    if neighbor not in visited:
                        queue.append((neighbor, dist + 1, path + [neighbor]))

        results.sort(key=lambda r: abs(r.final_impact), reverse=True)
        logger.info(
            f"[Chain] 事件'{event.title}'传导完成: "
            f"{len(results)}个节点受影响, 顶层影响={results[0].final_impact if results else 0}"
        )
        return results

    def export_eCharts_data(self, chain_name: str) -> dict:
        """导出为 ECharts tree 格式（前端渲染用）"""
        chain = self.load_chain(chain_name)
        if not chain:
            return {"name": chain_name, "children": []}

        nodes = chain.get("nodes", {})
        color_map = {"upstream": "#38bdf8", "midstream": "#fbbf24", "downstream": "#34d399"}

        def build_tree(parent_id: Optional[str] = None) -> list:
            children = []
            for nid, n in nodes.items():
                if n.get("parent_id") == parent_id:
                    children.append({
                        "name": n["name"],
                        "id": nid,
                        "itemStyle": {"color": color_map.get(n.get("segment", ""), "#64748B")},
                        "stocks": n.get("stock_codes", []),
                        "weight": n.get("weight", 1.0),
                        "children": build_tree(nid),
                    })
            return children

        return {
            "name": chain["name"],
            "children": [
                {"name": "上游供给", "itemStyle": {"color": color_map["upstream"]}, "children": [c for c in build_tree() if any(n.get("segment") == "upstream" for n in nodes.values() if n.get("id") == c.get("id"))] or build_tree()},
            ] if nodes else build_tree(),
        }


# 单例
_svc: Optional[IndustryChainService] = None


def get_chain_service() -> IndustryChainService:
    global _svc
    if _svc is None:
        _svc = IndustryChainService()
    return _svc

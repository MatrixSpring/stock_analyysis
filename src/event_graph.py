# -*- coding: utf-8 -*-
"""
===================================
事件传导图谱 — EventPropagationGraph
===================================

职责：
1. 跟踪宏观事件 → 行业 → 个股的传导路径
2. 构建因果关系图
3. 量化传导强度和延迟

示例传导链：
  美联储加息 → 美元走强 → 人民币贬值 → 出口型企业受益 → 纺织/家电板块上涨
  芯片禁令 → 供应链中断 → 半导体设备短缺 → 国产替代加速 → 中芯国际利好
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EventNode:
    """事件节点"""
    id: str
    name: str
    level: str = "macro"  # macro / industry / stock
    category: str = ""     # policy / geopolitics / tech / finance / supply
    description: str = ""
    impact_score: float = 0.0   # -1.0 (极度利空) ~ +1.0 (极度利好)
    timestamp: str = ""


@dataclass
class PropagationEdge:
    """传导边"""
    from_node: str     # 源节点 ID
    to_node: str        # 目标节点 ID
    strength: float = 0.5   # 传导强度 0-1
    delay_days: int = 0     # 传导延迟（天）
    confidence: float = 0.5  # 置信度
    mechanism: str = ""      # 传导机制描述


class EventPropagationGraph:
    """
    事件传导图谱。

    使用方式：
        graph = EventPropagationGraph()
        graph.add_node("fed_hike", "美联储加息", level="macro")
        graph.add_node("rmb_depreciation", "人民币贬值", level="macro")
        graph.add_edge("fed_hike", "rmb_depreciation", strength=0.9, mechanism="利差扩大")
        paths = graph.find_paths("fed_hike")  # 找到所有受影响节点
    """

    def __init__(self):
        self._nodes: Dict[str, EventNode] = {}
        self._edges: List[PropagationEdge] = []
        self._adjacency: Dict[str, List[PropagationEdge]] = defaultdict(list)
        self._reverse_adj: Dict[str, List[PropagationEdge]] = defaultdict(list)

    # ============================================================
    # 节点/边管理
    # ============================================================

    def add_node(
        self, node_id: str, name: str, level: str = "macro",
        category: str = "", description: str = "", impact: float = 0.0,
    ) -> EventNode:
        node = EventNode(
            id=node_id, name=name, level=level, category=category,
            description=description, impact_score=impact,
            timestamp=datetime.now().isoformat(),
        )
        self._nodes[node_id] = node
        return node

    def add_edge(
        self, from_id: str, to_id: str, strength: float = 0.5,
        delay_days: int = 0, confidence: float = 0.5,
        mechanism: str = "",
    ):
        edge = PropagationEdge(
            from_node=from_id, to_node=to_id,
            strength=strength, delay_days=delay_days,
            confidence=confidence, mechanism=mechanism,
        )
        self._edges.append(edge)
        self._adjacency[from_id].append(edge)
        self._reverse_adj[to_id].append(edge)

    def remove_node(self, node_id: str):
        self._nodes.pop(node_id, None)
        self._edges = [e for e in self._edges
                       if e.from_node != node_id and e.to_node != node_id]
        self._adjacency.pop(node_id, None)
        self._reverse_adj.pop(node_id, None)

    # ============================================================
    # 路径分析
    # ============================================================

    def find_paths(
        self, from_id: str, max_depth: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        BFS 查找从事件出发的所有传导路径。

        Returns:
            [{path: [...], total_strength, total_delay}]
        """
        if from_id not in self._nodes:
            return []

        paths = []
        visited_paths: Set[tuple] = set()

        def dfs(current: str, path: List[str], strength: float, delay: int, depth: int):
            if depth > max_depth:
                return
            edges = self._adjacency.get(current, [])
            if not edges and len(path) > 1:
                path_tuple = tuple(path)
                if path_tuple not in visited_paths:
                    visited_paths.add(path_tuple)
                    paths.append({
                        "path": [self._nodes[n].name for n in path],
                        "path_ids": list(path),
                        "total_strength": round(strength, 3),
                        "total_delay_days": delay,
                        "depth": len(path) - 1,
                    })
                return
            for edge in edges:
                if edge.to_node not in path:
                    dfs(
                        edge.to_node,
                        path + [edge.to_node],
                        strength * edge.strength,
                        delay + edge.delay_days,
                        depth + 1,
                    )
            # 也记录当前路径
            if len(path) > 1:
                path_tuple = tuple(path)
                if path_tuple not in visited_paths:
                    visited_paths.add(path_tuple)
                    paths.append({
                        "path": [self._nodes[n].name for n in path],
                        "path_ids": list(path),
                        "total_strength": round(strength, 3),
                        "total_delay_days": delay,
                        "depth": len(path) - 1,
                    })

        dfs(from_id, [from_id], 1.0, 0, 0)
        return sorted(paths, key=lambda p: -p["total_strength"])

    def find_affected_stocks(
        self, event_id: str, stock_nodes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        查找受事件影响的个股。

        Returns:
            [{stock_id, stock_name, impact, path, confidence}]
        """
        paths = self.find_paths(event_id, max_depth=5)
        affected = []

        for p in paths:
            last_id = p["path_ids"][-1]
            last_node = self._nodes.get(last_id)
            if last_node and last_node.level == "stock":
                affected.append({
                    "stock_id": last_node.id,
                    "stock_name": last_node.name,
                    "impact": round(last_node.impact_score * p["total_strength"], 3),
                    "path": p["path"],
                    "confidence": round(p["total_strength"], 3),
                    "delay_days": p["total_delay_days"],
                })

        # 按影响绝对值排序
        return sorted(affected, key=lambda a: -abs(a["impact"]))

    def impact_assessment(
        self, event_id: str,
    ) -> Dict[str, Any]:
        """事件影响评估报告"""
        node = self._nodes.get(event_id)
        if node is None:
            return {"error": "事件不存在"}

        paths = self.find_paths(event_id)
        affected = self.find_affected_stocks(event_id)

        by_industry: Dict[str, float] = defaultdict(float)
        for p in paths:
            for nid in p["path_ids"][1:]:
                n = self._nodes.get(nid)
                if n and n.level == "industry":
                    by_industry[n.name] += p["total_strength"]

        return {
            "event": node.name,
            "event_id": event_id,
            "level": node.level,
            "category": node.category,
            "direct_impact": node.impact_score,
            "propagation_paths": len(paths),
            "affected_stocks": len(affected),
            "top_affected": affected[:10],
            "industry_exposure": dict(
                sorted(by_industry.items(), key=lambda x: -x[1])[:5]
            ),
        }

    # ============================================================
    # 预置传导链
    # ============================================================

    def load_preset_chains(self):
        """加载预置的已知传导链"""
        presets = [
            # 美联储 → 汇率 → 出口
            ("fed_hike", "美联储加息", "macro", "policy",
             [("rmb_depreciation", "人民币贬值", "macro", 0.9, 1, "利差扩大→资本外流"),
              ("export_benefit", "出口型企业受益", "industry", 0.7, 5, "本币贬值→出口竞争力提升"),
              ("textile_up", "纺织板块", "industry", 0.5, 3, "出口占比高"),
              ("home_appliance_up", "家电板块", "industry", 0.6, 3, "海外收入占比高")]),
            # 芯片禁令 → 国产替代
            ("chip_ban", "芯片出口管制", "macro", "geopolitics",
             [("supply_shortage", "半导体供应短缺", "industry", 0.85, 30, "设备/材料断供"),
              ("domestic_substitution", "国产替代加速", "industry", 0.8, 60, "自主可控需求"),
              ("smic_benefit", "中芯国际", "stock", 0.5, 60, "国产代工龙头")]),
            # 降准降息 → 流动性 → 券商
            ("rrr_cut", "降准降息", "macro", "policy",
             [("liquidity_boost", "流动性改善", "macro", 0.95, 1, "释放长期资金"),
              ("broker_benefit", "券商受益", "industry", 0.7, 3, "交易活跃度提升")]),
            # 油价上涨 → 成本传导
            ("oil_rise", "原油价格上涨", "macro", "finance",
             [("chemical_cost", "化工成本上升", "industry", 0.8, 7, "原料成本传导"),
              ("airline_cost", "航空成本上升", "industry", 0.75, 3, "燃油成本占比高"),
              ("new_energy_benefit", "新能源受益", "industry", 0.6, 10, "替代效应")]),
        ]

        for event_id, event_name, level, category, edges in presets:
            self.add_node(event_id, event_name, level=level, category=category)
            prev = event_id
            for target_id, target_name, target_level, strength, delay, mechanism in edges:
                self.add_node(target_id, target_name, level=target_level)
                self.add_edge(prev, target_id, strength=strength,
                            delay_days=delay, mechanism=mechanism)
                prev = target_id

        logger.info(f"[EventGraph] 加载预置传导链: {len(presets)} 条根事件, {len(self._nodes)} 节点, {len(self._edges)} 边")

    def count(self) -> Dict[str, int]:
        return {"nodes": len(self._nodes), "edges": len(self._edges)}

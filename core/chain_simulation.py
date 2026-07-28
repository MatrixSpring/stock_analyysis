# -*- coding: utf-8 -*-
"""
===================================
产业链传导仿真引擎 — core/chain_simulation.py
===================================

输入：事件 + 所有传导链路与强度
输出：更新产业链状态、预期状态、个股价格冲击假设

作为连接图谱和右侧面板的数学中间层。
当用户修改任意传导权重或审核确认事件后，触发本引擎重新演算。

核心算法：加权级联传导
- 事件源头冲击强度 I₀
- 每级传导衰减: Iₙ = Iₙ₋₁ × decay_factorₙ
- 多路径汇聚: 叠加效应
- 最终输出: 各标的冲击向量

使用方式：
    from core.chain_simulation import ChainSimulator
    sim = ChainSimulator()
    impact = sim.simulate(event_id)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from core.global_state import GlobalState, TransferLink, StockInfo

logger = logging.getLogger(__name__)


class ChainSimulator:
    """
    产业链传导仿真引擎。

    算法：
    1. 从事件节点出发，沿传导链路 BFS 扩散
    2. 每条链路产生冲击: impact = source_strength × link.strength / 10 × link.decay_factor
    3. 多路径汇聚时叠加冲击
    4. 输出每个标的的综合冲击评分和方向
    """

    def __init__(self):
        self.state = GlobalState.get_instance()

    def simulate(self, event_id: str) -> Dict[str, Any]:
        """
        对指定事件执行传导仿真。

        Returns:
            {
                "event_id": str,
                "stock_impacts": {code: {"direction": str, "score": float, "paths": [...]}},
                "chain_summary": str,
            }
        """
        event = self.state.events.get(event_id)
        if not event:
            return {"event_id": event_id, "error": "事件不存在"}

        if event.audit_status != "confirmed":
            return {
                "event_id": event_id,
                "status": "preview",
                "note": "事件未审核通过，以下为预览结果",
                "stock_impacts": self._calculate_preview(event),
            }

        # 审核通过：正式仿真
        stock_impacts = self._calculate_confirmed(event)
        return {
            "event_id": event_id,
            "status": "confirmed",
            "stock_impacts": stock_impacts,
            "chain_summary": self._summarize(stock_impacts),
        }

    def _calculate_preview(self, event) -> Dict[str, Dict]:
        """预览模式：灰色草稿，不纳入正式预测"""
        return self._propagate(event, confirmed_only=False)

    def _calculate_confirmed(self, event) -> Dict[str, Dict]:
        """正式模式：已确认链路参与计算"""
        return self._propagate(event, confirmed_only=True)

    def _propagate(self, event, confirmed_only: bool = False) -> Dict[str, Dict]:
        """
        核心传播算法：BFS 从事件节点沿链路扩散。

        Args:
            event: 事件对象
            confirmed_only: True=仅走已确认链路, False=包含待审核链路

        Returns:
            {stock_code: {"direction": str, "score": float, "impact": str, "paths": [...]}}
        """
        # 收集所有相关链路
        active_links: List[TransferLink] = []
        for lid in event.transfer_links:
            link = self.state.transfer_links.get(lid)
            if not link:
                continue
            if confirmed_only and link.audit_status != "confirmed":
                continue
            active_links.append(link)

        if not active_links:
            return {}

        # 构建邻接表
        adjacency: Dict[str, List[Tuple[str, TransferLink]]] = defaultdict(list)
        for link in active_links:
            adjacency[link.from_node].append((link.to_node, link))

        # BFS 传播：从图中没有入边的节点（根节点）出发
        # 根节点 = 在 active_links 中有出边但无入边的节点
        all_to_nodes = {link.to_node for link in active_links}
        all_from_nodes = {link.from_node for link in active_links}
        root_nodes = all_from_nodes - all_to_nodes

        # 如果没有明确的根节点，从所有 from_nodes 出发
        if not root_nodes:
            root_nodes = all_from_nodes

        stock_impacts: Dict[str, Dict[str, Any]] = {}
        visited: Dict[str, float] = {}  # node_id -> 累计冲击强度

        # 初始冲击 = 事件强度 × 1.0（事件直接冲击根节点）
        initial_strength = float(event.strength)

        for src in root_nodes:
            queue = [(src, initial_strength, [src])]
            visited[src] = initial_strength

            while queue:
                current_node, current_strength, path = queue.pop(0)

                for next_node, link in adjacency.get(current_node, []):
                    # 传导衰减
                    decayed = current_strength * (link.strength / 10.0) * link.decay_factor

                    # 检查是否到达上市公司节点
                    next_node_obj = self.state.industry_nodes.get(next_node)
                    if next_node_obj and next_node_obj.node_type == "company":
                        stock_code = next_node_obj.properties.get("stock_code") or next_node_obj.name
                        if stock_code not in stock_impacts:
                            stock_impacts[stock_code] = {
                                "direction": link.direction,
                                "score": 0.0,
                                "paths": [],
                                "name": next_node_obj.name,
                            }
                        stock_impacts[stock_code]["score"] += decayed
                        # 构建可读路径
                        path_names = []
                        for n in path + [next_node]:
                            node_obj = self.state.industry_nodes.get(n)
                            path_names.append(node_obj.name if node_obj else n)
                        stock_impacts[stock_code]["paths"].append({
                            "route": " → ".join(path_names),
                            "strength": round(decayed, 3),
                            "link_id": link.link_id,
                        })

                    # 继续传播（如果节点未访问或冲击更大）
                    if next_node not in visited or decayed > visited[next_node]:
                        visited[next_node] = decayed
                        new_path = path + [next_node]
                        queue.append((next_node, decayed, new_path))

        # 归一化评分到 0~1
        if stock_impacts:
            max_score = max(s["score"] for s in stock_impacts.values())
            if max_score > 0:
                for imp in stock_impacts.values():
                    imp["score"] = round(imp["score"] / max_score, 4)
                    imp["impact"] = self._impact_label(imp["direction"], imp["score"])

        return stock_impacts

    @staticmethod
    def _impact_label(direction: str, score: float) -> str:
        """冲击标签"""
        if direction == "positive":
            if score > 0.7:
                return "强烈利好"
            elif score > 0.4:
                return "温和利好"
            return "轻微利好"
        elif direction == "negative":
            if score > 0.7:
                return "强烈利空"
            elif score > 0.4:
                return "温和利空"
            return "轻微利空"
        return "中性震荡"

    def _summarize(self, stock_impacts: Dict[str, Dict]) -> str:
        """生成传导仿真摘要"""
        if not stock_impacts:
            return "暂无有效传导路径"

        lines = []
        for code, impact in stock_impacts.items():
            name = impact.get("name", code)
            score = impact.get("score", 0)
            direction_icon = "🟢" if impact.get("direction") == "positive" else "🔴"
            lines.append(f"{direction_icon} {name}: {impact.get('impact', '?')} (得分: {score:.2f})")

        return "\n".join(lines)

    def simulate_all_events(self) -> Dict[str, Any]:
        """对所有已确认事件进行综合仿真"""
        all_impacts: Dict[str, Dict] = {}

        for event in self.state.get_confirmed_events():
            result = self.simulate(event.event_id)
            for code, impact in result.get("stock_impacts", {}).items():
                if code not in all_impacts:
                    all_impacts[code] = {
                        "score": 0.0,
                        "positive_score": 0.0,
                        "negative_score": 0.0,
                        "event_count": 0,
                        "events": [],
                    }
                all_impacts[code]["score"] += impact.get("score", 0)
                if impact.get("direction") == "positive":
                    all_impacts[code]["positive_score"] += impact.get("score", 0)
                else:
                    all_impacts[code]["negative_score"] += impact.get("score", 0)
                all_impacts[code]["event_count"] += 1
                all_impacts[code]["events"].append(event.event_id)

        # 计算净影响
        for code, impact in all_impacts.items():
            impact["net_score"] = impact["positive_score"] - impact["negative_score"]
            if impact["net_score"] > 0.3:
                impact["overall"] = "偏多"
            elif impact["net_score"] < -0.3:
                impact["overall"] = "偏空"
            else:
                impact["overall"] = "震荡"

        return all_impacts


# ============================================================
# 便捷函数
# ============================================================

def simulate_event(event_id: str) -> Dict[str, Any]:
    """快捷仿真入口"""
    sim = ChainSimulator()
    return sim.simulate(event_id)

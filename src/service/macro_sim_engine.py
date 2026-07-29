"""
宏观货币流动性冲击推演引擎
国家节点 BFS 传导: 利率/汇率/贸易/资本四类链路
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# 全球宏观传导网络：国家→国家，四类边
MACRO_EDGES = [
    {"source": "USA", "target": "CN", "type": "TRADE_CAPITAL", "coeff": 0.72, "time_lag_days": 14, "label": "贸易+资本"},
    {"source": "USA", "target": "JP", "type": "RATE_SPREAD", "coeff": 0.85, "time_lag_days": 5, "label": "利率传导"},
    {"source": "USA", "target": "DE", "type": "RATE_SPREAD", "coeff": 0.68, "time_lag_days": 10, "label": "利率传导"},
    {"source": "CN", "target": "JP", "type": "TRADE_CAPITAL", "coeff": 0.55, "time_lag_days": 20, "label": "贸易"},
    {"source": "CN", "target": "DE", "type": "TRADE_CAPITAL", "coeff": 0.60, "time_lag_days": 18, "label": "贸易"},
    {"source": "CN", "target": "IN", "type": "TRADE_CAPITAL", "coeff": 0.45, "time_lag_days": 25, "label": "贸易+投资"},
    {"source": "DE", "target": "JP", "type": "CAPITAL_FLOW", "coeff": 0.38, "time_lag_days": 15, "label": "资本"},
    {"source": "DE", "target": "IN", "type": "CAPITAL_FLOW", "coeff": 0.32, "time_lag_days": 22, "label": "资本"},
    {"source": "JP", "target": "CN", "type": "CAPITAL_FLOW", "coeff": 0.42, "time_lag_days": 12, "label": "资本"},
    {"source": "JP", "target": "IN", "type": "TRADE_CAPITAL", "coeff": 0.35, "time_lag_days": 24, "label": "贸易"},
]

MACRO_EVENTS = [
    {"id": "m001", "title": "美联储鹰派加息50bp", "type": "rate", "direction": "negative", "target": "USA"},
    {"id": "m002", "title": "中国央行降准释放流动性", "type": "rate", "direction": "positive", "target": "CN"},
    {"id": "m003", "title": "欧洲能源危机加剧", "type": "geo", "direction": "negative", "target": "DE"},
    {"id": "m004", "title": "全球去美元化加速", "type": "geo", "direction": "negative", "target": "USA"},
    {"id": "m005", "title": "日本央行结束负利率", "type": "rate", "direction": "positive", "target": "JP"},
]

EDGE_TYPE_LABEL = {
    "RATE_SPREAD": "利率传导", "TRADE_CAPITAL": "贸易+资本",
    "CAPITAL_FLOW": "资本流动", "SUPPLY_CHAIN": "供应链",
}


@dataclass
class MacroSimStep:
    source_id: str
    target_id: str
    edge_type: str
    single_coeff: float
    total_coeff: float
    final_impact: float
    total_lag_days: int
    step: int


class MacroSimEngine:
    """宏观货币 BFS 传导引擎"""

    def calculate(
        self, root_id: str, base_strength: float = 0.8,
        min_coeff: float = 0.10, max_level: int = 5,
    ) -> List[MacroSimStep]:
        adj: Dict[str, list] = {}
        for e in MACRO_EDGES:
            adj.setdefault(e["source"], []).append(e)
            adj.setdefault(e["target"], [])

        results, visited = [], {root_id}
        queue = [(root_id, 0, 1.0, 0)]

        while queue:
            cur, step, total_c, total_d = queue.pop(0)
            if step >= max_level:
                continue
            for edge in adj.get(cur, []):
                nxt = edge["target"]
                if nxt in visited:
                    continue
                visited.add(nxt)
                new_c = total_c * edge["coeff"]
                new_d = total_d + edge.get("time_lag_days", 14)
                if new_c < min_coeff:
                    continue
                results.append(MacroSimStep(
                    source_id=cur, target_id=nxt,
                    edge_type=edge["type"], single_coeff=edge["coeff"],
                    total_coeff=round(new_c, 4),
                    final_impact=round(base_strength * new_c, 4),
                    total_lag_days=new_d, step=step + 1,
                ))
                queue.append((nxt, step + 1, new_c, new_d))

        results.sort(key=lambda r: r.total_lag_days)
        return results

    def get_events(self) -> list:
        return MACRO_EVENTS

    def get_graph(self) -> dict:
        nodes = [
            {"id": "USA", "label": "🇺🇸 美国", "risk": 32},
            {"id": "CN", "label": "🇨🇳 中国", "risk": 28},
            {"id": "JP", "label": "🇯🇵 日本", "risk": 45},
            {"id": "DE", "label": "🇩🇪 德国", "risk": 38},
            {"id": "IN", "label": "🇮🇳 印度", "risk": 52},
        ]
        edges = [
            {"source": e["source"], "target": e["target"],
             "edgeType": EDGE_TYPE_LABEL.get(e["type"], e["type"]),
             "coeff": e["coeff"], "timeLag": f'{e["time_lag_days"]}天', "time_lag_days": e["time_lag_days"]}
            for e in MACRO_EDGES
        ]
        return {"nodes": nodes, "edges": edges}


_macro_engine: MacroSimEngine | None = None


def get_macro_engine() -> MacroSimEngine:
    global _macro_engine
    if _macro_engine is None:
        _macro_engine = MacroSimEngine()
    return _macro_engine

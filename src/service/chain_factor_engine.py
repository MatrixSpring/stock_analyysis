"""
产业链多因子加权传导引擎
五大因子: 产业政策 / 行业博弈 / 舆情情绪 / 资金流向 / 地缘政治
产出: 传导溯源日志 + 三级公司穿透
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

CHAIN_DATA = Path("data/industry_chains.json")

FACTOR_WEIGHTS = {
    "policy": {"label": "产业政策", "icon": "📋", "direction": 1},
    "game": {"label": "行业博弈", "icon": "⚔️", "direction": -1},
    "sentiment": {"label": "舆情情绪", "icon": "📰", "direction": 1},
    "capital": {"label": "资金流向", "icon": "💰", "direction": 1},
    "geo": {"label": "地缘政治", "icon": "🌍", "direction": -1},
}

# 内置公司传导样本（生产环境对接 DB）
COMPANY_MAP = {
    "GPU芯片": [
        {"name": "寒武纪", "code": "688256", "level": "强", "impact": 8.5, "reason": "核心GPU设计"},
        {"name": "海光信息", "code": "688041", "level": "中", "impact": 5.2, "reason": "DCU替代"},
    ],
    "光模块": [
        {"name": "中际旭创", "code": "300308", "level": "强", "impact": 9.2, "reason": "800G龙头"},
        {"name": "新易盛", "code": "300502", "level": "中", "impact": 6.8, "reason": "400G放量"},
    ],
    "AI服务器": [
        {"name": "浪潮信息", "code": "000977", "level": "强", "impact": 7.8, "reason": "AI服务器龙头"},
        {"name": "中科曙光", "code": "603019", "level": "中", "impact": 5.5, "reason": "算力基建"},
    ],
    "动力电池": [
        {"name": "宁德时代", "code": "300750", "level": "强", "impact": 9.5, "reason": "全球龙头"},
        {"name": "亿纬锂能", "code": "300014", "level": "中", "impact": 6.2, "reason": "二线放量"},
    ],
    "新能源整车": [
        {"name": "比亚迪", "code": "002594", "level": "强", "impact": 8.8, "reason": "全产业链"},
        {"name": "赛力斯", "code": "601127", "level": "中", "impact": 5.8, "reason": "华为合作"},
    ],
}


@dataclass
class TransmissionStep:
    type: str  # event / factor / node / intermediate
    title: str
    detail: str = ""
    impact: float = 0.0
    coeff: float = 0.0
    time: str = ""


@dataclass
class FactorResult:
    steps: List[TransmissionStep] = field(default_factory=list)
    tier1_nodes: List[dict] = field(default_factory=list)
    tier2_sectors: List[dict] = field(default_factory=list)
    tier3_stocks: List[dict] = field(default_factory=list)
    total_impact: float = 0.0
    dominant_factor: str = ""


class ChainFactorEngine:
    """多因子加权传导引擎"""

    def calculate(
        self, event_title: str, target_node: str, factors: Dict[str, float],
        chain_name: str = "AI算力",
    ) -> FactorResult:
        steps = []
        total = 0.0
        dominant = ("", 0)

        # 第 0 层: 事件
        steps.append(TransmissionStep(
            type="event", title=f"触发事件: {event_title}",
            detail=f"冲击起点: {target_node}", time="T+0",
        ))

        # 第 1 层: 五因子解析
        for key, label_info in FACTOR_WEIGHTS.items():
            val = factors.get(key, 0)
            if val > 1:
                weighted = val * label_info["direction"] * 0.2
                total += weighted
                if abs(weighted) > abs(dominant[1]):
                    dominant = (label_info["label"], weighted)
                steps.append(TransmissionStep(
                    type="factor",
                    title=f"{label_info['icon']} {label_info['label']}因子",
                    detail=f"强度 {val}/10 → 加权影响 {weighted:+.1f}",
                    impact=round(weighted, 1),
                ))

        # 第 2 层: 节点逐级传导（模拟 BFS 3 层）
        chain = self._load_chain(chain_name)
        nodes = chain.get("nodes", {})
        node_list = []
        for nid, n in nodes.items():
            seg = n.get("segment", "")
            node_list.append({"id": nid, "name": n.get("name", nid), "segment": seg})

        # 上游→中游→下游衰减
        decay_levels = {"upstream": 1.0, "midstream": 0.7, "downstream": 0.4}
        tier1 = []
        for n in node_list:
            decay = decay_levels.get(n["segment"], 0.5)
            impact = round(total * decay, 2)
            tier1.append({**n, "impact": impact})
            if abs(impact) > 1:
                steps.append(TransmissionStep(
                    type="node",
                    title=f"{n['name']} ({n['segment']})",
                    detail=f"经{decay*100:.0f}%衰减 → 影响 {impact:+.2f}",
                    impact=impact, coeff=decay, time=f"T+{list(decay_levels.keys()).index(n['segment'])+1}",
                ))

        # 二级: 赛道估值
        tier2 = [
            {"name": "算力基建", "score": round(total * 6.5, 1)},
            {"name": "AI应用", "score": round(total * 4.2, 1)},
            {"name": "半导体设备", "score": round(total * 3.8, 1)},
        ]

        # 三级: 个股
        tier3 = []
        for n in tier1[:4]:
            stocks = COMPANY_MAP.get(n["name"], [])
            for s in stocks:
                tier3.append({**s, "impact": round(s["impact"] * abs(total) * 0.3, 2)})

        return FactorResult(
            steps=steps, tier1_nodes=tier1, tier2_sectors=tier2,
            tier3_stocks=tier3, total_impact=round(total, 1),
            dominant_factor=dominant[0],
        )

    def _load_chain(self, name: str) -> dict:
        chain = {}
        if CHAIN_DATA.exists():
            data = json.loads(CHAIN_DATA.read_text(encoding="utf-8"))
            chain = data.get(name, {})
        # 兼容旧格式
        if not chain.get("nodes") and chain.get("upstream"):
            nodes = {}
            for seg in ("upstream", "midstream", "downstream"):
                for item in chain.get(seg, []):
                    nid = f"n_{seg}_{item}"
                    nodes[nid] = {"name": item, "segment": seg}
            chain["nodes"] = nodes
        return chain


_engine: Optional[ChainFactorEngine] = None


def get_factor_engine() -> ChainFactorEngine:
    global _engine
    if _engine is None:
        _engine = ChainFactorEngine()
    return _engine

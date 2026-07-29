"""产业链多因子动态推演 API — 四层节点 + 五因子 + 三级穿透"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/expert", tags=["专家产业链推演"])


class ChainSimRequest(BaseModel):
    eventKey: str
    layers: List[str] = []


EVENT_SCORE_MAP = {
    "us_rate_cut": {"1": 50, "2": 55, "3": 88, "4": 82, "5": 72, "6": 68, "7": 78,
                    "desc": "流动性宽松利好成长制造、算力配套环节"},
    "cn_loose": {"1": 52, "2": 58, "3": 85, "4": 80, "5": 70, "6": 75, "7": 65,
                 "desc": "国内流动性宽松，中下游制造与消费端受益"},
    "commodity_up": {"1": 90, "2": 82, "3": 60, "4": 55, "5": 50, "6": 48, "7": 52,
                     "desc": "大宗商品涨价，上游资源盈利抬升，中游成本承压"},
    "tech_sanction": {"1": 70, "2": 65, "3": 86, "4": 80, "5": 62, "6": 58, "7": 75,
                      "desc": "海外技术限制，国产替代环节高度受益"},
    "new_energy_policy": {"1": 60, "2": 55, "3": 72, "4": 88, "5": 82, "6": 76, "7": 68,
                          "desc": "产业政策落地，新能源制造与终端应用景气上行"},
    "trade_benefit": {"1": 55, "2": 58, "3": 68, "4": 85, "5": 80, "6": 70, "7": 72,
                      "desc": "出口贸易利好，工业制造与出海配套环节受益"},
}

STOCK_LIST = [
    {"code": "688001", "name": "科创龙头A", "relation": "中游核心标的", "effect": "强受益", "effectType": "success",
     "logic": "核心零部件环节，事件传导弹性高，订单与毛利率持续改善"},
    {"code": "300001", "name": "制造龙头B", "relation": "整机集成龙头", "effect": "强受益", "effectType": "success",
     "logic": "整机制造核心标的，行业格局优化，产能利用率提升"},
    {"code": "002001", "name": "资源标的C", "relation": "上游配套标的", "effect": "中受益", "effectType": "warning",
     "logic": "原材料价格随周期波动，阶段性受益，持续性中等"},
    {"code": "600001", "name": "传统制造D", "relation": "边缘关联标的", "effect": "弱承压", "effectType": "info",
     "logic": "传统产能环节无壁垒，行业博弈下存在毛利率小幅承压"},
]


@router.get("/overview")
def expert_overview():
    """专家选股全局概览数据"""
    from src.api.response import ApiResp
    return ApiResp.ok(data={
        "macro": {"liquidity": "中性偏宽", "riskAppetite": "回暖", "rateTrend": "下行通道",
                  "fundFlow": "北向净流入+85亿｜两融回升", "cycleScore": 72},
        "industries": [
            {"rank": 1, "name": "AI算力", "score": 92, "trend": "up", "signal": "强推",
             "reason": "算力需求爆发+政策加持+国产替代"},
            {"rank": 2, "name": "机器人", "score": 88, "trend": "up", "signal": "推荐",
             "reason": "产业化落地加速+龙头扩产"},
            {"rank": 3, "name": "半导体设备", "score": 85, "trend": "up", "signal": "推荐",
             "reason": "国产化率提升+资本开支上行"},
        ],
        "stocks": [
            {"code": "688256", "name": "寒武纪", "sector": "AI算力", "score": 95, "rating": "强推", "logic": "国产GPU龙头"},
            {"code": "300308", "name": "中际旭创", "sector": "AI算力", "score": 93, "rating": "强推", "logic": "800G光模块龙头"},
            {"code": "300750", "name": "宁德时代", "sector": "新能源", "score": 88, "rating": "推荐", "logic": "全球动力电池龙头"},
        ],
    })


@router.post("/chain/sim")
def expert_chain_sim(req: ChainSimRequest):
    """多因子图层动态产业链推演"""
    score_data = EVENT_SCORE_MAP.get(req.eventKey, {})
    policy_desc = "产业政策处于落地执行期，对高端制造、新能源赛道形成持续加持"
    sentiment_desc = "市场舆情整体偏暖，赛道利好情绪持续发酵，无重大利空舆情反转"

    nodes = [
        {"id": 1, "name": "上游原材料/核心资源", "layer": "上游层", "category": 0},
        {"id": 2, "name": "核心辅料/关键材料", "layer": "上游层", "category": 0},
        {"id": 3, "name": "核心零部件/模组", "layer": "中游层", "category": 1},
        {"id": 4, "name": "整机制造/集成代工", "layer": "中游层", "category": 1},
        {"id": 5, "name": "ToB工业应用", "layer": "下游层", "category": 2},
        {"id": 6, "name": "ToC终端消费", "layer": "下游层", "category": 2},
        {"id": 7, "name": "设备/算力/渠道配套", "layer": "配套层", "category": 3},
    ]

    links = [
        {"source": 1, "target": 3, "value": "成本传导", "elastic": 0.85},
        {"source": 2, "target": 3, "value": "材料支撑", "elastic": 0.75},
        {"source": 3, "target": 4, "value": "部件供给", "elastic": 0.90},
        {"source": 4, "target": 5, "value": "终端供货", "elastic": 0.80},
        {"source": 4, "target": 6, "value": "消费供给", "elastic": 0.82},
        {"source": 7, "target": 4, "value": "配套支撑", "elastic": 0.70},
    ]

    for n in nodes:
        s = score_data.get(str(n["id"]), 50)
        n["score"] = s
        if s > 70:
            n.update({"supplyDemand": "需求爆发+供给偏紧", "elastic": "高弹性(0.9)", "capital": "机构持续加仓", "risk": "低风险"})
        elif s > 55:
            n.update({"supplyDemand": "供需平衡、景气改善", "elastic": "中弹性(0.6)", "capital": "资金中性流入", "risk": "中低风险"})
        else:
            n.update({"supplyDemand": "供给过剩/需求疲软", "elastic": "低弹性(0.3)", "capital": "资金流出压力", "risk": "高风险"})
        n["barrier"] = "寡头壁垒" if n["id"] in [3, 4] else "充分竞争"

    return {
        "graphData": {"nodes": nodes, "links": links},
        "policyDesc": policy_desc,
        "sentimentDesc": sentiment_desc,
        "stockList": STOCK_LIST,
        "resultDesc": "本次事件经过五层因子叠加推演：中游核心零部件、整机制造为最大受益端；上游资源阶段性受益；下游终端需求稳步改善。整体赛道景气结构分化明确，资金聚焦高壁垒、高弹性中游核心环节。",
    }

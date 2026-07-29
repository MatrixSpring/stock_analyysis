"""宏观货币流动性 API — 国家指标 + 推演"""

from fastapi import APIRouter
from src.api.response import ApiResp

router = APIRouter(prefix="/macro", tags=["宏观流动性"])

MACRO_COUNTRIES = [
    {"id":"USA","name":"美国","flag":"🇺🇸","currency":"USD","riskScore":32,
     "indicators":{"debt_gdp":124,"external_debt_reserve":65,"short_debt_ratio":32,"cds_spread":35,"fiscal_deficit":5.2,
                   "ca_gdp":-3.1,"trade_balance":"-920亿USD","fdi_flow":"+126亿","sec_flow":"+84亿",
                   "policy_rate":5.25,"real_rate":2.4,"cpi":3.3,"neer":118.6,
                   "fx_reserve":"3312亿USD","fx_reserve_mom":"-21亿","gold_stock":8133,"gold_half_year":12}},
    {"id":"CN","name":"中国","flag":"🇨🇳","currency":"CNY","riskScore":28,
     "indicators":{"debt_gdp":78,"external_debt_reserve":42,"short_debt_ratio":28,"cds_spread":55,"fiscal_deficit":3.0,
                   "ca_gdp":2.2,"trade_balance":"+820亿USD","fdi_flow":"+78亿","sec_flow":"-32亿",
                   "policy_rate":3.45,"real_rate":1.8,"cpi":0.3,"neer":96.2,
                   "fx_reserve":"3.2万亿USD","fx_reserve_mom":"+45亿","gold_stock":2262,"gold_half_year":58}},
    {"id":"JP","name":"日本","flag":"🇯🇵","currency":"JPY","riskScore":45,
     "indicators":{"debt_gdp":252,"external_debt_reserve":48,"short_debt_ratio":35,"cds_spread":28,"fiscal_deficit":6.5,
                   "ca_gdp":3.5,"trade_balance":"-185亿USD","fdi_flow":"+52亿","sec_flow":"+18亿",
                   "policy_rate":0.25,"real_rate":-1.2,"cpi":2.8,"neer":78.5,
                   "fx_reserve":"1.25万亿USD","fx_reserve_mom":"-12亿","gold_stock":846,"gold_half_year":3}},
    {"id":"DE","name":"德国","flag":"🇩🇪","currency":"EUR","riskScore":38,
     "indicators":{"debt_gdp":64,"external_debt_reserve":55,"short_debt_ratio":22,"cds_spread":18,"fiscal_deficit":2.5,
                   "ca_gdp":6.8,"trade_balance":"+275亿USD","fdi_flow":"+38亿","sec_flow":"+56亿",
                   "policy_rate":3.75,"real_rate":1.5,"cpi":2.4,"neer":104.3,
                   "fx_reserve":"2890亿USD","fx_reserve_mom":"+8亿","gold_stock":3352,"gold_half_year":-5}},
    {"id":"IN","name":"印度","flag":"🇮🇳","currency":"INR","riskScore":52,
     "indicators":{"debt_gdp":82,"external_debt_reserve":72,"short_debt_ratio":38,"cds_spread":120,"fiscal_deficit":5.9,
                   "ca_gdp":-1.2,"trade_balance":"-265亿USD","fdi_flow":"+42亿","sec_flow":"-15亿",
                   "policy_rate":6.50,"real_rate":2.1,"cpi":5.5,"neer":72.8,
                   "fx_reserve":"5860亿USD","fx_reserve_mom":"+18亿","gold_stock":803,"gold_half_year":15}},
]


@router.get("/countries")
async def list_countries():
    return ApiResp.ok(data=MACRO_COUNTRIES)


@router.get("/country/{country_id}")
async def get_country(country_id: str):
    for c in MACRO_COUNTRIES:
        if c["id"] == country_id:
            return ApiResp.ok(data=c)
    return ApiResp.fail(code=404, msg="经济体不存在")


# ===================== 宏观推演 =====================

from pydantic import BaseModel, Field


class MacroSimRequest(BaseModel):
    rootNodeId: str = "USA"
    baseStrength: float = Field(0.8, ge=0, le=1)
    minCoeffFilter: float = Field(0.10, ge=0, le=1)
    maxLevel: int = Field(5, ge=1, le=10)


@router.post("/sim/calcPath")
def macro_calc_path(req: MacroSimRequest):
    """宏观 BFS 传导路径计算"""
    from src.service.macro_sim_engine import get_macro_engine
    engine = get_macro_engine()
    steps = engine.calculate(req.rootNodeId, req.baseStrength, req.minCoeffFilter, req.maxLevel)
    return [
        {"source_id": s.source_id, "target_id": s.target_id,
         "edge_type": s.edge_type, "single_coeff": s.single_coeff,
         "total_coeff": s.total_coeff, "final_impact": s.final_impact,
         "total_lag_days": s.total_lag_days, "step": s.step}
        for s in steps
    ]


@router.get("/sim/events")
def macro_list_events():
    from src.service.macro_sim_engine import get_macro_engine
    return get_macro_engine().get_events()


@router.get("/sim/graph")
def macro_graph_data():
    """宏观 G6 图数据 (nodes+edges)"""
    from src.service.macro_sim_engine import get_macro_engine
    return ApiResp.ok(data=get_macro_engine().get_graph())

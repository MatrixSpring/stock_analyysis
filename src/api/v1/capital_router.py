from fastapi import APIRouter, Query
from src.api.response import ApiResp
from src.compat.adapter import CapitalServiceAdapter

router = APIRouter(prefix="/capital", tags=["资金流向接口"])


@router.get("/daily", summary="获取个股每日资金流向")
async def get_capital_daily(
    code: str = Query(..., description="股票代码"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    accumulate_days: int = Query(0, description="是否计算滚动累计净额，0不计算，支持5/10/20"),
    use_cache: bool = Query(True)
):
    df = CapitalServiceAdapter.query_capital_flow(code, start_date, end_date, use_cache)
    if accumulate_days > 0:
        df = CapitalServiceAdapter.calc_rolling_accumulate(df, accumulate_days)

    return ApiResp.ok(data=df.to_dict("records"))

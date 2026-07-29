from fastapi import APIRouter, Query
from src.api.response import ApiResp
from src.compat.adapter import StockServiceAdapter

router = APIRouter(prefix="/stock", tags=["股票行情接口"])


@router.get("/info", summary="获取股票基础信息")
async def get_stock_info(
    code: str = Query(..., description="股票代码，例如 000001")
):
    data = StockServiceAdapter.get_stock_base_info(code)
    return ApiResp.ok(data=data)


@router.get("/kline", summary="获取日线K线行情")
async def get_stock_kline(
    code: str = Query(..., description="股票代码"),
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    use_cache: bool = Query(True, description="是否开启缓存")
):
    df = StockServiceAdapter.query_kline_data(code, start_date, end_date, use_cache)
    result_list = df.to_dict("records") if hasattr(df, "to_dict") else []
    return ApiResp.ok(data=result_list)

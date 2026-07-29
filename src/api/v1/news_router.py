from fastapi import APIRouter, Query
from src.api.response import ApiResp
from src.compat.adapter import NewsServiceAdapter

router = APIRouter(prefix="/news", tags=["资讯舆情接口"])


@router.get("/stock", summary="获取个股资讯列表")
async def get_stock_news(
    code: str = Query(..., description="股票代码"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    stat: bool = Query(False, description="是否返回情感统计汇总"),
    use_cache: bool = Query(True)
):
    df = NewsServiceAdapter.get_stock_news(code, start_date, end_date, use_cache)
    result = {
        "list": df.to_dict("records")
    }
    if stat:
        result["sentiment_stat"] = NewsServiceAdapter.sentiment_statistic(df)
    return ApiResp.ok(data=result)


@router.get("/industry", summary="获取行业资讯列表")
async def get_industry_news(
    industry: str = Query(..., description="行业名称"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    stat: bool = Query(False, description="是否返回情感统计汇总"),
    use_cache: bool = Query(True)
):
    df = NewsServiceAdapter.get_industry_news(industry, start_date, end_date, use_cache)
    result = {
        "list": df.to_dict("records")
    }
    if stat:
        result["sentiment_stat"] = NewsServiceAdapter.sentiment_statistic(df)
    return ApiResp.ok(data=result)

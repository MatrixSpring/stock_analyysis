from fastapi import APIRouter, Query
from src.api.response import ApiResp

router = APIRouter(prefix="/industry", tags=["产业链接口"])


@router.get("/chains", summary="获取产业链列表")
async def list_chains():
    # TODO: 接入 industry_chain_service
    return ApiResp.ok(data={"chains": []})


@router.get("/chain/{name}", summary="获取产业链详情")
async def get_chain(name: str):
    return ApiResp.ok(data={"name": name, "status": "pending"})

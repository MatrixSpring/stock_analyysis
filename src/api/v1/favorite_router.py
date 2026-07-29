from fastapi import APIRouter, Query
from src.api.response import ApiResp
from src.compat.adapter import FavoriteAdapter

router = APIRouter(prefix="/favorite", tags=["自选股管理"])


@router.get("/list")
async def get_favorite():
    df = FavoriteAdapter.list_favorite()
    return ApiResp.ok(data=df.to_dict("records"))


@router.post("/add")
async def add_favorite(code: str = Query(...), name: str = Query("")):
    FavoriteAdapter.add(code, name)
    return ApiResp.ok(msg="添加成功")


@router.delete("/delete")
async def del_favorite(fav_id: int = Query(...)):
    FavoriteAdapter.remove(fav_id)
    return ApiResp.ok(msg="删除成功")

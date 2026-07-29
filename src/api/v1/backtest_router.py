from fastapi import APIRouter, Body, Query
from pydantic import BaseModel
from src.api.response import ApiResp
from src.compat.adapter import BacktestAdapter

router = APIRouter(prefix="/backtest", tags=["策略回测"])


class BackTestReq(BaseModel):
    stock_code: str
    start_date: str
    end_date: str
    strategy_name: str
    params: dict = {}


@router.post("/run")
async def run_backtest(req: BackTestReq):
    task_id = BacktestAdapter.create_task(
        req.stock_code, req.start_date, req.end_date, req.strategy_name, req.params
    )
    return ApiResp.ok(data={"task_id": task_id})


@router.get("/task/list")
async def list_task(code: str = None):
    df = BacktestAdapter.list_task(code)
    return ApiResp.ok(data=df.to_dict("records"))

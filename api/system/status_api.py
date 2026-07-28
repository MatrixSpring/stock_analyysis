# -*- coding: utf-8 -*-
"""
===================================
系统监控面板后端接口 — api/system/status_api.py
===================================

提供：
- GET  /api/system/monitor     系统全局监控数据
- GET  /api/system/task/list   任务队列状态
- GET  /api/system/health      系统健康检查
- POST /api/system/clear-cache 清理 LLM 缓存

在 main.py 中注册：
    from api.system.status_api import router as system_router
    app.include_router(system_router)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Query

from core.system_monitor import get_monitor, get_monitor_info, start_monitoring
from core.task_queue import get_task_queue
from utils.exception_handler import create_success_response, create_error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["SystemMonitor"])


# ---- 启动监控（模块导入时自动启动）----

try:
    start_monitoring(interval_seconds=300)
except Exception:
    pass


# ---- 监控接口 ----

@router.get("/monitor", summary="获取系统全局监控数据")
async def get_system_monitor():
    """
    返回系统监控大盘全部数据：
    - 数据源健康状态
    - LLM 模型状态与调用统计
    - 任务统计
    - 系统资源
    """
    try:
        info = get_monitor_info()
        return create_success_response(info)
    except Exception as e:
        logger.error(f"[StatusAPI] 监控数据获取失败: {e}")
        return create_error_response(5001, f"监控数据获取失败: {e}")


@router.get("/task/list", summary="获取任务队列状态")
async def get_task_list(limit: int = Query(50, ge=1, le=200)):
    """获取最近任务列表与统计"""
    try:
        tq = get_task_queue()
        tasks = tq.get_all_tasks(limit=limit)
        stats = tq.get_stats()
        return create_success_response({"tasks": tasks, "stats": stats})
    except Exception as e:
        return create_error_response(4002, str(e))


@router.get("/task/{job_id}", summary="查询单个任务状态")
async def get_task_status(job_id: str):
    """按 job_id 查询任务"""
    tq = get_task_queue()
    status = tq.get_status(job_id)
    return create_success_response(status)


@router.get("/health", summary="系统健康检查")
async def system_health():
    """轻量健康检查，供外部监控调用"""
    info = get_monitor_info()
    datasource_healthy = all(
        s.get("status") == "ok"
        for s in info.get("datasource_status", {}).values()
    ) if info.get("datasource_status") else None

    return {
        "status": "ok",
        "datasource_healthy": datasource_healthy,
        "uptime_seconds": info.get("uptime_seconds", 0),
    }


@router.post("/clear-cache", summary="清理 LLM 推理缓存")
async def clear_llm_cache(ttl_hours: int = Query(168, ge=1, le=720)):
    """手动清理过期 LLM 缓存"""
    try:
        from core.llm_engine import get_llm_engine
        engine = get_llm_engine()
        engine.cache.cleanup(ttl_hours=ttl_hours)
        stats = engine.cache.stats()
        return create_success_response({
            "msg": f"已清理 {ttl_hours}h 以前的缓存",
            "remaining_entries": stats["total_entries"],
        })
    except Exception as e:
        return create_error_response(5001, str(e))


@router.get("/datasource/check", summary="手动触发数据源连通性检查")
async def check_datasources():
    """立即检查所有数据源状态"""
    monitor = get_monitor()
    monitor._collect_datasource_status()
    return create_success_response(monitor.data.get("datasource_status", {}))

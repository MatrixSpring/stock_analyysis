# -*- coding: utf-8 -*-
"""
===================================
健康检查接口
===================================

职责：
1. 提供 /api/v1/health 健康检查接口
2. 用于负载均衡器和监控系统
3. 提供 LegacyGateway 网关统计信息
"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter

from api.v1.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    健康检查接口

    用于负载均衡器或监控系统检查服务状态

    Returns:
        HealthResponse: 包含服务状态和时间戳
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat()
    )


@router.get("/health/gateway")
async def gateway_health() -> Dict[str, Any]:
    """
    LegacyGateway 统一数据网关状态。

    Returns:
        dict: 网关统计信息（请求数、成功率、延迟、路由健康、审计摘要）
    """
    try:
        from src.adapters import LegacyGateway
        gw = LegacyGateway.get_instance()
        if not gw.is_initialized:
            return {"status": "not_initialized", "message": "LegacyGateway 未初始化"}
        return {"status": "ok", **gw.get_stats()}
    except ImportError:
        return {"status": "unavailable", "message": "adapters 模块未加载"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -*- coding: utf-8 -*-
"""
===================================
统一数据适配层
===================================

职责：
1. LegacyGateway — 统一数据入口，屏蔽底层存储差异
2. RouteEngine — 智能路由引擎，冷热数据自动分发
3. DTOAdapter — 新旧数据格式双向转换
4. ReadOnlyGuard — 只读守卫，拦截旧模块写入操作

使用方式：
    from src.adapters import LegacyGateway

    gateway = LegacyGateway.get_instance()
    gateway.init(db_manager)
    data, err = gateway.query_kline("600519", start="2024-01-01")
"""

from src.adapters.legacy_gateway import LegacyGateway, GatewayRequest
from src.adapters.route_engine import RouteEngine, RouteDecision, StorageTier, SourceHealth
from src.adapters.dto_adapter import DTOAdapter, AdapterConfig
from src.adapters.readonly_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    WriteAttempt,
)

__all__ = [
    "LegacyGateway",
    "GatewayRequest",
    "RouteEngine",
    "RouteDecision",
    "StorageTier",
    "SourceHealth",
    "DTOAdapter",
    "AdapterConfig",
    "ReadOnlyGuard",
    "ReadOnlyViolationError",
    "WriteAttempt",
]

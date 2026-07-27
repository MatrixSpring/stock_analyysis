# -*- coding: utf-8 -*-
"""
健康检查服务 — 容器编排/负载均衡存活探测

Usage:
    from src.services.health_check import health_check
    status = health_check.get_status()
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


class HealthCheck:
    """系统健康检查"""

    def __init__(self):
        self._start_time = datetime.now(timezone.utc)

    def get_status(self) -> Dict[str, Any]:
        """获取全局健康状态"""
        checks: Dict[str, Any] = {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": (datetime.now(timezone.utc) - self._start_time).total_seconds(),
        }

        # MongoDB
        try:
            from src.data_storage import get_mongo
            mongo = get_mongo()
            if mongo.db is not None:
                mongo.db.command("ping")
                checks["mongodb"] = "ok"
            else:
                checks["mongodb"] = "disabled"
        except Exception as e:
            checks["mongodb"] = f"error: {e}"
            if checks["status"] == "ok":
                checks["status"] = "degraded"

        # Redis
        try:
            from src.data_storage import get_redis
            redis = get_redis()
            if redis.client is not None:
                redis.client.ping()
                checks["redis"] = "ok"
            else:
                checks["redis"] = "disabled"
        except Exception as e:
            checks["redis"] = f"error: {e}"
            if checks["status"] == "ok":
                checks["status"] = "degraded"

        # DeepSeek API key check
        try:
            import os
            dk = os.getenv("DEEPSEEK_API_KEY")
            checks["llm"] = "configured" if dk else "missing_key"
        except Exception:
            checks["llm"] = "unknown"

        # Data sources
        try:
            from data_provider.provider_router import ProviderRouter
            router = ProviderRouter()
            health = router.get_health_report()
            checks["data_sources"] = f"{len(health.get('sources', []))} tracked"
        except Exception:
            checks["data_sources"] = "unavailable"

        return checks

    def is_healthy(self) -> bool:
        return self.get_status()["status"] == "ok"


health_check = HealthCheck()

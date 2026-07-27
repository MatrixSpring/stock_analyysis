# -*- coding: utf-8 -*-
"""
API 限流中间件 — 滑动窗口 + 令牌桶算法
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimiter:
    """内存滑动窗口限流器"""

    def __init__(self):
        self._store: Dict[str, List[float]] = defaultdict(list)

    def check(self, identifier: str, limit: int, window: int) -> Tuple[bool, int, int]:
        now = time.time()
        timestamps = self._store[identifier]
        cutoff = now - window
        timestamps = [t for t in timestamps if t > cutoff]
        self._store[identifier] = timestamps

        if len(timestamps) >= limit:
            reset_at = int(timestamps[0] + window) if timestamps else int(now + window)
            return False, 0, reset_at

        timestamps.append(now)
        return True, limit - len(timestamps), int(now + window)


# 接口级别限流配置（次数, 窗口秒数）
ENDPOINT_LIMITS = {
    "/api/v1/agent/chat": (20, 60),
    "/api/v1/agent/stream": (10, 60),
    "/api/v1/backtest/run": (5, 60),
    "/api/v1/analysis/analyze": (10, 60),
    "/api/v1/sentiment/query": (30, 60),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI 限流中间件"""

    def __init__(self, app, default_limit: int = 60, default_window: int = 60):
        super().__init__(app)
        self.limiter = RateLimiter()
        self.default_limit = default_limit
        self.default_window = default_window

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        limit, window = ENDPOINT_LIMITS.get(path, (self.default_limit, self.default_window))

        allowed, remaining, reset_at = self.limiter.check(client_ip, limit, window)
        if not allowed:
            retry_after = reset_at - int(time.time())
            return JSONResponse(
                status_code=429,
                content={"detail": f"请求频率超限({limit}次/{window}秒)，请{retry_after}秒后重试"},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(max(retry_after, 1)),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response

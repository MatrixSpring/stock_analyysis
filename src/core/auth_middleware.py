"""鉴权 + 令牌桶限流中间件"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from src.config.prod_settings import settings
from src.core.prod_logger import api_logger


# 简易令牌桶限流
class TokenBucket:
    def __init__(self, capacity: int, refill_rate: int):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill_ts = time.time()

    def consume(self) -> bool:
        now = time.time()
        delta = now - self.last_refill_ts
        add_tokens = delta * (self.refill_rate / 60)
        self.tokens = min(self.capacity, self.tokens + add_tokens)
        self.last_refill_ts = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


bucket_map = defaultdict(
    lambda: TokenBucket(settings.RATE_LIMIT_CAPACITY, settings.RATE_LIMIT_REFILL_PER_MIN)
)

WHITELIST = {"/health", "/docs", "/openapi.json", "/redoc"}


async def auth_middleware(request: Request, call_next):
    # 白名单放行
    if request.url.path in WHITELIST:
        return await call_next(request)

    # 鉴权
    token = request.headers.get("X-API-Token")
    if settings.API_TOKEN and token != settings.API_TOKEN:
        api_logger.warning(f"非法token 来源IP:{request.client.host if request.client else '?'}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token invalid",
        )

    # 限流
    if settings.RATE_LIMIT_ENABLE:
        ip = request.client.host if request.client else "unknown"
        bucket = bucket_map[ip]
        if not bucket.consume():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="request limited",
            )

    response = await call_next(request)
    return response

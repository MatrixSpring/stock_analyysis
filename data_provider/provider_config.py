# -*- coding: utf-8 -*-
"""
采集元数据与管理约束 — 从 .env 加载，兼容现有 Config 系统

与 data_provider/base.py 配合使用，不改动现有 base.py 结构，
通过装饰器和独立模块注入增强能力。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

# ============================================================
# 缓存配置
# ============================================================

CACHE_CONFIG: Dict[str, int] = {
    "realtime_quote_ttl": int(os.getenv("CACHE_REALTIME_TTL", "300")),
    "stock_minute_ttl": int(os.getenv("CACHE_MINUTE_TTL", "3600")),
    "stock_daily_ttl": int(os.getenv("CACHE_DAILY_TTL", "86400")),
    "chip_data_ttl": int(os.getenv("CACHE_CHIP_TTL", "86400")),
    "fundamental_ttl": int(os.getenv("CACHE_FUNDAMENTAL_TTL", "432000")),
    "industry_tag_ttl": int(os.getenv("CACHE_INDUSTRY_TAG_TTL", "-1")),
}

# ============================================================
# NoSQL 存储配置
# ============================================================

NOSQL_CONFIG = {
    "enabled": os.getenv("ENABLE_NOSQL_STORAGE", "true").lower() == "true",
    "mongo_uri": os.getenv("MONGO_URI", "mongodb://localhost:27017"),
    "mongo_db": os.getenv("MONGO_DB", "dsa_stock"),
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "cache_enabled": os.getenv("ENABLE_CACHE_LAYER", "true").lower() == "true",
}

# ============================================================
# 流控与熔断配置
# ============================================================

RATE_LIMIT_CONFIG = {
    # 免费数据源 (请求/秒)
    "free_tier_rps": float(os.getenv("RATE_FREE_RPS", "3.0")),
    "free_tier_min_interval_ms": int(os.getenv("RATE_FREE_MIN_INTERVAL", "300")),
    # 付费数据源
    "paid_tier_rps": float(os.getenv("RATE_PAID_RPS", "10.0")),
    # 熔断器
    "circuit_failure_threshold": int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "5")),
    "circuit_cooldown_seconds": int(os.getenv("CIRCUIT_COOLDOWN_SECONDS", "300")),
    # 重试
    "max_retries": int(os.getenv("FETCH_MAX_RETRIES", "3")),
    "retry_base_delay": float(os.getenv("FETCH_RETRY_BASE_DELAY", "1.0")),
    "retry_max_delay": float(os.getenv("FETCH_RETRY_MAX_DELAY", "30.0")),
    # 并发控制
    "max_concurrent_free_fetchers": int(os.getenv("MAX_CONCURRENT_FREE", "2")),
}

# ============================================================
# 功能开关
# ============================================================

FEATURE_FLAGS = {
    "enable_nosql_storage": os.getenv("ENABLE_NOSQL_STORAGE", "true").lower() == "true",
    "enable_cache_layer": os.getenv("ENABLE_CACHE_LAYER", "true").lower() == "true",
    "enable_auto_provider_route": os.getenv("ENABLE_AUTO_PROVIDER_ROUTE", "true").lower() == "true",
    "enable_chip_distribution": os.getenv("ENABLE_CHIP_DISTRIBUTION", "true").lower() == "true",
    "enable_intraday_data": os.getenv("ENABLE_INTRADAY_DATA", "true").lower() == "true",
    "enable_crawl_metadata": os.getenv("ENABLE_CRAWL_METADATA", "true").lower() == "true",
}

# ============================================================
# 数据源优先级（逗号分隔 → 列表）
# ============================================================

def parse_source_priority(env_key: str, default: str) -> list:
    raw = (os.getenv(env_key, default) or default).strip()
    return [s.strip() for s in raw.split(",") if s.strip()]

PROVIDER_PRIORITY = {
    "daily_kline": parse_source_priority("PRIORITY_DAILY_KLINE", "tickflow,tushare,efinance,akshare,baostock"),
    "realtime_quote": parse_source_priority("PRIORITY_REALTIME", "tencent,akshare_sina,efinance"),
    "chip_distribution": parse_source_priority("PRIORITY_CHIP", "efinance,akshare"),
    "intraday": parse_source_priority("PRIORITY_INTRADAY", "efinance,tencent"),
    "fundamental": parse_source_priority("PRIORITY_FUNDAMENTAL", "akshare,baostock,tushare"),
    "industry_tag": parse_source_priority("PRIORITY_INDUSTRY", "tushare,akshare"),
}


@dataclass
class CrawlMetaRecord:
    """单次采集的元数据记录（存入 Mongo crawl_metadata 集合）"""
    code: str
    market: str = ""
    data_type: str = "daily"       # daily/minute/chip/fundamental/realtime/industry
    source: str = ""               # 数据源名称
    status: str = "ok"             # ok / failed / dirty / timeout
    crawl_at: str = ""             # UTC ISO 时间戳
    expire_at: str = ""            # 数据失效时间
    request_duration_ms: float = 0.0
    retry_count: int = 0
    error_message: str = ""
    quality: str = "ok"            # ok / missing_fields / dirty
    data_version: str = "1.0"

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ============================================================
# 令牌桶限流器
# ============================================================

@dataclass
class TokenBucket:
    """简易令牌桶 — 控制 API 请求速率"""
    rate: float                     # 每秒生成的令牌数
    max_tokens: float = 10.0
    tokens: float = field(init=False)
    last_refill: float = field(default_factory=lambda: __import__("time").time())

    def __post_init__(self):
        self.tokens = self.max_tokens

    def acquire(self, tokens: float = 1.0) -> bool:
        import time as _time
        now = _time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_and_acquire(self, tokens: float = 1.0, timeout: float = 30.0) -> bool:
        import time as _time
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            if self.acquire(tokens):
                return True
            _time.sleep(0.05)
        return False

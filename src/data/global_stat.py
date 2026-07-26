# -*- coding: utf-8 -*-
"""全局运行监控统计（P3）— 线程安全"""

import threading
from typing import Any, Dict


class GlobalStat:
    """缓存命中率 + 接口失败率 + 请求计数"""

    _lock = threading.Lock()

    cache_hit: int = 0
    cache_miss: int = 0
    req_total: int = 0
    req_fail: int = 0

    @classmethod
    def inc_cache_hit(cls):
        with cls._lock:
            cls.cache_hit += 1

    @classmethod
    def inc_cache_miss(cls):
        with cls._lock:
            cls.cache_miss += 1

    @classmethod
    def inc_req(cls, fail: bool = False):
        with cls._lock:
            cls.req_total += 1
            if fail:
                cls.req_fail += 1

    @classmethod
    def cache_hit_rate(cls) -> float:
        total = cls.cache_hit + cls.cache_miss
        return round(cls.cache_hit / total * 100, 2) if total > 0 else 0.0

    @classmethod
    def fail_rate(cls) -> float:
        return round(cls.req_fail / cls.req_total * 100, 2) if cls.req_total > 0 else 0.0

    @classmethod
    def report(cls) -> Dict[str, Any]:
        return {
            "cache_hit_rate_pct": cls.cache_hit_rate(),
            "cache_hit": cls.cache_hit,
            "cache_miss": cls.cache_miss,
            "req_total": cls.req_total,
            "req_fail": cls.req_fail,
            "req_fail_rate_pct": cls.fail_rate(),
        }

from src.core.cache import cache
from src.core.tracer import trace_cost


class BaseService:
    def __init__(self):
        self.cache = cache

    def get_cache_key(self, *args) -> str:
        """快速生成缓存key"""
        return ":".join([str(item) for item in args])

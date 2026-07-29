import threading
from typing import Optional, Any
from datetime import datetime, timedelta
from src.core.logger import get_logger

logger = get_logger()


class MemoryCache:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                cls._instance = super().__new__(cls)
                cls._instance.cache_data = dict()
        return cls._instance

    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        expire = datetime.now() + timedelta(seconds=ttl_seconds)
        self.cache_data[key] = (value, expire)

    def get(self, key: str) -> Optional[Any]:
        item = self.cache_data.get(key)
        if not item:
            return None
        val, expire = item
        if datetime.now() > expire:
            del self.cache_data[key]
            return None
        return val

    def delete(self, key: str):
        if key in self.cache_data:
            del self.cache_data[key]


cache = MemoryCache()

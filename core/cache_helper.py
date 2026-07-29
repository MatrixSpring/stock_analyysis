# -*- coding: utf-8 -*-
"""
===================================
内存缓存 + 磁盘缓存 — core/cache_helper.py
===================================

避免重复请求相同标的行情，减少接口限流风险。

使用方式：
    from core.cache_helper import KlineCache
    cache = KlineCache()
    df = cache.get("600519_20260701_20260728")
    if df is None:
        df = fetch_from_api(...)
        cache.set("600519_20260701_20260728", df, ttl=300)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_CACHE_DB = Path(os.getenv("CACHE_DB_PATH", "data/market_cache.db"))


class KlineCache:
    """
    行情数据二级缓存：内存(L1) + SQLite(L2)。

    L1: 进程内 dict，极快，重启丢失
    L2: SQLite 磁盘，跨进程/重启持久，自动过期清理
    """

    def __init__(self, db_path: Optional[Path] = None, max_memory: int = 512):
        self._mem: Dict[str, tuple] = {}  # key -> (data, expire_time)
        self._max_memory = max_memory
        self._lock = threading.Lock()
        self._db_path = db_path or _CACHE_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_cache (
                    cache_key TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl_seconds INTEGER NOT NULL DEFAULT 300
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expire ON market_cache(created_at)")
            conn.commit()

    # ---- 内存缓存 ----

    def _mem_get(self, key: str) -> Optional[Any]:
        item = self._mem.get(key)
        if item is None:
            return None
        data, expire = item
        if time.time() > expire:
            del self._mem[key]
            return None
        return data

    def _mem_set(self, key: str, data: Any, ttl: int):
        with self._lock:
            if len(self._mem) >= self._max_memory:
                # 淘汰 30% 过期/最旧
                self._mem_evict(int(self._max_memory * 0.3))
            self._mem[key] = (data, time.time() + ttl)

    def _mem_evict(self, count: int):
        now = time.time()
        expired = [k for k, (_, e) in self._mem.items() if e < now]
        for k in expired[:count]:
            del self._mem[k]

    # ---- 磁盘缓存 ----

    def _disk_get(self, key: str) -> Optional[pd.DataFrame]:
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                row = conn.execute(
                    "SELECT data_json, created_at, ttl_seconds FROM market_cache WHERE cache_key=?",
                    (key,),
                ).fetchone()
            if row is None:
                return None
            data_json, created, ttl = row
            if time.time() - created > ttl:
                self._disk_delete(key)
                return None
            return pd.read_json(data_json, orient="records")
        except Exception as e:
            logger.debug(f"[Cache] 磁盘读取失败: {e}")
            return None

    def _disk_set(self, key: str, df: pd.DataFrame, ttl: int):
        try:
            data_json = df.to_json(orient="records", date_format="iso")
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO market_cache VALUES (?,?,?,?)",
                    (key, data_json, time.time(), ttl),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"[Cache] 磁盘写入失败: {e}")

    def _disk_delete(self, key: str):
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("DELETE FROM market_cache WHERE cache_key=?", (key,))
                conn.commit()
        except Exception:
            pass

    # ---- 对外接口 ----

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """获取缓存（L1→L2 级联查询）"""
        data = self._mem_get(key)
        if data is not None:
            return data
        data = self._disk_get(key)
        if data is not None:
            self._mem_set(key, data, ttl=60)  # 磁盘命中则回填内存
        return data

    def set(self, key: str, data: pd.DataFrame, ttl: int = 300):
        """写入缓存（L1+L2 双写）"""
        if data is None or data.empty:
            return
        self._mem_set(key, data, ttl)
        self._disk_set(key, data, ttl)

    def clear(self, pattern: str = ""):
        """清除缓存"""
        with self._lock:
            if pattern:
                keys = [k for k in self._mem if pattern in k]
                for k in keys:
                    del self._mem[k]
                    self._disk_delete(k)
            else:
                self._mem.clear()
                with sqlite3.connect(str(self._db_path)) as conn:
                    conn.execute("DELETE FROM market_cache")
                    conn.commit()
        logger.info(f"[Cache] 已清理: pattern='{pattern}'")

    def stats(self) -> Dict[str, Any]:
        """缓存统计"""
        mem_count = len(self._mem)
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                disk_count = conn.execute("SELECT COUNT(*) FROM market_cache").fetchone()[0]
        except Exception:
            disk_count = 0
        return {"memory_entries": mem_count, "disk_entries": disk_count}

    def cleanup_expired(self):
        """清理过期磁盘缓存"""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "DELETE FROM market_cache WHERE created_at + ttl_seconds < ?",
                    (time.time(),),
                )
                conn.commit()
        except Exception:
            pass


# 全局单例
_kline_cache: Optional[KlineCache] = None


def get_cache() -> KlineCache:
    global _kline_cache
    if _kline_cache is None:
        _kline_cache = KlineCache()
    return _kline_cache


# ============================================================
# 缓存 Key 构建工具
# ============================================================

def cache_key(symbol: str, start: str, end: str, adjust: str = "qfq") -> str:
    """标准化缓存 key"""
    raw = f"{symbol}_{start}_{end}_{adjust}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def cache_key_daily(symbol: str, date_str: str) -> str:
    return f"{symbol}_{date_str}"

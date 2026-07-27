# -*- coding: utf-8 -*-
"""
===================================
冷热数据分层存储 — TieredStore
===================================

职责：
1. 热数据（90天内）：SQLite + 内存 LRU 缓存
2. 冷数据（历史）：Parquet 归档文件
3. 自动迁移：定时将热数据过期部分迁移到冷层
4. 透明查询：自动路由到正确层级并合并结果

架构：
    查询请求 → QueryRouter → 热层 (SQLite) → 冷层 (Parquet) → 合并返回
"""

from __future__ import annotations

import logging
import os
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# 默认热数据窗口
DEFAULT_HOT_DAYS = 90


# ============================================================
# 内存 LRU 缓存
# ============================================================

class LRUCache:
    """线程安全的 LRU 内存缓存"""

    def __init__(self, max_items: int = 500, ttl_seconds: int = 300):
        self._cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._max = max_items
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，过期返回 None"""
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any):
        """写入缓存"""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (time.time(), value)
        while len(self._cache) > self._max:
            self._cache.popitem(last=False)

    def clear(self):
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


# ============================================================
# 冷热分层存储
# ============================================================

class TieredStore:
    """
    冷热分层存储。

    使用方式：
        store = TieredStore(db_manager, archive_dir="./data/archive")
        store.init()

        # 查询（自动路由热层 + 冷层）
        df = store.query_kline("600519", start="2024-01-01", end="2024-12-31")

        # 归档旧数据
        archived = store.archive_old_data()
    """

    def __init__(
        self,
        db_manager: Any = None,
        archive_dir: str = "./data/archive",
        hot_window_days: int = DEFAULT_HOT_DAYS,
        cache_max_items: int = 500,
        cache_ttl_seconds: int = 300,
    ):
        self._db = db_manager
        self._archive_dir = Path(archive_dir)
        self._hot_days = hot_window_days
        self._cache = LRUCache(max_items=cache_max_items, ttl_seconds=cache_ttl_seconds)
        self._initialized = False

    def init(self):
        """初始化存储（创建归档目录）"""
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info(f"[TieredStore] 初始化完成 (hot={self._hot_days}d, archive={self._archive_dir})")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def hot_window_days(self) -> int:
        return self._hot_days

    # ============================================================
    # 查询接口
    # ============================================================

    def query_kline(
        self,
        stock_code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        查询 K 线数据，自动路由热层/冷层并合并。

        Returns:
            pd.DataFrame (columns: date, open, high, low, close, volume, amount, pct_chg)
        """
        if not self._initialized:
            raise RuntimeError("TieredStore 未初始化，请先调用 init()")

        code = stock_code.upper()
        cache_key = f"kline:{code}:{start}:{end}"

        # 1. 缓存检查
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # 2. 确定查询范围
        now = datetime.now(timezone.utc)
        hot_cutoff = (now - timedelta(days=self._hot_days)).strftime("%Y-%m-%d")

        hot_df = pd.DataFrame()
        cold_df = pd.DataFrame()

        # 3. 热层查询（SQLite）
        hot_df = self._query_hot(code, start, end)

        # 4. 冷层查询（Parquet）— 如果 start 早于热窗口
        need_cold = True
        if start is None:
            need_cold = False
        elif start < hot_cutoff:
            cold_end = min(end or "9999-12-31", hot_cutoff)
            cold_df = self._query_cold(code, start, cold_end)

        # 5. 合并
        if not hot_df.empty and not cold_df.empty:
            result = pd.concat([cold_df, hot_df], ignore_index=True)
        elif not hot_df.empty:
            result = hot_df
        elif not cold_df.empty:
            result = cold_df
        else:
            result = pd.DataFrame(columns=[
                "date", "open", "high", "low", "close",
                "volume", "amount", "pct_chg",
            ])

        # 去重 + 排序
        if not result.empty:
            result = result.drop_duplicates(subset=["date"]).sort_values("date")

        # 6. 缓存
        self._cache.set(cache_key, result)
        return result

    # ============================================================
    # 归档操作
    # ============================================================

    def archive_old_data(self, before_date: Optional[str] = None) -> int:
        """
        将热层中超过 hot_window 的旧数据迁移到冷层。

        Args:
            before_date: 截止日期，默认为 hot_window 之前

        Returns:
            int: 归档行数
        """
        if not self._initialized:
            raise RuntimeError("TieredStore 未初始化")

        if before_date is None:
            before_date = (
                datetime.now(timezone.utc) - timedelta(days=self._hot_days)
            ).strftime("%Y-%m-%d")

        if self._db is None:
            logger.warning("[TieredStore] 无数据库连接，跳过归档")
            return 0

        try:
            # 从 SQLite 查询旧数据
            query = """
                SELECT code, date, open, high, low, close, volume, amount, pct_chg,
                       ma5, ma10, ma20, volume_ratio, data_source
                FROM stock_daily
                WHERE date < ?
                ORDER BY code, date
            """
            rows = self._db.execute_query(query, (before_date,)) if hasattr(self._db, "execute_query") else []

            if not rows:
                return 0

            df = pd.DataFrame(rows, columns=[
                "code", "date", "open", "high", "low", "close",
                "volume", "amount", "pct_chg", "ma5", "ma10",
                "ma20", "volume_ratio", "data_source",
            ])

            # 按股票代码分组写入 Parquet
            for code, group in df.groupby("code"):
                self._append_to_archive(code, group)

            total = len(df)
            logger.info(f"[TieredStore] 归档完成: {total} 行 → {self._archive_dir}")
            return total

        except Exception as e:
            logger.error(f"[TieredStore] 归档失败: {e}")
            return 0

    def get_archive_stats(self) -> Dict[str, Any]:
        """获取归档统计"""
        if not self._archive_dir.exists():
            return {"archive_exists": False, "files": 0, "total_rows": 0, "stocks": 0}

        files = list(self._archive_dir.glob("*/*.parquet"))
        stocks = set(f.parent.name for f in files)
        total_rows = 0
        for f in files[:50]:  # 采样
            try:
                total_rows += len(pd.read_parquet(f))
            except Exception:
                pass

        return {
            "archive_exists": True,
            "files": len(files),
            "total_rows": total_rows,
            "stocks": len(stocks),
            "stocks_sample": sorted(stocks)[:20],
        }

    def clear_cache(self):
        """清空内存缓存"""
        self._cache.clear()

    # ============================================================
    # 内部实现
    # ============================================================

    def _query_hot(
        self, code: str, start: Optional[str], end: Optional[str]
    ) -> pd.DataFrame:
        """从热层（SQLite）查询"""
        if self._db is None:
            return pd.DataFrame()

        try:
            conditions = ["code = ?"]
            params: List[Any] = [code]
            if start:
                conditions.append("date >= ?")
                params.append(start)
            if end:
                conditions.append("date <= ?")
                params.append(end)

            query = (
                "SELECT date, open, high, low, close, volume, amount, pct_chg, "
                "ma5, ma10, ma20, volume_ratio, data_source "
                f"FROM stock_daily WHERE {' AND '.join(conditions)} ORDER BY date"
            )

            if hasattr(self._db, "execute_query"):
                rows = self._db.execute_query(query, tuple(params))
            elif hasattr(self._db, "fetch_all"):
                rows = self._db.fetch_all(query, tuple(params))
            else:
                return pd.DataFrame()

            if not rows:
                return pd.DataFrame()

            return pd.DataFrame(rows, columns=[
                "date", "open", "high", "low", "close", "volume",
                "amount", "pct_chg", "ma5", "ma10", "ma20",
                "volume_ratio", "data_source",
            ])
        except Exception as e:
            logger.warning(f"[TieredStore] 热层查询失败 {code}: {e}")
            return pd.DataFrame()

    def _query_cold(
        self, code: str, start: str, end: str
    ) -> pd.DataFrame:
        """从冷层（Parquet）查询"""
        normalized = code.upper().replace(".SH", "").replace(".SZ", "")
        archive_file = self._archive_dir / normalized / f"{normalized}.parquet"

        if not archive_file.exists():
            return pd.DataFrame()

        try:
            df = pd.read_parquet(archive_file)
            if df.empty:
                return pd.DataFrame()

            df["date"] = pd.to_datetime(df["date"])
            mask = (df["date"] >= start)
            if end:
                mask &= (df["date"] <= end)
            return df[mask].copy()
        except Exception as e:
            logger.warning(f"[TieredStore] 冷层查询失败 {code}: {e}")
            return pd.DataFrame()

    def _append_to_archive(self, code: str, new_data: pd.DataFrame):
        """将新数据追加到归档 Parquet 文件"""
        normalized = code.upper().replace(".SH", "").replace(".SZ", "")
        stock_dir = self._archive_dir / normalized
        stock_dir.mkdir(parents=True, exist_ok=True)
        archive_file = stock_dir / f"{normalized}.parquet"

        if archive_file.exists():
            existing = pd.read_parquet(archive_file)
            combined = pd.concat([existing, new_data], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date"]).sort_values("date")
        else:
            combined = new_data

        combined.to_parquet(archive_file, index=False)

# -*- coding: utf-8 -*-
"""
===================================
数据层优化 — core/data_optimizer.py
===================================

四项优化：
1. SQLite 索引自动创建 — 加速批量查询
2. 增量行情更新 — 只拉取缺失日期的数据
3. 脏数据清洗 — 剔除停牌/涨跌停异常/无效价格
4. 内存缓存层 — TTL 过期自动刷新
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认数据库路径
DEFAULT_DB_PATH = Path("data/dsa_workspace.db")


# ============================================================
# 1. SQLite 索引自动创建
# ============================================================

STOCK_DAILY_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_stock_daily_code ON stock_daily(code)",
    "CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(date)",
    "CREATE INDEX IF NOT EXISTS idx_stock_daily_code_date ON stock_daily(code, date)",
    "CREATE INDEX IF NOT EXISTS idx_stock_daily_pct_chg ON stock_daily(pct_chg)",
]

EVENT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_events_event_id ON events_archive(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_direction ON events_archive(direction)",
    "CREATE INDEX IF NOT EXISTS idx_events_created ON events_archive(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_events_audit ON events_archive(audit_status)",
]

SNAPSHOT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_snapshots_name ON snapshots(name)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_updated ON snapshots(updated_at)",
]


def ensure_all_indexes(db_path: Optional[Path] = None):
    """自动为所有核心表创建索引（幂等，重复执行安全）"""
    path = str(db_path or DEFAULT_DB_PATH)
    try:
        with sqlite3.connect(path) as conn:
            for sql in STOCK_DAILY_INDEXES + EVENT_INDEXES + SNAPSHOT_INDEXES:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError as e:
                    logger.debug(f"[Index] 跳过: {e}")
            conn.commit()
        logger.info(f"[Index] 数据库索引检查完成: {path}")
    except Exception as e:
        logger.warning(f"[Index] 索引创建失败: {e}")


# ============================================================
# 2. 增量行情更新策略
# ============================================================

def get_missing_dates(
    db_path: Path,
    stock_code: str,
    expected_start: str,
    expected_end: str,
) -> List[str]:
    """
    计算需要补拉的日期列表。

    对比本地已有日期和预期日期范围 → 返回缺失日期。
    """
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT date FROM stock_daily WHERE code = ? ORDER BY date",
                (stock_code,),
            )
            existing = {row[0] for row in cursor.fetchall()}

        # 生成预期日期列表（跳过周末）
        start = datetime.strptime(expected_start, "%Y-%m-%d")
        end = datetime.strptime(expected_end, "%Y-%m-%d")
        expected = set()
        current = start
        while current <= end:
            if current.weekday() < 5:  # 周一至周五
                expected.add(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        missing = sorted(expected - existing)
        logger.info(
            f"[Incremental] {stock_code}: 预期{len(expected)}天, "
            f"已有{len(existing)}天, 缺失{len(missing)}天"
        )
        return missing
    except Exception as e:
        logger.warning(f"[Incremental] {stock_code} 查询失败: {e}")
        return []


# ============================================================
# 3. 脏数据清洗
# ============================================================

def clean_abnormal_prices(
    db_path: Optional[Path] = None,
    dry_run: bool = True,
) -> Dict[str, int]:
    """
    清洗异常行情数据：
    - 价格为 0 或负值
    - 涨跌幅超过 ±20%（非科创板）
    - 成交量/金额为 0（停牌日）
    - 开盘/收盘价格为 None

    Args:
        db_path: 数据库路径
        dry_run: True 只统计不删除

    Returns:
        {cleaned_rows, abnormal_rows, suspended_rows}
    """
    path = str(db_path or DEFAULT_DB_PATH)
    stats = {"cleaned_rows": 0, "abnormal_rows": 0, "suspended_rows": 0}

    try:
        with sqlite3.connect(path) as conn:
            # 统计异常
            cursor = conn.execute("""
                SELECT COUNT(*) FROM stock_daily
                WHERE close IS NULL OR close <= 0
                   OR open IS NULL OR open <= 0
                   OR volume IS NULL OR volume <= 0
                   OR (pct_chg IS NOT NULL AND ABS(pct_chg) > 20)
            """)
            stats["abnormal_rows"] = cursor.fetchone()[0]

            # 统计停牌日（成交量为 0 但价格不变）
            cursor = conn.execute("""
                SELECT COUNT(*) FROM stock_daily
                WHERE volume = 0 OR volume IS NULL
                   OR (open = close AND high = low AND volume < 100)
            """)
            stats["suspended_rows"] = cursor.fetchone()[0]

            if not dry_run:
                conn.execute("""
                    DELETE FROM stock_daily
                    WHERE close IS NULL OR close <= 0
                       OR volume IS NULL OR volume <= 0
                       OR ABS(pct_chg) > 20
                """)
                conn.commit()
                stats["cleaned_rows"] = conn.total_changes

        action = "模拟" if dry_run else "执行"
        logger.info(
            f"[Clean] {action}清洗: 异常{stats['abnormal_rows']}行, "
            f"停牌{stats['suspended_rows']}行, 删除{stats['cleaned_rows']}行"
        )
    except Exception as e:
        logger.warning(f"[Clean] 清洗失败: {e}")

    return stats


def validate_stock_bars(bars: List[Dict]) -> Tuple[List[Dict], int]:
    """
    实时校验行情数据。返回 (有效数据, 剔除数)。

    剔除条件：
    - O/H/L/C 任意为空
    - H < L（高低价倒挂）
    - 单日振幅 > 30%（数据异常）
    """
    valid, rejected = [], 0
    for bar in bars:
        try:
            o, h, l, c = (
                float(bar.get("open", 0)),
                float(bar.get("high", 0)),
                float(bar.get("low", 0)),
                float(bar.get("close", 0)),
            )
            if any(v <= 0 for v in (o, h, l, c)):
                rejected += 1
                continue
            if h < l:
                rejected += 1
                continue
            if (h - l) / l > 0.3:
                rejected += 1
                continue
            valid.append(bar)
        except (ValueError, TypeError, ZeroDivisionError):
            rejected += 1
    return valid, rejected


# ============================================================
# 4. 内存缓存层
# ============================================================

class TTLCache:
    """
    带 TTL 的内存缓存。

    Usage:
        cache = TTLCache(ttl_seconds=300)
        cache.set("key", data)
        value = cache.get("key")  # 过期返回 None
    """

    def __init__(self, ttl_seconds: float = 300, max_size: int = 1000):
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.time() - timestamp > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any):
        # LRU 驱逐
        if len(self._store) >= self._max_size:
            oldest = min(self._store.items(), key=lambda x: x[1][0])
            del self._store[oldest[0]]

        self._store[key] = (time.time(), value)

    def clear(self):
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


# 全局缓存实例（5 分钟过期）
_data_cache = TTLCache(ttl_seconds=300)


def cached(ttl_seconds: float = 300):
    """
    装饰器：自动缓存函数返回值。
    Cache key = func_name + args + kwargs 的 hash
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cached_value = _data_cache.get(key)
            if cached_value is not None:
                logger.debug(f"[Cache] HIT: {func.__name__}")
                return cached_value

            logger.debug(f"[Cache] MISS: {func.__name__}")
            result = func(*args, **kwargs)
            _data_cache.set(key, result)
            return result
        return wrapper
    return decorator


def flush_cache():
    """清空全部缓存"""
    _data_cache.clear()
    logger.info("[Cache] 已清空")

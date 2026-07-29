# -*- coding: utf-8 -*-
"""数据库连接管理 — SQLite 线程安全会话"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from src.config.settings import DB_PATH
from src.config.constants import (
    TABLE_STOCK_DAILY, TABLE_CAPITAL_FLOW, TABLE_NEWS,
    TABLE_EVENTS, TABLE_SNAPSHOTS, TABLE_AUDIT_LOG,
)

logger = logging.getLogger(__name__)

STOCK_DAILY_DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_STOCK_DAILY} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL, pct_chg REAL,
    ma5 REAL, ma10 REAL, ma20 REAL,
    turnover_rate REAL, volume_ratio REAL,
    data_source TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(code, date)
)"""

INDEXES = [
    f"CREATE INDEX IF NOT EXISTS idx_sd_code ON {TABLE_STOCK_DAILY}(code)",
    f"CREATE INDEX IF NOT EXISTS idx_sd_date ON {TABLE_STOCK_DAILY}(date)",
    f"CREATE INDEX IF NOT EXISTS idx_sd_code_date ON {TABLE_STOCK_DAILY}(code,date)",
]


class DBConnection:
    """SQLite 连接管理器"""
    _instance: Optional["DBConnection"] = None

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _ensure_tables(self):
        with self.connect() as conn:
            conn.execute(STOCK_DAILY_DDL)
            for idx in INDEXES:
                try:
                    conn.execute(idx)
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @classmethod
    def get_instance(cls) -> "DBConnection":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

#!/usr/bin/env python3
"""
数据库初始化脚本
python scripts/init_db.py          # 创建表 + 索引
python scripts/init_db.py --reset  # 删除重建
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.connection import DBConnection
from src.config.constants import (
    TABLE_STOCK_DAILY, TABLE_CAPITAL_FLOW, TABLE_NEWS,
    TABLE_EVENTS, TABLE_SNAPSHOTS, TABLE_AUDIT_LOG,
)

TABLES = {
    TABLE_STOCK_DAILY: """
        CREATE TABLE IF NOT EXISTS {t} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL, date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume REAL, amount REAL, pct_chg REAL,
            ma5 REAL, ma10 REAL, ma20 REAL,
            turnover_rate REAL, volume_ratio REAL,
            data_source TEXT, created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(code, date)
        )""",
    TABLE_CAPITAL_FLOW: """
        CREATE TABLE IF NOT EXISTS {t} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL, date TEXT NOT NULL,
            main_net_inflow REAL, north_net_inflow REAL,
            retail_net_inflow REAL, big_order_ratio REAL,
            UNIQUE(code, date)
        )""",
    TABLE_NEWS: """
        CREATE TABLE IF NOT EXISTS {t} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, date TEXT, title TEXT,
            content TEXT, source TEXT, sentiment TEXT,
            url TEXT UNIQUE, created_at TEXT DEFAULT (datetime('now'))
        )""",
    TABLE_EVENTS: """
        CREATE TABLE IF NOT EXISTS {t} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE, title TEXT,
            direction TEXT, strength INTEGER,
            audit_status TEXT, parsed_json TEXT,
            created_at TEXT, archived_at TEXT DEFAULT (datetime('now'))
        )""",
    TABLE_SNAPSHOTS: """
        CREATE TABLE IF NOT EXISTS {t} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE, state_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
    TABLE_AUDIT_LOG: """
        CREATE TABLE IF NOT EXISTS {t} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT, action TEXT,
            operator TEXT DEFAULT 'system', detail TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
}

INDEXES = [
    f"CREATE INDEX IF NOT EXISTS idx_sd_code ON {TABLE_STOCK_DAILY}(code)",
    f"CREATE INDEX IF NOT EXISTS idx_sd_date ON {TABLE_STOCK_DAILY}(date)",
    f"CREATE INDEX IF NOT EXISTS idx_sd_code_date ON {TABLE_STOCK_DAILY}(code,date)",
    f"CREATE INDEX IF NOT EXISTS idx_cf_code ON {TABLE_CAPITAL_FLOW}(code)",
    f"CREATE INDEX IF NOT EXISTS idx_news_code ON {TABLE_NEWS}(code)",
    f"CREATE INDEX IF NOT EXISTS idx_events_dir ON {TABLE_EVENTS}(direction)",
    f"CREATE INDEX IF NOT EXISTS idx_snaps_name ON {TABLE_SNAPSHOTS}(name)",
]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="初始化数据库")
    parser.add_argument("--reset", action="store_true", help="删除所有表后重建")
    args = parser.parse_args()

    db = DBConnection()
    print(f"数据库: {db.db_path}")

    with db.connect() as conn:
        if args.reset:
            for t in TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {t}")
            print("已删除所有表")

        for t, ddl in TABLES.items():
            conn.execute(ddl.format(t=t))
            print(f"  ✅ {t}")

        for idx in INDEXES:
            try:
                conn.execute(idx)
            except Exception:
                pass
        conn.commit()
        print(f"  ✅ {len(INDEXES)} 个索引")

    print("数据库初始化完成")


if __name__ == "__main__":
    main()

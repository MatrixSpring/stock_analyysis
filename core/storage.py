# -*- coding: utf-8 -*-
"""
===================================
本地持久化模块 — core/storage.py
===================================

落地能力：
- 保存事件库、产业链图谱结构、推演方案快照到 SQLite
- 浏览器刷新 / 重启系统后，可加载历史推演工程
- 解决当前系统重大缺失：刷新页面全部配置丢失

使用方式：
    from core.storage import Storage
    store = Storage()
    store.save_snapshot("snapshot_name")
    store.load_snapshot("snapshot_name")
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.global_state import GlobalState

logger = logging.getLogger(__name__)

# 默认数据库路径
DEFAULT_DB_PATH = Path(os.getenv("DSA_STORAGE_DB", "data/dsa_workspace.db"))


class Storage:
    """
    本地持久化管理器（SQLite）。

    表结构：
    - snapshots: 完整工作区快照
    - events_archive: 历史事件归档
    - audit_log: 审核操作日志
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_db()

    def _ensure_db(self):
        """初始化数据库表"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    title TEXT,
                    direction TEXT,
                    strength INTEGER,
                    audit_status TEXT,
                    parsed_json TEXT,
                    created_at TEXT,
                    archived_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    operator TEXT DEFAULT 'system',
                    detail TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

    # ---- 快照 ----

    def save_snapshot(self, name: str) -> bool:
        """
        保存当前完整工作区快照。

        Args:
            name: 快照名称（唯一标识）

        Returns:
            是否保存成功
        """
        try:
            gs = GlobalState.get_instance()
            state_json = json.dumps(gs.get_all_state(), ensure_ascii=False, default=str)

            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT INTO snapshots (name, state_json, updated_at)
                       VALUES (?, ?, datetime('now'))
                       ON CONFLICT(name) DO UPDATE SET
                       state_json=excluded.state_json,
                       updated_at=datetime('now')""",
                    (name, state_json),
                )
                conn.commit()

            logger.info(f"[Storage] 快照已保存: {name}")
            return True
        except Exception as e:
            logger.error(f"[Storage] 保存快照失败: {e}")
            return False

    def load_snapshot(self, name: str) -> bool:
        """
        从快照恢复工作区。

        Returns:
            是否恢复成功
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                row = conn.execute(
                    "SELECT state_json FROM snapshots WHERE name=?",
                    (name,),
                ).fetchone()

            if not row:
                logger.warning(f"[Storage] 快照不存在: {name}")
                return False

            state_json = json.loads(row[0])
            gs = GlobalState.get_instance()
            gs.restore_state(state_json)

            logger.info(f"[Storage] 快照已恢复: {name}")
            return True
        except Exception as e:
            logger.error(f"[Storage] 恢复快照失败: {e}")
            return False

    def list_snapshots(self) -> List[Dict[str, str]]:
        """列出所有快照"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                rows = conn.execute(
                    "SELECT name, created_at, updated_at FROM snapshots ORDER BY updated_at DESC"
                ).fetchall()
            return [
                {"name": r[0], "created_at": r[1], "updated_at": r[2]}
                for r in rows
            ]
        except Exception as e:
            logger.error(f"[Storage] 列出快照失败: {e}")
            return []

    def delete_snapshot(self, name: str) -> bool:
        """删除快照"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM snapshots WHERE name=?", (name,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[Storage] 删除快照失败: {e}")
            return False

    # ---- 事件归档 ----

    def archive_event(self, event_id: str) -> bool:
        """将事件存入归档数据库"""
        gs = GlobalState.get_instance()
        event = gs.events.get(event_id)
        if not event:
            return False

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT INTO events_archive
                       (event_id, title, direction, strength, audit_status, parsed_json, created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        event.event_id,
                        event.title,
                        event.direction,
                        event.strength,
                        event.audit_status,
                        json.dumps(event.parsed_json, ensure_ascii=False, default=str),
                        event.created_at,
                    ),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[Storage] 归档事件失败: {e}")
            return False

    def list_archived_events(
        self, direction: Optional[str] = None, audit_status: Optional[str] = None, limit: int = 50
    ) -> List[Dict]:
        """查询已归档事件"""
        try:
            query = "SELECT * FROM events_archive WHERE 1=1"
            params: list = []
            if direction:
                query += " AND direction=?"
                params.append(direction)
            if audit_status:
                query += " AND audit_status=?"
                params.append(audit_status)
            query += " ORDER BY archived_at DESC LIMIT ?"
            params.append(limit)

            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[Storage] 查询归档失败: {e}")
            return []

    # ---- 审核日志 ----

    def log_audit(self, event_id: str, action: str, operator: str = "system", detail: str = ""):
        """记录审核操作"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    "INSERT INTO audit_log (event_id, action, operator, detail) VALUES (?,?,?,?)",
                    (event_id, action, operator, detail),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"[Storage] 审核日志写入失败: {e}")

    def get_audit_history(self, event_id: str) -> List[Dict]:
        """获取事件的审核操作历史"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE event_id=? ORDER BY created_at DESC",
                    (event_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[Storage] 审核历史查询失败: {e}")
            return []

    # ---- 自动保存 ----

    def auto_save(self):
        """自动保存当前状态到默认快照"""
        self.save_snapshot("_auto_save")

    def auto_load(self) -> bool:
        """启动时自动恢复"""
        return self.load_snapshot("_auto_save")

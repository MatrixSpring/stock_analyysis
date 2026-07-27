# -*- coding: utf-8 -*-
"""
SSE 连接管理器 — 心跳检测、自动回收
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SSEManager:
    """SSE 连接管理器"""

    _instance: Optional["SSEManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._conns: Dict[str, Dict[str, Any]] = {}
            cls._instance._running = False
        return cls._instance

    def register(self, user_id: str = "anonymous",
                 metadata: Optional[Dict[str, Any]] = None) -> str:
        conn_id = str(uuid.uuid4())[:8]
        self._conns[conn_id] = {
            "id": conn_id, "user_id": user_id, "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "last_heartbeat": datetime.utcnow().isoformat(),
            "message_count": 0, "is_active": True,
            "event_queue": asyncio.Queue(maxsize=500),
        }
        logger.info(f"SSE registered: {conn_id}")
        return conn_id

    def unregister(self, conn_id: str):
        conn = self._conns.pop(conn_id, None)
        if conn:
            conn["is_active"] = False
            logger.info(f"SSE unregistered: {conn_id}")

    async def send_event(self, conn_id: str, event_type: str, data: Any,
                         event_id: Optional[str] = None) -> bool:
        conn = self._conns.get(conn_id)
        if not conn or not conn["is_active"]:
            return False
        try:
            await conn["event_queue"].put({
                "id": event_id or str(uuid.uuid4())[:8],
                "event": event_type,
                "data": json.dumps(data, default=str),
            })
            conn["message_count"] += 1
            return True
        except asyncio.QueueFull:
            return False

    async def stream_response(self, conn_id: str, heartbeat: int = 30):
        conn = self._conns.get(conn_id)
        if not conn:
            yield f"event: error\ndata: {json.dumps({'error': 'connection not found'})}\n\n"
            return

        try:
            while conn["is_active"]:
                try:
                    event = await asyncio.wait_for(conn["event_queue"].get(), timeout=heartbeat)
                    yield f"id: {event['id']}\n"
                    yield f"event: {event['event']}\n"
                    yield f"data: {event['data']}\n\n"
                    conn["last_heartbeat"] = datetime.utcnow().isoformat()
                except asyncio.TimeoutError:
                    conn["last_heartbeat"] = datetime.utcnow().isoformat()
                    yield f"event: heartbeat\ndata: {json.dumps({'ts': datetime.utcnow().isoformat()})}\n\n"
        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            self.unregister(conn_id)

    def get_stats(self) -> Dict[str, Any]:
        active = sum(1 for c in self._conns.values() if c["is_active"])
        return {"total": len(self._conns), "active": active, "idle": len(self._conns) - active}


sse_manager = SSEManager()

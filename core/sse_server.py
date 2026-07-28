# -*- coding: utf-8 -*-
"""
===================================
SSE 流式推送服务 — core/sse_server.py
===================================

提供 Server-Sent Events 实时推送能力：
- 任务进度（AI 分析 / 批量选股 / 回测）
- LLM 推理实时日志
- 数据源拉取状态

配合前端 EventSource 使用：
    const es = new EventSource('/api/sse/task/progress?job_id=xxx')
    es.onmessage = (e) => console.log(JSON.parse(e.data))

在 FastAPI 中注册：
    from core.sse_server import create_sse_router
    app.include_router(create_sse_router())
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 事件存储（内存，用于 SSE 推送）
# ============================================================

class EventStream:
    """单任务事件流"""

    def __init__(self, stream_id: str, max_events: int = 500):
        self.stream_id = stream_id
        self.events: List[Dict[str, Any]] = []
        self.max_events = max_events
        self._subscribers: List[asyncio.Queue] = []
        self.created_at = time.time()
        self.status = "active"

    def push(self, event_type: str, data: Any):
        """推送事件到流"""
        event = {
            "id": str(uuid.uuid4())[:8],
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        # 通知订阅者
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        """创建订阅队列"""
        queue = asyncio.Queue(maxsize=256)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def get_history(self) -> List[Dict]:
        return list(self.events)


class SSEManager:
    """SSE 流管理器（单例）"""

    _instance: Optional["SSEManager"] = None

    def __init__(self):
        self.streams: Dict[str, EventStream] = {}

    @classmethod
    def get_instance(cls) -> "SSEManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_stream(self, stream_id: str) -> EventStream:
        stream = EventStream(stream_id)
        self.streams[stream_id] = stream
        return stream

    def get_stream(self, stream_id: str) -> Optional[EventStream]:
        return self.streams.get(stream_id)

    def push_event(self, stream_id: str, event_type: str, data: Any):
        stream = self.get_stream(stream_id)
        if stream:
            stream.push(event_type, data)
        else:
            logger.warning(f"[SSE] 流不存在: {stream_id}")

    def cleanup(self, max_age_seconds: int = 3600):
        """清理过期流"""
        now = time.time()
        expired = [
            sid for sid, s in self.streams.items()
            if now - s.created_at > max_age_seconds
        ]
        for sid in expired:
            del self.streams[sid]
        if expired:
            logger.info(f"[SSE] 清理 {len(expired)} 个过期流")


# ============================================================
# FastAPI SSE 路由
# ============================================================

def create_sse_router() -> "APIRouter":
    """创建 SSE FastAPI 路由"""
    from fastapi import APIRouter, Request
    from fastapi.responses import StreamingResponse

    router = APIRouter(prefix="/api/sse", tags=["SSE"])

    @router.get("/task/{stream_id}")
    async def stream_task_events(stream_id: str, request: Request):
        """SSE 端点：订阅任务事件流"""
        manager = SSEManager.get_instance()
        stream = manager.get_stream(stream_id)

        async def event_generator():
            if stream is None:
                yield f"data: {json.dumps({'error': '流不存在'})}\n\n"
                return

            # 先发送历史事件
            for event in stream.get_history():
                if await request.is_disconnected():
                    return
                yield f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

            # 订阅新事件
            queue = stream.subscribe()
            try:
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                stream.unsubscribe(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/task/{stream_id}/push")
    async def push_task_event(stream_id: str, event_type: str = "progress", data: Dict[str, Any] = None):
        """推送事件到指定流（内部 API）"""
        manager = SSEManager.get_instance()
        manager.push_event(stream_id, event_type, data or {})
        return {"ok": True, "stream_id": stream_id}

    @router.get("/streams")
    async def list_streams():
        """列出所有活跃流"""
        manager = SSEManager.get_instance()
        return {
            "streams": {
                sid: {
                    "status": s.status,
                    "event_count": len(s.events),
                    "created_at": s.created_at,
                }
                for sid, s in manager.streams.items()
            }
        }

    return router


# ============================================================
# 便捷工具
# ============================================================

class TaskProgress:
    """任务进度推送器（配合 SSEManager）"""

    def __init__(self, stream_id: str, total_steps: int = 100):
        self.stream_id = stream_id
        self.total_steps = total_steps
        self.current_step = 0
        self.manager = SSEManager.get_instance()
        self.manager.create_stream(stream_id)

    def progress(self, msg: str, step: int = 1, detail: Optional[Dict] = None):
        """推送进度"""
        self.current_step = min(self.current_step + step, self.total_steps)
        pct = round(self.current_step / self.total_steps * 100, 1)
        self.manager.push_event(self.stream_id, "progress", {
            "msg": msg,
            "pct": pct,
            "step": self.current_step,
            "total": self.total_steps,
            "detail": detail,
        })
        logger.debug(f"[TaskProgress] {self.stream_id}: {pct}% - {msg}")

    def info(self, msg: str, **kwargs):
        """推送信息"""
        self.manager.push_event(self.stream_id, "info", {"msg": msg, **kwargs})

    def warn(self, msg: str, **kwargs):
        """推送警告"""
        self.manager.push_event(self.stream_id, "warn", {"msg": msg, **kwargs})

    def error(self, msg: str, **kwargs):
        """推送错误"""
        self.manager.push_event(self.stream_id, "error", {"msg": msg, **kwargs})
        stream = self.manager.get_stream(self.stream_id)
        if stream:
            stream.status = "error"

    def complete(self, result: Any = None):
        """标记完成"""
        self.current_step = self.total_steps
        self.manager.push_event(self.stream_id, "complete", {
            "msg": "任务完成",
            "result": result,
        })
        stream = self.manager.get_stream(self.stream_id)
        if stream:
            stream.status = "completed"

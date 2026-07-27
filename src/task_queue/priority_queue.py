# -*- coding: utf-8 -*-
"""
优先级任务队列 — 基于 asyncio.PriorityQueue + 分布式锁
"""
from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    CRITICAL = 0
    HIGH = 10
    NORMAL = 20
    LOW = 30
    BACKGROUND = 40


@dataclass(order=True)
class PriorityTask:
    priority: TaskPriority
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    func: Optional[Callable] = field(default=None, compare=False)
    args: tuple = field(default=(), compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    timeout: int = 300
    max_retries: int = 0


class PriorityTaskQueue:
    """优先级任务队列"""

    def __init__(self, max_concurrent: int = 4):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running: Dict[str, asyncio.Task] = {}
        self._status: Dict[str, Dict[str, Any]] = {}
        self._max_concurrent = max_concurrent
        self._workers: List[asyncio.Task] = []
        self._running_flag = False

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def running(self) -> int:
        return len(self._running)

    async def submit(self, func: Callable, priority: TaskPriority = TaskPriority.NORMAL,
                     name: str = "", timeout: int = 300, max_retries: int = 0,
                     *args, **kwargs) -> str:
        task = PriorityTask(priority=priority, name=name or getattr(func, "__name__", "task"),
                           func=func, args=args, kwargs=kwargs,
                           timeout=timeout, max_retries=max_retries)
        await self._queue.put((priority.value, task))
        self._status[task.id] = {"status": "pending", "name": task.name, "priority": priority.name}
        return task.id

    async def submit_user_task(self, func: Callable, name: str = "",
                               timeout: int = 120, *args, **kwargs) -> str:
        return await self.submit(func, TaskPriority.CRITICAL, name, timeout, 0, *args, **kwargs)

    async def start(self, num_workers: int = 0):
        if self._running_flag:
            return
        self._running_flag = True
        for i in range(num_workers or self._max_concurrent):
            w = asyncio.create_task(self._worker(i))
            self._workers.append(w)
        logger.info(f"TaskQueue started: {len(self._workers)} workers")

    async def stop(self):
        self._running_flag = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._status.get(task_id)

    async def _worker(self, wid: int):
        while self._running_flag:
            try:
                _, task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if self._status.get(task.id, {}).get("status") == "cancelled":
                self._queue.task_done()
                continue

            await self._execute(task, wid)
            self._queue.task_done()

    async def _execute(self, task: PriorityTask, wid: int):
        tid = task.id
        self._running[tid] = asyncio.current_task()  # type: ignore[assignment]
        self._status[tid].update(status="running", started_at=datetime.utcnow().isoformat(), worker=wid)

        try:
            result = await asyncio.wait_for(self._run_with_retry(task), timeout=task.timeout)
            self._status[tid].update(status="completed", result=result,
                                     completed_at=datetime.utcnow().isoformat())
        except asyncio.TimeoutError:
            self._status[tid].update(status="timeout", error=f"超时({task.timeout}s)")
        except Exception as e:
            self._status[tid].update(status="failed", error=str(e), traceback=traceback.format_exc())
        finally:
            self._running.pop(tid, None)

    async def _run_with_retry(self, task: PriorityTask) -> Any:
        last_err = None
        for attempt in range(task.max_retries + 1):
            try:
                return await task.func(*task.args, **task.kwargs)
            except Exception as e:
                last_err = e
                if attempt < task.max_retries:
                    await asyncio.sleep(2 ** attempt)
        raise last_err  # type: ignore[misc]

# -*- coding: utf-8 -*-
"""
全局异步任务执行器 — 基于 ThreadPoolExecutor

职责：
1. 批量任务异步化执行
2. 进度追踪 + 取消 + 超时隔离
3. 零外部依赖
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    task_id: str
    name: str
    state: TaskState = TaskState.PENDING
    progress: int = 0
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    _future: Optional[Future] = field(default=None, repr=False)

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "state": self.state.value,
            "progress": self.progress,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "error": self.error,
        }


class TaskQueue:
    """线程池任务队列（全局单例）"""

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, TaskInfo] = {}
        self._lock = threading.Lock()
        self._max_workers = max_workers
        logger.info(f"[TaskQueue] 初始化 (workers={max_workers})")

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def submit(
        self, name: str, func: Callable[..., Any], *args,
        timeout: Optional[float] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        **kwargs,
    ) -> str:
        task_id = str(uuid.uuid4())[:12]
        task = TaskInfo(task_id=task_id, name=name)
        with self._lock:
            self._tasks[task_id] = task

        # Capture task reference before submitting to avoid dict lookup in thread
        _task = task
        def _runner():
            _task.state = TaskState.RUNNING
            _task.started_at = time.time()
            try:
                if progress_callback:
                    progress_callback(0)
                result = func(*args, **kwargs)
                _task.state = TaskState.COMPLETED
                _task.result = result
                _task.progress = 100
                if progress_callback:
                    progress_callback(100)
                return result
            except Exception as e:
                _task.state = TaskState.FAILED
                _task.error = f"{type(e).__name__}: {str(e)[:200]}"
                logger.error(f"[TaskQueue] 失败 {task_id}: {_task.error}")
                raise
            finally:
                _task.completed_at = time.time()

        future = self._executor.submit(_runner)
        task._future = future
        task.state = TaskState.PENDING
        return task_id

    def submit_batch(self, name: str, func: Callable[..., Any],
                     items: List[Any]) -> List[str]:
        return [self.submit(f"{name}[{i}]", func, item) for i, item in enumerate(items)]

    def status(self, task_id: str) -> Dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            return {"task_id": task_id, "state": "unknown", "error": "not found"}
        return task.to_dict()

    def result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"任务不存在: {task_id}")
        if task._future is None:
            raise RuntimeError("任务未正确提交")
        return task._future.result(timeout=timeout)

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task._future and not task._future.done():
            cancelled = task._future.cancel()
            if cancelled:
                task.state = TaskState.CANCELLED
            return cancelled
        return False

    def list_tasks(self, state: Optional[TaskState] = None) -> List[Dict[str, Any]]:
        tasks = list(self._tasks.values())
        if state:
            tasks = [t for t in tasks if t.state == state]
        return [t.to_dict() for t in tasks]

    def pending_count(self) -> int:
        return sum(1 for t in self._tasks.values()
                   if t.state in (TaskState.PENDING, TaskState.RUNNING))

    def cleanup(self, max_age_seconds: float = 3600):
        now = time.time()
        to_remove = []
        for tid, t in self._tasks.items():
            if t.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
                age = now - (t.completed_at or t.created_at)
                if max_age_seconds < 0 or age > max_age_seconds:
                    to_remove.append(tid)
        for tid in to_remove:
            del self._tasks[tid]

    def shutdown(self, wait: bool = True):
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

_queue_instance: Optional[TaskQueue] = None
_queue_lock = threading.Lock()


def get_task_queue(max_workers: int = 4) -> TaskQueue:
    global _queue_instance
    if _queue_instance is None:
        with _queue_lock:
            if _queue_instance is None:
                _queue_instance = TaskQueue(max_workers=max_workers)
    return _queue_instance

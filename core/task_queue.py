# -*- coding: utf-8 -*-
"""
===================================
异步任务队列 — core/task_queue.py
===================================

轻量化异步任务调度，支持 RQ（Redis Queue）。
无 Redis 时降级为内存线程池模式。

使用方式：
    from core.task_queue import TaskQueue
    tq = TaskQueue()
    job_id = tq.submit(my_func, arg1, arg2)
    status = tq.get_status(job_id)
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 线程池大小
_MAX_WORKERS = int(os.getenv("TASK_WORKERS", "4"))


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"


class TaskRecord:
    """任务记录"""
    __slots__ = ("job_id", "status", "func_name", "result", "error", "created_at", "started_at", "finished_at")

    def __init__(self, job_id: str, func_name: str):
        self.job_id = job_id
        self.status = TaskStatus.PENDING
        self.func_name = func_name
        self.result: Any = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "func_name": self.func_name,
            "error": self.error,
            "created_at": self.created_at,
            "duration": (
                round(self.finished_at - self.started_at, 3)
                if self.started_at and self.finished_at else None
            ),
        }


class TaskQueue:
    """
    异步任务队列。

    优先使用 RQ+Redis，不可用时降级为内存线程池。
    """

    def __init__(self):
        self._mode = self._detect_mode()
        self._executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)
        self._tasks: Dict[str, TaskRecord] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._redis_queue = None
        self._redis_conn = None

        if self._mode == "redis":
            self._init_redis()

    def _detect_mode(self) -> str:
        """检测可用模式"""
        if os.getenv("TASK_USE_REDIS", "").lower() == "true":
            try:
                import redis as _redis
                r = _redis.Redis(host="127.0.0.1", port=6379, socket_connect_timeout=2)
                r.ping()
                return "redis"
            except Exception:
                logger.warning("[TaskQueue] Redis 不可用，降级为线程池模式")
        return "threadpool"

    def _init_redis(self):
        try:
            from rq import Queue
            import redis as _redis
            self._redis_conn = _redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", "6379")),
            )
            self._redis_queue = Queue("stock_task", connection=self._redis_conn)
            logger.info("[TaskQueue] Redis 模式已启用")
        except Exception as e:
            logger.warning(f"[TaskQueue] Redis 初始化失败: {e}")
            self._mode = "threadpool"

    # ---- 提交任务 ----

    def submit(self, func: Callable, *args, **kwargs) -> str:
        """
        提交异步任务。

        Returns:
            job_id: 任务唯一标识
        """
        job_id = f"task_{uuid.uuid4().hex[:12]}"
        func_name = getattr(func, "__name__", str(func))

        record = TaskRecord(job_id, func_name)
        with self._lock:
            self._tasks[job_id] = record

        if self._mode == "redis" and self._redis_queue:
            self._redis_queue.enqueue(self._wrapped_execute, job_id, func, args, kwargs)
        else:
            future = self._executor.submit(self._wrapped_execute, job_id, func, args, kwargs)
            with self._lock:
                self._futures[job_id] = future

        logger.info(f"[TaskQueue] 任务已提交: {job_id} ({func_name})")
        return job_id

    def _wrapped_execute(self, job_id: str, func: Callable, args: tuple, kwargs: dict):
        """包装执行 + 状态记录"""
        with self._lock:
            record = self._tasks.get(job_id)
            if record:
                record.status = TaskStatus.RUNNING
                record.started_at = time.time()

        # 更新监控统计
        try:
            from core.system_monitor import get_monitor
            monitor = get_monitor()
            current = monitor.data.get("task_stat", {})
            monitor.update_task_stat(running=current.get("running", 0) + 1)
        except Exception:
            pass

        try:
            result = func(*args, **kwargs)
            with self._lock:
                if record:
                    record.status = TaskStatus.SUCCESS
                    record.result = result
                    record.finished_at = time.time()
            self._update_monitor("success")
        except Exception as e:
            logger.error(f"[TaskQueue] 任务失败 {job_id}: {e}")
            with self._lock:
                if record:
                    record.status = TaskStatus.FAILED
                    record.error = str(e)[:500]
                    record.finished_at = time.time()
            self._update_monitor("fail")

    def _update_monitor(self, status: str):
        try:
            from core.system_monitor import get_monitor
            monitor = get_monitor()
            current = monitor.data.get("task_stat", {})
            if status == "success":
                monitor.update_task_stat(
                    running=max(0, current.get("running", 1) - 1),
                    success=current.get("success", 0) + 1,
                )
            else:
                monitor.update_task_stat(
                    running=max(0, current.get("running", 1) - 1),
                    fail=current.get("fail", 0) + 1,
                )
        except Exception:
            pass

    # ---- 查询 ----

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """查询任务状态"""
        with self._lock:
            record = self._tasks.get(job_id)

        if record:
            return record.to_dict()

        # 尝试 RQ 查询
        if self._mode == "redis" and self._redis_conn:
            try:
                from rq.job import Job
                job = Job.fetch(job_id, connection=self._redis_conn)
                return {
                    "job_id": job.id,
                    "status": job.get_status(),
                    "result": str(job.result)[:200] if job.result else None,
                    "error": str(job.exc_info)[:200] if job.exc_info else None,
                }
            except Exception:
                pass

        return {"job_id": job_id, "status": TaskStatus.NOT_FOUND}

    def get_all_tasks(self, limit: int = 50) -> List[Dict]:
        """获取所有任务列表"""
        with self._lock:
            tasks = list(self._tasks.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def get_stats(self) -> Dict[str, int]:
        """任务统计"""
        with self._lock:
            tasks = list(self._tasks.values())
        return {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
            "success": sum(1 for t in tasks if t.status == TaskStatus.SUCCESS),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
        }

    def cleanup(self, max_age_hours: int = 24):
        """清理过期任务记录"""
        cutoff = time.time() - max_age_hours * 3600
        with self._lock:
            to_delete = [
                jid for jid, t in self._tasks.items()
                if t.finished_at and t.finished_at < cutoff
            ]
            for jid in to_delete:
                del self._tasks[jid]
                self._futures.pop(jid, None)
        if to_delete:
            logger.info(f"[TaskQueue] 清理 {len(to_delete)} 个过期任务")


# 全局单例
_task_queue_instance: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    global _task_queue_instance
    if _task_queue_instance is None:
        _task_queue_instance = TaskQueue()
    return _task_queue_instance

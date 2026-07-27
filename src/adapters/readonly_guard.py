# -*- coding: utf-8 -*-
"""
===================================
只读守卫 — ReadOnlyGuard
===================================

职责：
1. 拦截旧模块的写入操作并拒绝
2. 记录所有被拦截的写入尝试（审计日志）
3. 提供白名单机制：允许特定可信模块写入
4. 返回清晰的错误信息，引导使用新版接口
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class WriteAttempt:
    """写入尝试记录"""
    timestamp: float
    module: str
    operation: str
    table: str = ""
    caller: str = ""
    blocked: bool = True


class ReadOnlyGuard:
    """
    只读守卫。

    在旧模块的数据库操作层注入，拦截 INSERT/UPDATE/DELETE，
    只允许 SELECT/READ 操作通过。

    使用方式：
        guard = ReadOnlyGuard()
        guard.allow_write("new_module.auth")  # 白名单

        # 在 Repository 层包裹
        result = guard.guard("legacy_analysis", "INSERT INTO ...", lambda: execute())
    """

    def __init__(self):
        self._write_lock = threading.Lock()
        self._allowed_writers: Set[str] = set()
        self._attempts: List[WriteAttempt] = []
        self._max_attempts = 1000  # 最多保留记录数
        self._enabled = True

        # 默认允许新版内部模块写入
        self._allowed_writers.update([
            "src.services",
            "src.core",
            "api.v1",
            "data_provider",
            "new_module",
        ])

    # ============================================================
    # 守卫方法
    # ============================================================

    def guard(
        self,
        module: str,
        operation: str,
        executor: Callable[[], Any],
        table: str = "",
    ) -> Any:
        """
        守卫执行：检测到写入操作时拒绝或放行。

        Args:
            module: 调用方模块名（如 "legacy_analysis", "src.services.analysis"）
            operation: 操作描述（如 "INSERT", "UPDATE", "DELETE", "SELECT"）
            executor: 实际执行的函数
            table: 操作的目标表名

        Returns:
            executor 的返回值（允许时）
            Raises PermissionError（拒绝时）

        Raises:
            ReadOnlyViolationError: 写入操作被拦截
        """
        if not self._enabled:
            return executor()

        # 判断是否是写入操作
        op_upper = operation.upper().strip()
        is_write = any(
            op_upper.startswith(verb)
            for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "WRITE")
        )

        if not is_write:
            return executor()

        # 检查白名单
        if self._is_allowed(module):
            logger.debug(f"[ReadOnlyGuard] 允许写入: {module} -> {operation}")
            return executor()

        # 拦截
        self._record_attempt(module, operation, table, blocked=True)
        raise ReadOnlyViolationError(
            module=module,
            operation=operation,
            table=table,
        )

    def guard_method(self, module: str):
        """
        装饰器模式：标记方法为只读守卫保护。

        用法：
            guard = ReadOnlyGuard()

            @guard.guard_method("legacy.analysis")
            def insert_analysis(self, data):
                ...
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                func_name = getattr(func, "__name__", "unknown")
                operation = self._infer_operation(func_name)
                if operation and self._is_write_operation(operation):
                    if not self._is_allowed(module):
                        raise ReadOnlyViolationError(
                            module=module,
                            operation=operation,
                            table="",
                        )
                return func(*args, **kwargs)
            return wrapper
        return decorator

    # ============================================================
    # 白名单管理
    # ============================================================

    def allow_write(self, module: str):
        """将指定模块加入写入白名单"""
        with self._write_lock:
            self._allowed_writers.add(module)
            logger.info(f"[ReadOnlyGuard] 写入白名单添加: {module}")

    def revoke_write(self, module: str):
        """撤销指定模块的写入权限"""
        with self._write_lock:
            self._allowed_writers.discard(module)
            logger.info(f"[ReadOnlyGuard] 写入白名单移除: {module}")

    def list_allowed_writers(self) -> List[str]:
        """列出所有允许写入的模块"""
        return sorted(self._allowed_writers)

    # ============================================================
    # 审计与监控
    # ============================================================

    def get_blocked_attempts(
        self,
        module: Optional[str] = None,
        since: Optional[float] = None,
    ) -> List[WriteAttempt]:
        """获取被拦截的写入尝试记录"""
        result = self._attempts
        if module:
            result = [a for a in result if a.module == module]
        if since:
            result = [a for a in result if a.timestamp >= since]
        return result

    def get_audit_summary(self) -> Dict[str, Any]:
        """获取审计摘要"""
        blocked = [a for a in self._attempts if a.blocked]
        by_module: Dict[str, int] = {}
        for a in blocked:
            by_module[a.module] = by_module.get(a.module, 0) + 1

        return {
            "total_blocked": len(blocked),
            "total_attempts": len(self._attempts),
            "by_module": dict(sorted(by_module.items(), key=lambda x: -x[1])[:10]),
            "guard_enabled": self._enabled,
            "allowed_writers": sorted(self._allowed_writers),
        }

    def clear_attempts(self):
        """清空写入尝试记录"""
        self._attempts.clear()

    # ============================================================
    # 开关控制
    # ============================================================

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        logger.info(f"[ReadOnlyGuard] 守卫状态: {'启用' if value else '禁用'}")

    # ============================================================
    # 内部
    # ============================================================

    def _is_allowed(self, module: str) -> bool:
        return module in self._allowed_writers

    def _record_attempt(self, module: str, operation: str, table: str, blocked: bool):
        attempt = WriteAttempt(
            timestamp=time.time(),
            module=module,
            operation=operation,
            table=table,
            blocked=blocked,
        )
        self._attempts.append(attempt)
        if len(self._attempts) > self._max_attempts:
            self._attempts = self._attempts[-self._max_attempts:]

        if blocked:
            logger.warning(
                f"[ReadOnlyGuard] 已拦截写入: module={module} op={operation} table={table}"
            )

    @staticmethod
    def _infer_operation(func_name: str) -> str:
        """从函数名推断操作类型"""
        name_lower = func_name.lower()
        if any(w in name_lower for w in ("insert", "add", "create", "save")):
            return "INSERT"
        if any(w in name_lower for w in ("update", "modify", "edit", "set")):
            return "UPDATE"
        if any(w in name_lower for w in ("delete", "remove", "drop", "clear")):
            return "DELETE"
        if any(w in name_lower for w in ("select", "get", "query", "find", "fetch", "read", "list")):
            return "SELECT"
        return "UNKNOWN"

    @staticmethod
    def _is_write_operation(operation: str) -> bool:
        return operation.upper() in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE")


class ReadOnlyViolationError(PermissionError):
    """读写违规异常"""

    def __init__(self, module: str, operation: str, table: str = ""):
        self.module = module
        self.operation = operation
        self.table = table
        target = f" on table {table}" if table else ""
        super().__init__(
            f"[ReadOnlyGuard] 旧模块 '{module}' 尝试执行写入操作 '{operation}'{target} 已被拦截。"
            f"旧模块仅支持只读回溯查询。如需写入数据，请使用新版 API 接口。"
        )

# -*- coding: utf-8 -*-
"""
===================================
增强日志工具 — core/logging_enhance.py
===================================

在项目现有 logging 基础上提供便捷函数，不替代原有日志系统。

使用方式：
    from core.logging_enhance import log_call, get_caller_info
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
import traceback
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_logger = logging.getLogger("dsa.enhance")


# ============================================================
# 调用日志装饰器
# ============================================================

def log_call(
    level: int = logging.DEBUG,
    log_args: bool = False,
    log_result: bool = False,
    log_time: bool = True,
    reraise: bool = True,
    default_return: Any = None,
):
    """
    装饰器：自动记录函数调用、耗时、异常。

    Args:
        level: 日志级别
        log_args: 是否记录参数
        log_result: 是否记录返回值
        log_time: 是否记录耗时
        reraise: 异常后是否重新抛出
        default_return: 异常时的默认返回值

    Usage:
        @log_call(log_time=True)
        def fetch_data(symbol): ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            t0 = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - t0) * 1000
                extra = f" ({elapsed:.0f}ms)" if log_time else ""
                _logger.log(level, f"{func_name} ✓{extra}")
                return result
            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                _logger.error(
                    f"{func_name} ✗ {type(e).__name__}: {e} ({elapsed:.0f}ms)\n"
                    f"{traceback.format_exc()[-500:]}"
                )
                if reraise:
                    raise
                return default_return
        return wrapper  # type: ignore[return-value]
    return decorator


# ============================================================
# 安全包装执行
# ============================================================

def safe_call(
    func: Callable,
    *args,
    default: Any = None,
    log_errors: bool = True,
    **kwargs,
) -> Any:
    """
    安全执行函数，异常时返回默认值并记录日志。

    Args:
        func: 要执行的函数
        default: 异常时的默认返回值
        log_errors: 是否记录异常
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            _logger.warning(
                f"safe_call({getattr(func, '__name__', str(func))}): "
                f"{type(e).__name__}: {e}"
            )
        return default


# ============================================================
# 调用栈信息
# ============================================================

def get_caller_info() -> str:
    """获取调用者的文件名和行号"""
    frame = inspect.currentframe()
    caller = frame.f_back.f_back if frame and frame.f_back else None
    if caller:
        return f"{caller.f_code.co_filename}:{caller.f_lineno}"
    return "unknown"

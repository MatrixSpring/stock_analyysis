# -*- coding: utf-8 -*-
"""
===================================
网络请求工具 — core/network_utils.py
===================================

统一对外部 API 调用的超时、重试、降级策略。
数据源调用必须经过此层，避免页面卡死或被限流封禁。

使用方式：
    from core.network_utils import fetch_with_timeout, safe_request
"""

from __future__ import annotations

import functools
import logging
import signal
import time
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# 默认配置（可通过环境变量覆盖）
DEFAULT_TIMEOUT_SEC = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_BACKOFF = 2.0


# ============================================================
# 超时包装（跨平台，不依赖 signal）
# ============================================================

def with_timeout(timeout_sec: float = DEFAULT_TIMEOUT_SEC):
    """
    装饰器：为函数调用添加超时限制。

    超时后抛出 TimeoutError，由上层重试机制接管。
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_sec)
                except concurrent.futures.TimeoutError:
                    logger.error(
                        f"[timeout] {func.__name__} 执行超时 ({timeout_sec}s)"
                    )
                    raise TimeoutError(
                        f"{func.__name__} 超时 ({timeout_sec}s)，数据源可能不可用"
                    )
        return wrapper  # type: ignore[return-value]
    return decorator


# ============================================================
# 安全请求封装（超时 + 重试 + 降级）
# ============================================================

def safe_request(
    func: Callable,
    *args,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    backoff: float = DEFAULT_BACKOFF,
    default: Any = None,
    **kwargs,
) -> Any:
    """
    安全执行外部请求：超时 + 自动重试 + 降级返回默认值。

    Args:
        func: 要执行的函数
        timeout_sec: 单次超时秒数
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟
        backoff: 退避倍数
        default: 全部失败后的降级返回值
    """
    delay = retry_delay
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(func, *args, **kwargs)
                return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            last_error = TimeoutError(f"{getattr(func, '__name__', 'request')} 超时 ({timeout_sec}s)")
            logger.warning(f"[safe_request] 第{attempt}次超时 ({timeout_sec}s)")
        except Exception as e:
            last_error = e
            logger.warning(
                f"[safe_request] 第{attempt}次失败: {type(e).__name__}: {e}"
            )

        if attempt < max_retries:
            logger.info(f"[safe_request] {delay:.1f}s 后重试...")
            time.sleep(delay)
            delay *= backoff

    logger.error(
        f"[safe_request] {getattr(func, '__name__', 'request')} "
        f"重试{max_retries}次全部失败，返回降级值: {last_error}"
    )
    return default


# ============================================================
# 限流器（令牌桶）
# ============================================================

class RateLimiter:
    """简易令牌桶限流器，防止频繁调用第三方 API 被封。"""

    def __init__(self, max_calls: int = 10, per_seconds: float = 60.0):
        self._max_calls = max_calls
        self._per_seconds = per_seconds
        self._tokens = max_calls
        self._last_refill = time.time()

    def acquire(self) -> bool:
        """尝试获取令牌，成功返回 True。"""
        now = time.time()
        elapsed = now - self._last_refill

        # 按时间比例补充令牌
        refill = int(elapsed / self._per_seconds * self._max_calls)
        if refill > 0:
            self._tokens = min(self._max_calls, self._tokens + refill)
            self._last_refill = now

        if self._tokens > 0:
            self._tokens -= 1
            return True
        return False

    def wait_and_acquire(self, timeout: float = 60.0) -> bool:
        """等待直到获取令牌或超时。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.acquire():
                return True
            time.sleep(1.0)
        return False

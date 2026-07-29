import time
from functools import wraps
from src.core.logger import get_logger

logger = get_logger()


def trace_cost(func_name: str = None):
    """函数耗时装饰器，记录执行时长"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            real_name = func_name or func.__name__
            try:
                res = func(*args, **kwargs)
                cost = round((time.perf_counter() - start) * 1000, 2)
                logger.info(f"[Trace] {real_name} 执行耗时 {cost} ms")
                return res
            except Exception as e:
                cost = round((time.perf_counter() - start) * 1000, 2)
                logger.error(f"[Trace] {real_name} 异常，耗时 {cost} ms err={str(e)}")
                raise
        return wrapper
    return decorator

# -*- coding: utf-8 -*-
"""
===================================
全局异常体系 — utils/exception_handler.py
===================================

统一错误码、标准化异常、FastAPI 全局异常拦截。
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 错误码常量
# ============================================================

class ErrorCode:
    """统一错误码"""
    SUCCESS = 0
    # 通用 1xxx
    PARAM_INVALID = 1001
    NOT_FOUND = 1002
    UNAUTHORIZED = 1003
    RATE_LIMITED = 1004
    # 数据源 2xxx
    DATA_SOURCE_FAILED = 2001
    DATA_EMPTY = 2002
    DATA_CLEAN_FAILED = 2003
    # LLM 3xxx
    LLM_TIMEOUT = 3001
    LLM_AUTH_FAILED = 3002
    LLM_RATE_LIMITED = 3003
    LLM_PARSE_FAILED = 3004
    LLM_CONTEXT_OVERFLOW = 3005
    # 任务 4xxx
    TASK_NOT_FOUND = 4001
    TASK_FAILED = 4002
    TASK_TIMEOUT = 4003
    # 系统 5xxx
    INTERNAL_ERROR = 5001
    CONFIG_ERROR = 5002
    DB_ERROR = 5003


# ============================================================
# 业务异常
# ============================================================

class BizException(Exception):
    """业务异常基类，携带错误码和消息"""

    def __init__(self, code: int = ErrorCode.INTERNAL_ERROR, msg: str = "服务器内部异常"):
        self.code = code
        self.msg = msg
        super().__init__(msg)


# 子异常类型
class ParamInvalidError(BizException):
    def __init__(self, msg: str = "参数无效", detail: Optional[str] = None):
        super().__init__(ErrorCode.PARAM_INVALID, f"{msg}" + (f": {detail}" if detail else ""))


class DataSourceError(BizException):
    def __init__(self, msg: str = "数据源异常", source: str = ""):
        super().__init__(ErrorCode.DATA_SOURCE_FAILED, f"[{source}] {msg}" if source else msg)


class LLMError(BizException):
    def __init__(self, code: int = ErrorCode.LLM_TIMEOUT, msg: str = "LLM调用异常"):
        super().__init__(code, msg)


class TaskError(BizException):
    def __init__(self, code: int = ErrorCode.TASK_FAILED, msg: str = "任务异常"):
        super().__init__(code, msg)


# ============================================================
# FastAPI 全局异常拦截器
# ============================================================

def create_error_response(code: int, msg: str, data: dict = None):
    """创建统一错误响应格式"""
    return {
        "code": code,
        "msg": msg,
        "data": data or {},
    }


def create_success_response(data: dict = None, msg: str = "ok"):
    """创建统一成功响应格式"""
    return {
        "code": ErrorCode.SUCCESS,
        "msg": msg,
        "data": data or {},
    }


# ============================================================
# FastAPI 集成（在 app 中注册）
# ============================================================

def register_exception_handlers(app):
    """向 FastAPI 应用注册全局异常处理器"""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(BizException)
    async def biz_exception_handler(request: Request, exc: BizException):
        logger.warning(f"[BizException] code={exc.code} msg={exc.msg} path={request.url.path}")
        return JSONResponse(
            status_code=400 if exc.code < 5000 else 500,
            content=create_error_response(exc.code, exc.msg),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"[Unhandled] path={request.url.path} error={exc}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(ErrorCode.INTERNAL_ERROR, f"服务器内部异常: {str(exc)[:200]}"),
        )

    logger.info("[ExceptionHandler] 全局异常拦截器已注册")

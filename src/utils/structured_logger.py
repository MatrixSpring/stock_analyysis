# -*- coding: utf-8 -*-
"""
结构化日志 — JSON 格式，支持请求链路追踪
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


class StructuredFormatter(logging.Formatter):
    """JSON 结构化日志格式化器"""

    def __init__(self, service_name: str = "dsa"):
        super().__init__()
        self.service = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "service": self.service,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "location": f"{record.filename}:{record.lineno}",
        }

        trace_id = trace_id_var.get()
        if trace_id:
            log_data["trace_id"] = trace_id
        span_id = span_id_var.get()
        if span_id:
            log_data["span_id"] = span_id

        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "msg": str(record.exc_info[1]),
                "traceback": "".join(traceback.format_exception(*record.exc_info))[-2000:],
            }

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_structured_logging(level: int = logging.INFO):
    """配置结构化日志输出到 stdout"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

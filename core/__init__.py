# -*- coding: utf-8 -*-
"""
===================================
Core 基础设施模块
===================================

提供：
- GlobalState:   全局统一状态中心
- MessageBus:    iframe ↔ Python 双向消息总线
- utils:         通用工具函数（JSON 清洗、重试、异常封装）
"""

from core.global_state import GlobalState
from core.message_bus import MessageBus
from core.utils import clean_llm_json, retry, safe_execute, generate_id, clamp

__all__ = [
    "GlobalState",
    "MessageBus",
    "clean_llm_json",
    "retry",
    "safe_execute",
    "generate_id",
    "clamp",
]

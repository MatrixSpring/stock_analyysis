# -*- coding: utf-8 -*-
"""
===================================
Core 基础设施模块
===================================

提供：
- GlobalState:       全局统一状态中心（五大状态组）
- MessageBus:        iframe ↔ Python 双向消息总线
- EventAnalyzer:     新闻事件解析引擎 → 结构化 JSON → 自动图谱
- ChainSimulator:    产业链传导仿真引擎（BFS 级联衰减）
- Storage:           本地持久化（快照 + 事件归档 + 审核日志）
- utils:             通用工具（JSON 清洗、重试、异常封装）
"""

from core.global_state import GlobalState
from core.message_bus import MessageBus
from core.event_analyzer import EventAnalyzer
from core.chain_simulation import ChainSimulator, simulate_event
from core.storage import Storage
from core.utils import clean_llm_json, retry, safe_execute, generate_id, clamp, validate_event_json

__all__ = [
    "GlobalState",
    "MessageBus",
    "EventAnalyzer",
    "ChainSimulator",
    "simulate_event",
    "Storage",
    "clean_llm_json",
    "validate_event_json",
    "retry",
    "safe_execute",
    "generate_id",
    "clamp",
]

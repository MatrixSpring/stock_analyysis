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
- DataSourceAdapter: 多数据源统一适配器（自动降级）
- DataCleaner:       数据清洗过滤器
- LLMEngine:         统一 LLM 调用引擎（缓存、限流、截断）
- TaskQueue:         异步任务队列
- SystemMonitor:     系统状态采集服务
- utils:             通用工具（JSON 清洗、重试、异常封装）
"""

from core.global_state import GlobalState
from core.message_bus import MessageBus
from core.event_analyzer import EventAnalyzer
from core.chain_simulation import ChainSimulator, simulate_event
from core.storage import Storage
from core.data_adapter import DataSourceAdapter, get_data_adapter
from core.data_cleaner import clean_stock_data, detect_data_missing, validate_data_quality
from core.llm_engine import LLMEngine, get_llm_engine
from core.task_queue import TaskQueue, get_task_queue
from core.system_monitor import SystemMonitor, get_monitor, get_monitor_info, start_monitoring
from core.utils import clean_llm_json, retry, safe_execute, generate_id, clamp, validate_event_json

__all__ = [
    "GlobalState",
    "MessageBus",
    "EventAnalyzer",
    "ChainSimulator",
    "simulate_event",
    "Storage",
    "DataSourceAdapter",
    "get_data_adapter",
    "clean_stock_data",
    "detect_data_missing",
    "validate_data_quality",
    "LLMEngine",
    "get_llm_engine",
    "TaskQueue",
    "get_task_queue",
    "SystemMonitor",
    "get_monitor",
    "get_monitor_info",
    "start_monitoring",
    "clean_llm_json",
    "validate_event_json",
    "retry",
    "safe_execute",
    "generate_id",
    "clamp",
]

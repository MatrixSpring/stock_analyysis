# -*- coding: utf-8 -*-
"""
LLM 调度与 Prompt 管理模块

统一入口：LLMGateway
- analyze_news()      新闻结构化解析
- simulate_chain()    产业链传导推演
- diagnose_stock()    单标的多因子诊断
- revise_audit()      审核修正
- review_code()       AI 代码审查
- analyze_kline()     K 线技术解读
- screen_stocks()     自然语言选股
- chat()              通用对话
"""

from llm.gateway import LLMGateway, get_gateway, ModelProvider, TaskType, LLMResult

__all__ = ["LLMGateway", "get_gateway", "ModelProvider", "TaskType", "LLMResult"]

# -*- coding: utf-8 -*-
"""LLM 抽象基类 — 上层 Service 只依赖此接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class LLMResult:
    success: bool
    content: str = ""
    model_used: str = ""
    latency_ms: float = 0.0
    tokens_used: int = 0
    error: Optional[str] = None
    parsed_json: Optional[Dict[str, Any]] = None


class BaseLLMClient(ABC):
    """LLM 客户端抽象"""

    @abstractmethod
    def chat(
        self, prompt: str, system_prompt: str = "",
        temperature: float = 0.3, max_tokens: int = 4096,
    ) -> LLMResult:
        ...

    @abstractmethod
    def chat_with_json(
        self, prompt: str, system_prompt: str = "",
        temperature: float = 0.3, max_tokens: int = 4096,
    ) -> LLMResult:
        """要求返回 JSON，自动清洗解析"""
        ...

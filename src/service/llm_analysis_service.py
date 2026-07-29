# -*- coding: utf-8 -*-
"""LLM 分析服务 — 统一封装 AI 分析能力，供其他 Service 和 UI 调用"""

import json
import logging
from typing import Any, Dict, List, Optional

from src.llm.doubao_client import DoubaoClient, get_doubao
from src.llm.base_client import LLMResult

logger = logging.getLogger(__name__)

# 内置 Prompt 模板
PROMPT_KLINE = """你是A股技术分析专家。根据以下K线数据，输出JSON：
{ "trend":"bullish|bearish|neutral", "confidence":0.0~1.0, "signals":["信号1"], "summary":"一句话总结" }"""

PROMPT_CODE_REVIEW = """审查以下代码，输出JSON：
{ "score":0~100, "issues":[{"severity":"critical|warning|info","file":"","line":"","desc":"","fix":""}], "summary":"" }"""

PROMPT_SCREEN = """你是一位量化选股专家。将以下自然语言需求翻译为量化条件JSON：
{ "conditions":[{"field":"","operator":"","value":0,"description":""}], "market_filter":"all", "limit":20 }"""


class LLMAnalysisService:
    """AI 分析服务"""

    def __init__(self, client: Optional[DoubaoClient] = None):
        self._client = client or get_doubao()

    def analyze_kline(self, data: Dict[str, Any]) -> LLMResult:
        return self._client.chat_with_json(
            f"K线数据：{json.dumps(data, ensure_ascii=False)}",
            system_prompt=PROMPT_KLINE,
        )

    def review_code(self, file_path: str, code: str) -> LLMResult:
        return self._client.chat_with_json(
            f"文件：{file_path}\n代码：{code}",
            system_prompt=PROMPT_CODE_REVIEW,
        )

    def screen_stocks(self, query: str) -> LLMResult:
        return self._client.chat_with_json(
            f"选股需求：{query}",
            system_prompt=PROMPT_SCREEN,
        )

    def chat(self, msg: str, professional: bool = False) -> LLMResult:
        system = "你是专业量化分析师，回答简洁准确。" if professional else "你是股票分析助手。"
        return self._client.chat(msg, system_prompt=system)


_llm_service: Optional[LLMAnalysisService] = None


def get_llm_service() -> LLMAnalysisService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMAnalysisService()
    return _llm_service

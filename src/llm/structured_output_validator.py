# -*- coding: utf-8 -*-
"""
LLM 结构化输出校验 + 自动重试修复
解决 JSON 乱码、markdown 包裹、注释、格式错误问题
"""
from __future__ import annotations

import json, logging, re
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*\n([\s\S]*?)\n```")
COMMENT_PATTERN = re.compile(r"//.*$|/\*[\s\S]*?\*/", re.MULTILINE)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class StructuredOutputValidator:
    """LLM 结构化输出校验器"""

    def __init__(self, max_retry: int = 2):
        self.max_retry = max_retry

    def clean_text(self, raw: str) -> str:
        """清洗 LLM 原始输出"""
        # 提取 JSON 代码块
        m = JSON_BLOCK_PATTERN.search(raw)
        if m:
            raw = m.group(1)
        # 移除注释
        raw = COMMENT_PATTERN.sub("", raw)
        # 移除控制字符
        raw = CONTROL_CHAR_PATTERN.sub("", raw)
        # 修复常见 JSON 错误：尾随逗号
        raw = re.sub(r",\s*}", "}", raw)
        raw = re.sub(r",\s*]", "]", raw)
        return raw.strip()

    def try_parse(self, text: str) -> Optional[Dict[str, Any]]:
        """尝试 JSON 解析"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试修复单引号
        try:
            return json.loads(text.replace("'", '"'))
        except json.JSONDecodeError:
            pass
        return None

    def validate(self, raw_text: str, model: Type[T], *,
                 max_retry: Optional[int] = None) -> tuple:
        """
        校验 LLM 输出是否符合 Pydantic Schema。

        Returns:
            (parsed_model | None, success: bool, error_message: str)
        """
        retry = max_retry if max_retry is not None else self.max_retry

        for attempt in range(retry + 1):
            clean = self.clean_text(raw_text)
            data = self.try_parse(clean)

            if data is None:
                if attempt < retry:
                    continue
                return None, False, f"JSON parse failed after {retry + 1} attempts"

            try:
                obj = model(**data)
                logger.info(f"LLM structured validation OK (attempt {attempt + 1})")
                return obj, True, "ok"
            except Exception as e:
                logger.warning(f"Pydantic validation failed (attempt {attempt + 1}): {e}")
                # 尝试类型修复
                if attempt < retry:
                    raw_text = self._fix_types(raw_text, model)
                    continue
                return None, False, str(e)

        return None, False, "max retries exhausted"

    async def run_with_retry(
        self, llm_func: Callable, prompt: str,
        model: Type[T], trace_id: str = "", **kwargs,
    ) -> tuple:
        """
        调用 LLM + 校验 + 自动重试修复。

        Args:
            llm_func: async callable → str
            prompt: 原始 prompt
            model: Pydantic 类
            trace_id: 链路追踪 ID

        Returns:
            (parsed_model | None, success: bool, error: str)
        """
        current_prompt = prompt
        for attempt in range(self.max_retry + 1):
            try:
                resp = await llm_func(current_prompt, **kwargs)
            except Exception as e:
                logger.error(f"[{trace_id}] LLM call failed (attempt {attempt + 1}): {e}")
                if attempt >= self.max_retry:
                    return None, False, f"LLM call failed: {e}"
                continue

            obj, ok, err = self.validate(resp, model, max_retry=0)
            if ok:
                logger.info(f"[{trace_id}] Structured output OK (attempt {attempt + 1})")
                return obj, True, "ok"

            if attempt >= self.max_retry:
                return None, False, err

            # 构建修复 prompt
            schema_desc = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)
            current_prompt = (
                f"{prompt}\n\n"
                f"[上一轮输出无法解析，请严格按照 Schema 输出纯 JSON]\n"
                f"错误：{err}\n"
                f"Schema：{schema_desc}\n"
                f"禁止注释、禁止 markdown 代码块、禁止多余字符。"
            )

        return None, False, "max retries exhausted"

    @staticmethod
    def _fix_types(raw_text: str, model: Type[BaseModel]) -> str:
        """尝试修复数值类型不匹配（如 '123' → 123）"""
        try:
            schema = model.model_json_schema()
            props = schema.get("properties", {})
            data = json.loads(raw_text)
            for key, prop in props.items():
                if key in data and prop.get("type") in ("number", "integer"):
                    try:
                        data[key] = float(data[key]) if prop["type"] == "number" else int(data[key])
                    except (ValueError, TypeError):
                        pass
            return json.dumps(data, ensure_ascii=False)
        except Exception:
            return raw_text


# 全局单例
output_validator = StructuredOutputValidator(max_retry=2)

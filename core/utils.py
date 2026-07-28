# -*- coding: utf-8 -*-
"""
===================================
核心工具函数 — core/utils.py
===================================

通用工具：JSON 清洗、日志、异常捕获、token 统计、重试机制。
跨模块复用，避免重复实现。
"""

from __future__ import annotations

import json
import logging
import re
import time
import functools
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ============================================================
# JSON 清洗与校验
# ============================================================

def clean_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    从 LLM 输出中提取并清洗 JSON。
    容忍常见问题：markdown 代码块包裹、前后多余字符、尾逗号。

    Returns:
        解析成功的 dict，失败返回 None
    """
    if not raw_text or not raw_text.strip():
        return None

    text = raw_text.strip()

    # 1. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 移除 markdown 代码块包裹
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block_match:
        text = code_block_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 3. 提取 { ... } 最外层
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        text = brace_match.group(0)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 4. 尝试修复常见错误：尾逗号、单引号
    text = re.sub(r",\s*([}\]])", r"\1", text)  # 移除尾逗号
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    logger.warning("[utils] JSON 清洗失败，原始文本前100字: %s", raw_text[:100])
    return None


def validate_event_json(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    校验事件解析 JSON 的字段合法性。
    返回 (是否合法, 错误列表)
    """
    errors = []

    # event_meta 校验
    meta = data.get("event_meta", {})
    if not meta.get("event_title"):
        errors.append("缺少 event_meta.event_title")
    direction = meta.get("overall_direction")
    if direction not in ("positive", "negative", "neutral"):
        errors.append(f"overall_direction 无效: {direction}")
    strength = meta.get("impact_strength")
    if not isinstance(strength, (int, float)) or not (1 <= strength <= 10):
        errors.append(f"impact_strength 无效: {strength}")
    cycle = meta.get("impact_cycle")
    if cycle not in ("short", "middle", "long"):
        errors.append(f"impact_cycle 无效: {cycle}")

    # transfer_chain 校验
    chains = data.get("transfer_chain", [])
    if not isinstance(chains, list):
        errors.append("transfer_chain 必须是数组")
    else:
        for i, link in enumerate(chains):
            if not link.get("from_node"):
                errors.append(f"transfer_chain[{i}] 缺少 from_node")
            if not link.get("to_node"):
                errors.append(f"transfer_chain[{i}] 缺少 to_node")
            link_dir = link.get("direction")
            if link_dir not in ("positive", "negative"):
                errors.append(f"transfer_chain[{i}] direction 无效: {link_dir}")

    return len(errors) == 0, errors


# ============================================================
# 重试机制
# ============================================================

def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_failure: str = "raise",
):
    """
    装饰器：自动重试。

    Args:
        max_attempts: 最大尝试次数
        delay_seconds: 初始延迟秒数
        backoff: 退避倍数
        exceptions: 捕获的异常类型
        on_failure: "raise" 抛出最终异常 / "return_none" 返回 None / "return_default" 返回默认值
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            delay = delay_seconds
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"[retry] {func.__name__} 失败 (第{attempt}次): {e}，"
                            f"{delay:.1f}s 后重试..."
                        )
                        time.sleep(delay)
                        delay *= backoff
                    else:
                        logger.error(
                            f"[retry] {func.__name__} 重试{max_attempts}次全部失败: {e}"
                        )

            if on_failure == "raise":
                raise last_exc  # type: ignore[misc]
            elif on_failure == "return_none":
                return None
            else:
                return on_failure  # 直接返回值作为默认值

        return wrapper  # type: ignore[return-value]
    return decorator


# ============================================================
# 安全执行（异常封装）
# ============================================================

def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    log_error: bool = True,
    **kwargs,
) -> Any:
    """
    安全执行函数，异常时返回默认值。

    Args:
        func: 要执行的函数
        default: 异常时的默认返回值
        log_error: 是否打印异常日志
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_error:
            logger.warning(f"[safe_execute] {func.__name__} 执行异常: {e}")
        return default


# ============================================================
# ID 生成
# ============================================================

import uuid as _uuid

def generate_id(prefix: str = "") -> str:
    """生成带前缀的唯一 ID"""
    uid = _uuid.uuid4().hex[:10]
    return f"{prefix}_{uid}" if prefix else uid


# ============================================================
# 数字处理
# ============================================================

def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """将值限制在区间内"""
    return max(min_val, min(max_val, value))


def safe_round(value: float, decimals: int = 2) -> float:
    """安全四舍五入"""
    try:
        return round(float(value), decimals)
    except (ValueError, TypeError):
        return 0.0

# -*- coding: utf-8 -*-
"""
===================================
统一 LLM 调用引擎 — core/llm_engine.py
===================================

封装：Token 统计、超长截断、推理缓存（SQLite）、限流控制、结构化 JSON 强制输出。
向下兼容现有 LLM 调用代码。

使用方式：
    from core.llm_engine import LLMEngine
    engine = LLMEngine()
    result = await engine.chat_structured("deepseek-chat", "stock_analysis_prompt",
                                          {"stock_info": "..."})
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 缓存数据库路径
_CACHE_DB = Path(os.getenv("LLM_CACHE_DB", "data/llm_cache.db"))


class TokenCounter:
    """Token 计数器（无 tiktoken 时的降级实现）"""

    @staticmethod
    def count(text: str, model: str = "gpt-3.5-turbo") -> int:
        """估算 token 数量"""
        try:
            import tiktoken
            try:
                enc = tiktoken.encoding_for_model(model)
            except KeyError:
                enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            # 降级：中文字符 ≈2 tokens, 英文 ≈0.3 tokens/char
            chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
            other_chars = len(text) - chinese_chars
            return int(chinese_chars * 2 + other_chars * 0.4)


class LLMCache:
    """SQLite 持久化推理缓存"""

    _init_lock = threading.Lock()

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or _CACHE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    result TEXT NOT NULL,
                    model TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    hit_count INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_created
                ON llm_cache(created_at)
            """)
            conn.commit()

    def get(self, cache_key: str) -> Optional[Dict]:
        """查询缓存"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                row = conn.execute(
                    "SELECT result FROM llm_cache WHERE cache_key=?",
                    (cache_key,),
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE llm_cache SET hit_count=hit_count+1 WHERE cache_key=?",
                        (cache_key,),
                    )
                    conn.commit()
                    return json.loads(row[0])
        except Exception as e:
            logger.warning(f"[LLMCache] 查询失败: {e}")
        return None

    def set(self, cache_key: str, result: Dict, model: str = "", tokens: int = 0):
        """写入缓存"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO llm_cache
                       (cache_key, result, model, tokens_used, created_at)
                       VALUES (?,?,?,?,datetime('now'))""",
                    (cache_key, json.dumps(result, ensure_ascii=False), model, tokens),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"[LLMCache] 写入失败: {e}")

    def stats(self) -> Dict[str, Any]:
        """缓存统计"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                total = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
                total_hits = conn.execute(
                    "SELECT COALESCE(SUM(hit_count),0) FROM llm_cache"
                ).fetchone()[0]
                return {"total_entries": total, "total_hits": total_hits}
        except Exception:
            return {"total_entries": 0, "total_hits": 0}

    def cleanup(self, ttl_hours: int = 168):
        """清理过期缓存"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    "DELETE FROM llm_cache WHERE created_at < datetime('now', ?)",
                    (f"-{ttl_hours} hours",),
                )
                conn.commit()
        except Exception:
            pass


class LLMEngine:
    """
    统一 LLM 调用引擎。

    特性：
    - 自动 Token 计算与超长文本截断
    - SQLite 推理缓存，避免重复调用
    - 线程安全并发锁
    - 强制 JSON 结构化输出
    - 统一异常处理与重试
    """

    def __init__(self):
        self.max_context_tokens = int(os.getenv("LLM_MAX_TOKENS", "12000"))
        self.rate_limit_qps = float(os.getenv("LLM_RATE_QPS", "3"))
        self.timeout = int(os.getenv("LLM_TIMEOUT", "45"))
        self.cache = LLMCache()

        # 限流控制
        self._last_call_time = 0.0
        self._lock = threading.Lock()

        # 统计
        self._call_count = 0
        self._fail_count = 0
        self._total_tokens = 0

    # ---- Token 工具 ----

    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        return TokenCounter.count(text, model)

    def truncate_context(self, text: str, max_tokens: int = None) -> str:
        """
        超长文本智能截断。

        策略：从尾部截断（保留开头 Prompt 和结尾信息），
        限制在 max_tokens 以内。
        """
        limit = max_tokens or self.max_context_tokens
        current = self.count_tokens(text)

        if current <= limit:
            return text

        # 保留开头 40% 和结尾 60%（结尾通常包含更关键的数据）
        ratio = limit / current
        keep_len = int(len(text) * ratio)

        head_len = int(keep_len * 0.4)
        tail_len = keep_len - head_len

        truncated = (
            text[:head_len] +
            "\n\n[... 上下文过长，已自动截断中间部分 ...]\n\n" +
            text[-tail_len:]
        )

        logger.info(f"[LLMEngine] 文本截断: {current}→{self.count_tokens(truncated)} tokens")
        return truncated

    # ---- 缓存 Key ----

    def _cache_key(self, model: str, prompt_key: str, inputs: Dict) -> str:
        payload = json.dumps({
            "model": model,
            "key": prompt_key,
            "inputs": inputs,
        }, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    # ---- 限流 ----

    def _rate_limit(self):
        """简单的 QPS 限流"""
        now = time.time()
        min_interval = 1.0 / self.rate_limit_qps if self.rate_limit_qps > 0 else 0.1
        elapsed = now - self._last_call_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call_time = time.time()

    # ---- 主入口 ----

    def chat_structured(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        use_cache: bool = True,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        同步 LLM 调用，强制返回 JSON 结构化结果。

        Args:
            model_name: 模型名 (deepseek-chat, gpt-4o-mini, doubao-seed-code)
            system_prompt: 系统指令
            user_prompt: 用户输入
            use_cache: 是否使用缓存
            temperature: 随机度
            max_tokens: 最大输出 token

        Returns:
            解析后的 JSON dict，出错时返回 {"error": str, "raw": str}
        """
        # 截断
        user_prompt = self.truncate_context(user_prompt)

        # 缓存
        cache_key = self._cache_key(model_name, "", {
            "s": system_prompt[:200], "u": user_prompt[:200], "t": temperature, "m": max_tokens,
        })

        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"[LLMEngine] 缓存命中: {cache_key}")
                return cached

        # 限流
        self._rate_limit()

        # 构建消息
        messages = [
            {
                "role": "system",
                "content": system_prompt + "\n\n你必须严格输出标准JSON，禁止额外文字、注释、markdown标记。",
            },
            {"role": "user", "content": user_prompt},
        ]

        # 调用
        try:
            import litellm

            with self._lock:
                response = litellm.completion(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.timeout,
                )

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0

            self._call_count += 1
            self._total_tokens += tokens_used

            # JSON 清洗
            result = self._parse_json(content)

            # 缓存
            if use_cache and "error" not in result:
                self.cache.set(cache_key, result, model=model_name, tokens=tokens_used)

            return result

        except Exception as e:
            self._fail_count += 1
            error_msg = str(e)[:500]
            logger.error(f"[LLMEngine] 调用失败 model={model_name}: {error_msg}")
            return {"error": error_msg, "raw": ""}

    def _parse_json(self, raw_text: str) -> Dict[str, Any]:
        """从 LLM 输出中提取 JSON"""
        from core.utils import clean_llm_json
        parsed = clean_llm_json(raw_text)
        if parsed is not None:
            return parsed
        return {"error": "JSON解析失败", "raw": raw_text[:500]}

    # ---- 统计 ----

    def get_stats(self) -> Dict[str, Any]:
        """获取引擎运行统计"""
        cache_stats = self.cache.stats()
        return {
            "call_count": self._call_count,
            "fail_count": self._fail_count,
            "total_tokens": self._total_tokens,
            "success_rate": (
                round(1 - self._fail_count / max(self._call_count, 1), 4)
                if self._call_count > 0 else 0
            ),
            "cache_entries": cache_stats["total_entries"],
            "cache_hits": cache_stats["total_hits"],
        }


# 全局单例
_llm_engine_instance: Optional[LLMEngine] = None


def get_llm_engine() -> LLMEngine:
    global _llm_engine_instance
    if _llm_engine_instance is None:
        _llm_engine_instance = LLMEngine()
    return _llm_engine_instance

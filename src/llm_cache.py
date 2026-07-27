# -*- coding: utf-8 -*-
"""
===================================
LLM 分析缓存系统 — LLMCache
===================================

职责：
1. 相同标的+周期+维度分析自动缓存（默认 TTL 30-60 min）
2. 基于 (stock_code, analysis_type, model, prompt_hash) 的 key 去重
3. 内存 + 可选磁盘持久化
4. 缓存命中率统计
5. Token/成本节省估算

使用方式：
    cache = LLMCache(ttl_minutes=30)
    cached = cache.get("600519", "full_analysis", model="deepseek-chat", prompt="...")
    if cached:
        return cached
    result = call_llm(prompt)
    cache.set("600519", "full_analysis", result, model="deepseek-chat", prompt=prompt)
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL_MINUTES = 30


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    stock_code: str
    analysis_type: str
    model: str
    prompt_hash: str
    result: Any
    token_count: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def is_expired(self, ttl_seconds: int) -> bool:
        return self.age_seconds > ttl_seconds


class LLMCache:
    """
    LLM 分析结果缓存。

    特性：
    - 基于内容的去重 key
    - TTL 过期自动失效
    - 线程安全
    - 可选磁盘持久化
    - 命中率/token 节省统计
    """

    def __init__(
        self,
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
        max_entries: int = 1000,
        persist_path: Optional[str] = None,
    ):
        self._ttl_seconds = ttl_minutes * 60
        self._max_entries = max_entries
        self._entries: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._persist_path = Path(persist_path) if persist_path else None

        # 统计
        self._hits = 0
        self._misses = 0
        self._estimated_tokens_saved = 0

        # 从磁盘恢复
        if self._persist_path and self._persist_path.exists():
            self._load_from_disk()

        logger.info(
            f"[LLMCache] 初始化完成 (ttl={ttl_minutes}min, max={max_entries})"
        )

    # ============================================================
    # 缓存操作
    # ============================================================

    def get(
        self,
        stock_code: str,
        analysis_type: str,
        model: str = "",
        prompt: str = "",
        prompt_hash: Optional[str] = None,
    ) -> Optional[Any]:
        """
        获取缓存的分析结果。

        Returns:
            cached_result or None
        """
        key = self._make_key(stock_code, analysis_type, model, prompt, prompt_hash)

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired(self._ttl_seconds):
                del self._entries[key]
                self._misses += 1
                return None

            self._hits += 1
            self._estimated_tokens_saved += entry.token_count
            logger.debug(
                f"[LLMCache] HIT {key[:40]}... "
                f"(age={entry.age_seconds:.0f}s, tokens_saved={entry.token_count})"
            )
            return entry.result

    def set(
        self,
        stock_code: str,
        analysis_type: str,
        result: Any,
        model: str = "",
        prompt: str = "",
        prompt_hash: Optional[str] = None,
        token_count: int = 0,
    ):
        """
        写入缓存。

        Args:
            stock_code: 股票代码
            analysis_type: 分析类型
            result: LLM 返回结果
            model: 模型名
            prompt: 完整 Prompt
            prompt_hash: Prompt 哈希（不提供则自动计算）
            token_count: 本次消耗的 Token 数
        """
        key = self._make_key(stock_code, analysis_type, model, prompt, prompt_hash)

        with self._lock:
            # 淘汰
            self._evict_if_needed()

            entry = CacheEntry(
                key=key,
                stock_code=stock_code,
                analysis_type=analysis_type,
                model=model,
                prompt_hash=prompt_hash or self._hash_text(prompt),
                result=result,
                token_count=token_count,
            )
            self._entries[key] = entry

            logger.debug(
                f"[LLMCache] SET {key[:40]}... (entries={len(self._entries)})"
            )

    def delete(
        self,
        stock_code: str,
        analysis_type: str = "",
        model: str = "",
    ):
        """删除匹配的缓存条目"""
        with self._lock:
            to_delete = []
            for key, entry in self._entries.items():
                if entry.stock_code != stock_code:
                    continue
                if analysis_type and entry.analysis_type != analysis_type:
                    continue
                if model and entry.model != model:
                    continue
                to_delete.append(key)

            for key in to_delete:
                del self._entries[key]

            if to_delete:
                logger.info(f"[LLMCache] 删除 {len(to_delete)} 条缓存")

    def clear(self):
        """清空所有缓存"""
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            logger.info(f"[LLMCache] 清空 {count} 条缓存")

    def clear_expired(self) -> int:
        """清理过期条目"""
        with self._lock:
            to_delete = [
                k for k, e in self._entries.items()
                if e.is_expired(self._ttl_seconds)
            ]
            for k in to_delete:
                del self._entries[k]
            if to_delete:
                logger.debug(f"[LLMCache] 清理 {len(to_delete)} 条过期缓存")
            return len(to_delete)

    # ============================================================
    # 统计
    # ============================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        with self._lock:
            entry_count = len(self._entries)

        return {
            "entries": entry_count,
            "max_entries": self._max_entries,
            "ttl_minutes": self._ttl_seconds // 60,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1), 3),
            "estimated_tokens_saved": self._estimated_tokens_saved,
            "estimated_cost_saved_usd": round(
                self._estimated_tokens_saved * 0.000002, 4  # ~$2/1M tokens
            ),
        }

    # ============================================================
    # 持久化
    # ============================================================

    def save_to_disk(self):
        """保存缓存到磁盘"""
        if self._persist_path is None:
            return

        try:
            with self._lock:
                data = {
                    key: {
                        "stock_code": e.stock_code,
                        "analysis_type": e.analysis_type,
                        "model": e.model,
                        "prompt_hash": e.prompt_hash,
                        "result": json.dumps(e.result, ensure_ascii=False, default=str),
                        "token_count": e.token_count,
                        "created_at": e.created_at,
                    }
                    for key, e in self._entries.items()
                }

            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

            logger.info(
                f"[LLMCache] 持久化完成: {len(data)} 条 → {self._persist_path}"
            )
        except Exception as e:
            logger.warning(f"[LLMCache] 持久化失败: {e}")

    # ============================================================
    # 内部
    # ============================================================

    def _make_key(
        self,
        stock_code: str,
        analysis_type: str,
        model: str = "",
        prompt: str = "",
        prompt_hash: Optional[str] = None,
    ) -> str:
        """生成缓存 key"""
        components = [
            stock_code.upper(),
            analysis_type,
            model or "default",
            prompt_hash or self._hash_text(prompt),
        ]
        return ":".join(components)

    @staticmethod
    def _hash_text(text: str) -> str:
        """文本哈希（取前 16 位）"""
        if not text:
            return "empty"
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _evict_if_needed(self):
        """超过上限时淘汰最旧条目"""
        while len(self._entries) >= self._max_entries:
            oldest_key = min(
                self._entries.keys(),
                key=lambda k: self._entries[k].created_at,
            )
            del self._entries[oldest_key]

    def _load_from_disk(self):
        """从磁盘恢复缓存"""
        if self._persist_path is None or not self._persist_path.exists():
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for key, raw in data.items():
                try:
                    entry = CacheEntry(
                        key=key,
                        stock_code=raw.get("stock_code", ""),
                        analysis_type=raw.get("analysis_type", ""),
                        model=raw.get("model", ""),
                        prompt_hash=raw.get("prompt_hash", ""),
                        result=json.loads(raw.get("result", "{}")),
                        token_count=raw.get("token_count", 0),
                        created_at=raw.get("created_at", time.time()),
                    )
                    if not entry.is_expired(self._ttl_seconds):
                        self._entries[key] = entry
                except Exception:
                    continue

            logger.info(
                f"[LLMCache] 从磁盘恢复 {len(self._entries)} 条缓存"
            )
        except Exception as e:
            logger.warning(f"[LLMCache] 磁盘恢复失败: {e}")


# 全局实例
_cache_instance: Optional[LLMCache] = None
_cache_lock = threading.Lock()


def get_llm_cache(ttl_minutes: int = DEFAULT_TTL_MINUTES) -> LLMCache:
    """获取全局 LLM 缓存实例"""
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = LLMCache(ttl_minutes=ttl_minutes)
    return _cache_instance

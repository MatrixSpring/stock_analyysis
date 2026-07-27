# -*- coding: utf-8 -*-
"""
GDELT 全球事件数据抓取器 — 从 ai_mark 子系统融合

GDELT (Global Database of Events, Language, and Tone):
  全球最大的开放事件数据库，每15分钟更新一次。
  适用场景：地缘风险预警、供应链中断监测、贸易流向分析

原始来源：ai_mark/integrations/sources/gdelt_fetcher.py
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ============================================================
# GDELT 预定义查询主题
# ============================================================

GDELT_QUERIES = {
    "supply_chain": {
        "query": "supply chain disruption OR trade restriction OR export control",
        "category": "industry",
        "display_name": "GDELT-供应链",
    },
    "geopolitics": {
        "query": "geopolitical conflict OR sanctions OR tariff war",
        "category": "geopolitics",
        "display_name": "GDELT-地缘",
    },
    "energy": {
        "query": "oil supply disruption OR energy crisis OR OPEC",
        "category": "industry",
        "display_name": "GDELT-能源",
    },
    "semiconductor": {
        "query": "chip export control OR semiconductor restriction OR ASML",
        "category": "tech",
        "display_name": "GDELT-半导体",
    },
    "shipping": {
        "query": "shipping disruption OR port congestion OR Suez Canal OR Panama Canal",
        "category": "industry",
        "display_name": "GDELT-航运",
    },
}


@dataclass
class GDELTConfig:
    """GDELT 数据源配置"""
    name: str = "gdelt"
    display_name: str = "GDELT全球事件"
    category: str = "geopolitics"
    source_type: str = "gdelt"
    api_base: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    max_records: int = 50
    mode: str = "artlist"
    timeout_sec: int = 30
    enabled: bool = True
    priority: int = 60
    region: str = "global"
    language: str = "en"
    search_query: str = "supply chain disruption"


class GDELTFetcher:
    """GDELT 全球事件数据源 — 轻量级，不依赖 ai_mark 基础设施"""

    def __init__(self, config: Optional[GDELTConfig] = None):
        self.config = config or GDELTConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._seen_hashes: set = set()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.config.timeout_sec)
        return self._client

    async def fetch(self, max_items: int = 10) -> List[Dict[str, Any]]:
        """抓取 GDELT 事件文章"""
        articles: List[Dict[str, Any]] = []
        query = self.config.search_query
        try:
            client = await self._get_client()
            url = (
                f"{self.config.api_base}"
                f"?query={query}"
                f"&mode={self.config.mode}"
                f"&format=json"
                f"&maxrecords={min(max_items, self.config.max_records)}"
            )
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

            for item in (data.get("articles") or [])[:max_items]:
                title = (item.get("title") or "").strip()
                if not title or self._is_duplicate(title):
                    continue
                articles.append(self._normalize(title=title, item=item))
        except Exception as e:
            logger.warning(f"GDELT fetch failed [{self.config.name}]: {e}")

        return articles

    def fetch_sync(self, max_items: int = 10) -> List[Dict[str, Any]]:
        """同步抓取（兼容 data_provider 主线程调用）"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.fetch(max_items))
                    return future.result(timeout=self.config.timeout_sec + 10)
            return loop.run_until_complete(self.fetch(max_items))
        except RuntimeError:
            return asyncio.run(self.fetch(max_items))

    def health_check(self) -> bool:
        """检测 GDELT API 是否可用"""
        try:
            import socket
            from urllib.parse import urlparse
            host = urlparse(self.config.api_base).hostname
            if host:
                socket.create_connection((host, 443), timeout=5)
            return True
        except Exception:
            return False

    def _is_duplicate(self, title: str, content: str = "") -> bool:
        import hashlib
        h = hashlib.md5(f"{title[:100]}{content[:200]}".encode()).hexdigest()[:16]
        if h in self._seen_hashes:
            return True
        self._seen_hashes.add(h)
        return False

    def _normalize(self, title: str, item: dict) -> Dict[str, Any]:
        return {
            "title": title,
            "content": (item.get("seendate") or "")[:5000],
            "source_name": self.config.display_name,
            "source_key": self.config.name,
            "source_url": item.get("url", ""),
            "source_type": "gdelt",
            "publish_time": item.get("seendate", datetime.utcnow().isoformat()),
            "category": self.config.category,
            "fetch_time": datetime.utcnow().isoformat(),
            "region": "global",
            "language": "en",
        }

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


def fetch_gdelt_events(queries: Optional[List[str]] = None,
                       max_per_query: int = 10) -> List[Dict[str, Any]]:
    """
    便捷函数：按预定义主题批量查询 GDELT 事件。

    Args:
        queries: 查询主题列表，默认 ['supply_chain', 'geopolitics']
        max_per_query: 每个主题最多返回条数

    Returns:
        标准化文章列表
    """
    queries = queries or ["supply_chain", "geopolitics"]
    all_articles: List[Dict[str, Any]] = []

    for qkey in queries:
        qcfg = GDELT_QUERIES.get(qkey)
        if not qcfg:
            continue
        config = GDELTConfig(
            name=f"gdelt_{qkey}",
            display_name=qcfg["display_name"],
            category=qcfg["category"],
            search_query=qcfg["query"],
        )
        fetcher = GDELTFetcher(config)
        articles = fetcher.fetch_sync(max_per_query)
        all_articles.extend(articles)
        logger.info(f"GDELT [{qkey}]: fetched {len(articles)} articles")

    return all_articles

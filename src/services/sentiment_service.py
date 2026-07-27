# -*- coding: utf-8 -*-
"""
舆情数据服务 — 给 Agent / WebUI / 告警提供舆情消费接口

基于 data_provider 新增的采集能力，在 service 层做：
  1. 舆情聚合指标查询
  2. 情绪异动检测
  3. Agent prompt 注入格式化
  4. 缓存层对接
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from data_provider.realtime_types import (
    StockSentimentItem,
    SentimentAggResult,
    aggregate_sentiment,
    compute_simple_sentiment,
)

logger = logging.getLogger(__name__)


class SentimentService:
    """舆情分析服务"""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def get_sentiment_agg(
        self, code: str, market: str = "a",
        time_window: str = "24h",
        use_cache: bool = True,
    ) -> Optional[SentimentAggResult]:
        """
        获取单只股票的舆情聚合指标。

        调用链：缓存 → Mongo → ProviderRouter → 实时采集
        """
        cache_key = f"sent_agg:{code}:{time_window}"

        # L1: 内存缓存
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now(timezone.utc) -
                datetime.fromisoformat(cached.get("cached_at", "2000-01-01T00:00:00")).replace(tzinfo=timezone.utc)
                ).total_seconds() < 1800:
                return cached.get("data")

        # L2: Redis → Mongo → ProviderRouter
        try:
            from src.data_storage import get_cache_pipeline
            pipeline = get_cache_pipeline()
            result = await pipeline.afetch(
                redis_key=f"sentiment_agg:{code}",
                mongo_collection="stock_sentiment_agg",
                mongo_filter={"code": code, "time_window": time_window},
                fetcher_fn=lambda: self._fetch_and_aggregate(code, market, time_window),
                redis_ttl=1800,  # 30 分钟
            )
            if result and result.get("data"):
                agg_data = result["data"]
                agg_result = SentimentAggResult(
                    code=code, market=market, time_window=time_window,
                    post_count=agg_data.get("post_count", 0),
                    total_interact=agg_data.get("total_interact", 0),
                    avg_sentiment_score=agg_data.get("avg_sentiment_score", 0.0),
                    divergence_index=agg_data.get("divergence_index", 0.0),
                    hot_keywords=agg_data.get("hot_keywords", []),
                    crawl_at=datetime.now(timezone.utc).isoformat(),
                )
                if use_cache:
                    self._cache[cache_key] = {
                        "data": agg_result,
                        "cached_at": datetime.now(timezone.utc).isoformat(),
                    }
                return agg_result
        except Exception as e:
            logger.warning(f"[SentimentService] get_sentiment_agg failed for {code}: {e}")

        return None

    def _fetch_and_aggregate(
        self, code: str, market: str, time_window: str,
    ) -> Optional[Dict[str, Any]]:
        """通过 ProviderRouter 拉取原始舆情并聚合"""
        import asyncio
        try:
            from data_provider.provider_router import ProviderRouter
            router = ProviderRouter()
            items_raw = asyncio.run(
                router.get_stock_sentiment(code, market, limit=100),
            )
            if not items_raw:
                return None

            items = [
                StockSentimentItem(
                    sentiment_id=item.get("sentiment_id", ""),
                    code=code, market=market,
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    publish_time=item.get("publish_time", ""),
                    source_platform=item.get("source_platform", ""),
                    like_count=item.get("like_count", 0),
                    reply_count=item.get("reply_count", 0),
                    author=item.get("author", ""),
                    sentiment_score=item.get("sentiment_score"),
                )
                for item in items_raw
            ]

            agg = aggregate_sentiment(code, market, items, time_window)
            return agg.__dict__ if hasattr(agg, "__dict__") else {
                "code": code, "post_count": len(items),
                "avg_sentiment_score": 0.0,
                "divergence_index": 0.0,
                "hot_keywords": [],
            }
        except Exception as e:
            logger.warning(f"[SentimentService] _fetch_and_aggregate failed: {e}")
            return None

    def detect_sentiment_anomaly(
        self, agg: SentimentAggResult,
        extreme_threshold: float = 0.6,
        divergence_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """
        检测舆情异动。

        Returns:
            {"alert": bool, "reason": str, "level": "info"|"warning"|"critical"}
        """
        alerts = []

        # 极端多头情绪
        if agg.avg_sentiment_score > extreme_threshold:
            alerts.append({
                "reason": f"极端多头情绪 ({agg.avg_sentiment_score:.2f})",
                "level": "warning",
                "suggestion": "警惕过度乐观，追高风险",
            })

        # 极端空头情绪
        if agg.avg_sentiment_score < -extreme_threshold:
            alerts.append({
                "reason": f"极端空头情绪 ({agg.avg_sentiment_score:.2f})",
                "level": "warning",
                "suggestion": "关注是否恐慌过度，可能存在超跌反弹机会",
            })

        # 多空严重分歧
        if agg.divergence_index > divergence_threshold:
            alerts.append({
                "reason": f"多空严重分歧 ({agg.divergence_index:.2f})",
                "level": "critical",
                "suggestion": "分歧加大通常预示变盘，建议观望或减仓",
            })

        # 热度突然飙升（发文量 > 平常5倍）
        if agg.post_count > 50:  # 阈值可配置
            alerts.append({
                "reason": f"讨论热度异常 ({agg.post_count} posts/24h)",
                "level": "info",
                "suggestion": "关注是否有重大事件驱动",
            })

        if alerts:
            top = max(alerts, key=lambda a: {"critical": 3, "warning": 2, "info": 1}.get(a["level"], 0))
            return {"alert": True, "alerts": alerts, "top_level": top["level"]}

        return {"alert": False, "alerts": [], "top_level": "info"}

    def format_sentiment_for_agent_prompt(
        self, code: str, agg: Optional[SentimentAggResult] = None,
    ) -> str:
        """将舆情指标格式化为 Agent 分析 prompt 上下文"""
        if agg is None or agg.post_count == 0:
            return ""

        level_emoji = "🔥" if agg.post_count > 50 else "📊"
        sentiment_label = "多头占优" if agg.avg_sentiment_score > 0.15 else (
            "空头占优" if agg.avg_sentiment_score < -0.15 else "多空均衡"
        )

        lines = [
            f"## {level_emoji} 社区舆情情绪指标（近{agg.time_window}）",
            "",
            f"- 讨论热度: {agg.post_count} 条帖子 / {agg.total_interact} 次互动",
            f"- 情绪均值: {agg.avg_sentiment_score:+.2f} ({sentiment_label})",
            f"- 多空分歧: {agg.divergence_index:.2f} "
            f"({'高度分歧⚠️' if agg.divergence_index > 0.7 else '相对一致'})",
        ]
        if agg.hot_keywords:
            lines.append(f"- 热门关键词: {', '.join(agg.hot_keywords[:10])}")
        lines.append("")
        lines.append("> 数据来源：东方财富股吧 + 雪球社区，情感基于词典自动打分")

        return "\n".join(lines)


# ============================================================
# 便捷函数
# ============================================================

_sentiment_service: Optional[SentimentService] = None


def get_sentiment_service() -> SentimentService:
    global _sentiment_service
    if _sentiment_service is None:
        _sentiment_service = SentimentService()
    return _sentiment_service

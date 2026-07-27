# -*- coding: utf-8 -*-
"""
扩展数据源注册与调度门面 — 从 ai_mark 子系统融合

统一对外接口，隐藏底层数据源细节:
  - 自动注册所有预定义扩展数据源
  - 按分类/类型筛选
  - 并行抓取 + 去重合并
  - 自动分类 + 情感标记

原始来源：ai_mark/integrations/fetcher_registry.py
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from data_provider.extended.gdelt_fetcher import GDELTFetcher, GDELTConfig, GDELT_QUERIES
from data_provider.extended.hotlist_fetcher import HotlistFetcher

logger = logging.getLogger(__name__)

# ============================================================
# 分类关键词 → 自动分类
# ============================================================

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "policy": ["政策", "国务院", "发改委", "工信部", "财政部", "央行", "银保监", "证监会", "监管",
               "关税", "出口管制", "制裁", "法规", "标准", "审批"],
    "finance": ["股市", "A股", "基金", "债券", "利率", "汇率", "降准", "降息", "IPO", "融资",
                "北向", "资金", "保险", "银行", "券商"],
    "industry": ["产业", "供应链", "产能", "开工", "订单", "出货", "排产", "装机", "交付", "投产"],
    "geopolitics": ["地缘", "冲突", "制裁", "军事", "海峡", "同盟", "G20", "北约", "联合国", "外交"],
    "tech": ["AI", "人工智能", "芯片", "半导体", "新能源", "光伏", "储能", "电池", "机器人", "自动驾驶"],
}

SENTIMENT_KEYWORDS: Dict[str, List[str]] = {
    "positive": ["利好", "增长", "突破", "创新高", "翻倍", "暴涨", "获批", "超预期", "复苏", "回暖",
                 "政策支持", "补贴", "降息", "放量"],
    "negative": ["利空", "下跌", "暴跌", "违约", "暴雷", "退市", "制裁", "调查", "处罚", "停产",
                 "亏损", "下滑", "萎缩", "收紧", "通胀"],
}


class ExtendedFetcherRegistry:
    """扩展数据源注册与调度门面（类级别，无需实例化）"""

    _HOTLIST_FINANCE_PLATFORMS = ["toutiao", "baidu", "weibo", "wallstreetcn", "cls", "36kr"]

    @classmethod
    def list_categories(cls) -> List[Dict[str, Any]]:
        """列出所有分类及可用数据源"""
        return [
            {"category": "gdelt", "label": "GDELT 全球事件", "sources": list(GDELT_QUERIES.keys())},
            {"category": "hotlist", "label": "多平台热榜", "sources": ["newsnow"],
             "default_platforms": cls._HOTLIST_FINANCE_PLATFORMS},
        ]

    @classmethod
    def fetch_gdelt(cls, queries: Optional[List[str]] = None,
                    max_per_query: int = 10) -> List[Dict[str, Any]]:
        """
        抓取 GDELT 全球事件。

        Args:
            queries: 查询主题列表，默认 ['supply_chain', 'geopolitics']
            max_per_query: 每个主题最多返回条数

        Returns:
            标准化文章列表，每条含 title/content/source_name/category/sentiment
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
            try:
                articles = fetcher.fetch_sync(max_per_query)
                # 自动分类 + 情感标记
                for doc in articles:
                    cls._auto_classify(doc)
                    cls._auto_sentiment(doc)
                all_articles.extend(articles)
                logger.info(f"[ExtendedFetcher] GDELT [{qkey}]: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[ExtendedFetcher] GDELT [{qkey}] failed: {e}")

        unique = cls._deduplicate(all_articles)
        logger.info(f"[ExtendedFetcher] GDELT total: {len(all_articles)} fetched, {len(unique)} unique")
        return unique

    @classmethod
    def fetch_hotlist(cls, platforms: Optional[List[str]] = None,
                      top_n: int = 15) -> List[Dict[str, Any]]:
        """
        抓取多平台热搜趋势。

        Args:
            platforms: 平台列表，默认金融相关 ['toutiao','baidu','weibo','wallstreetcn','cls','36kr']
            top_n: 返回前 N 条

        Returns:
            趋势列表
        """
        fetcher = HotlistFetcher()
        try:
            trending = fetcher.fetch_trending(platforms=platforms, top_n=top_n)
            logger.info(f"[ExtendedFetcher] Hotlist: {len(trending)} trending items")
            return trending
        except Exception as e:
            logger.warning(f"[ExtendedFetcher] Hotlist failed: {e}")
            return []

    @classmethod
    def fetch_all_extended(cls, gdelt_queries: Optional[List[str]] = None,
                           hotlist_platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        一站式抓取所有扩展数据源。

        Returns:
            {"gdelt": [...], "hotlist": [...], "errors": [...], "timestamp": "..."}
        """
        errors: List[Dict[str, str]] = []
        gdelt_articles: List[Dict] = []
        hotlist_items: List[Dict] = []

        # GDELT
        try:
            gdelt_articles = cls.fetch_gdelt(queries=gdelt_queries)
        except Exception as e:
            errors.append({"source": "gdelt", "error": str(e)})

        # Hotlist
        try:
            hotlist_items = cls.fetch_hotlist(platforms=hotlist_platforms)
        except Exception as e:
            errors.append({"source": "hotlist", "error": str(e)})

        return {
            "gdelt": gdelt_articles,
            "hotlist": hotlist_items,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ============================================================
    # 内部工具方法
    # ============================================================

    @classmethod
    def _auto_classify(cls, doc: Dict[str, Any]) -> None:
        """基于关键词自动分类"""
        text = f"{doc.get('title', '')} {doc.get('content', '')}"
        scores: Dict[str, int] = {}
        for cat, kws in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in kws if kw in text)
            if score > 0:
                scores[cat] = score
        if scores:
            doc["category"] = max(scores, key=scores.get)  # type: ignore[arg-type]
        elif "category" not in doc or not doc.get("category"):
            doc["category"] = "industry"

    @classmethod
    def _auto_sentiment(cls, doc: Dict[str, Any]) -> None:
        """基于关键词自动情感标记"""
        text = f"{doc.get('title', '')} {doc.get('content', '')}"
        pos = sum(1 for kw in SENTIMENT_KEYWORDS["positive"] if kw in text)
        neg = sum(1 for kw in SENTIMENT_KEYWORDS["negative"] if kw in text)
        if pos > neg:
            doc["sentiment"] = "positive"
            doc["sentiment_score"] = 0.5
        elif neg > pos:
            doc["sentiment"] = "negative"
            doc["sentiment_score"] = -0.5
        else:
            doc["sentiment"] = "neutral"
            doc["sentiment_score"] = 0.0

    @classmethod
    def _deduplicate(cls, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按内容哈希去重"""
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for doc in articles:
            h = doc.get("_content_hash") or hash(
                f"{doc.get('title', '')[:100]}{doc.get('content', '')[:200]}"
            )
            if h in seen:
                continue
            seen.add(h)
            unique.append(doc)
        return unique

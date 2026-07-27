# -*- coding: utf-8 -*-
"""
统一存储层 v2 — NoSQL (MongoDB) + 多级缓存 + 旧 storage 兼容

与现有 src/storage.py 并行运行，通过 feature flag 控制切换。
稳定后逐步替代旧存储。

MongoDB 集合规划：
  - stock_daily       日线 K 线
  - stock_minute      分时/分钟 K 线
  - stock_chip        筹码分布
  - stock_fundamental 基本面财务数据
  - stock_realtime    实时行情快照
  - stock_industry    申万行业+产业链标签
  - stock_news        个股新闻
  - crawl_metadata    采集元数据

每条文档强制字段：code, market, dt, source, crawl_at, expire_at, quality
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from data_provider.provider_config import (
    NOSQL_CONFIG,
    CACHE_CONFIG,
    FEATURE_FLAGS,
    CrawlMetaRecord,
)

logger = logging.getLogger(__name__)


# ============================================================
# MongoDB 客户端封装
# ============================================================

class MongoStorage:
    """MongoDB 持久存储封装（懒加载单例）"""

    _instance: Optional["MongoStorage"] = None
    _client = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def enabled(self) -> bool:
        return FEATURE_FLAGS.get("enable_nosql_storage", True)

    def _connect(self):
        if self._db is not None:
            return
        if not self.enabled:
            return
        try:
            from pymongo import MongoClient, IndexModel, ASCENDING
            self._client = MongoClient(
                NOSQL_CONFIG["mongo_uri"],
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
            )
            self._db = self._client[NOSQL_CONFIG["mongo_db"]]
            self._client.admin.command("ping")
            logger.info(f"[MongoDB] Connected: {NOSQL_CONFIG['mongo_db']}")
            self._ensure_indexes()
        except Exception as e:
            logger.warning(f"[MongoDB] Not available ({e}) — NoSQL features disabled")
            self._client = None
            self._db = None

    def _ensure_indexes(self):
        """创建核心索引"""
        if not self._db:
            return
        from pymongo import IndexModel, ASCENDING, DESCENDING

        indexes = {
            "stock_daily": [
                IndexModel([("code", ASCENDING), ("dt", DESCENDING)], unique=True, name="idx_code_dt"),
                IndexModel([("market", ASCENDING), ("dt", DESCENDING)], name="idx_market_dt"),
            ],
            "stock_minute": [
                IndexModel([("code", ASCENDING), ("dt", ASCENDING)], unique=True, name="idx_code_minute"),
            ],
            "stock_chip": [
                IndexModel([("code", ASCENDING), ("dt", DESCENDING)], unique=True, name="idx_chip_code_dt"),
            ],
            "stock_fundamental": [
                IndexModel([("code", ASCENDING), ("dt", DESCENDING)], name="idx_fund_code_dt"),
            ],
            "stock_realtime": [
                IndexModel([("code", ASCENDING)], unique=True, name="idx_rt_code"),
            ],
            "stock_industry": [
                IndexModel([("code", ASCENDING)], unique=True, name="idx_ind_code"),
                IndexModel([("industry_code", ASCENDING)], name="idx_ind_code_sector"),
                IndexModel([("chain_tags", ASCENDING)], name="idx_ind_chain"),
            ],
            "stock_news": [
                IndexModel([("code", ASCENDING), ("publish_time", DESCENDING)], name="idx_news_code_time"),
            ],
            "crawl_metadata": [
                IndexModel([("code", ASCENDING), ("data_type", ASCENDING)], name="idx_crawl_code_type"),
                IndexModel([("source", ASCENDING), ("status", ASCENDING)], name="idx_crawl_source"),
            ],
        }

        for coll_name, idx_list in indexes.items():
            try:
                self._db[coll_name].create_indexes(idx_list)
            except Exception as e:
                logger.debug(f"[MongoDB] Indexes for {coll_name}: {e}")

    @property
    def db(self):
        self._connect()
        return self._db

    # ============================================================
    # 泛型 CRUD
    # ============================================================

    def upsert_one(self, collection: str, filter_doc: dict, doc: dict) -> bool:
        if not self.db:
            return False
        try:
            self.db[collection].update_one(
                filter_doc,
                {"$set": doc},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"[MongoDB] upsert {collection}: {e}")
            return False

    def find_one(self, collection: str, filter_doc: dict,
                 sort: Optional[List] = None) -> Optional[Dict]:
        if not self.db:
            return None
        try:
            cursor = self.db[collection].find(filter_doc).limit(1)
            if sort:
                cursor = cursor.sort(sort)
            result = list(cursor)
            return result[0] if result else None
        except Exception as e:
            logger.error(f"[MongoDB] find {collection}: {e}")
            return None

    def find_many(self, collection: str, filter_doc: dict,
                  sort: Optional[List] = None,
                  limit: int = 100) -> List[Dict]:
        if not self.db:
            return []
        try:
            cursor = self.db[collection].find(filter_doc).limit(limit)
            if sort:
                cursor = cursor.sort(sort)
            return list(cursor)
        except Exception as e:
            logger.error(f"[MongoDB] find_many {collection}: {e}")
            return []

    def delete_old(self, collection: str, before_dt: str) -> int:
        if not self.db:
            return 0
        try:
            result = self.db[collection].delete_many({"dt": {"$lt": before_dt}})
            return result.deleted_count
        except Exception as e:
            logger.error(f"[MongoDB] delete {collection}: {e}")
            return 0

    # ============================================================
    # 专用方法：采集元数据
    # ============================================================

    def record_crawl(self, meta: CrawlMetaRecord) -> bool:
        """写入采集元数据"""
        return self.upsert_one(
            "crawl_metadata",
            {"code": meta.code, "data_type": meta.data_type, "source": meta.source},
            meta.to_dict(),
        )

    def get_source_health_from_meta(self, source_name: str,
                                    data_type: str = "daily",
                                    lookback_hours: int = 24) -> Dict[str, Any]:
        """从 crawl_metadata 读取数据源近期健康状态"""
        since = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
        records = self.find_many(
            "crawl_metadata",
            {"source": source_name, "data_type": data_type, "crawl_at": {"$gte": since}},
        )
        if not records:
            return {"source": source_name, "recent_requests": 0, "success_rate": 0.0}

        ok_count = sum(1 for r in records if r.get("status") == "ok")
        return {
            "source": source_name,
            "recent_requests": len(records),
            "success_rate": round(ok_count / len(records), 3),
            "last_crawl": max((r.get("crawl_at", "") for r in records), default=""),
        }

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
            self._db = None


# ============================================================
# Redis 缓存封装
# ============================================================

class RedisCache:
    """Redis 内存缓存封装（懒加载单例）"""

    _instance: Optional["RedisCache"] = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def enabled(self) -> bool:
        return FEATURE_FLAGS.get("enable_cache_layer", True)

    def _connect(self):
        if self._client is not None:
            return
        if not self.enabled:
            return
        try:
            import redis
            self._client = redis.from_url(
                NOSQL_CONFIG["redis_url"],
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._client.ping()
            logger.info("[Redis] Connected")
        except Exception as e:
            logger.warning(f"[Redis] Not available ({e}) — cache disabled")
            self._client = None

    @property
    def client(self):
        self._connect()
        return self._client

    def get(self, key: str) -> Optional[str]:
        if not self.client:
            return None
        try:
            val = self.client.get(key)
            return val.decode("utf-8") if val else None
        except Exception:
            return None

    def set(self, key: str, value: str, ttl: int = 300) -> bool:
        if not self.client:
            return False
        try:
            self.client.setex(key, ttl, value)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception:
            return False

    def get_json(self, key: str) -> Optional[Dict]:
        val = self.get(key)
        if val:
            import json
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return None
        return None

    def set_json(self, key: str, data: Dict, ttl: int = 300) -> bool:
        import json
        return self.set(key, json.dumps(data, ensure_ascii=False, default=str), ttl)

    def close(self):
        if self._client:
            self._client.close()
            self._client = None


# ============================================================
# 多级缓存读取 Pipeline
# ============================================================

class CachePipeline:
    """
    三级缓存读取流水线：

    业务请求 → Redis 查询
      → 命中 → 直接返回
      → 未命中 → Mongo 查询
        → Mongo 有效 → 回填 Redis + 返回
        → Mongo 无数据 / 过期 → 触发远程 API
          → 成功 → 同时写 Mongo + Redis
          → 失败 → 返回兜底旧数据 + 告警
    """

    def __init__(self):
        self._redis = RedisCache()
        self._mongo = MongoStorage()

    def fetch(
        self,
        redis_key: str,
        mongo_collection: str,
        mongo_filter: dict,
        fetcher_fn: Callable,
        redis_ttl: Optional[int] = None,
        fallback_data: Any = None,
    ) -> Dict[str, Any]:
        """
        多级缓存读取。

        Returns:
            {"data": ..., "source": "redis"|"mongo"|"api"|"fallback", "cache_hit": bool}
        """
        # L1: Redis
        cached = self._redis.get_json(redis_key)
        if cached is not None:
            return {"data": cached, "source": "redis", "cache_hit": True}

        # L2: Mongo
        mongo_doc = self._mongo.find_one(mongo_collection, mongo_filter)
        if mongo_doc:
            # 移除 Mongo 内部字段后回填 Redis
            clean_doc = {k: v for k, v in mongo_doc.items() if not k.startswith("_")}
            ttl = redis_ttl or 3600
            self._redis.set_json(redis_key, clean_doc, ttl)
            return {"data": clean_doc, "source": "mongo", "cache_hit": True}

        # L3: Remote API
        try:
            data = fetcher_fn()
            if data is not None:
                # 写入 Mongo（忽略 NoSQL 不可用的情况）
                self._mongo.upsert_one(mongo_collection, mongo_filter, data if isinstance(data, dict) else {"raw": str(data)})
                # 回填 Redis
                ttl = redis_ttl or 3600
                if isinstance(data, dict):
                    self._redis.set_json(redis_key, data, ttl)
                return {"data": data, "source": "api", "cache_hit": False}
        except Exception as e:
            logger.warning(f"[CachePipeline] API fetch failed: {e}")

        # 兜底
        return {"data": fallback_data, "source": "fallback", "cache_hit": False}

    async def afetch(
        self,
        redis_key: str,
        mongo_collection: str,
        mongo_filter: dict,
        fetcher_fn: Callable,
        redis_ttl: Optional[int] = None,
        fallback_data: Any = None,
    ) -> Dict[str, Any]:
        """异步版本"""
        # L1
        cached = self._redis.get_json(redis_key)
        if cached is not None:
            return {"data": cached, "source": "redis", "cache_hit": True}

        # L2
        mongo_doc = self._mongo.find_one(mongo_collection, mongo_filter)
        if mongo_doc:
            clean_doc = {k: v for k, v in mongo_doc.items() if not k.startswith("_")}
            ttl = redis_ttl or 3600
            self._redis.set_json(redis_key, clean_doc, ttl)
            return {"data": clean_doc, "source": "mongo", "cache_hit": True}

        # L3
        try:
            if hasattr(fetcher_fn, "__call__"):
                data = await fetcher_fn() if hasattr(fetcher_fn, "__await__") else fetcher_fn()
            else:
                data = fetcher_fn()
            if data is not None:
                doc = data if isinstance(data, dict) else {"raw": str(data)}
                self._mongo.upsert_one(mongo_collection, mongo_filter, doc)
                ttl = redis_ttl or 3600
                if isinstance(data, dict):
                    self._redis.set_json(redis_key, data, ttl)
                return {"data": data, "source": "api", "cache_hit": False}
        except Exception as e:
            logger.warning(f"[CachePipeline] async fetch failed: {e}")

        return {"data": fallback_data, "source": "fallback", "cache_hit": False}


# ============================================================
# 便捷函数
# ============================================================

def get_mongo() -> MongoStorage:
    return MongoStorage()


def get_redis() -> RedisCache:
    return RedisCache()


def get_cache_pipeline() -> CachePipeline:
    return CachePipeline()

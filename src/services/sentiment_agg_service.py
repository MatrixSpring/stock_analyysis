# -*- coding: utf-8 -*-
"""
舆情聚合服务 — P0 核心优化版
新增：时间衰减权重 + 信源加权降噪 + 预期/落地/兑现三分类高级词库

对标：RavenPack 舆情体系
"""
from __future__ import annotations

import asyncio, logging, math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import jieba
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False


def _cut(text: str) -> List[str]:
    if not _HAS_JIEBA:
        return text.split()
    try:
        return list(jieba.lcut(text))
    except AttributeError:
        return list(jieba.cut(text))


# ============================================================
# 升级词库：预期/落地/兑现 三分类
# ============================================================

POS_EXPECT = {"有望", "预期", "拟", "计划", "或将", "潜在利好", "预计增长", "预告"}
POS_LANDED = {"落地", "获批", "中标", "签订", "业绩大增", "涨停", "突破", "加仓", "放量拉升"}
NEG_EXPECT = {"风险", "担忧", "或将下跌", "潜在利空", "不确定性"}
NEG_LANDED = {"暴雷", "亏损", "减持", "跌停", "立案", "退市", "大跌", "闪崩", "跳水"}

STOP_WORDS = {"的", "了", "是", "就", "都", "还", "有", "和", "不", "我", "他", "也", "很", "这"}

# 信源权重（机构级 > 自媒体）
SOURCE_WEIGHT: Dict[str, float] = {
    "财联社": 1.0, "证券时报": 1.0, "上交所": 1.0, "深交所": 1.0,
    "巨潮": 1.0, "新浪财经": 0.9, "东方财富": 0.8, "第一财经": 0.9,
    "eastmoney": 0.8, "股吧": 0.4, "头条": 0.5, "雪球": 0.6,
}


# ============================================================
# 数据模型
# ============================================================

@dataclass
class SentimentAggWindow:
    code: str
    market: str = "a"
    window_type: str = "24h"
    window_start: str = ""
    post_count: int = 0
    total_interact: int = 0
    sentiment_score: float = 0.0      # 加权情绪得分
    heat_momentum: float = 0.0        # 热度动量
    divergence_index: float = 0.0     # 多空分歧
    hot_keywords: List[str] = field(default_factory=list)
    is_sentiment_spike: bool = False
    spike_detail: str = ""
    crawl_at: str = ""
    industry_code: str = ""
    chain_tags: List[str] = field(default_factory=list)

    def to_mongo_doc(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_mongo_doc(cls, doc: Dict) -> "SentimentAggWindow":
        doc.pop("_id", None)
        return cls(**{k: v for k, v in doc.items() if k in cls.__dataclass_fields__})


# ============================================================
# 聚合服务
# ============================================================

class SentimentAggService:
    """舆情聚合计算服务（P0版）"""

    def __init__(self):
        self.cache_ttl_min: int = 30
        self.spike_sentiment_shift: float = 0.35
        self.spike_post_growth: float = 1.8
        self._initialized: bool = False

    async def init(self):
        """异步初始化（确保 MongoDB 索引就绪）"""
        if self._initialized:
            return
        try:
            from src.data_storage import get_mongo
            db = get_mongo().db
            if db:
                db["stock_sentiment_agg"].create_index([("code", 1), ("window_type", 1)])
        except Exception:
            pass
        self._initialized = True
        self.heat_base: int = 50

    # ============================================================
    # 时间衰减（24h=1.0, 48h=0.5, 72h=0.1, >72h=0）
    # ============================================================

    @staticmethod
    def get_time_decay_weight(publish_time: str) -> float:
        try:
            t = datetime.fromisoformat(publish_time.replace("Z", "+00:00"))
            delta = (datetime.now(timezone.utc) - t.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if delta <= 24: return 1.0
            if delta <= 48: return 0.5
            if delta <= 72: return 0.1
            return 0.0
        except Exception:
            return 0.5

    # ============================================================
    # 信源加权
    # ============================================================

    @staticmethod
    def get_source_weight(source: str) -> float:
        for k, v in SOURCE_WEIGHT.items():
            if k in source:
                return v
        return 0.5

    # ============================================================
    # 三分类加权情感打分
    # ============================================================

    def calc_sentiment_score(self, text: str, source: str = "",
                             pub_time: str = "") -> float:
        words = _cut(text)
        w_time = self.get_time_decay_weight(pub_time)
        w_source = self.get_source_weight(source)
        total_weight = w_time * w_source

        p_exp = sum(1 for w in words if w in POS_EXPECT)
        p_fal = sum(1 for w in words if w in POS_LANDED)
        n_exp = sum(1 for w in words if w in NEG_EXPECT)
        n_fal = sum(1 for w in words if w in NEG_LANDED)

        # 落地条款权重高于预期条款
        p_total = (p_exp * 0.7 + p_fal * 1.0) * total_weight
        n_total = (n_exp * 0.7 + n_fal * 1.0) * total_weight

        if p_total + n_total == 0:
            return 0.0
        return round((p_total - n_total) / (p_total + n_total), 3)

    # ============================================================
    # 热度动量（对数标准化）
    # ============================================================

    def calc_heat_momentum(self, post_count: int, interact_total: int) -> float:
        raw = math.log(1 + post_count + interact_total / 100)
        base = math.log(1 + self.heat_base)
        return round(min(raw / base, 1.0), 3)

    # ============================================================
    # 分歧度
    # ============================================================

    @staticmethod
    def calc_divergence_index(scores: List[float]) -> float:
        if len(scores) <= 3:
            return 0.15
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        return round(min(math.sqrt(variance) * 2, 1.0), 3)

    # ============================================================
    # 关键词
    # ============================================================

    @staticmethod
    def extract_keywords(text_list: List[str], top_k: int = 10) -> List[str]:
        all_words: List[str] = []
        for t in text_list:
            all_words.extend(w for w in _cut(t) if len(w) >= 2 and w not in STOP_WORDS)
        return [k for k, _ in Counter(all_words).most_common(top_k)]

    # ============================================================
    # 核心：构建聚合
    # ============================================================

    async def build_agg(self, code: str, market: str = "a",
                        window_hours: int = 24) -> SentimentAggWindow:
        w_type = "24h" if window_hours <= 24 else "7d"
        w_start = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()

        raw_items = await self._fetch_raw(code, window_hours)
        if not raw_items:
            return SentimentAggWindow(code=code, market=market, window_type=w_type,
                                      window_start=w_start,
                                      crawl_at=datetime.now(timezone.utc).isoformat())

        scores, texts, interacts = [], [], 0
        for item in raw_items:
            txt = item.get("content", item.get("title", ""))
            src = item.get("source_platform", item.get("source", ""))
            pt = item.get("publish_time", "")
            s = self.calc_sentiment_score(txt, src, pt)
            scores.append(s)
            texts.append(txt)
            interacts += item.get("like_count", 0) + item.get("reply_count", 0)

        avg_score = round(sum(scores) / len(scores), 3)
        momentum = self.calc_heat_momentum(len(raw_items), interacts)
        divergence = self.calc_divergence_index(scores)
        keywords = self.extract_keywords(texts)
        is_spike, spike_detail = await self._detect_spike(code, avg_score, len(raw_items), w_type)

        return SentimentAggWindow(
            code=code, market=market, window_type=w_type, window_start=w_start,
            post_count=len(raw_items), total_interact=interacts,
            sentiment_score=avg_score, heat_momentum=momentum,
            divergence_index=divergence, hot_keywords=keywords,
            is_sentiment_spike=is_spike, spike_detail=spike_detail,
            crawl_at=datetime.now(timezone.utc).isoformat(),
        )

    async def get_or_build(self, code: str, market: str = "a",
                           window_type: str = "24h",
                           force_refresh: bool = False) -> SentimentAggWindow:
        if not force_refresh:
            cached = await self._get_cached(code, market, window_type)
            if cached:
                return cached
        wh = 24 if window_type == "24h" else 168
        agg = await self.build_agg(code, market, wh)
        await self._save_cache(agg)
        return agg

    async def save_agg(self, agg: SentimentAggWindow):
        try:
            from src.data_storage import get_mongo
            db = get_mongo().db
            if db:
                db["stock_sentiment_agg"].update_one(
                    {"code": agg.code, "window_type": agg.window_type},
                    {"$set": agg.to_mongo_doc()}, upsert=True,
                )
        except Exception as e:
            logger.warning(f"Save agg failed: {e}")
        if agg.is_sentiment_spike:
            logger.warning(f"舆情异动 {agg.code}: score={agg.sentiment_score:+.2f} {agg.spike_detail}")
        if agg.divergence_index > 0.7:
            logger.info(f"高分歧反转 {agg.code}: div={agg.divergence_index:.2f}")

    async def batch_refresh(self, codes: List[str], market: str = "a",
                            window_type: str = "24h"):
        for i, code in enumerate(codes):
            try:
                agg = await self.build_agg(code, market, 24 if window_type == "24h" else 168)
                await self.save_agg(agg)
            except Exception as e:
                logger.warning(f"Batch {code}: {e}")
            if (i + 1) % 5 == 0:
                await asyncio.sleep(0.5)

    def format_for_agent(self, agg: SentimentAggWindow) -> str:
        if agg.post_count == 0:
            return ""
        label = "多头占优" if agg.sentiment_score > 0.15 else (
            "空头占优" if agg.sentiment_score < -0.15 else "多空均衡")
        spike_tag = "🔥 异动!" if agg.is_sentiment_spike else ""
        return (
            f"## 📊 社区舆情（近{agg.window_type}）{spike_tag}\n"
            f"- 热度：{agg.post_count}帖 / {agg.total_interact}互动"
            f" | 情绪：{agg.sentiment_score:+.2f}（{label}）\n"
            f"- 分歧：{agg.divergence_index:.2f}"
            f"{' ⚠️反转窗口' if agg.divergence_index > 0.7 else ''}\n"
            f"- 热词：{', '.join(agg.hot_keywords[:8])}"
        )

    # ============================================================
    # 内部
    # ============================================================

    async def _fetch_raw(self, code: str, hours: int) -> List[Dict]:
        try:
            from src.data_storage import get_mongo
            db = get_mongo().db
            if db:
                since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                return list(db["stock_sentiment"].find(
                    {"code": code, "publish_time": {"$gte": since}},
                    limit=200,
                ).sort("publish_time", -1))
        except Exception:
            pass
        try:
            from data_provider.provider_router import ProviderRouter
            items = ProviderRouter()._try_fetch_async("efinance", "get_stock_sentiment", code, "a", 100, None)
            return items or []
        except Exception:
            return []

    async def _get_cached(self, code: str, market: str, window_type: str) -> Optional[SentimentAggWindow]:
        try:
            from src.data_storage import get_mongo
            db = get_mongo().db
            if not db:
                return None
            doc = db["stock_sentiment_agg"].find_one(
                {"code": code, "market": market, "window_type": window_type})
            if not doc:
                return None
            crawl_str = doc.get("crawl_at", "")
            if crawl_str:
                ct = datetime.fromisoformat(crawl_str)
                if datetime.now(timezone.utc) - ct > timedelta(minutes=self.cache_ttl_min):
                    return None
            return SentimentAggWindow.from_mongo_doc(doc)
        except Exception:
            return None

    async def _save_cache(self, agg: SentimentAggWindow):
        await self.save_agg(agg)

    async def _detect_spike(self, code: str, curr_score: float,
                            curr_count: int, w_type: str) -> tuple:
        try:
            from src.data_storage import get_mongo
            db = get_mongo().db
            if not db:
                return False, ""
            prev = db["stock_sentiment_agg"].find_one(
                {"code": code, "window_type": w_type}, sort=[("crawl_at", -1)])
            if not prev:
                return False, ""
            prev_score = float(prev.get("sentiment_score", 0))
            prev_count = int(prev.get("post_count", 1))
            shift = abs(curr_score - prev_score)
            growth = curr_count / max(prev_count, 1)
            if shift >= self.spike_sentiment_shift and growth >= self.spike_post_growth:
                return True, f"情绪+热度共振(shift={shift:+.2f}, growth={growth:.1f}x)"
            if shift >= self.spike_sentiment_shift:
                d = "多头爆发" if curr_score > prev_score else "空头蔓延"
                return True, f"情绪{d}({prev_score:+.2f}→{curr_score:+.2f})"
            if growth >= self.spike_post_growth:
                return True, f"热度暴增 {growth:.1f}x({prev_count}→{curr_count}帖)"
        except Exception:
            pass
        return False, ""


sentiment_agg_service = SentimentAggService()

# -*- coding: utf-8 -*-
"""
===================================
市场数据快照系统 — MarketSnapshot
===================================

职责：
1. 每次分析/回测/研判时自动生成完整市场快照
2. 严格还原当日：价格、资金、舆情、政策环境
3. 杜绝后视镜偏差（look-ahead bias）
4. 支持历史快照回溯和对比

快照内容：
- 行情快照：OHLCV + 技术指标
- 资金快照：北向/主力/融资融券
- 舆情快照：新闻情感/关键词
- 宏观快照：政策事件/地缘风险
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SnapshotPoint:
    """单个时间点的数据快照"""
    # 行情
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    amount: float = 0.0
    pct_chg: float = 0.0
    # 技术指标
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    # 额外
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketSnapshot:
    """
    完整市场快照。

    涵盖一只股票在某个时间点的全量可观测数据。
    """
    snapshot_id: str = ""
    stock_code: str = ""
    stock_name: str = ""
    analysis_date: str = ""          # YYYY-MM-DD
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 行情数据
    price_data: List[SnapshotPoint] = field(default_factory=list)

    # 资金数据
    capital_flow: Dict[str, Any] = field(default_factory=dict)
    # north_bound, main_capital, margin, dragon_tiger

    # 舆情数据
    sentiment: Dict[str, Any] = field(default_factory=dict)
    # news_sentiment, social_buzz, key_topics

    # 宏观环境
    macro: Dict[str, Any] = field(default_factory=dict)
    # risk_score, geopolitics_level, policy_direction, market_phase

    # 行业数据
    industry: Dict[str, Any] = field(default_factory=dict)
    # boom_score, phase, competitors

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "analysis_date": self.analysis_date,
            "created_at": self.created_at,
            "price_data": [
                {"date": str(p.extra.get("date", "")), "close": p.close,
                 "volume": p.volume, "pct_chg": p.pct_chg,
                 "ma5": p.ma5, "ma10": p.ma10, "ma20": p.ma20}
                for p in self.price_data[-20:]  # 最近20条
            ],
            "capital_flow": self.capital_flow,
            "sentiment": self.sentiment,
            "macro": self.macro,
            "industry": self.industry,
        }

    def digest(self) -> str:
        """生成快照摘要（用于比较）"""
        closes = [p.close for p in self.price_data[-5:]] if self.price_data else []
        avg_close = np.mean(closes) if closes else 0
        return (
            f"{self.stock_code}@{self.analysis_date}: "
            f"close={avg_close:.2f} "
            f"capital={self.capital_flow.get('score', 'N/A')} "
            f"sentiment={self.sentiment.get('overall', 'N/A')} "
            f"macro_risk={self.macro.get('risk_score', 'N/A')}"
        )


class SnapshotStore:
    """
    快照存储与检索。

    使用方式：
        store = SnapshotStore("./data/snapshots")
        snap = store.capture("600519", price_data, capital_data, ...)
        store.save(snap)

        # 回溯
        old_snap = store.load("600519", "2024-01-15")
    """

    def __init__(self, storage_dir: str = "./data/snapshots"):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, List[str]] = {}  # stock_code → [snapshot_ids]
        self._load_index()

    def capture(
        self,
        stock_code: str,
        stock_name: str = "",
        analysis_date: Optional[str] = None,
        price_data: Optional[List[Dict[str, Any]]] = None,
        capital_flow: Optional[Dict[str, Any]] = None,
        sentiment: Optional[Dict[str, Any]] = None,
        macro: Optional[Dict[str, Any]] = None,
        industry: Optional[Dict[str, Any]] = None,
        **metadata,
    ) -> MarketSnapshot:
        """生成快照"""
        snap_id = hashlib.md5(
            f"{stock_code}:{analysis_date or datetime.now().date()}:{time.time()}".encode()
        ).hexdigest()[:16]

        snap = MarketSnapshot(
            snapshot_id=snap_id,
            stock_code=stock_code.upper(),
            stock_name=stock_name,
            analysis_date=analysis_date or datetime.now().strftime("%Y-%m-%d"),
            price_data=[
                SnapshotPoint(
                    open=p.get("open", 0), high=p.get("high", 0),
                    low=p.get("low", 0), close=p.get("close", 0),
                    volume=p.get("volume", 0), amount=p.get("amount", 0),
                    pct_chg=p.get("pct_chg", 0),
                    ma5=p.get("ma5", 0), ma10=p.get("ma10", 0), ma20=p.get("ma20", 0),
                    extra={"date": str(p.get("date", ""))},
                )
                for p in (price_data or [])
            ],
            capital_flow=capital_flow or {},
            sentiment=sentiment or {},
            macro=macro or {},
            industry=industry or {},
            metadata=metadata,
        )

        # 更新索引
        code = stock_code.upper()
        if code not in self._index:
            self._index[code] = []
        self._index[code].append(snap_id)

        return snap

    def save(self, snap: MarketSnapshot):
        """持久化快照"""
        file_path = self._dir / f"{snap.stock_code}_{snap.analysis_date}_{snap.snapshot_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snap.to_dict(), f, ensure_ascii=False, indent=2)
        self._save_index()
        logger.info(f"[SnapshotStore] 保存: {file_path}")

    def load(self, stock_code: str, analysis_date: str) -> Optional[MarketSnapshot]:
        """加载历史快照"""
        pattern = f"{stock_code.upper()}_{analysis_date}_"
        for f in self._dir.glob(f"{pattern}*.json"):
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return self._from_dict(data)
        return None

    def list_snapshots(self, stock_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出快照"""
        result = []
        for f in sorted(self._dir.glob("*.json"), reverse=True):
            code = f.stem.split("_")[0]
            if stock_code and code != stock_code.upper():
                continue
            result.append({
                "stock_code": code,
                "analysis_date": f.stem.split("_")[1] if len(f.stem.split("_")) > 1 else "",
                "file": str(f.name),
                "size": f.stat().st_size,
            })
        return result[:100]

    def compare(
        self, stock_code: str, date_a: str, date_b: str,
    ) -> Dict[str, Any]:
        """对比两个时间点的快照"""
        snap_a = self.load(stock_code, date_a)
        snap_b = self.load(stock_code, date_b)
        if not snap_a or not snap_b:
            return {"error": "快照不完整"}

        return {
            "stock_code": stock_code,
            "date_a": date_a, "date_b": date_b,
            "price_change": round(
                (snap_b.price_data[-1].close / max(snap_a.price_data[-1].close, 0.01) - 1), 4
            ) if snap_a.price_data and snap_b.price_data else None,
            "sentiment_change": {
                "a": snap_a.sentiment.get("overall", ""),
                "b": snap_b.sentiment.get("overall", ""),
            },
            "macro_change": {
                "a": snap_a.macro.get("risk_score", 50),
                "b": snap_b.macro.get("risk_score", 50),
            },
        }

    def _from_dict(self, data: Dict[str, Any]) -> MarketSnapshot:
        return MarketSnapshot(
            snapshot_id=data.get("snapshot_id", ""),
            stock_code=data.get("stock_code", ""),
            stock_name=data.get("stock_name", ""),
            analysis_date=data.get("analysis_date", ""),
            capital_flow=data.get("capital_flow", {}),
            sentiment=data.get("sentiment", {}),
            macro=data.get("macro", {}),
            industry=data.get("industry", {}),
            metadata=data.get("metadata", {}),
        )

    def _save_index(self):
        path = self._dir / "_index.json"
        with open(path, "w") as f:
            json.dump(self._index, f)

    def _load_index(self):
        path = self._dir / "_index.json"
        if path.exists():
            with open(path) as f:
                self._index = json.load(f)

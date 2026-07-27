# -*- coding: utf-8 -*-
"""
因子预计算 & 持久化服务

将回测常用指标（均线/波动率/动量/换手率）预计算存入 MongoDB，
避免每次回测实时重算，大幅提升回测速度。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ============================================================
# 预计算因子定义
# ============================================================

FACTOR_DEFINITIONS = {
    "ma":       {"label": "移动均线", "windows": [5, 10, 20, 60, 120]},
    "volatility": {"label": "历史波动率", "windows": [5, 20, 60]},
    "momentum":   {"label": "动量", "windows": [5, 10, 20, 60]},
    "volume_ma":  {"label": "量比", "windows": [5, 20]},
    "rsi":        {"label": "RSI", "windows": [6, 14, 24]},
    "atr":        {"label": "ATR", "windows": [14]},
}


@dataclass
class FactorSnapshot:
    """单日因子快照"""
    code: str
    trade_date: str
    factors: Dict[str, Dict[str, float]] = field(default_factory=dict)
    source: str = "precompute"
    computed_at: str = ""


class FactorPrecomputeService:
    """因子预计算服务"""

    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            try:
                from src.data_storage import get_mongo
                self._db = get_mongo().db
            except Exception:
                pass
        return self._db

    # ============================================================
    # 单标的计算
    # ============================================================

    def compute_factors(self, df: pd.DataFrame, code: str) -> List[FactorSnapshot]:
        """
        从 OHLC DataFrame 计算全部预定义因子。

        Args:
            df: columns = [date, open, high, low, close, volume]
            code: 股票代码

        Returns:
            FactorSnapshot 列表
        """
        if df is None or df.empty:
            return []

        df = df.sort_values("date").reset_index(drop=True)
        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float)

        snapshots: List[FactorSnapshot] = []
        for i in range(len(df)):
            factors: Dict[str, Dict[str, float]] = {}

            # MA
            ma_vals = {}
            for w in FACTOR_DEFINITIONS["ma"]["windows"]:
                if i >= w - 1:
                    ma_vals[f"ma{w}"] = round(float(np.mean(close[i - w + 1:i + 1])), 3)
            if ma_vals:
                factors["ma"] = ma_vals

            # Volatility (daily return std * sqrt(252))
            for w in FACTOR_DEFINITIONS["volatility"]["windows"]:
                if i >= w:
                    rets = np.diff(close[i - w:i + 1]) / close[i - w:i]
                    factors.setdefault("volatility", {})[f"vol{w}"] = round(
                        float(np.std(rets) * np.sqrt(252)), 4)

            # Momentum (price change %)
            for w in FACTOR_DEFINITIONS["momentum"]["windows"]:
                if i >= w:
                    factors.setdefault("momentum", {})[f"mom{w}"] = round(
                        float((close[i] / close[i - w] - 1) * 100), 2)

            # Volume ratio (current vol / N-day avg vol)
            for w in FACTOR_DEFINITIONS["volume_ma"]["windows"]:
                if i >= w:
                    avg_vol = np.mean(volume[i - w + 1:i + 1])
                    factors.setdefault("volume_ma", {})[f"vol_ratio{w}"] = round(
                        float(volume[i] / avg_vol), 2) if avg_vol > 0 else 1.0

            # RSI
            for w in FACTOR_DEFINITIONS["rsi"]["windows"]:
                if i >= w:
                    rsi_val = self._calc_rsi(close, i, w)
                    factors.setdefault("rsi", {})[f"rsi{w}"] = round(rsi_val, 1)

            # ATR
            for w in FACTOR_DEFINITIONS["atr"]["windows"]:
                if i >= w:
                    atr_val = self._calc_atr(high, low, close, i, w)
                    factors.setdefault("atr", {})[f"atr{w}"] = round(atr_val, 3)

            snapshots.append(FactorSnapshot(
                code=code,
                trade_date=str(df.iloc[i]["date"]),
                factors=factors,
                computed_at=datetime.now(timezone.utc).isoformat(),
            ))

        return snapshots

    # ============================================================
    # 持久化
    # ============================================================

    def save_factors(self, snapshots: List[FactorSnapshot]) -> int:
        """批量写入 stock_factors 集合"""
        if not self.db or not snapshots:
            return 0
        count = 0
        for snap in snapshots:
            try:
                self.db["stock_factors"].update_one(
                    {"code": snap.code, "trade_date": snap.trade_date},
                    {"$set": snap.__dict__}, upsert=True,
                )
                count += 1
            except Exception as e:
                logger.warning(f"Factor save failed {snap.code}/{snap.trade_date}: {e}")
        return count

    def load_factors(self, code: str, start_date: str, end_date: str) -> List[Dict]:
        """从 MongoDB 加载预计算因子"""
        if not self.db:
            return []
        return list(self.db["stock_factors"].find({
            "code": code,
            "trade_date": {"$gte": start_date, "$lte": end_date},
        }).sort("trade_date", 1))

    def is_cached(self, code: str, trade_date: str) -> bool:
        """检查因子是否已缓存"""
        if not self.db:
            return False
        return self.db["stock_factors"].count_documents(
            {"code": code, "trade_date": trade_date}) > 0

    # ============================================================
    # 指标计算
    # ============================================================

    @staticmethod
    def _calc_rsi(close: np.ndarray, idx: int, window: int) -> float:
        if idx < window:
            return 50.0
        diffs = np.diff(close[idx - window:idx + 1])
        gains = np.sum(diffs[diffs > 0]) if len(diffs[diffs > 0]) else 0
        losses = -np.sum(diffs[diffs < 0]) if len(diffs[diffs < 0]) else 0
        if losses == 0:
            return 100.0
        rs = gains / losses
        return float(100 - 100 / (1 + rs))

    @staticmethod
    def _calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                  idx: int, window: int) -> float:
        if idx < window:
            return 0.0
        tr_list = []
        for j in range(idx - window + 1, idx + 1):
            tr = max(high[j] - low[j],
                     abs(high[j] - close[j - 1]),
                     abs(low[j] - close[j - 1]))
            tr_list.append(tr)
        return float(np.mean(tr_list))


factor_precompute = FactorPrecomputeService()

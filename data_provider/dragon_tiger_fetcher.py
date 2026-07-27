# -*- coding: utf-8 -*-
"""
龙虎榜数据采集扩展 — 识别机构 / 游资动向
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# 龙虎榜标准数据模型
# ============================================================

DRAGON_TIGER_COLUMNS = [
    "code", "name", "trade_date",
    "close", "pct_chg", "turnover_rate", "total_amount",
    "buy_amount", "sell_amount", "net_amount",
    "buy_inst_amount", "sell_inst_amount",   # 机构席位
    "buy_hot_amount", "sell_hot_amount",      # 游资席位
    "top_buy_seats", "top_sell_seats",
    "reason",                                 # 上榜原因
]


def fetch_dragon_tiger_akshare(trade_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    通过 akshare 获取龙虎榜数据。

    Args:
        trade_date: YYYYMMDD 格式，默认最近交易日

    Returns:
        标准化龙虎榜列表
    """
    try:
        import akshare as ak
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y%m%d")

        df = ak.stock_lhb_detail_em(date=trade_date)
        if df is None or df.empty:
            logger.info(f"No dragon/tiger data for {trade_date}")
            return []

        results = []
        for _, row in df.iterrows():
            results.append({
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "trade_date": trade_date,
                "close": safe_float(row.get("收盘价", 0)),
                "pct_chg": safe_float(row.get("涨跌幅", 0)),
                "turnover_rate": safe_float(row.get("换手率", 0)),
                "total_amount": safe_float(row.get("成交额", 0)),
                "buy_amount": safe_float(row.get("买入额", 0)),
                "sell_amount": safe_float(row.get("卖出额", 0)),
                "net_amount": safe_float(row.get("净买额", 0)),
                "reason": str(row.get("上榜原因", "")),
                "source": "akshare",
                "crawl_at": datetime.now(timezone.utc).isoformat(),
            })
        logger.info(f"Dragon/tiger: {len(results)} stocks on {trade_date}")
        return results
    except Exception as e:
        logger.warning(f"Dragon/tiger fetch failed: {e}")
        return []


def fetch_dragon_tiger_efinance(trade_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """efinance 龙虎榜备选源"""
    try:
        import efinance as ef
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        df = ef.stock.get_dragon_tiger(trade_date)
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.iterrows():
            results.append({
                "code": str(row.get("股票代码", row.get("code", ""))),
                "name": str(row.get("股票名称", row.get("name", ""))),
                "trade_date": trade_date,
                "close": safe_float(row.get("收盘价", 0)),
                "pct_chg": safe_float(row.get("涨跌幅", 0)),
                "net_amount": safe_float(row.get("净买额", 0)),
                "reason": str(row.get("上榜原因", "")),
                "source": "efinance",
                "crawl_at": datetime.now(timezone.utc).isoformat(),
            })
        return results
    except Exception:
        return []


def save_dragon_tiger_to_mongo(items: List[Dict[str, Any]]) -> int:
    """保存龙虎榜数据到 MongoDB"""
    if not items:
        return 0
    try:
        from src.data_storage import get_mongo
        db = get_mongo().db
        if not db:
            return 0
        count = 0
        for item in items:
            db["stock_dragon_tiger"].update_one(
                {"code": item["code"], "trade_date": item["trade_date"]},
                {"$set": item}, upsert=True,
            )
            count += 1
        return count
    except Exception as e:
        logger.warning(f"Dragon/tiger save failed: {e}")
        return 0


def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

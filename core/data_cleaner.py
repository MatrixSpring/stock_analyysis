# -*- coding: utf-8 -*-
"""
===================================
数据清洗过滤器 — core/data_cleaner.py
===================================

自动过滤停牌、异常价格、空值、脏数据；
统一字段命名、检测行情断档。

使用方式：
    from core.data_cleaner import clean_stock_data, detect_data_missing
    clean_df = clean_stock_data(raw_df)
    missing = detect_data_missing(clean_df)
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import List, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 标准行情输出字段
STANDARD_COLUMNS = [
    "date", "open", "high", "low", "close",
    "volume", "amount", "pct_change", "turnover",
]

# 价格相关列
_PRICE_COLS = ["open", "high", "low", "close"]


def clean_stock_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    数据清洗主入口。

    流程：
    1. 删除全空行
    2. 过滤价格为0或负的行
    3. 过滤极端异常值（0.2% ~ 99.8% 分位数外）
    4. 去重、排序
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    df = df.copy()
    before = len(df)

    # 1. 删除全空行
    df = df.dropna(how="all")

    # 2. 过滤价格为0或负的行
    for col in _PRICE_COLS:
        if col in df.columns:
            df = df[df[col] > 0]

    # 3. 过滤停牌日（开盘=收盘=最高=最低 且成交量为0）
    price_cols_in_df = [c for c in _PRICE_COLS if c in df.columns]
    if len(price_cols_in_df) >= 4 and "volume" in df.columns:
        mask_suspend = (
            (df["open"] == df["close"]) &
            (df["close"] == df["high"]) &
            (df["high"] == df["low"]) &
            (df["volume"] <= 0)
        )
        df = df[~mask_suspend]

    # 4. 过滤极端异常值（分位数过滤）
    for col in price_cols_in_df:
        if df[col].std() > 0 and len(df) > 10:
            upper = df[col].quantile(0.998)
            lower = df[col].quantile(0.002)
            df = df[(df[col] >= lower) & (df[col] <= upper)]

    # 5. 去重（按日期）
    if "date" in df.columns:
        df = df.drop_duplicates(subset=["date"], keep="last")

    # 6. 按日期排序
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)

    after = len(df)
    if before > after:
        logger.debug(f"[DataCleaner] 清洗: {before}→{after} 行 (移除 {before-after})")

    return df


def detect_data_missing(df: pd.DataFrame, date_col: str = "date") -> List[str]:
    """
    检测行情时间断档，返回缺失交易日列表。

    Args:
        df: 行情 DataFrame
        date_col: 日期列名

    Returns:
        缺失日期字符串列表
    """
    if df is None or df.empty:
        return []

    df = df.copy()
    if date_col not in df.columns:
        return []

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    if len(df) < 2:
        return []

    all_days = pd.date_range(
        start=df[date_col].min(),
        end=df[date_col].max(),
        freq="D",
    )
    exist_days = set(d.date() for d in df[date_col])
    missing = [d.strftime("%Y-%m-%d") for d in all_days if d.date() not in exist_days]

    if missing:
        logger.warning(f"[DataCleaner] 检测到 {len(missing)} 个缺失交易日")

    return missing


def validate_data_quality(df: pd.DataFrame) -> dict:
    """
    数据质量校验，返回质量报告。

    Returns:
        {"total_rows": int, "null_counts": dict, "issues": list[str], "score": float 0~1}
    """
    if df is None or df.empty:
        return {"total_rows": 0, "null_counts": {}, "issues": ["数据为空"], "score": 0.0}

    issues = []
    null_counts = df.isnull().sum().to_dict()

    # 空值检查
    for col in _PRICE_COLS:
        if col in df.columns and null_counts.get(col, 0) > len(df) * 0.1:
            issues.append(f"列 {col} 空值过多 ({null_counts[col]}/{len(df)})")

    # 价格合理性检查
    for col in _PRICE_COLS:
        if col in df.columns:
            neg_count = (df[col] <= 0).sum()
            if neg_count > 0:
                issues.append(f"列 {col} 含 {neg_count} 个非正价格")

    # 涨跌停异常检查
    if "pct_change" in df.columns:
        extreme_count = (df["pct_change"].abs() > 10.5).sum()
        if extreme_count > 0:
            issues.append(f"{extreme_count} 行涨跌幅超过 ±10.5%")

    # 质量评分
    total_checks = len(_PRICE_COLS) + 2
    failed = len(issues)
    score = max(0.0, 1.0 - failed / total_checks)

    return {
        "total_rows": len(df),
        "null_counts": {k: int(v) for k, v in null_counts.items() if int(v) > 0},
        "issues": issues,
        "score": round(score, 2),
    }

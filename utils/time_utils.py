# -*- coding: utf-8 -*-
"""
===================================
时区统一工具 — utils/time_utils.py
===================================

强制统一所有行情时间为 Asia/Shanghai，消除跨市场时间错位。
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime
from typing import Optional

try:
    import pytz
    SH_TZ = pytz.timezone("Asia/Shanghai")
except ImportError:
    import warnings
    warnings.warn("pytz not installed, using UTC+8 offset fallback")
    from datetime import timezone, timedelta
    SH_TZ = timezone(timedelta(hours=8))


def standard_timezone(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    """
    统一时间转换为 Asia/Shanghai 时区。

    Args:
        df: 待处理的 DataFrame
        col: 时间列名

    Returns:
        时区标准化后的 DataFrame
    """
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()

    df = df.copy()
    if col not in df.columns:
        return df

    df[col] = pd.to_datetime(df[col], errors="coerce")

    # 如果无时区信息，假设为 UTC
    if df[col].dt.tz is None:
        df[col] = df[col].dt.tz_localize("UTC", ambiguous="infer", nonexistent="shift_forward")

    # 转换到上海时区
    df[col] = df[col].dt.tz_convert(SH_TZ)

    return df


def get_today_str(fmt: str = "%Y%m%d") -> str:
    """获取当前上海时区日期字符串"""
    return datetime.now(SH_TZ).strftime(fmt)


def get_today_datetime() -> datetime:
    """获取当前上海时区 datetime"""
    return datetime.now(SH_TZ)


def format_timestamp(ts: float, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """将 Unix 时间戳格式化为上海时区字符串"""
    return datetime.fromtimestamp(ts, SH_TZ).strftime(fmt)

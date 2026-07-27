# -*- coding: utf-8 -*-
"""
交易日历 & 时区统一工具
- 全局 UTC 存储 / 本地时区显示转换
- A股/港股/美股交易日判断
- 上一交易日、下一交易日查询
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# 市场时区
# ============================================================

MARKET_TIMEZONE: dict = {
    "a": timezone(timedelta(hours=8)),   # A股 CST
    "hk": timezone(timedelta(hours=8)),  # 港股 HKT
    "us": timezone(timedelta(hours=-4)), # 美股 EDT (简化)
    "jp": timezone(timedelta(hours=9)),
    "kr": timezone(timedelta(hours=9)),
    "tw": timezone(timedelta(hours=8)),
}

CHINA_TZ = timezone(timedelta(hours=8))
UTC = timezone.utc

# ============================================================
# A股交易日历（基于 exchange_calendars 或缓存 fallback）
# ============================================================

def get_china_calendar():
    """懒加载 A 股交易日历"""
    try:
        import exchange_calendars as ec
        return ec.get_calendar("XSHG")
    except Exception:
        return None


def is_trading_day(market: str = "a", dt: Optional[date] = None) -> bool:
    """判断是否为交易日"""
    dt = dt or date.today()
    if market == "a":
        cal = get_china_calendar()
        if cal:
            try:
                return cal.is_session(dt.isoformat())
            except Exception:
                pass
        # Fallback: 周末非交易日
        if dt.weekday() >= 5:
            return False
        # 简易 A 股节假日（可扩展）
        simple_holidays = {
            "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30",
            "2025-01-31", "2025-02-01", "2025-02-02", "2025-02-03",
            "2025-02-04", "2025-04-04", "2025-04-05", "2025-05-01",
            "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05",
            "2025-05-31", "2025-06-01", "2025-06-02", "2025-10-01",
            "2025-10-02", "2025-10-03", "2025-10-04", "2025-10-05",
            "2025-10-06", "2025-10-07", "2025-10-08",
        }
        return dt.isoformat() not in simple_holidays and dt.weekday() < 5

    # 港股/美股简易判断
    return dt.weekday() < 5


def prev_trading_day(market: str = "a", dt: Optional[date] = None,
                     offset: int = 1) -> date:
    """获取前 N 个交易日"""
    dt = dt or date.today()
    count = 0
    current = dt - timedelta(days=1)
    while count < offset:
        if is_trading_day(market, current):
            count += 1
            if count >= offset:
                return current
        current -= timedelta(days=1)
    return current


def next_trading_day(market: str = "a", dt: Optional[date] = None) -> date:
    """获取下一个交易日"""
    dt = dt or date.today()
    current = dt + timedelta(days=1)
    while not is_trading_day(market, current):
        current += timedelta(days=1)
    return current


# ============================================================
# 时区转换
# ============================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_market(market: str = "a") -> datetime:
    tz = MARKET_TIMEZONE.get(market, CHINA_TZ)
    return datetime.now(tz)


def to_utc(dt: datetime, market: str = "a") -> datetime:
    """本地时间 → UTC"""
    tz = MARKET_TIMEZONE.get(market, CHINA_TZ)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime, market: str = "a") -> datetime:
    """UTC → 本地时间"""
    tz = MARKET_TIMEZONE.get(market, CHINA_TZ)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def format_trade_date(dt: Optional[datetime | date] = None,
                      market: str = "a") -> str:
    """格式化交易日 YYYYMMDD（统一本地日期）"""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if isinstance(dt, datetime):
        dt = to_local(dt, market)
    return dt.strftime("%Y%m%d") if hasattr(dt, "strftime") else str(dt)


def is_market_open(market: str = "a") -> bool:
    """判断当前是否交易时段（简化版）"""
    if not is_trading_day(market):
        return False
    now = now_market(market)
    t = now.time()
    if market in ("a", "cn"):
        return (t.hour == 9 and t.minute >= 30) or (10 <= t.hour < 11) or (t.hour == 11 and t.minute <= 30) or (t.hour == 13) or (t.hour == 14) or (t.hour == 15 and t.minute == 0)
    if market in ("hk",):
        return (t.hour == 9 and t.minute >= 30) or (10 <= t.hour < 12) or (t.hour == 12) or (13 <= t.hour < 16)
    if market == "us":
        return (9 <= t.hour < 16)  # 简化
    return True

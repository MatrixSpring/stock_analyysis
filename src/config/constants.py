from enum import Enum


class MarketType(str, Enum):
    """市场类型"""
    A_SHARE = "A"
    HK_SHARE = "HK"
    US_SHARE = "US"


class CapitalDirection(str, Enum):
    """资金流向方向"""
    INFLOW = "inflow"
    OUTFLOW = "outflow"


# 日期格式化常量
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

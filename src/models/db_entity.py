"""
数据库实体定义，sqlite表结构定义参考
后续scripts/init_database.py 会执行建表
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class StockInfoEntity:
    """股票基础信息表"""
    stock_code: str
    stock_name: str
    market: str
    industry: str
    list_date: date


@dataclass
class StockDailyKlineEntity:
    """日线行情表"""
    stock_code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


@dataclass
class StockCapitalDailyEntity:
    """个股每日资金流向表"""
    stock_code: str
    trade_date: str
    main_inflow: float       # 主力净流入
    retail_inflow: float     # 散户净流入
    big_order: float
    mid_order: float
    small_order: float
    net_amount: float        # 当日净额


@dataclass
class StockNewsEntity:
    """个股资讯舆情数据表"""
    news_id: str               # 资讯唯一ID
    stock_code: str            # 关联股票代码
    publish_date: str          # 发布日期 YYYY-MM-DD
    publish_time: str          # 完整时间
    title: str                 # 标题
    content: str               # 正文摘要
    source: str                # 资讯来源
    sentiment: float           # 情感分值 [-1,1] 负向~正向
    industry: str              # 所属行业


@dataclass
class StockFavoriteEntity:
    """用户自选股"""
    id: int
    stock_code: str
    stock_name: str
    create_time: str


@dataclass
class BacktestTaskEntity:
    """回测任务记录"""
    task_id: str
    stock_code: str
    start_date: str
    end_date: str
    strategy_name: str
    params: str
    result: str
    total_return: float
    max_drawdown: float
    win_rate: float
    status: str
    create_time: str
    finish_time: str

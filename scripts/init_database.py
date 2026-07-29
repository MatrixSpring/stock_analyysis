from src.db.base_repo import BaseRepo
from src.core.logger import get_logger

logger = get_logger()

repo = BaseRepo()

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_info (
    stock_code TEXT PRIMARY KEY,
    stock_name TEXT,
    market TEXT,
    industry TEXT,
    list_date TEXT
);

CREATE TABLE IF NOT EXISTS stock_daily_kline (
    stock_code TEXT,
    trade_date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    PRIMARY KEY (stock_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_kline_code_date ON stock_daily_kline(stock_code, trade_date);

CREATE TABLE IF NOT EXISTS stock_capital_daily (
    stock_code TEXT,
    trade_date TEXT,
    main_inflow REAL,
    retail_inflow REAL,
    big_order REAL,
    mid_order REAL,
    small_order REAL,
    net_amount REAL,
    PRIMARY KEY (stock_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_capital_code_date ON stock_capital_daily(stock_code, trade_date);

CREATE TABLE IF NOT EXISTS stock_news (
    news_id TEXT PRIMARY KEY,
    stock_code TEXT,
    publish_date TEXT,
    publish_time TEXT,
    title TEXT,
    content TEXT,
    source TEXT,
    sentiment REAL,
    industry TEXT
);

CREATE INDEX IF NOT EXISTS idx_news_code_date ON stock_news(stock_code, publish_date);
CREATE INDEX IF NOT EXISTS idx_news_industry_date ON stock_news(industry, publish_date);

CREATE TABLE IF NOT EXISTS stock_favorite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    create_time TEXT
);
CREATE INDEX IF NOT EXISTS idx_fav_code ON stock_favorite(stock_code);

CREATE TABLE IF NOT EXISTS backtest_task (
    task_id TEXT PRIMARY KEY,
    stock_code TEXT,
    start_date TEXT,
    end_date TEXT,
    strategy_name TEXT,
    params TEXT,
    result TEXT,
    total_return REAL,
    max_drawdown REAL,
    win_rate REAL,
    status TEXT,
    create_time TEXT,
    finish_time TEXT
);
CREATE INDEX IF NOT EXISTS idx_backtest_code ON backtest_task(stock_code);
"""

if __name__ == "__main__":
    sql_list = [s.strip() for s in TABLE_SQL.split(";") if s.strip()]
    for sql in sql_list:
        repo.execute(sql)
    logger.info("✅ 数据表初始化完成")

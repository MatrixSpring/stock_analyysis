import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from scripts.task_config import (
    SYNC_STOCK_CODES,
    DEFAULT_START_DATE,
    DEFAULT_END_DATE,
    TASK_SWITCH,
    CRON_INTERVAL,
)
from scripts.task_logger import task_logger

# 仓储层导入（复用已有 repo，零 SQL 手写）
from src.db.stock_repo import stock_repo
from src.db.capital_repo import capital_repo
from src.db.news_repo import news_repo


def get_trade_date_range(start_date: str, end_date: str):
    """获取交易日序列，兜底最近30天"""
    if not start_date or not end_date:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=45)).strftime("%Y%m%d")
    return start_date, end_date


def sync_single_kline(code: str, s_date: str, e_date: str):
    """同步单只股票日线行情"""
    try:
        task_logger.info(f"开始同步K线 {code} [{s_date} ~ {e_date}]")
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=s_date, end_date=e_date, adjust="")
        if df.empty:
            task_logger.warning(f"{code} K线无数据")
            return
        df.rename(columns={
            "日期": "trade_date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount"
        }, inplace=True)
        df["stock_code"] = code
        df = df[["stock_code", "trade_date", "open", "high", "low", "close", "volume", "amount"]]
        stock_repo.batch_save_kline(df)
        task_logger.info(f"{code} K线入库完成，行数:{len(df)}")
    except Exception as e:
        task_logger.exception(f"{code} K线同步失败: {str(e)}")


def sync_single_capital(code: str, s_date: str, e_date: str):
    """同步单只股票资金流向"""
    try:
        task_logger.info(f"开始同步资金流向 {code} [{s_date} ~ {e_date}]")
        import akshare as ak
        df = ak.stock_individual_fund_flow(symbol=code, start_date=s_date, end_date=e_date)
        if df.empty:
            task_logger.warning(f"{code} 资金数据为空")
            return
        df.rename(columns={
            "日期": "trade_date",
            "主力净流入-净额": "main_inflow",
            "散户净流入-净额": "retail_inflow",
            "大单净流入-净额": "big_order",
            "中单净流入-净额": "mid_order",
            "小单净流入-净额": "small_order",
            "净额": "net_amount"
        }, inplace=True)
        df["stock_code"] = code
        capital_repo.batch_save_capital(df)
        task_logger.info(f"{code} 资金流向入库完成，行数:{len(df)}")
    except Exception as e:
        task_logger.exception(f"{code} 资金同步失败: {str(e)}")


def sync_single_news(code: str, s_date: str, e_date: str):
    """
    资讯同步说明：
    akshare个股新闻接口有限；
    此处为模板，后续可替换第三方资讯源；
    LLM情感打分可在此处或者后台消费任务补充
    """
    task_logger.info(f"资讯同步模板 {code}，待对接数据源")
    try:
        import akshare as ak
        df = ak.stock_news_em(symbol=code)
        if df.empty:
            task_logger.warning(f"{code} 资讯为空")
            return
        df.rename(columns={
            "新闻标题": "title",
            "新闻内容": "content",
            "发布时间": "publish_time",
            "文章来源": "source",
        }, inplace=True, errors="ignore")
        df["stock_code"] = code
        df["news_id"] = df.apply(
            lambda r: f"{code}_{r.get('publish_time', '')}_{hash(str(r.get('title','')))%100000}", axis=1
        )
        df["sentiment"] = 0.0  # 默认中性，后续由 LLM 消费队列补打分
        df["industry"] = ""
        if "publish_time" in df.columns:
            df["publish_date"] = pd.to_datetime(df["publish_time"]).dt.strftime("%Y-%m-%d")
        else:
            df["publish_date"] = datetime.now().strftime("%Y-%m-%d")
        news_repo.batch_save_news(df)
        task_logger.info(f"{code} 资讯入库完成，行数:{len(df)}")
    except Exception as e:
        task_logger.exception(f"{code} 资讯同步失败: {str(e)}")


def run_full_sync(start_date: str = None, end_date: str = None):
    """执行一次全量同步"""
    s_date, e_date = get_trade_date_range(
        start_date or DEFAULT_START_DATE,
        end_date or DEFAULT_END_DATE,
    )
    task_logger.info(f"===== 启动一轮同步任务 {s_date} ~ {e_date} =====")

    for code in SYNC_STOCK_CODES:
        if TASK_SWITCH.get("sync_kline", True):
            sync_single_kline(code, s_date, e_date)
            time.sleep(0.8)
        if TASK_SWITCH.get("sync_capital", True):
            sync_single_capital(code, s_date, e_date)
            time.sleep(0.8)
        if TASK_SWITCH.get("sync_news", True):
            sync_single_news(code, s_date, e_date)

    task_logger.info("===== 当前轮次同步全部完成 =====\n")


def run_cron_loop():
    """持续循环定时任务"""
    task_logger.info(f"启动定时循环模式，间隔 {CRON_INTERVAL}s")
    while True:
        run_full_sync()
        time.sleep(CRON_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="行情&资金定时同步任务")
    parser.add_argument("--mode", type=str, default="once",
                        choices=["once", "cron"],
                        help="once单次执行 / cron持续定时")
    parser.add_argument("--start", type=str, default="",
                        help="起始日期 YYYYMMDD")
    parser.add_argument("--end", type=str, default="",
                        help="结束日期 YYYYMMDD")
    args = parser.parse_args()

    if args.mode == "once":
        run_full_sync(args.start, args.end)
    elif args.mode == "cron":
        run_cron_loop()

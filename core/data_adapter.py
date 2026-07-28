# -*- coding: utf-8 -*-
"""
===================================
统一数据源适配器 — core/data_adapter.py
===================================

提供多数据源自动降级、超时重试、时区标准化、统一输出格式。
支持 akshare / tushare / yfinance / efinance 自动切换。

使用方式：
    from core.data_adapter import DataSourceAdapter
    adapter = DataSourceAdapter()
    df = adapter.get_stock_kline("600519", "20260701", "20260728")
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from core.data_cleaner import clean_stock_data
from utils.time_utils import standard_timezone

logger = logging.getLogger(__name__)


class DataSourceAdapter:
    """
    统一数据源适配器。

    特性：
    - 按优先级依次尝试数据源
    - 每个数据源支持重试
    - 失败自动降级到下一个数据源
    - 统一输出格式和时区
    """

    def __init__(self):
        self.source_list = ["akshare", "tushare", "efinance", "yfinance"]
        self.timeout = 15
        self.retry_times = 2
        self.default_adjust = "qfq"  # 前复权
        self._load_config()

    def _load_config(self):
        """从中心化配置加载参数"""
        try:
            import yaml
            from pathlib import Path
            config_path = Path(__file__).parent.parent / "config" / "system_config.yaml"
            if config_path.exists():
                with open(config_path) as f:
                    conf = yaml.safe_load(f)
                ds_conf = conf.get("DATA_SOURCE_CONF", {})
                self.source_list = ds_conf.get("priority", self.source_list)
                self.timeout = ds_conf.get("timeout", self.timeout)
                self.retry_times = ds_conf.get("retry_times", self.retry_times)
                self.default_adjust = ds_conf.get("default_adjust", self.default_adjust)
        except Exception as e:
            logger.debug(f"[DataAdapter] 配置加载跳过，使用默认值: {e}")

    # ---- 对外统一入口 ----

    def get_stock_kline(
        self, symbol: str, start_date: str, end_date: str, adjust: str = None
    ) -> pd.DataFrame:
        """
        获取个股日K线（自动多源降级）。

        Args:
            symbol: 股票代码（纯数字，如 600519）
            start_date: 起始日期 YYYYMMDD
            end_date: 截止日期 YYYYMMDD
            adjust: 复权类型 qfq/hfq/None

        Returns:
            标准化 DataFrame，失败返回空 DataFrame
        """
        adjust = adjust or self.default_adjust

        for source in self.source_list:
            for attempt in range(self.retry_times):
                try:
                    df = self._fetch_from(source, symbol, start_date, end_date, adjust)
                    if df is not None and not df.empty:
                        df = standard_timezone(df)
                        df = clean_stock_data(df)
                        logger.info(
                            f"[DataAdapter] {symbol} 数据源={source} "
                            f"行数={len(df)} 尝试={attempt+1}"
                        )
                        return df
                except Exception as e:
                    logger.warning(
                        f"[DataAdapter] {source} {symbol} 失败 "
                        f"(第{attempt+1}次): {e}"
                    )
                    if attempt < self.retry_times - 1:
                        time.sleep(1.0)

            logger.warning(f"[DataAdapter] {source} {symbol} 所有重试均失败")

        logger.error(f"[DataAdapter] {symbol} 全部数据源失败: {self.source_list}")
        return pd.DataFrame()

    # ---- 各数据源实现 ----

    def _fetch_from(
        self, source: str, symbol: str, start_date: str, end_date: str, adjust: str
    ) -> Optional[pd.DataFrame]:
        """路由到具体数据源获取方法"""
        if source == "akshare":
            return self._fetch_akshare(symbol, start_date, end_date, adjust)
        elif source == "tushare":
            return self._fetch_tushare(symbol, start_date, end_date, adjust)
        elif source == "yfinance":
            return self._fetch_yfinance(symbol, start_date, end_date)
        elif source == "efinance":
            return self._fetch_efinance(symbol, start_date, end_date, adjust)
        return None

    def _fetch_akshare(
        self, symbol: str, start_date: str, end_date: str, adjust: str
    ) -> Optional[pd.DataFrame]:
        """akshare 数据源"""
        try:
            import akshare as ak
            adjust_map = {"qfq": "qfq", "hfq": "hfq", "": ""}
            adj = adjust_map.get(adjust, "qfq")
            df = ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=start_date, end_date=end_date, adjust=adj
            )
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume",
                    "成交额": "amount", "振幅": "amplitude",
                    "涨跌幅": "pct_change", "涨跌额": "change",
                    "换手率": "turnover",
                })
            return df
        except ImportError:
            logger.warning("[DataAdapter] akshare 未安装，跳过")
            return None

    def _fetch_tushare(
        self, symbol: str, start_date: str, end_date: str, adjust: str
    ) -> Optional[pd.DataFrame]:
        """tushare 数据源"""
        try:
            import tushare as ts
            pro = ts.pro_api()
            adj_map = {"qfq": "qfq", "hfq": "hfq", "": None}
            adj = adj_map.get(adjust)
            ts_code = f"{symbol}.{'SH' if symbol.startswith('6') else 'SZ'}"
            df = pro.daily(
                ts_code=ts_code, start_date=start_date,
                end_date=end_date, adj=adj,
            )
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "trade_date": "date", "open": "open", "close": "close",
                    "high": "high", "low": "low", "vol": "volume",
                    "amount": "amount",
                })
                df = df.sort_values("date")
            return df
        except ImportError:
            logger.debug("[DataAdapter] tushare 未安装，跳过")
            return None

    def _fetch_yfinance(
        self, symbol: str, start_date: str, end_date: str
    ) -> Optional[pd.DataFrame]:
        """yfinance 数据源（适用于港股/美股）"""
        try:
            import yfinance as yf
            start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, auto_adjust=True)
            if df is not None and not df.empty:
                df = df.reset_index()
                df = df.rename(columns={
                    "Date": "date", "Open": "open", "Close": "close",
                    "High": "high", "Low": "low", "Volume": "volume",
                })
            return df
        except ImportError:
            logger.debug("[DataAdapter] yfinance 未安装，跳过")
            return None

    def _fetch_efinance(
        self, symbol: str, start_date: str, end_date: str, adjust: str
    ) -> Optional[pd.DataFrame]:
        """efinance 数据源"""
        try:
            import efinance as ef
            df = ef.stock.get_quote_history(symbol, beg=start_date, end=end_date)
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume",
                    "成交额": "amount", "涨跌幅": "pct_change",
                    "换手率": "turnover",
                })
            return df
        except ImportError:
            logger.debug("[DataAdapter] efinance 未安装，跳过")
            return None


# 全局单例
_data_adapter_instance: Optional[DataSourceAdapter] = None


def get_data_adapter() -> DataSourceAdapter:
    """获取数据源适配器单例"""
    global _data_adapter_instance
    if _data_adapter_instance is None:
        _data_adapter_instance = DataSourceAdapter()
    return _data_adapter_instance

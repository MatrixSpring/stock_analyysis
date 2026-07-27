# -*- coding: utf-8 -*-
"""
数据 ETL 管道 — 从 ai_mark 子系统融合并标准化

提供统一的数据抽取→转换→加载管道：
  - DataTransformer: 将各数据源不同格式统一为标准化 Schema
  - ETLPipeline: 编排抓取→转换→入库流程

与 data_provider/base.py 的 STANDARD_COLUMNS 对齐：
  STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']

原始来源：ai_mark/integrations/financial_data/pipeline.py
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ============================================================
# 标准化列名（与 data_provider/base.py 对齐）
# ============================================================

STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']


# ============================================================
# 数据转换层 (Transformer)
# ============================================================

class DataTransformer:
    """将不同数据源输出转为标准化格式"""

    @staticmethod
    def stock_daily(df: pd.DataFrame, code: str, source: str) -> pd.DataFrame:
        """
        股票日线标准化 → {date, open, high, low, close, volume, amount, pct_chg, code}

        支持的列名映射：
          - akshare: 日期/开盘/最高/最低/收盘/成交量/成交额/涨跌幅
          - baostock: date/open/high/low/close/volume/amount/pctChg
          - tushare: trade_date/open/high/low/close/vol/amount/pct_chg
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS + ["code"])

        df = df.copy()

        # 列名映射
        source_maps = {
            "akshare": {"日期": "date", "开盘": "open", "最高": "high", "最低": "low",
                       "收盘": "close", "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg"},
            "baostock": {"pctChg": "pct_chg"},
            "tushare": {"trade_date": "date", "ts_code": "code", "vol": "volume"},
            "efinance": {"日期": "date", "开盘": "open", "最高": "high", "最低": "low",
                        "收盘": "close", "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg"},
        }

        source_map = source_maps.get(source, {})
        if source_map:
            df.rename(columns=source_map, inplace=True)

        # 确保标准列存在
        for c in STANDARD_COLUMNS:
            if c not in df.columns:
                df[c] = 0.0
        df["code"] = code
        df["source"] = source

        return df[STANDARD_COLUMNS + ["code", "source"]]

    @staticmethod
    def index_daily(df: pd.DataFrame, code: str, name: str, source: str) -> pd.DataFrame:
        """指数日线标准化"""
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        rename_map = {
            "日期": "date", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close", "成交量": "volume", "涨跌幅": "pct_chg",
        }
        df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

        for c in STANDARD_COLUMNS:
            if c not in df.columns:
                df[c] = 0.0

        df["code"] = code
        df["name"] = name
        df["source"] = source
        return df

    @staticmethod
    def fund_flow(df: pd.DataFrame, code: str, source: str) -> pd.DataFrame:
        """资金流向标准化"""
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        rename_map = {
            "日期": "date", "主力净流入": "main_net_flow",
            "超大单净流入": "super_large_net", "大单净流入": "large_net",
            "中单净流入": "medium_net", "小单净流入": "small_net",
        }
        df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
        df["code"] = code
        df["source"] = source
        return df

    @staticmethod
    def news_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        新闻/情报文章标准化。

        统一字段：
          - title, content, source_name, source_url, publish_time
          - category (policy/finance/industry/geopolitics/tech)
          - sentiment (positive/negative/neutral)
          - region (cn/us/eu/global)
        """
        normalized = []
        for art in articles:
            norm = {
                "title": (art.get("title") or "").strip(),
                "content": (art.get("content") or "")[:5000],
                "source_name": art.get("source_name", art.get("source", "unknown")),
                "source_url": art.get("source_url", art.get("url", "")),
                "publish_time": art.get("publish_time", art.get("published", "")),
                "category": art.get("category", "industry"),
                "sentiment": art.get("sentiment", "neutral"),
                "sentiment_score": art.get("sentiment_score", 0.0),
                "region": art.get("region", "cn"),
                "language": art.get("language", "zh"),
                "fetch_time": art.get("fetch_time", datetime.utcnow().isoformat()),
            }
            if norm["title"]:
                normalized.append(norm)
        return normalized


# ============================================================
# ETL 管道编排
# ============================================================

@dataclass
class ETLStep:
    """单个 ETL 步骤的定义"""
    name: str
    fetcher: Callable
    transformer: Optional[Callable] = None
    enabled: bool = True


class ETLPipeline:
    """
    ETL 管道编排器 — 抓取→转换→加载。

    使用示例:
        pipeline = ETLPipeline()
        pipeline.add_step("stock_daily", fetch_akshare, DataTransformer.stock_daily)
        results = pipeline.run()
    """

    def __init__(self):
        self._steps: List[ETLStep] = []
        self._results: Dict[str, Any] = {}

    def add_step(self, name: str, fetcher: Callable,
                 transformer: Optional[Callable] = None,
                 enabled: bool = True):
        """添加 ETL 步骤"""
        self._steps.append(ETLStep(name=name, fetcher=fetcher,
                                   transformer=transformer, enabled=enabled))

    def run(self) -> Dict[str, Any]:
        """
        顺序执行所有 ETL 步骤。

        Returns:
            {step_name: {"success": bool, "data": ..., "error": str}}
        """
        for step in self._steps:
            if not step.enabled:
                self._results[step.name] = {"success": False, "data": None, "error": "disabled"}
                continue

            try:
                logger.info(f"[ETL] Running step: {step.name}")
                raw_data = step.fetcher()

                if step.transformer and raw_data is not None:
                    data = step.transformer(raw_data)
                else:
                    data = raw_data

                self._results[step.name] = {"success": True, "data": data, "error": None}
                logger.info(f"[ETL] Step '{step.name}' completed successfully")
            except Exception as e:
                logger.error(f"[ETL] Step '{step.name}' failed: {e}")
                self._results[step.name] = {"success": False, "data": None, "error": str(e)}

        return self._results

    @property
    def summary(self) -> Dict[str, int]:
        """管道执行摘要"""
        total = len(self._steps)
        success = sum(1 for r in self._results.values() if r["success"])
        failed = total - success
        return {"total": total, "success": success, "failed": failed}

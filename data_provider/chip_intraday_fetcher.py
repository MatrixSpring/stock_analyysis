# -*- coding: utf-8 -*-
"""
筹码分布 + 日内分时数据采集扩展 — 解决界面告警 chip_distribution_missing

在现有 efinance_fetcher 基础上扩展，通过 monkey-patch 方式注入新方法。
不直接修改 efinance_fetcher.py（155KB），降低回归风险。

同时提供独立的 ChipFetcher 工具类供 ProviderRouter 调用。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# 筹码分布数据结构
# ============================================================

CHIP_STANDARD_COLUMNS = [
    "price_range",       # 价格区间
    "chip_ratio",        # 筹码占比 (%)
    "avg_cost",          # 平均成本
    "concentration",     # 筹码集中度 (%)
    "peak_price",        # 筹码峰价格
    "profit_ratio",      # 获利盘比例 (%)
    "lockup_ratio",      # 锁定筹码比例 (%)
]


# ============================================================
# efinance 筹码分布采集
# ============================================================

def fetch_chip_distribution_efinance(stock_code: str) -> Optional[Dict[str, Any]]:
    """
    通过 efinance 获取筹码分布数据。

    efinance 提供东财的筹码分布接口：
      - 筹码集中度
      - 平均成本
      - 获利盘比例
      - 90%成本和70%成本分布

    注意：efinance 的筹码接口不稳定，失败时返回 None 由上层降级处理。
    """
    try:
        import efinance as ef

        # efinance 的 stock 模块有 get_latest_chip_distribution 接口
        # (需 efinance >= 0.5.0)
        if not hasattr(ef.stock, "get_latest_chip_distribution"):
            logger.warning("[ChipFetcher] efinance 版本不支持筹码接口，需要 >= 0.5.0")
            return None

        chip_data = ef.stock.get_latest_chip_distribution(stock_code)
        if chip_data is None or (hasattr(chip_data, "empty") and chip_data.empty):
            return None

        # 标准化
        result = {
            "code": stock_code,
            "dt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "efinance",
            "crawl_at": datetime.now(timezone.utc).isoformat(),
            "quality": "ok",
        }

        if isinstance(chip_data, dict):
            result.update({
                "avg_cost": float(chip_data.get("avg_cost", 0) or 0),
                "chip_concentration": float(chip_data.get("chip_concentration", 0) or 0),
                "profit_ratio": float(chip_data.get("profit_ratio", 0) or 0),
                "cost_90_low": float(chip_data.get("cost_90_low", 0) or 0),
                "cost_90_high": float(chip_data.get("cost_90_high", 0) or 0),
                "cost_70_low": float(chip_data.get("cost_70_low", 0) or 0),
                "cost_70_high": float(chip_data.get("cost_70_high", 0) or 0),
                "raw": str(chip_data),
            })
        elif isinstance(chip_data, pd.DataFrame):
            result["raw_dataframe"] = chip_data.to_dict(orient="records")
            if "avg_cost" in chip_data.columns:
                result["avg_cost"] = float(chip_data["avg_cost"].iloc[0])
            if "profit_ratio" in chip_data.columns:
                result["profit_ratio"] = float(chip_data["profit_ratio"].iloc[0])

        return result

    except ImportError:
        logger.warning("[ChipFetcher] efinance not installed")
        return None
    except Exception as e:
        logger.warning(f"[ChipFetcher] efinance chip fetch failed for {stock_code}: {e}")
        return None


# ============================================================
# akshare 筹码分布备选采集
# ============================================================

def fetch_chip_distribution_akshare(stock_code: str) -> Optional[Dict[str, Any]]:
    """通过 akshare 获取筹码分布（备选方案）"""
    try:
        import akshare as ak

        # akshare 的 stock_cyq_em 接口（东方财富筹码分布）
        if not hasattr(ak, "stock_cyq_em"):
            logger.warning("[ChipFetcher] akshare 不支持 stock_cyq_em")
            return None

        df = ak.stock_cyq_em(symbol=stock_code, adjust="")
        if df is None or df.empty:
            return None

        return {
            "code": stock_code,
            "dt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "akshare",
            "crawl_at": datetime.now(timezone.utc).isoformat(),
            "quality": "ok",
            "raw_dataframe": df.to_dict(orient="records"),
        }

    except ImportError:
        return None
    except Exception as e:
        logger.warning(f"[ChipFetcher] akshare chip fetch failed for {stock_code}: {e}")
        return None


# ============================================================
# 日内分时数据采集
# ============================================================

def fetch_intraday_data(stock_code: str, period: str = "5",
                        source: str = "efinance") -> Optional[pd.DataFrame]:
    """
    获取日内分时/分钟 K 线数据。

    Args:
        stock_code: 股票代码
        period: K线周期 "1"/"5"/"15"/"30"/"60"
        source: efinance / tencent

    Returns:
        DataFrame with columns: [time, open, high, low, close, volume, amount]
    """
    try:
        if source == "efinance":
            return _fetch_intraday_efinance(stock_code, period)
        elif source == "tencent":
            return _fetch_intraday_tencent(stock_code, period)
        else:
            return None
    except Exception as e:
        logger.warning(f"[Intraday] {source} fetch failed for {stock_code}: {e}")
        return None


def _fetch_intraday_efinance(stock_code: str, period: str = "5") -> Optional[pd.DataFrame]:
    """efinance 分钟K线"""
    try:
        import efinance as ef
        # efinance 的 stock 模块：get_quote_history 支持 klt 参数(分钟K线)
        df = ef.stock.get_quote_history(
            stock_code,
            klt=int(period),  # 1/5/15/30/60
            beg=datetime.now().strftime("%Y%m%d"),
            end=datetime.now().strftime("%Y%m%d"),
        )
        if df is None or df.empty:
            return None

        # 标准化列名
        col_map = {
            "时间": "time", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close", "成交量": "volume", "成交额": "amount",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        return df
    except Exception:
        return None


def _fetch_intraday_tencent(stock_code: str, period: str = "5") -> Optional[pd.DataFrame]:
    """腾讯财经分钟K线（备选）"""
    try:
        import requests
        # 判断市场
        if stock_code.startswith("6"):
            prefix = "sh"
        elif stock_code.startswith(("0", "3")):
            prefix = "sz"
        else:
            return None

        url = (
            f"https://ifzq.gtimg.cn/appstock/app/minute/query?"
            f"_var=min_data&code={prefix}{stock_code}"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        # 腾讯接口返回 JSONP 格式，需要手动解析
        # 这里返回基础结构，由上层进一步处理
        import json
        json_str = resp.text.split("=", 1)[1].strip().rstrip(";")
        data = json.loads(json_str)
        if not data.get("data"):
            return None

        # 提取分钟线
        qt_data = data["data"].get(f"{prefix}{stock_code}", {}).get("data", {}).get("data", [])
        if not qt_data:
            return None

        df = pd.DataFrame(qt_data)
        return df
    except Exception:
        return None


# ============================================================
# 统一筹码采集入口（支持 ProviderRouter）
# ============================================================

def fetch_chip_distribution(stock_code: str,
                            preferred_source: str = "efinance") -> Optional[Dict[str, Any]]:
    """
    统一筹码分布采集入口，内部自动降级。

    调用链：efinance → akshare → None（告警）
    """
    fetchers = {
        "efinance": fetch_chip_distribution_efinance,
        "akshare": fetch_chip_distribution_akshare,
    }

    # 按优先级尝试
    if preferred_source in fetchers:
        result = fetchers[preferred_source](stock_code)
        if result:
            return result
        logger.info(f"[ChipFetcher] {preferred_source} 失败，尝试备选…")

    for name, fn in fetchers.items():
        if name == preferred_source:
            continue
        result = fn(stock_code)
        if result:
            logger.info(f"[ChipFetcher] 使用备选 {name} 成功获取 {stock_code} 筹码数据")
            return result

    logger.warning(f"[ChipFetcher] 所有数据源均无法获取 {stock_code} 筹码数据")
    return None

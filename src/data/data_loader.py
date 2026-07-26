# -*- coding: utf-8 -*-
"""
统一数据中间层 DataLoader（P0 核心升级）

双数据源兜底：AKShare + BaoStock（永久免费，无需密钥）
输出标准化字段，直连四维量化打分、智能选股、行业景气分析

特性：
  - 真实实时 K 线 + 技术指标（MA/RSI/量比）
  - 资金面（主力净流入/北向/换手率）
  - 基本面（PE/营收增速/利润增速）
  - 行业自动识别
  - 本地缓存 60s + 限流 0.8s/次
  - 全异常兜底，任何环节失败都返回模板数据，不崩溃
"""

from __future__ import annotations

import atexit
import logging
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---- 可选依赖 ----
_ak_available = False
_bs_available = False

try:
    import akshare as ak  # noqa: F401
    _ak_available = True
except ImportError:
    logger.info("[DataLoader] AKShare 未安装，将使用模板数据降级")

try:
    import baostock as bs
    _bs_available = True
    bs.login()
    logger.debug("[DataLoader] BaoStock 登录成功")
except ImportError:
    logger.info("[DataLoader] BaoStock 未安装")
except Exception as e:
    logger.warning(f"[DataLoader] BaoStock 登录失败: {e}")

# ---- 缓存 ----
_DATA_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 60.0  # 单标的缓存 60 秒


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    entry = _DATA_CACHE.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts < _CACHE_TTL:
        return data
    del _DATA_CACHE[key]
    return None


def _cache_set(key: str, data: Dict[str, Any]):
    _DATA_CACHE[key] = (time.time(), data)


# ---- 空数据模板（兜底） ----

def _kline_template() -> Dict[str, Any]:
    return {"ma5": 0.0, "ma10": 0.0, "ma20": 0.0, "rsi": 50.0, "vol_ratio": 1.0, "close": 0.0}


def _money_template() -> Dict[str, Any]:
    return {"main_net_in": 0.0, "north_net_in": 0.0, "turnover": 5.0}


def _fund_template() -> Dict[str, Any]:
    return {"pe": 30.0, "revenue_growth": 0.0, "profit_growth": 0.0}


# ============================================================
# DataLoader
# ============================================================

class StockDataLoader:
    """统一股票数据加载器 — 独立数据中台。

    使用方式：
        loader = StockDataLoader()
        kline = loader.get_kline_indicators("600519")
        money = loader.get_money_flow("600519")
        fund  = loader.get_fundamental("600519")
        industry = loader.get_industry("600519")
    """

    def __init__(self, req_interval: float = 0.8):
        self._last_request = 0.0
        self._req_interval = req_interval
        self._ak_ok = _ak_available
        self._bs_ok = _bs_available

    # ---- 限流 ----

    def _rate_limit(self):
        now = time.time()
        gap = now - self._last_request
        if gap < self._req_interval:
            time.sleep(self._req_interval - gap)
        self._last_request = time.time()

    # ---- 代码标准化 ----

    @staticmethod
    def _normalize_code(code: str) -> Tuple[str, str]:
        """(baostock_code, akshare_code)"""
        code = code.strip()
        # 沪市
        if code.startswith(("60", "68")):
            return f"sh.{code}", code
        # 深市
        if code.startswith(("00", "30")):
            return f"sz.{code}", code
        # 港股
        if code.startswith("hk"):
            return code, code
        # 美股
        if code.isalpha():
            return code.lower(), code.lower()
        # 默认沪市
        return f"sh.{code}", code

    # ============================================================
    # K 线 + 技术指标
    # ============================================================

    def get_kline_indicators(self, code: str) -> Dict[str, Any]:
        """获取真实 K 线数据 + 计算 MA5/MA10/MA20/RSI/量比。

        适配 quant_scorer.calc_tech_score()
        """
        cache_key = f"kline_{code}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        self._rate_limit()

        # 方法 1: AKShare
        if self._ak_ok:
            try:
                result = self._kline_from_akshare(code)
                if result and result.get("close", 0) > 0:
                    _cache_set(cache_key, result)
                    return result
            except Exception as e:
                logger.debug(f"[DataLoader] AKShare K线 {code} 失败: {e}")

        # 方法 2: BaoStock
        if self._bs_ok:
            try:
                result = self._kline_from_baostock(code)
                if result and result.get("close", 0) > 0:
                    _cache_set(cache_key, result)
                    return result
            except Exception as e:
                logger.debug(f"[DataLoader] BaoStock K线 {code} 失败: {e}")

        logger.warning(f"[DataLoader] {code} K线双源均失败，降级为模板数据")
        return _kline_template()

    def _kline_from_akshare(self, code: str) -> Dict[str, Any]:
        import akshare as ak
        _, ak_code = self._normalize_code(code)
        df = ak.stock_zh_a_hist(
            symbol=ak_code, period="daily",
            start_date="", end_date="", adjust="qfq",
        )
        if df is None or df.empty or len(df) < 20:
            return _kline_template()
        return self._compute_kline_indicators(df.tail(20))

    def _kline_from_baostock(self, code: str) -> Dict[str, Any]:
        import baostock as bs
        bs_code, _ = self._normalize_code(code)
        end = time.strftime("%Y-%m-%d")
        start = (pd.Timestamp.now() - pd.Timedelta(days=60)).strftime("%Y-%m-%d")

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,close,volume",
            start_date=start, end_date=end,
            frequency="d", adjustflag="2",
        )
        if rs.error_code != "0":
            return _kline_template()

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if len(rows) < 20:
            return _kline_template()

        df = pd.DataFrame(rows, columns=["date", "close", "volume"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df = df.tail(20).reset_index(drop=True)
        return self._compute_kline_indicators(df)

    @staticmethod
    def _compute_kline_indicators(df) -> Dict[str, Any]:
        """从 OHLC DataFrame 计算技术指标（纯 numpy，无外部依赖）"""
        try:
            close = df["close"].astype(float)
            volume = df["volume"].astype(float)

            ma5 = float(close.tail(5).mean())
            ma10 = float(close.tail(10).mean())
            ma20 = float(close.tail(20).mean())

            # RSI(14) 标准算法
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100.0 - (100.0 / (1.0 + float(rs.iloc[-1]))) if not np.isnan(rs.iloc[-1]) and not np.isinf(rs.iloc[-1]) else 50.0

            # 量比
            vol5_avg = float(volume.tail(5).mean())
            vol_ratio = float(volume.iloc[-1]) / vol5_avg if vol5_avg > 0 else 1.0

            return {
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "ma20": round(ma20, 2),
                "rsi": round(rsi, 2),
                "vol_ratio": round(vol_ratio, 2),
                "close": round(float(close.iloc[-1]), 2),
            }
        except Exception:
            return _kline_template()

    # ============================================================
    # 资金面
    # ============================================================

    def get_money_flow(self, code: str) -> Dict[str, Any]:
        """获取主力净流入 / 北向资金 / 换手率。

        适配 quant_scorer.calc_money_score()
        """
        cache_key = f"money_{code}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        self._rate_limit()

        if self._ak_ok:
            try:
                result = self._money_from_akshare(code)
                if result:
                    _cache_set(cache_key, result)
                    return result
            except Exception as e:
                logger.debug(f"[DataLoader] AKShare 资金 {code} 失败: {e}")

        return _money_template()

    def _money_from_akshare(self, code: str) -> Dict[str, Any]:
        import akshare as ak
        _, ak_code = self._normalize_code(code)

        # 个股资金流向
        try:
            df = ak.stock_individual_fund_flow_rank(symbol=ak_code)
            main_in = float(df["主力净流入-净额"].iloc[0]) if "主力净流入-净额" in df.columns else 0.0
            turnover = float(df["换手率"].iloc[0]) if "换手率" in df.columns else 5.0
        except Exception:
            main_in = 0.0
            turnover = 5.0

        # 北向资金
        north_in = 0.0
        try:
            df_north = ak.stock_hsgt_individual(symbol=ak_code)
            if df_north is not None and not df_north.empty:
                north_in = float(df_north["北向资金净流入"].iloc[-1])
        except Exception:
            pass

        return {
            "main_net_in": round(main_in, 2),
            "north_net_in": round(north_in, 2),
            "turnover": round(turnover, 2),
        }

    # ============================================================
    # 基本面
    # ============================================================

    def get_fundamental(self, code: str) -> Dict[str, Any]:
        """获取 PE / 营收增速 / 利润增速。

        适配 quant_scorer.calc_fund_score()
        """
        cache_key = f"fund_{code}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        self._rate_limit()

        if self._ak_ok:
            try:
                result = self._fund_from_akshare(code)
                if result:
                    _cache_set(cache_key, result)
                    return result
            except Exception as e:
                logger.debug(f"[DataLoader] AKShare 基本面 {code} 失败: {e}")

        return _fund_template()

    def _fund_from_akshare(self, code: str) -> Dict[str, Any]:
        import akshare as ak
        _, ak_code = self._normalize_code(code)

        pe = 30.0
        try:
            df_val = ak.stock_zh_a_valuation(symbol=ak_code)
            if df_val is not None and not df_val.empty and "滚动市盈率" in df_val.columns:
                pe = float(df_val["滚动市盈率"].iloc[0])
        except Exception:
            pass

        rev_growth = 0.0
        profit_growth = 0.0
        try:
            df_fin = ak.stock_financial_analysis_indicator(symbol=ak_code)
            if df_fin is not None and not df_fin.empty:
                df_fin = df_fin.tail(1)
                if "营业总收入同比增长率" in df_fin.columns:
                    rev_growth = float(df_fin["营业总收入同比增长率"].iloc[0])
                if "净利润同比增长率" in df_fin.columns:
                    profit_growth = float(df_fin["净利润同比增长率"].iloc[0])
        except Exception:
            pass

        return {
            "pe": round(pe, 2),
            "revenue_growth": round(rev_growth, 2),
            "profit_growth": round(profit_growth, 2),
        }

    # ============================================================
    # 行业识别
    # ============================================================

    def get_industry(self, code: str) -> str:
        """自动获取个股所属行业，对接 industry_chain 分析。

        适配 industry_analyzer.analyze()
        """
        cache_key = f"industry_{code}"
        cached = _cache_get(cache_key)
        if cached:
            return cached.get("industry", "未知行业")

        if self._ak_ok:
            try:
                import akshare as ak
                _, ak_code = self._normalize_code(code)
                df = ak.stock_zh_a_industry()
                row = df[df["代码"] == ak_code]
                if not row.empty:
                    industry = str(row["行业"].iloc[0])
                    _cache_set(cache_key, {"industry": industry})
                    return industry
            except Exception as e:
                logger.debug(f"[DataLoader] 行业识别 {code} 失败: {e}")

        return "未知行业"

    # ============================================================
    # 全量一键加载
    # ============================================================

    def load_all(self, code: str) -> Dict[str, Any]:
        """一键加载某只股票的全部量化数据。

        Returns:
            {
                code, industry_name,
                kline_data: {ma5, ma10, ma20, rsi, vol_ratio, close},
                money_data: {main_net_in, north_net_in, turnover},
                fund_data:  {pe, revenue_growth, profit_growth},
                news_sentiment: float
            }
        """
        kline = self.get_kline_indicators(code)
        money = self.get_money_flow(code)
        fund = self.get_fundamental(code)
        industry = self.get_industry(code)

        result = {
            "code": code,
            "industry_name": industry,
            "kline_data": kline,
            "money_data": money,
            "fund_data": fund,
            "news_sentiment": 0.0,  # P1 迭代接入真实舆情
        }

        logger.info(
            f"[DataLoader] {code} 全量加载完成: "
            f"行业={industry}, close={kline.get('close', 'N/A')}, "
            f"PE={fund.get('pe', 'N/A')}, RSI={kline.get('rsi', 'N/A')}"
        )
        return result


# ============================================================
# 全局单例 + 退出清理
# ============================================================

data_loader = StockDataLoader()


def _cleanup_baostock():
    """程序退出时登出 BaoStock，释放连接"""
    if _bs_available:
        try:
            import baostock as bs
            bs.logout()
        except Exception:
            pass


atexit.register(_cleanup_baostock)

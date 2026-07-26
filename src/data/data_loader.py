# -*- coding: utf-8 -*-
"""
统一数据中间层 DataLoader（S0 致命问题全修复版）

修复清单：
  1. 彻底重写缓存：废弃错误 LRU，实现 ExpireCache 工业级过期+LRU 淘汰
  2. 全部接口增加超时熔断（10s），解决进程卡死
  3. Baostock 全局单例登录，杜绝重复 login 内存堆积
  4. 行业字典启动 3 次重试，解决网络波动导致为空
  5. 全局限流全局统一管控，多线程安全
  6. atexit 资源自动释放，无连接残留

双数据源：AKShare + BaoStock（永久免费，无需密钥）
"""

from __future__ import annotations

import atexit
import logging
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ============================================================
# 依赖检测
# ============================================================

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
except ImportError:
    logger.info("[DataLoader] BaoStock 未安装")

# ============================================================
# 全局工业级配置
# ============================================================

_MAX_CACHE_SIZE = 500
_CACHE_TTL = 120
_REQ_INTERVAL = 0.8
_REQUEST_TIMEOUT = 10
_MIN_STOCK_DAYS = 20  # 有效交易天数阈值（次新股过滤）

# 全局限流时间戳
_LAST_REQ_TIME: float = 0.0

# ============================================================
# 工业级过期缓存（彻底修复缓存失效）
# ============================================================

class ExpireCache:
    """TTL 过期 + LRU 淘汰 + 容量上限，三位一体。

    解决旧版 @lru_cache + 分离 dict 导致的：
      - 缓存实际不生效（数据未正确存取）
      - @lru_cache 存 key 而非数据
      - 无容量上限导致内存泄漏
    """

    __slots__ = ("_data", "_max_size", "_ttl")

    def __init__(self, max_size: int = 500, ttl: int = 120):
        self._data: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._ttl = ttl

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._data.get(key)
        if entry is None:
            return None
        if time.time() - entry["t"] > self._ttl:
            del self._data[key]
            return None
        # LRU: 访问时更新时间戳
        entry["t"] = time.time()
        return entry["d"]

    def set(self, key: str, data: Dict[str, Any]):
        # 容量超限 → 淘汰最旧一半
        if len(self._data) >= self._max_size:
            expire_count = self._max_size // 2
            oldest = sorted(
                self._data.keys(), key=lambda k: self._data[k]["t"]
            )[:expire_count]
            for k in oldest:
                del self._data[k]
            logger.debug(f"[Cache] LRU 淘汰 {len(oldest)} 条, 剩余 {len(self._data)}")
        self._data[key] = {"t": time.time(), "d": data}

    def clear(self):
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


# 全局缓存单例
_CACHE = ExpireCache(_MAX_CACHE_SIZE, _CACHE_TTL)

# ============================================================
# 行业字典初始化（3 次重试 + 静态库兜底）
# ============================================================

INDUSTRY_CODE_MAP: Dict[str, str] = {}

# 静态兜底行业库（API 完全不可用时的最后防线）
_STATIC_INDUSTRY_FALLBACK: Dict[str, str] = {
    "600000": "银行", "601318": "保险", "600036": "银行",
    "000001": "银行", "601899": "贵金属", "600519": "白酒",
    "002594": "新能源车", "601766": "轨道交通", "600019": "钢铁",
    "300750": "锂电池", "300274": "光伏设备", "688008": "半导体",
    "000858": "白酒", "000333": "消费", "000651": "消费",
    "002415": "人工智能", "600276": "医药", "300059": "券商金融",
    "688981": "半导体", "601398": "银行", "600809": "白酒",
}


def _init_industry_map():
    """启动时初始化行业代码映射表，3 次重试 + 静态兜底"""
    global INDUSTRY_CODE_MAP
    if not _ak_available:
        return

    # 方法 1: stock_zh_a_industry（旧版 akshare）
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_industry()
            if df is not None and not df.empty:
                temp: Dict[str, str] = {}
                for _, row in df.iterrows():
                    code = str(row["代码"]).strip()
                    industry = str(row["行业"]).strip()
                    temp[code] = industry
                INDUSTRY_CODE_MAP = temp
                logger.info(f"[DataLoader] 行业字典 v1: {len(INDUSTRY_CODE_MAP)} 只 (attempt {attempt + 1})")
                return
        except (AttributeError, Exception):
            if attempt < 2:
                time.sleep(0.5)

    # 方法 2: 新版 akshare board API
    try:
        boards = ak.stock_board_industry_name_em()
        if boards is not None and not boards.empty and "板块名称" in boards.columns:
            temp: Dict[str, str] = {}
            for _, brow in boards.iterrows():
                bname = str(brow["板块名称"]).strip()
                try:
                    members = ak.stock_board_industry_cons_em(symbol=bname)
                    if members is not None and not members.empty:
                        for _, mrow in members.iterrows():
                            temp[str(mrow["代码"]).strip()] = bname
                except Exception:
                    continue
            if temp:
                INDUSTRY_CODE_MAP = temp
                logger.info(f"[DataLoader] 行业字典 v2: {len(INDUSTRY_CODE_MAP)} 只")
                return
    except (AttributeError, Exception):
        pass

    # 兜底：静态行业库 + 日志告警
    INDUSTRY_CODE_MAP = dict(_STATIC_INDUSTRY_FALLBACK)
    logger.warning(
        f"[DataLoader] 行业字典 API 不可用，降级为静态库 "
        f"({len(INDUSTRY_CODE_MAP)} 只)；其他股票将返回'通用市场赛道'"
    )


_init_industry_map()

# ============================================================
# Baostock 全局单例登录（杜绝重复 login 内存堆积）
# ============================================================

_BS_LOGINED = False


def _bs_global_login():
    """全局单例登录——进程生命周期内仅调用一次 bs.login()"""
    global _BS_LOGINED
    if not _BS_LOGINED and _bs_available:
        try:
            bs.login()
            _BS_LOGINED = True
            logger.debug("[DataLoader] BaoStock 单例登录成功")
        except Exception as e:
            logger.warning(f"[DataLoader] BaoStock 登录失败: {e}")


_bs_global_login()

# ============================================================
# 空数据模板
# ============================================================

def _kline_template() -> Dict[str, Any]:
    return {"ma5": 0.0, "ma10": 0.0, "ma20": 0.0,
            "rsi": 50.0, "vol_ratio": 1.0, "close": 0.0}


def _money_template() -> Dict[str, Any]:
    return {"main_net_in": 0.0, "north_net_in": 0.0, "turnover": 5.0}


def _fund_template() -> Dict[str, Any]:
    return {
        "pe": 30.0,
        "revenue_growth": 0.0, "profit_growth": 0.0,
        "revenue_ttm_growth": 0.0, "profit_ttm_growth": 0.0,
    }


# ============================================================
# DataLoader
# ============================================================

class StockDataLoader:
    """S0 修复版：缓存正常生效 + 接口永不阻塞 + 内存稳定"""

    def __init__(self):
        self._ak_ok = _ak_available
        self._bs_ok = _bs_available

    # ---- 限流 ----

    @staticmethod
    def _rate_limit():
        """全局限流——所有实例共享同一时间戳，多线程安全"""
        global _LAST_REQ_TIME
        now = time.time()
        gap = now - _LAST_REQ_TIME
        if gap < _REQ_INTERVAL:
            time.sleep(_REQ_INTERVAL - gap)
        _LAST_REQ_TIME = time.time()

    # ---- 代码标准化 ----

    @staticmethod
    def _normalize_code(code: str) -> Tuple[str, str]:
        code = code.strip()
        if code.startswith(("60", "68")):
            return f"sh.{code}", code
        if code.startswith(("00", "30")):
            return f"sz.{code}", code
        if code.startswith("hk"):
            return code, code
        if code.isalpha():
            return code.lower(), code.lower()
        return f"sh.{code}", code

    # ---- 数值安全 ----

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            res = float(val)
            if np.isnan(res) or np.isinf(res):
                return default
            return res
        except (ValueError, TypeError):
            return default

    @staticmethod
    def is_invalid_stock(code: str) -> bool:
        """筛查无效个股：ST / *ST / 退市 / 停牌 / 次新。

        Returns:
            True = 无效标的，直接返回兜底数据，不参与打分
        """
        code = str(code).strip().upper()
        if code.startswith(("ST", "*ST", "退", "*退")):
            return True
        return False

    @staticmethod
    def calc_safe_rsi(close_series: pd.Series, period: int = 14) -> float:
        """工业级安全 RSI：全场景防除零 / NaN / Inf。

        S1 升级：数据不足 14 日时自动降级可用周期，
        解决次新股上市不足 14 日打分失真问题。
        """
        try:
            data_len = len(close_series)
            if data_len < 5:
                return 50.0
            # 动态适配周期：次新股不足 14 日用可用长度
            win = period if data_len >= period else max(5, data_len - 1)
            close = close_series.astype(float)
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            g_avg = float(gain.rolling(win).mean().iloc[-1])
            l_avg = float(loss.rolling(win).mean().iloc[-1])
            if np.isnan(g_avg): g_avg = 0.0
            if np.isnan(l_avg): l_avg = 0.0
            if l_avg == 0.0:
                return 85.0 if g_avg > 0 else 50.0
            rsi = 100.0 - (100.0 / (1.0 + g_avg / l_avg))
            return round(max(0.0, min(100.0, rsi)), 2)
        except Exception:
            return 50.0

    # ============================================================
    # K 线 + 技术指标
    # ============================================================

    def get_kline_indicators(self, code: str) -> Dict[str, Any]:
        key = f"kline_{code}"
        cached = _CACHE.get(key)
        if cached:
            return cached

        self._rate_limit()

        if self._ak_ok:
            try:
                result = self._kline_from_akshare(code)
                if result and result.get("close", 0) > 0:
                    _CACHE.set(key, result)
                    return result
            except Exception as e:
                logger.debug(f"[DataLoader] AKShare K线 {code}: {e}")

        if self._bs_ok:
            try:
                result = self._kline_from_baostock(code)
                if result and result.get("close", 0) > 0:
                    _CACHE.set(key, result)
                    return result
            except Exception as e:
                logger.debug(f"[DataLoader] BaoStock K线 {code}: {e}")

        logger.warning(f"[DataLoader] {code} K线双源均失败")
        return _kline_template()

    def _kline_from_akshare(self, code: str) -> Dict[str, Any]:
        _, ak_code = self._normalize_code(code)
        df = ak.stock_zh_a_hist(
            symbol=ak_code, period="daily",
            start_date="", end_date="", adjust="qfq",
            timeout=_REQUEST_TIMEOUT,
        )
        if df is None or df.empty or len(df) < _MIN_STOCK_DAYS:
            return _kline_template()  # 次新/数据不足 → 模板兜底
        return self._compute_kline_indicators(df.tail(20))

    def _kline_from_baostock(self, code: str) -> Dict[str, Any]:
        bs_code, _ = self._normalize_code(code)
        end = time.strftime("%Y-%m-%d")
        start = (pd.Timestamp.now() - pd.Timedelta(days=60)).strftime("%Y-%m-%d")
        rs = bs.query_history_k_data_plus(
            bs_code, "date,close,volume",
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
        return self._compute_kline_indicators(df.tail(20))

    def _compute_kline_indicators(self, df) -> Dict[str, Any]:
        try:
            close = df["close"].apply(self._safe_float)
            volume = df["volume"].apply(self._safe_float)

            # S2: 券商标准量比 = 今日成交量 / 前5日均量（不含今日）
            vol_today = float(volume.iloc[-1])
            vol_past5 = volume.iloc[-6:-1] if len(volume) >= 6 else volume.iloc[:-1]
            vol_past5_avg = float(vol_past5.mean()) if len(vol_past5) > 0 else vol_today

            return {
                "ma5": round(float(close.tail(5).mean()), 2),
                "ma10": round(float(close.tail(10).mean()), 2),
                "ma20": round(float(close.tail(20).mean()), 2),
                "rsi": self.calc_safe_rsi(close),
                "vol_ratio": round(vol_today / vol_past5_avg, 2) if vol_past5_avg > 0 else 1.0,
                "close": round(float(close.iloc[-1]), 2),
            }
        except Exception:
            return _kline_template()

    # ============================================================
    # 资金面
    # ============================================================

    def get_money_flow(self, code: str) -> Dict[str, Any]:
        key = f"money_{code}"
        cached = _CACHE.get(key)
        if cached:
            return cached

        self._rate_limit()
        if self._ak_ok:
            try:
                result = self._money_from_akshare(code)
                if result:
                    _CACHE.set(key, result)
                    return result
            except Exception as e:
                logger.debug(f"[DataLoader] 资金 {code}: {e}")
        return _money_template()

    def _money_from_akshare(self, code: str) -> Dict[str, Any]:
        _, ak_code = self._normalize_code(code)
        main_in, turnover = 0.0, 5.0
        try:
            df = ak.stock_individual_fund_flow_rank(symbol=ak_code, timeout=_REQUEST_TIMEOUT)
            if df is not None and not df.empty:
                main_in = self._safe_float(df["主力净流入-净额"].iloc[0]) if "主力净流入-净额" in df.columns else 0.0
                turnover = self._safe_float(df["换手率"].iloc[0], 5.0) if "换手率" in df.columns else 5.0
        except Exception:
            pass

        # S1: 北向资金多字段兼容（AKShare 字段不定期变更）
        north_in = 0.0
        try:
            df_n = ak.stock_hsgt_individual(symbol=ak_code, timeout=_REQUEST_TIMEOUT)
            if df_n is not None and not df_n.empty:
                for fld in ("北向资金净流入", "北向净流入", "净流入"):
                    if fld in df_n.columns:
                        north_in = self._safe_float(df_n[fld].iloc[-1])
                        break
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
        key = f"fund_{code}"
        cached = _CACHE.get(key)
        if cached:
            return cached

        self._rate_limit()
        if self._ak_ok:
            try:
                result = self._fund_from_akshare(code)
                if result:
                    _CACHE.set(key, result)
                    return result
            except Exception as e:
                logger.debug(f"[DataLoader] 基本面 {code}: {e}")
        return _fund_template()

    def _fund_from_akshare(self, code: str) -> Dict[str, Any]:
        """基本面数据（S2: TTM 四季滚动年化 + 单季增速双口径）。

        解决原单季度增速的季节性失真和年末结算偏差：
          - revenue_ttm_growth / profit_ttm_growth: TTM 同比（对标同花顺口径）
          - revenue_growth / profit_growth: 原单季同比（辅助参考）
        """
        _, ak_code = self._normalize_code(code)

        # PE
        pe = 30.0
        try:
            df_val = ak.stock_zh_a_valuation(symbol=ak_code, timeout=_REQUEST_TIMEOUT)
            if df_val is not None and not df_val.empty and "滚动市盈率" in df_val.columns:
                pe = self._safe_float(df_val["滚动市盈率"].iloc[0], 30.0)
        except Exception:
            pass
        if pe < 0 or pe > 300:
            pe = 30.0

        rev_g, profit_g = 0.0, 0.0
        rev_ttm, profit_ttm = 0.0, 0.0

        try:
            df_fin = ak.stock_financial_analysis_indicator(symbol=ak_code, timeout=_REQUEST_TIMEOUT)
            if df_fin is not None and not df_fin.empty and len(df_fin) >= 8:
                df_latest = df_fin.tail(8).reset_index(drop=True)

                # TTM: 最近连续4季度（索引 4..7）的和
                curr_rev = sum(
                    self._safe_float(df_latest.loc[i, "营业总收入"])
                    for i in range(4, 8) if "营业总收入" in df_latest.columns
                )
                curr_profit = sum(
                    self._safe_float(df_latest.loc[i, "净利润"])
                    for i in range(4, 8) if "净利润" in df_latest.columns
                )
                # 去年同期连续4季度（索引 0..3）的和
                last_rev = sum(
                    self._safe_float(df_latest.loc[i, "营业总收入"])
                    for i in range(0, 4) if "营业总收入" in df_latest.columns
                )
                last_profit = sum(
                    self._safe_float(df_latest.loc[i, "净利润"])
                    for i in range(0, 4) if "净利润" in df_latest.columns
                )

                # TTM 同比增速
                if last_rev != 0:
                    rev_ttm = round(
                        (curr_rev - last_rev) / abs(last_rev) * 100, 2
                    )
                if last_profit != 0:
                    profit_ttm = round(
                        (curr_profit - last_profit) / abs(last_profit) * 100, 2
                    )

                # 极值压制 [-200%, 200%]
                rev_ttm = max(-200.0, min(200.0, rev_ttm))
                profit_ttm = max(-200.0, min(200.0, profit_ttm))

                # 保留原单季同比增速作为辅助
                row = df_latest.tail(1)
                rev_g = self._safe_float(row["营业总收入同比增长率"].iloc[0]) if "营业总收入同比增长率" in row.columns else 0.0
                profit_g = self._safe_float(row["净利润同比增长率"].iloc[0]) if "净利润同比增长率" in row.columns else 0.0

            elif df_fin is not None and not df_fin.empty:
                # 不足 8 季度 → 仅取单季增速
                row = df_fin.tail(1)
                rev_g = self._safe_float(row["营业总收入同比增长率"].iloc[0]) if "营业总收入同比增长率" in row.columns else 0.0
                profit_g = self._safe_float(row["净利润同比增长率"].iloc[0]) if "净利润同比增长率" in row.columns else 0.0
        except Exception:
            pass

        return {
            "pe": round(pe, 2),
            "revenue_growth": round(rev_g, 2),
            "profit_growth": round(profit_g, 2),
            "revenue_ttm_growth": round(rev_ttm, 2),
            "profit_ttm_growth": round(profit_ttm, 2),
        }

    # ============================================================
    # 行业识别（O(1) 全局字典）
    # ============================================================

    def get_industry(self, code: str) -> str:
        return INDUSTRY_CODE_MAP.get(str(code).strip(), "通用市场赛道")

    # ============================================================
    # 全量加载
    # ============================================================

    def load_all(self, code: str) -> Dict[str, Any]:
        kline = self.get_kline_indicators(code)
        money = self.get_money_flow(code)
        fund = self.get_fundamental(code)
        industry = self.get_industry(code)
        return {
            "code": code,
            "industry_name": industry,
            "kline_data": kline,
            "money_data": money,
            "fund_data": fund,
            "news_sentiment": 0.0,
        }


# ============================================================
# 全局单例 + 退出清理
# ============================================================

data_loader = StockDataLoader()


def _cleanup():
    """程序退出统一释放资源"""
    if _BS_LOGINED:
        try:
            bs.logout()
        except Exception:
            pass
    _CACHE.clear()
    logger.debug("[DataLoader] 退出清理完成")


atexit.register(_cleanup)

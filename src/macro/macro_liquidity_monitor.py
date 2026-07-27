# -*- coding: utf-8 -*-
"""
宏观流动性监控 — P0 核心优化版
新增：60日滚动动态标准化 + 全自动地缘风险量化爬虫 + 动态仓位比例

对标：macro-regime-monitor（滚动归一化）+ FinSynapse（地缘风险算法）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 60日滚动标准化器
# ============================================================

class RollingNormalizer:
    """滚动窗口动态标准化 → [-1, 1]"""

    def __init__(self, window: int = 60):
        self.window = window
        self.history: List[float] = []

    def update(self, value: float) -> float:
        self.history.append(value)
        if len(self.history) > self.window:
            self.history.pop(0)
        if len(self.history) < 20:
            return 0.0
        mn, mx = min(self.history), max(self.history)
        if mx == mn:
            return 0.0
        return round((value - mn) / (mx - mn) * 2 - 1, 3)

    def normalize_to_01(self, value: float) -> float:
        """滚动标准化到 [0, 1]"""
        raw = self.update(value)
        return round(max(min((raw + 1) / 2, 1.0), 0.0), 3)


# 全局标准化器
_norm_liq = RollingNormalizer(60)
_norm_pressure = RollingNormalizer(60)
_norm_fx = RollingNormalizer(60)


# ============================================================
# 地缘风险自动爬虫 + 三级量化打分
# ============================================================

class GeoRiskMonitor:
    """全自动地缘风险量化（对标 FinSynapse 全球风险体系）"""

    def __init__(self):
        self.risk_level1 = ["冲突", "战事", "制裁", "地缘危机", "极端政策",
                           "贸易封杀", "中美摩擦", "军事", "脱钩"]
        self.risk_level2 = ["政策调整", "央行表态", "经贸磋商", "行业新规",
                           "关税", "涉外变动", "出口管制"]
        self.risk_level3 = ["经济数据", "会议纪要", "调研", "日常新闻"]
        self._cache_score: float = 0.2
        self._cache_ts: float = 0.0
        self._ttl: int = 3 * 3600

    async def fetch_macro_news(self) -> List[str]:
        """爬取财联社宏观快讯（免费稳定源）"""
        news: List[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://www.cls.cn/v1/roll/1?rn=80")
                data = resp.json()
                for item in data.get("data", []):
                    title = item.get("title", "")
                    if title:
                        news.append(title)
        except Exception as e:
            logger.debug(f"Geo-risk news fetch: {e}")
        return news

    def calc_risk_from_news(self, news_list: List[str]) -> float:
        if not news_list:
            return 0.2
        total = len(news_list)
        l1 = sum(1 for t in news_list if any(k in t for k in self.risk_level1))
        l2 = sum(1 for t in news_list if any(k in t for k in self.risk_level2))
        l3 = total - l1 - l2
        score = (l1 * 1.0 + l2 * 0.4 + l3 * 0.05) / total
        return round(min(score * 1.2, 1.0), 3)

    async def get_score(self) -> float:
        now = datetime.now(timezone.utc).timestamp()
        if self._cache_ts and (now - self._cache_ts) < self._ttl:
            return self._cache_score
        news = await self.fetch_macro_news()
        score = self.calc_risk_from_news(news)
        self._cache_score = score
        self._cache_ts = now
        logger.info(f"Geo-risk updated: {score:.3f} (from {len(news)} news items)")
        return score

    def get_score_sync(self) -> float:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return 0.2
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self.get_score()).result(timeout=10)
        return asyncio.run(self.get_score())


_geo_monitor = GeoRiskMonitor()


# ============================================================
# 数据结构
# ============================================================

@dataclass
class MacroFactorResult:
    net_liquidity: float = 0.0
    fund_pressure: float = 0.0
    exchange_risk: float = 0.0
    geo_risk: float = 0.0
    market_regime: str = "neutral"
    market_trend: str = "oscillate"
    risk_level: str = "mid"
    position_ratio: float = 0.4
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


# ============================================================
# 宏观监控主类
# ============================================================

class MacroLiquidityMonitor:

    def __init__(self):
        self.liq_threshold = 0.2
        self.pressure_high = 0.7
        self._cache: Optional[MacroFactorResult] = None
        self._cache_ts: float = 0.0
        self._cache_ttl: int = 3600

    def get_macro_basic_data(self) -> Dict[str, float]:
        data: Dict[str, float] = {}
        try:
            import akshare as ak
            m2_df = ak.macro_china_money_supply()
            if m2_df is not None and not m2_df.empty:
                m2_col = next((c for c in m2_df.columns if "同比" in str(c)), m2_df.columns[1])
                data["m2_growth"] = float(m2_df.iloc[-1][m2_col])
            else:
                data["m2_growth"] = 8.0
        except Exception:
            data["m2_growth"] = 8.0
        try:
            import akshare as ak
            dr_df = ak.bond_china_yield(start_date="20240101")
            data["dr007"] = float(dr_df.iloc[-1, 1]) if dr_df is not None and not dr_df.empty else 2.0
        except Exception:
            data["dr007"] = 2.0
        try:
            import akshare as ak
            fx_df = ak.currency_boc_sina()
            if fx_df is not None and not fx_df.empty:
                usd_row = fx_df[fx_df.iloc[:, 0].astype(str).str.contains("美元")]
                data["usd_cny"] = float(usd_row.iloc[0, 1]) / 100 if not usd_row.empty else 7.2
            else:
                data["usd_cny"] = 7.2
        except Exception:
            data["usd_cny"] = 7.2
        return data

    def calc_net_liquidity(self, data: Dict[str, float]) -> float:
        m2, dr = data.get("m2_growth", 8.0), data.get("dr007", 2.0)
        raw = (m2 - 8) / 4 - (dr - 2) / 1.5
        return _norm_liq.update(raw)

    def calc_fund_pressure(self, data: Dict[str, float]) -> float:
        dr, m2 = data.get("dr007", 2.0), data.get("m2_growth", 8.0)
        raw = max(0, (dr - 1.5) / 2) * 0.5 + max(0, (9 - m2) / 5) * 0.5
        return _norm_pressure.normalize_to_01(raw)

    def calc_exchange_risk(self, data: Dict[str, float]) -> float:
        fx = data.get("usd_cny", 7.0)
        raw = abs(fx - 7.0) / 0.4
        return _norm_fx.normalize_to_01(raw)

    def calc_geo_risk(self) -> float:
        return _geo_monitor.get_score_sync()

    async def calc_geo_risk_async(self) -> float:
        return await _geo_monitor.get_score()

    def judge_market_regime(self, liq: float, pressure: float,
                           fx_risk: float) -> tuple:
        if liq > self.liq_threshold and pressure < 0.5 and fx_risk < 0.5:
            return "loose", "bull", "low"
        if liq < -self.liq_threshold or pressure > self.pressure_high or fx_risk > 0.7:
            return "tight", "bear", "high"
        return "neutral", "oscillate", "mid"

    def get_position_ratio(self, regime: str) -> float:
        return {"loose": 0.8, "neutral": 0.4, "tight": 0.0}.get(regime, 0.3)

    async def get_macro_overall_async(self) -> MacroFactorResult:
        basic = self.get_macro_basic_data()
        liq = self.calc_net_liquidity(basic)
        pressure = self.calc_fund_pressure(basic)
        fx_risk = self.calc_exchange_risk(basic)
        geo_risk = await self.calc_geo_risk_async()

        regime, trend, risk_level = self.judge_market_regime(liq, pressure, fx_risk)
        pos = self.get_position_ratio(regime)

        parts = []
        if trend == "bull": parts.append("流动性宽松，大盘上行确定性高")
        elif trend == "bear": parts.append("流动性收紧/资金压力大，系统性风险高")
        else: parts.append("宏观中性，题材驱动为主")
        if fx_risk > 0.7: parts.append("人民币汇率承压")
        if geo_risk > 0.7: parts.append("地缘风险升温，风险偏好下降")

        result = MacroFactorResult(
            net_liquidity=liq, fund_pressure=pressure,
            exchange_risk=fx_risk, geo_risk=geo_risk,
            market_regime=regime, market_trend=trend,
            risk_level=risk_level, position_ratio=pos,
            reason="；".join(parts),
        )
        self._cache = result
        self._cache_ts = datetime.now(timezone.utc).timestamp()
        return result

    def get_macro_overall(self) -> MacroFactorResult:
        if self._cache and (datetime.now(timezone.utc).timestamp() - self._cache_ts) < self._cache_ttl:
            return self._cache
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.get_macro_overall_async()).result(timeout=30)
        except RuntimeError:
            pass
        return asyncio.run(self.get_macro_overall_async())

    def format_for_agent(self, result: MacroFactorResult) -> str:
        emoji = {"loose": "🟢", "neutral": "🟡", "tight": "🔴"}
        trend_e = {"bull": "🐂", "oscillate": "↔️", "bear": "🐻"}
        return (
            f"## {trend_e.get(result.market_trend, '')} 宏观大势研判\n"
            f"- 周期：{emoji.get(result.market_regime, '')} {result.market_regime}"
            f" | 趋势：{result.market_trend} | 风险：{result.risk_level}\n"
            f"- 净流动性：{result.net_liquidity:+.2f} | 资金压力：{result.fund_pressure:.2f}\n"
            f"- 汇率风险：{result.exchange_risk:.2f} | 地缘风险：{result.geo_risk:.2f}\n"
            f"- 建议仓位：{result.position_ratio:.0%} | 归因：{result.reason}"
        )


macro_monitor = MacroLiquidityMonitor()

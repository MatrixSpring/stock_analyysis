# -*- coding: utf-8 -*-
"""
四维量化打分系统（对标 Finviz）

技术面 30% + 资金面 30% + 基本面 20% + 舆情 20%
输出 0-100 总分、涨跌概率、风险等级、操作建议

与 src/services/stock_scorer.py（基本面三因子）互补，不替代。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QuantScoreResult:
    """量化打分完整结果"""
    total_score: float = 50.0
    tech_score: float = 50.0
    money_score: float = 50.0
    fund_score: float = 50.0
    news_score: float = 50.0
    up_prob: float = 50.0
    down_prob: float = 50.0
    risk_level: str = "中风险"
    suggest: str = "观望为主"
    score_details: Dict[str, Any] = field(default_factory=dict)


class QuantScoreEngine:
    """四维量化综合打分引擎。

    使用方式：
        engine = QuantScoreEngine()
        result = engine.score(kline=data, money=data, fund=data, news_sentiment=0.2)
        print(f"总分: {result.total_score}, 涨概率: {result.up_prob}%")
    """

    def __init__(
        self,
        w_tech: float = 0.30,
        w_money: float = 0.30,
        w_fund: float = 0.20,
        w_news: float = 0.20,
    ):
        self.w_tech = w_tech
        self.w_money = w_money
        self.w_fund = w_fund
        self.w_news = w_news

    # ============================================================
    # 技术面 (30%)
    # ============================================================

    def calc_tech_score(self, kline: Dict[str, Any]) -> float:
        """
        技术面打分：均线排列 + RSI + MACD + 量能 + KDJ

        Args:
            kline: {"ma5", "ma10", "ma20", "rsi", "vol_ratio", "macd", "k", "d"}
        """
        score = 50.0
        details = {}

        try:
            # 1. 均线多头/空头排列 (±15)
            ma5 = float(kline.get("ma5") or 0)
            ma10 = float(kline.get("ma10") or 0)
            ma20 = float(kline.get("ma20") or 0)
            if ma5 > 0 and ma10 > 0 and ma20 > 0:
                if ma5 > ma10 > ma20:
                    score += 15
                    details["ma_trend"] = "多头排列 +15"
                elif ma5 < ma10 < ma20:
                    score -= 15
                    details["ma_trend"] = "空头排列 -15"
                elif ma5 > ma10:
                    score += 5
                    details["ma_trend"] = "短线偏多 +5"
                else:
                    details["ma_trend"] = "均线缠绕 0"
            else:
                details["ma_trend"] = "数据不足"

            # 2. RSI 超买/超卖 (±10)
            rsi = float(kline.get("rsi") or kline.get("rsi_14d") or 50)
            if rsi < 25:
                score += 12
                details["rsi"] = f"严重超卖({rsi:.0f}) +12"
            elif rsi < 35:
                score += 8
                details["rsi"] = f"超卖区({rsi:.0f}) +8"
            elif rsi > 80:
                score -= 12
                details["rsi"] = f"严重超买({rsi:.0f}) -12"
            elif rsi > 70:
                score -= 7
                details["rsi"] = f"超买区({rsi:.0f}) -7"
            else:
                details["rsi"] = f"中性({rsi:.0f}) 0"

            # 3. MACD 信号 (±8)
            macd = float(kline.get("macd") or 0)
            if macd > 0:
                score += 4
                details["macd"] = f"MACD>0 +4"
            elif macd < 0:
                score -= 3
                details["macd"] = f"MACD<0 -3"

            # 4. 量能 (±8)
            vol_ratio = float(kline.get("vol_ratio") or 1.0)
            if vol_ratio > 1.8:
                score += 8
                details["volume"] = f"显著放量({vol_ratio:.1f}x) +8"
            elif vol_ratio > 1.3:
                score += 4
                details["volume"] = f"温和放量({vol_ratio:.1f}x) +4"
            elif vol_ratio < 0.6:
                score -= 5
                details["volume"] = f"极致缩量({vol_ratio:.1f}x) -5"
            else:
                details["volume"] = f"正常({vol_ratio:.1f}x) 0"

        except Exception as e:
            logger.debug(f"技术面打分异常: {e}")
            details["error"] = str(e)[:100]

        final = float(max(0, min(100, score)))
        details["score"] = final
        return final

    # ============================================================
    # 资金面 (30%)
    # ============================================================

    def calc_money_score(self, money: Dict[str, Any]) -> float:
        """
        资金面打分：主力净流入 + 北向/南向 + 换手率 + 融资融券

        Args:
            money: {"main_net_in", "north_net_in", "turnover", "margin_ratio"}
        """
        score = 50.0
        details = {}

        try:
            # 1. 主力净流入方向 (±15)
            main_net = float(money.get("main_net_in") or 0)
            if main_net > 10000:
                score += 15
                details["main"] = f"主力大幅流入({main_net:.0f}万) +15"
            elif main_net > 0:
                score += 10
                details["main"] = "主力小幅流入 +10"
            elif main_net < -10000:
                score -= 15
                details["main"] = f"主力大幅流出({main_net:.0f}万) -15"
            elif main_net < 0:
                score -= 8
                details["main"] = "主力小幅流出 -8"
            else:
                details["main"] = "主力净流入为0"

            # 2. 北向资金 (±8)
            north_net = float(money.get("north_net_in") or 0)
            if north_net > 0:
                score += 8
                details["north"] = f"北向净流入 +8"
            elif north_net < 0:
                score -= 5
                details["north"] = f"北向净流出 -5"

            # 3. 换手率活跃度 (±8)
            turnover = float(money.get("turnover") or money.get("turnover_rate") or 5)
            if 3 < turnover < 15:
                score += 8
                details["turnover"] = f"活跃度适中({turnover:.1f}%) +8"
            elif turnover < 1:
                score -= 5
                details["turnover"] = f"换手过低({turnover:.1f}%) -5"
            elif turnover > 20:
                score -= 5
                details["turnover"] = f"换手过高({turnover:.1f}%) -5"
            elif turnover > 25:
                score -= 3
                details["turnover"] = f"妖股嫌疑({turnover:.1f}%) -3"
            else:
                details["turnover"] = f"换手率({turnover:.1f}%) 0"

        except Exception as e:
            logger.debug(f"资金面打分异常: {e}")
            details["error"] = str(e)[:100]

        final = float(max(0, min(100, score)))
        details["score"] = final
        return final

    # ============================================================
    # 基本面 (20%)
    # ============================================================

    def calc_fund_score(self, fund: Dict[str, Any]) -> float:
        """
        基本面打分：PE 估值 + 营收增速 + 利润增速 + ROE

        Args:
            fund: {"pe", "revenue_growth", "profit_growth", "roe", "pb"}
        """
        score = 50.0
        details = {}

        try:
            # 1. PE 估值 (±10)
            pe = float(fund.get("pe") or 30)
            if 10 < pe < 25:
                score += 10
                details["pe"] = f"估值合理(PE={pe:.0f}) +10"
            elif pe > 80 or pe < 0:
                score -= 10
                details["pe"] = f"估值异常(PE={pe:.0f}) -10"
            elif pe > 60:
                score -= 5
                details["pe"] = f"估值偏高(PE={pe:.0f}) -5"
            elif pe < 15:
                score += 6
                details["pe"] = f"低估值(PE={pe:.0f}) +6"
            else:
                details["pe"] = f"PE={pe:.0f} 0"

            # 2. 营收增速 (±10) — 优先 TTM 滚动年化，降级单季同比
            rev_growth = float(
                fund.get("revenue_ttm_growth")
                or fund.get("revenue_growth")
                or 0
            )
            if rev_growth > 30:
                score += 10
                details["revenue"] = f"高增长({rev_growth:.0f}%) +10"
            elif rev_growth > 10:
                score += 7
                details["revenue"] = f"稳健增长({rev_growth:.0f}%) +7"
            elif rev_growth < -10:
                score -= 8
                details["revenue"] = f"营收下滑({rev_growth:.0f}%) -8"
            elif rev_growth < 0:
                score -= 4
                details["revenue"] = f"微降({rev_growth:.0f}%) -4"
            else:
                details["revenue"] = f"持平({rev_growth:.0f}%) 0"

            # 3. 利润增速 (±10) — 优先 TTM 滚动年化，降级单季同比
            profit_g = float(
                fund.get("profit_ttm_growth")
                or fund.get("profit_growth")
                or 0
            )
            if profit_g > 30:
                score += 10
                details["profit"] = f"利润高增({profit_g:.0f}%) +10"
            elif profit_g > 10:
                score += 7
                details["profit"] = f"利润增长({profit_g:.0f}%) +7"
            elif profit_g < -10:
                score -= 8
                details["profit"] = f"利润下滑({profit_g:.0f}%) -8"
            else:
                details["profit"] = f"利润({profit_g:.0f}%) 0"

        except Exception as e:
            logger.debug(f"基本面打分异常: {e}")
            details["error"] = str(e)[:100]

        final = float(max(0, min(100, score)))
        details["score"] = final
        return final

    # ============================================================
    # 舆情 (20%)
    # ============================================================

    def calc_news_score(self, sentiment: float) -> float:
        """
        舆情情绪打分：-1.0(极度利空) ~ +1.0(极度利好)

        Args:
            sentiment: 情绪值，-1 到 1
        """
        score = 50.0 + sentiment * 30.0
        return float(max(0, min(100, score)))

    # ============================================================
    # 风险等级 & 概率预测
    # ============================================================

    @staticmethod
    def get_risk_level(total_score: float) -> tuple:
        """分数 → (风险等级, 操作建议)"""
        if total_score >= 80:
            return ("低风险", "偏多持仓，趋势向好，可积极介入")
        elif total_score >= 65:
            return ("中低风险", "谨慎看多，逢回调低吸，控制仓位")
        elif total_score >= 45:
            return ("中风险", "震荡格局，观望为主，减少操作频率")
        elif total_score >= 30:
            return ("中高风险", "偏空趋势，减仓避险，严控回撤")
        else:
            return ("高风险", "规避为主，不宜参与，耐心等待转势")

    @staticmethod
    def predict_prob(score: float) -> tuple:
        """根据总分映射涨跌概率"""
        up = min(95, max(5, score))
        down = round(100 - up, 1)
        return round(up, 1), down

    # ============================================================
    # 综合打分
    # ============================================================

    def score(
        self,
        kline: Dict[str, Any],
        money: Optional[Dict[str, Any]] = None,
        fund: Optional[Dict[str, Any]] = None,
        news_sentiment: float = 0.0,
    ) -> QuantScoreResult:
        """综合四维量化打分。

        Args:
            kline: K 线指标数据
            money: 资金面数据（可选）
            fund: 基本面数据（可选）
            news_sentiment: 舆情情绪值 -1~1

        Returns:
            QuantScoreResult
        """
        money = money or {}
        fund = fund or {}

        tech = self.calc_tech_score(kline)
        money_s = self.calc_money_score(money)
        fund_s = self.calc_fund_score(fund)
        news_s = self.calc_news_score(news_sentiment)

        total = (
            tech * self.w_tech
            + money_s * self.w_money
            + fund_s * self.w_fund
            + news_s * self.w_news
        )
        total = round(total, 2)

        up_p, down_p = self.predict_prob(total)
        risk, suggest = self.get_risk_level(total)

        return QuantScoreResult(
            total_score=total,
            tech_score=round(tech, 1),
            money_score=round(money_s, 1),
            fund_score=round(fund_s, 1),
            news_score=round(news_s, 1),
            up_prob=up_p,
            down_prob=down_p,
            risk_level=risk,
            suggest=suggest,
            score_details={
                "weights": {
                    "tech": self.w_tech,
                    "money": self.w_money,
                    "fund": self.w_fund,
                    "news": self.w_news,
                },
            },
        )


# ============================================================
# 全局实例
# ============================================================

quant_engine = QuantScoreEngine()

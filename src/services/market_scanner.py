# -*- coding: utf-8 -*-
"""
全市场智能量化选股扫描器（对标 TradingView / Finviz）

支持 9 大选股策略：
  突破、超跌、金叉、死叉、放量、缩量、筹码集中、均线多头、MACD 底背离

输出三类标的池：强势池、观望池、风险池
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ScanItem:
    """单只股票扫描结果"""
    code: str
    name: str
    market: str = "A股"
    total_score: float = 50.0
    up_prob: float = 50.0
    risk_level: str = "中风险"
    matched_tags: List[str] = field(default_factory=list)
    suggest: str = "观望"


class MarketScanner:
    """全市场智能扫描选股器。

    使用方式：
        scanner = MarketScanner()
        tags = scanner.scan(code="600519", name="贵州茅台", data={...})
        pools = scanner.scan_batch(stock_list)
    """

    def __init__(self):
        # 注册 9 大选股策略
        self._strategies: Dict[str, Tuple[str, Callable]] = {
            "breakout":       ("突破形态·放量突破阻力", self._check_breakout),
            "oversold":       ("超跌反弹·RSI 超卖", self._check_oversold),
            "golden_cross":   ("金叉信号·均线多头", self._check_golden_cross),
            "death_cross":    ("死叉预警·均线空头", self._check_death_cross),
            "volume_spike":   ("持续放量·资金涌入", self._check_volume_spike),
            "volume_shrink":  ("极致缩量·变盘点", self._check_volume_shrink),
            "chip_conc":      ("筹码集中·主力控盘", self._check_chip_concentration),
            "ma_bull":        ("均线多头·趋势向上", self._check_ma_bullish),
            "macd_divergence": ("MACD底背离·反转信号", self._check_macd_divergence),
        }

    # ============================================================
    # 选股策略
    # ============================================================

    @staticmethod
    def _check_breakout(data: Dict) -> bool:
        """放量突破 20 日均线"""
        close = data.get("close", 0) or data.get("price", 0)
        ma20 = data.get("ma20", 0)
        vol_ratio = data.get("vol_ratio", 1.0)
        return bool(close > 0 and ma20 > 0 and close > ma20 and vol_ratio > 1.3)

    @staticmethod
    def _check_oversold(data: Dict) -> bool:
        """RSI < 32 超跌（结合均线支撑更佳）"""
        rsi = data.get("rsi") or data.get("rsi_14d") or 50
        return bool(float(rsi) < 32)

    @staticmethod
    def _check_golden_cross(data: Dict) -> bool:
        """MA5 金叉 MA10"""
        ma5 = data.get("ma5", 0)
        ma10 = data.get("ma10", 0)
        ma20 = data.get("ma20", 0)
        # 只检测多头：MA5 > MA10 > MA20
        return bool(ma5 > 0 and ma10 > 0 and ma5 > ma10 > ma20)

    @staticmethod
    def _check_death_cross(data: Dict) -> bool:
        """MA5 死叉 MA10（预警）"""
        ma5 = data.get("ma5", 0)
        ma10 = data.get("ma10", 0)
        return bool(ma5 > 0 and ma10 > 0 and ma5 < ma10)

    @staticmethod
    def _check_volume_spike(data: Dict) -> bool:
        """量比 > 1.8 持续放量"""
        vol_ratio = data.get("vol_ratio", 1.0)
        return bool(float(vol_ratio) > 1.8)

    @staticmethod
    def _check_volume_shrink(data: Dict) -> bool:
        """量比 < 0.5 极致缩量（变盘前兆）"""
        vol_ratio = data.get("vol_ratio", 1.0)
        return bool(0 < float(vol_ratio) < 0.5)

    @staticmethod
    def _check_chip_concentration(data: Dict) -> bool:
        """筹码集中（通过获利比例等间接判断）"""
        profit_ratio = data.get("profit_ratio") or data.get("chip_profit_pct") or 50
        return bool(30 < float(profit_ratio) < 70)

    @staticmethod
    def _check_ma_bullish(data: Dict) -> bool:
        """MA5 > MA10 > MA20 且价格在 MA5 上方"""
        close = data.get("close", 0) or data.get("price", 0)
        ma5 = data.get("ma5", 0)
        ma10 = data.get("ma10", 0)
        ma20 = data.get("ma20", 0)
        return bool(
            close > 0 and ma5 > 0
            and close > ma5 > ma10 > ma20
        )

    @staticmethod
    def _check_macd_divergence(data: Dict) -> bool:
        """MACD 底背离（简化：MACD > 0 且之前为负）"""
        macd = data.get("macd", 0)
        macd_prev = data.get("macd_prev", macd)
        return bool(macd > 0 > float(macd_prev))

    # ============================================================
    # 扫描
    # ============================================================

    def scan(
        self,
        code: str,
        name: str = "",
        market: str = "A股",
        data: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """扫描单只股票匹配的形态标签。

        Args:
            code: 股票代码
            name: 股票名
            market: 市场类型
            data: K 线指标字典

        Returns:
            匹配的标签名列表
        """
        if not data:
            return []
        tags = []
        for tag, (desc, func) in self._strategies.items():
            try:
                if func(data):
                    tags.append(tag)
            except Exception as e:
                logger.debug(f"[Scanner] {code} {tag} 检查异常: {e}")
        return tags

    def scan_with_descriptions(
        self, code: str, name: str = "", market: str = "A股",
        data: Optional[Dict] = None,
    ) -> List[Dict[str, str]]:
        """扫描并附带中文描述"""
        if not data:
            return []
        result = []
        for tag, (desc, func) in self._strategies.items():
            try:
                if func(data):
                    result.append({"tag": tag, "desc": desc})
            except Exception:
                pass
        return result

    # ============================================================
    # 标的池分类
    # ============================================================

    @staticmethod
    def classify_pool(score: float) -> str:
        """根据量化总分分入标的池"""
        if score >= 70:
            return "强势标的池"
        elif score >= 45:
            return "观望震荡池"
        else:
            return "风险规避池"

    # ============================================================
    # 批量扫描
    # ============================================================

    def scan_batch(
        self,
        stock_list: List[Dict[str, Any]],
        score_engine=None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """全市场批量扫描，输出三类标的池。

        Args:
            stock_list: [{code, name, market, kline_data, money_data, fund_data, news_sentiment}]
            score_engine: QuantScoreEngine 实例（可选，用于打分分类）

        Returns:
            {
                "强势标的池": [{code, name, total_score, up_prob, risk_level, tags, suggest}],
                "观望震荡池": [...],
                "风险规避池": [...],
            }
        """
        pools: Dict[str, List[Dict]] = {
            "强势标的池": [],
            "观望震荡池": [],
            "风险规避池": [],
        }

        for s in stock_list:
            code = s.get("code", "unknown")
            name = s.get("name", code)
            market = s.get("market", "A股")
            data = s.get("kline_data") or s.get("data") or {}

            # 扫描形态标签
            tags = self.scan(code, name, market, data)

            # 量化打分（如果有打分引擎）
            total_score = 50.0
            up_prob = 50.0
            risk_level = "中风险"
            suggest = "观望"

            if score_engine:
                try:
                    res = score_engine.score(
                        kline=data,
                        money=s.get("money_data") or s.get("money", {}),
                        fund=s.get("fund_data") or s.get("fund", {}),
                        news_sentiment=s.get("news_sentiment", 0.0),
                    )
                    total_score = res.total_score
                    up_prob = res.up_prob
                    risk_level = res.risk_level
                    suggest = res.suggest
                except Exception as e:
                    logger.warning(f"[Scanner] {code} 打分失败: {e}")

            item = {
                "code": code,
                "name": name,
                "market": market,
                "total_score": total_score,
                "up_prob": up_prob,
                "risk_level": risk_level,
                "tags": tags,
                "suggest": suggest,
            }

            pool_name = self.classify_pool(total_score)
            pools[pool_name].append(item)

        # 按得分排序（每个池内）
        for pool_name in pools:
            pools[pool_name].sort(key=lambda x: x["total_score"], reverse=True)

        counts = {k: len(v) for k, v in pools.items()}
        logger.info(
            f"[Scanner] 全市场扫描完成: "
            f"强势={counts.get('强势标的池', 0)}, "
            f"观望={counts.get('观望震荡池', 0)}, "
            f"风险={counts.get('风险规避池', 0)}"
        )
        return pools

    # ============================================================
    # 策略信息
    # ============================================================

    def list_strategies(self) -> List[Dict[str, str]]:
        """列出所有选股策略"""
        return [
            {"tag": tag, "desc": desc}
            for tag, (desc, _) in self._strategies.items()
        ]


# ============================================================
# 全局实例
# ============================================================

market_scanner = MarketScanner()

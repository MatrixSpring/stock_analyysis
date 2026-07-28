# -*- coding: utf-8 -*-
"""
===================================
全市场自动选股器 — core/stock_selector.py
===================================

基于四维量化打分 + 行业过滤 + Top-N 输出。

使用方式：
    from core.stock_selector import StockSelector
    sel = StockSelector()
    picks = sel.screen(stocks_data, top_n=20)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from core.quant_score import QuantScorer, ScoreResult

logger = logging.getLogger(__name__)


@dataclass
class ScreenResult:
    """选股结果"""
    code: str = ""
    name: str = ""
    sector: str = ""
    total_score: float = 0.0
    trend_score: float = 0.0
    capital_score: float = 0.0
    value_score: float = 0.0
    sentiment_score: float = 0.0
    rank: int = 0
    tags: List[str] = field(default_factory=list)


class StockSelector:
    """
    全市场自动选股器。

    流程：
    1. 四维量化逐只打分
    2. 行业/市值/流动性过滤
    3. Top-N 排序输出
    4. 可选行业分散约束
    """

    def __init__(self, scorer: Optional[QuantScorer] = None):
        self.scorer = scorer or QuantScorer()

    # ---- 主入口 ----

    def screen(
        self,
        stocks_data: Dict[str, pd.DataFrame],
        top_n: int = 20,
        min_score: float = 0.3,
        sector_limit: int = 5,          # 单行业最多入选数
        min_volume_ratio: float = 0.0,   # 最低流动性过滤
        exclude_sectors: Optional[List[str]] = None,
        name_map: Optional[Dict[str, str]] = None,
        sector_map: Optional[Dict[str, str]] = None,
    ) -> List[ScreenResult]:
        """
        全市场选股。

        Args:
            stocks_data: {code: kline_df} 映射
            top_n: 最终入选数量
            min_score: 最低综合得分阈值
            sector_limit: 单行业最多入选数
            min_volume_ratio: 最低流动性（0=不过滤）
            exclude_sectors: 排除行业列表
            name_map: {code: name} 映射
            sector_map: {code: sector} 映射

        Returns:
            按 total_score 降序的选股列表
        """
        exclude = set(exclude_sectors or [])
        name_map = name_map or {}
        sector_map = sector_map or {}

        # 1. 批量打分
        scored = self.scorer.batch_score(stocks_data)

        # 2. 过滤
        candidates = []
        for s in scored:
            code = s.code
            sector = sector_map.get(code, "其他")

            # 得分门槛
            if s.total_score < min_score:
                continue

            # 行业排除
            if sector in exclude:
                continue

            # 流动性过滤
            if min_volume_ratio > 0:
                vol_ratio = s.details.get("volume_ratio", 1.0)
                if vol_ratio < min_volume_ratio:
                    continue

            candidates.append(ScreenResult(
                code=code,
                name=name_map.get(code, code),
                sector=sector,
                total_score=s.total_score,
                trend_score=s.trend_score,
                capital_score=s.capital_score,
                value_score=s.value_score,
                sentiment_score=s.sentiment_score,
                tags=s.risk_tags,
            ))

        # 3. 按得分排序
        candidates.sort(key=lambda x: x.total_score, reverse=True)

        # 4. 行业分散约束：单行业最多 sector_limit 只
        selected = []
        sector_count: Dict[str, int] = {}
        for c in candidates:
            sector = c.sector
            allowed = sector_count.get(sector, 0) < sector_limit
            if allowed:
                selected.append(c)
                sector_count[sector] = sector_count.get(sector, 0) + 1
            if len(selected) >= top_n:
                break

        # 5. 标排名
        for i, s in enumerate(selected):
            s.rank = i + 1

        logger.info(
            f"[StockSelector] 选股完成: 候选{candidates.__len__()}→入选{len(selected)}"
        )

        return selected

    # ---- 行业景气度筛选 ----

    @staticmethod
    def sector_ranking(
        stocks_data: Dict[str, pd.DataFrame],
        sector_map: Dict[str, str],
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        行业景气度排行。

        按行业内所有标的平均综合得分排序。
        """
        scorer = QuantScorer()
        sector_scores: Dict[str, List[float]] = {}

        for code, df in stocks_data.items():
            sector = sector_map.get(code, "其他")
            result = scorer.score(df, code=code)
            if sector not in sector_scores:
                sector_scores[sector] = []
            sector_scores[sector].append(result.total_score)

        ranking = []
        for sector, scores in sector_scores.items():
            ranking.append({
                "sector": sector,
                "avg_score": round(sum(scores) / len(scores), 4),
                "stock_count": len(scores),
                "top_stock_score": round(max(scores), 4),
            })

        ranking.sort(key=lambda x: x["avg_score"], reverse=True)
        return ranking[:top_n]

    # ---- 策略快照导出 ----

    def export_snapshot(self, results: List[ScreenResult]) -> Dict[str, Any]:
        """导出选股快照为可持久化 dict"""
        return {
            "created_at": pd.Timestamp.now().isoformat(),
            "total_picks": len(results),
            "picks": [
                {
                    "rank": r.rank,
                    "code": r.code,
                    "name": r.name,
                    "sector": r.sector,
                    "total_score": r.total_score,
                    "scores": {
                        "trend": r.trend_score,
                        "capital": r.capital_score,
                        "value": r.value_score,
                        "sentiment": r.sentiment_score,
                    },
                    "tags": r.tags,
                }
                for r in results
            ],
        }


# 全局单例
_stock_selector: Optional[StockSelector] = None


def get_selector() -> StockSelector:
    global _stock_selector
    if _stock_selector is None:
        _stock_selector = StockSelector()
    return _stock_selector

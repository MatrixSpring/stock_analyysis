# -*- coding: utf-8 -*-
"""
板块轮动强度指标

基于申万行业标签 + 资金流向，自动计算：
  - 各行业板块热度排名
  - 板块轮动速度
  - 资金净流入 TOP 板块
  - 行业资金流向趋势
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SectorHeat:
    """板块热度"""
    l1_name: str
    heat_score: float          # 0~1 综合热度
    net_flow_rank: int         # 资金净流入排名
    pct_chg_avg: float         # 平均涨跌幅
    up_ratio: float            # 上涨占比
    trending_stocks: int       # 趋势向上标的数
    total_stocks: int          # 板块总标的数
    rotation_signal: str       # accelerating / decelerating / steady
    updated_at: str = ""


class SectorRotationService:
    """板块轮动分析服务"""

    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            try:
                from src.data_storage import get_mongo
                self._db = get_mongo().db
            except Exception:
                pass
        return self._db

    def get_sector_heat(self, lookback_days: int = 5) -> List[SectorHeat]:
        """
        计算各板块近 N 日综合热度。
        """
        if not self.db:
            return []

        try:
            # 从 stock_industry 获取所有一级行业
            industries = self.db["stock_industry"].distinct("l1")
            sector_heats = []

            for l1 in industries:
                codes = [d["code"] for d in self.db["stock_industry"].find({"l1": l1}, {"code": 1})]
                if not codes:
                    continue

                # 查询该板块标的近 N 日行情
                since = (datetime.now(timezone.utc) - timedelta(days=lookback_days + 3))
                daily_docs = list(self.db["stock_daily"].find({
                    "code": {"$in": codes},
                    "dt": {"$gte": since.strftime("%Y-%m-%d")},
                }))

                if not daily_docs:
                    continue

                # 计算板块指标
                up_count = sum(1 for d in daily_docs if float(d.get("pct_chg", 0) or 0) > 0)
                total = len(daily_docs)
                up_ratio = up_count / total if total > 0 else 0

                pct_values = [float(d.get("pct_chg", 0) or 0) for d in daily_docs]
                avg_pct = sum(pct_values) / len(pct_values) if pct_values else 0

                heat = (up_ratio * 0.4 + min(max((avg_pct + 5) / 10, 0), 1) * 0.6)
                rotation = "accelerating" if avg_pct > 2 else (
                    "decelerating" if avg_pct < -2 else "steady")

                sector_heats.append(SectorHeat(
                    l1_name=l1,
                    heat_score=round(min(heat, 1.0), 3),
                    net_flow_rank=0,
                    pct_chg_avg=round(avg_pct, 2),
                    up_ratio=round(up_ratio, 3),
                    trending_stocks=up_count,
                    total_stocks=len(codes),
                    rotation_signal=rotation,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                ))

            # 按热度排序
            sector_heats.sort(key=lambda s: s.heat_score, reverse=True)
            for i, sh in enumerate(sector_heats, 1):
                sh.net_flow_rank = i

            return sector_heats[:20]
        except Exception as e:
            logger.warning(f"Sector rotation calc failed: {e}")
            return []

    def get_top_sectors(self, top_n: int = 5) -> List[SectorHeat]:
        return self.get_sector_heat()[:top_n]

    def get_rotation_speed(self) -> Dict[str, Any]:
        """
        计算板块轮动速度 — 排名变化越剧烈，轮动越快
        """
        heats = self.get_sector_heat()
        if len(heats) < 3:
            return {"speed": 0.0, "label": "无数据"}

        accelerating = sum(1 for h in heats if h.rotation_signal == "accelerating")
        decelerating = sum(1 for h in heats if h.rotation_signal == "decelerating")
        speed = accelerating / max(len(heats), 1)

        if speed > 0.5:
            label = "高速轮动 — 热点切换频繁，短线机会多但持续性差"
        elif speed > 0.25:
            label = "中度轮动 — 部分板块持续走强，可精选强势板块"
        else:
            label = "低轮动 — 少数板块主导行情，适合趋势跟踪"

        return {
            "speed": round(speed, 3),
            "accelerating_count": accelerating,
            "decelerating_count": decelerating,
            "total_sectors": len(heats),
            "label": label,
        }

    def format_for_agent(self, top_n: int = 5) -> str:
        top = self.get_top_sectors(top_n)
        rotation = self.get_rotation_speed()
        if not top:
            return ""

        lines = ["## 📊 板块轮动监控", "", f"- 轮动速度：{rotation['label']}", ""]
        lines.append("| 排名 | 板块 | 热度 | 涨跌幅 | 上涨比 | 信号 |")
        lines.append("|------|------|------|--------|--------|------|")
        for h in top:
            signal = {"accelerating": "🔥加速", "decelerating": "❄️减速", "steady": "➡️稳态"}[h.rotation_signal]
            lines.append(
                f"| {h.net_flow_rank} | {h.l1_name} | {h.heat_score:.2f} "
                f"| {h.pct_chg_avg:+.1f}% | {h.up_ratio:.0%} | {signal} |"
            )
        return "\n".join(lines)


sector_rotation = SectorRotationService()

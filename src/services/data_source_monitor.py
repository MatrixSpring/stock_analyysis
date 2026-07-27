# -*- coding: utf-8 -*-
"""
数据源健康监控服务 — 聚合 crawl_metadata 统计指标
在 Web 诊断面板展示：成功率、平均耗时、失败 TOP 标的
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SourceHealthSummary:
    """单个数据源健康摘要"""
    source: str
    data_type: str = "daily"
    total_requests: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    consecutive_failures: int = 0
    circuit_open: bool = False
    last_success_at: str = ""
    last_failure_at: str = ""
    last_error: str = ""
    failed_top_codes: List[str] = field(default_factory=list)
    status: str = "unknown"   # healthy / degraded / down


class DataSourceMonitor:
    """数据源健康监控服务"""

    def __init__(self):
        self._db = None
        self._lookback_hours = 24

    @property
    def db(self):
        if self._db is None:
            try:
                from src.data_storage import get_mongo
                self._db = get_mongo().db
            except Exception:
                pass
        return self._db

    def get_source_health(self, source: str,
                          data_type: str = "daily") -> SourceHealthSummary:
        """获取单个数据源的健康摘要"""
        if not self.db:
            return SourceHealthSummary(source=source, data_type=data_type)

        since = (datetime.now(timezone.utc) - timedelta(hours=self._lookback_hours))
        try:
            records = list(self.db["crawl_metadata"].find({
                "source": source,
                "data_type": data_type,
                "crawl_at": {"$gte": since.isoformat()},
            }))

            if not records:
                return SourceHealthSummary(source=source, data_type=data_type,
                                          total_requests=0, status="unknown")

            total = len(records)
            ok = sum(1 for r in records if r.get("status") == "ok")
            durations = [r.get("request_duration_ms", 0) or 0 for r in records]
            avg_dur = sum(durations) / total if durations else 0

            # 连续失败
            sorted_recs = sorted(records, key=lambda r: r.get("crawl_at", ""), reverse=True)
            cons_fails = 0
            for r in sorted_recs:
                if r.get("status") != "ok":
                    cons_fails += 1
                else:
                    break

            # 失败 TOP 标的
            failed = [r for r in records if r.get("status") != "ok"]
            failed_codes = list(dict.fromkeys(
                r.get("code", "") for r in failed if r.get("code")
            ))[:5]

            last_ok = next((r for r in sorted_recs if r.get("status") == "ok"), None)
            last_fail = next((r for r in sorted_recs if r.get("status") != "ok"), None)

            success_rate = round(ok / total, 3) if total > 0 else 0.0
            status = "healthy" if success_rate > 0.8 else ("degraded" if success_rate > 0.3 else "down")

            return SourceHealthSummary(
                source=source, data_type=data_type,
                total_requests=total, success_rate=success_rate,
                avg_duration_ms=round(avg_dur, 1),
                consecutive_failures=cons_fails,
                circuit_open=cons_fails >= 5,
                last_success_at=last_ok.get("crawl_at", "") if last_ok else "",
                last_failure_at=last_fail.get("crawl_at", "") if last_fail else "",
                last_error=str(last_fail.get("error_message", ""))[:200] if last_fail else "",
                failed_top_codes=failed_codes,
                status=status,
            )
        except Exception as e:
            logger.warning(f"Source health query failed: {e}")
            return SourceHealthSummary(source=source, data_type=data_type)

    def get_all_sources_health(self, data_type: str = "daily") -> List[SourceHealthSummary]:
        """获取所有数据源的健康摘要"""
        sources = set()
        if self.db:
            try:
                since = (datetime.now(timezone.utc) - timedelta(hours=self._lookback_hours))
                docs = self.db["crawl_metadata"].distinct(
                    "source",
                    {"data_type": data_type, "crawl_at": {"$gte": since.isoformat()}},
                )
                sources = set(docs)
            except Exception:
                pass

        return [self.get_source_health(s, data_type) for s in sorted(sources)]

    def get_monitoring_dashboard(self) -> Dict[str, Any]:
        """诊断面板监控汇总"""
        sources_health = self.get_all_sources_health("daily")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": [
                {
                    "source": s.source, "status": s.status,
                    "success_rate": s.success_rate,
                    "avg_ms": s.avg_duration_ms,
                    "consecutive_failures": s.consecutive_failures,
                    "failed_codes": s.failed_top_codes,
                }
                for s in sources_health
            ],
            "summary": {
                "total_sources": len(sources_health),
                "healthy": sum(1 for s in sources_health if s.status == "healthy"),
                "degraded": sum(1 for s in sources_health if s.status == "degraded"),
                "down": sum(1 for s in sources_health if s.status == "down"),
            },
        }


# 全局单例
data_source_monitor = DataSourceMonitor()

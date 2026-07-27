# -*- coding: utf-8 -*-
"""
===================================
统一数据网关 — LegacyGateway
===================================

职责：
1. 统一入口：所有数据请求通过本网关，不再直连数据库/API
2. 智能路由：自动将查询分发到热数据/归档/外部API
3. DTO 适配：自动转换新旧数据格式
4. 只读守卫：拦截旧模块写入操作
5. 可观测性：记录每次请求的延迟、数据源、成功/失败

使用方式：
    from src.adapters import LegacyGateway

    gateway = LegacyGateway.get_instance()
    gateway.init(db_manager, archive_dir="./data/archive")

    # 查询 K 线数据（自动路由 + 格式适配）
    data = gateway.query_kline("600519", start="2024-01-01", output_format="legacy")
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.adapters.dto_adapter import DTOAdapter
from src.adapters.readonly_guard import ReadOnlyGuard, ReadOnlyViolationError
from src.adapters.route_engine import RouteEngine, RouteDecision, StorageTier

logger = logging.getLogger(__name__)


# ============================================================
# 请求追踪
# ============================================================

@dataclass
class GatewayRequest:
    """一次网关请求的追踪记录"""
    request_id: str
    data_type: str
    params: Dict[str, Any]
    route_decision: Optional[RouteDecision] = None
    source: str = ""
    format: str = "new"  # "new" | "legacy"
    latency_ms: float = 0.0
    success: bool = False
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "data_type": self.data_type,
            "params": self.params,
            "route": self.route_decision.backend_name if self.route_decision else "",
            "source": self.source,
            "format": self.format,
            "latency_ms": round(self.latency_ms, 1),
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ============================================================
# 门面
# ============================================================

class LegacyGateway:
    """
    统一数据网关（单例）。

    所有数据请求的唯一切入点。整合了路由引擎、DTO 适配器和只读守卫。
    """

    _instance: Optional["LegacyGateway"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._route_engine: Optional[RouteEngine] = None
        self._readonly_guard: Optional[ReadOnlyGuard] = None
        self._db_manager: Any = None
        self._initialized = False
        self._requests: List[GatewayRequest] = []
        self._max_request_log = 500
        self._adapters: Dict[str, DTOAdapter] = {}

    # ============================================================
    # 单例
    # ============================================================

    @classmethod
    def get_instance(cls) -> "LegacyGateway":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ============================================================
    # 初始化
    # ============================================================

    def init(
        self,
        db_manager: Any = None,
        archive_dir: Optional[str] = None,
        hot_window_days: int = 90,
        enable_readonly_guard: bool = True,
    ):
        """
        初始化网关。

        Args:
            db_manager: DatabaseManager 实例
            archive_dir: 归档数据目录
            hot_window_days: 热数据窗口天数
            enable_readonly_guard: 是否启用只读守卫
        """
        if self._initialized:
            logger.warning("[LegacyGateway] 已经初始化，跳过重复初始化")
            return

        self._db_manager = db_manager
        self._route_engine = RouteEngine(
            db_manager=db_manager,
            archive_dir=archive_dir,
            hot_window_days=hot_window_days,
        )
        self._readonly_guard = ReadOnlyGuard()
        if not enable_readonly_guard:
            self._readonly_guard.enabled = False

        # 注册默认适配器
        self._adapters["kline"] = DTOAdapter.for_kline()
        self._adapters["stock_info"] = DTOAdapter.for_stock_info()
        self._adapters["capital_flow"] = DTOAdapter.for_capital_flow()
        self._adapters["backtest"] = DTOAdapter.for_backtest()

        self._initialized = True
        logger.info(
            f"[LegacyGateway] 初始化完成 "
            f"(hot_window={hot_window_days}d, readonly_guard={enable_readonly_guard})"
        )

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def route_engine(self) -> Optional[RouteEngine]:
        return self._route_engine

    @property
    def readonly_guard(self) -> Optional[ReadOnlyGuard]:
        return self._readonly_guard

    # ============================================================
    # 核心查询接口
    # ============================================================

    def query(
        self,
        data_type: str,
        executor: Callable[[], Any],
        params: Optional[Dict[str, Any]] = None,
        output_format: str = "new",
        adapter: Optional[DTOAdapter] = None,
        module: str = "unknown",
        *,
        is_write: bool = False,
    ) -> Tuple[Any, Optional[str]]:
        """
        通用查询入口。

        Args:
            data_type: 数据类型
            executor: 实际执行函数
            params: 查询参数
            output_format: "new" | "legacy" 输出格式
            adapter: 自定义适配器
            module: 调用模块名
            is_write: 是否为写入操作

        Returns:
            (data, error_message)
        """
        if not self._initialized:
            return None, "LegacyGateway 未初始化，请先调用 init()"

        request_id = f"{data_type}_{int(time.time() * 1000)}"
        request = GatewayRequest(
            request_id=request_id,
            data_type=data_type,
            params=params or {},
            format=output_format,
            source=module,
        )
        start = time.time()

        try:
            # 1. 写入检查
            if is_write and self._readonly_guard and self._readonly_guard.enabled:
                self._readonly_guard.guard(
                    module=module,
                    operation="WRITE",
                    executor=executor,
                )

            # 2. 路由决策
            if self._route_engine:
                start_date = (params or {}).get("start_date") or (params or {}).get("start")
                decision = self._route_engine.decide(data_type, start_date=start_date)
                request.route_decision = decision

            # 3. 执行
            data = executor()

            # 4. DTO 适配
            if data is not None and output_format == "legacy":
                _adapter = adapter or self._adapters.get(data_type)
                if _adapter:
                    if isinstance(data, list):
                        data = _adapter.to_legacy_format_batch(data)
                    elif isinstance(data, dict):
                        data = _adapter.to_legacy_format(data)

            # 5. 记录成功
            request.success = True
            request.latency_ms = (time.time() - start) * 1000
            self._log_request(request)

            return data, None

        except ReadOnlyViolationError as e:
            request.error = str(e)
            request.latency_ms = (time.time() - start) * 1000
            self._log_request(request)
            raise

        except Exception as e:
            request.error = f"{type(e).__name__}: {str(e)[:200]}"
            request.latency_ms = (time.time() - start) * 1000
            self._log_request(request)
            logger.error(f"[LegacyGateway] 查询失败: {request.error}")
            return None, request.error

    def query_kline(
        self,
        stock_code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        output_format: str = "new",
        module: str = "unknown",
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """查询 K 线数据"""
        params = {"stock_code": stock_code, "start_date": start, "end_date": end}

        def executor():
            if self._db_manager is None:
                return []
            # 使用 DatabaseManager 的通用查询能力
            # 这里是一个通用模板，实际使用时会根据后端注入具体逻辑
            return self._fetch_kline(stock_code, start, end)

        return self.query(
            data_type="kline",
            executor=executor,
            params=params,
            output_format=output_format,
            adapter=self._adapters.get("kline"),
            module=module,
        )

    def query_stock_info(
        self,
        stock_code: str,
        output_format: str = "new",
        module: str = "unknown",
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """查询股票基础信息"""
        params = {"stock_code": stock_code}

        def executor():
            if self._db_manager is None:
                return {}
            return self._fetch_stock_info(stock_code)

        return self.query(
            data_type="stock_info",
            executor=executor,
            params=params,
            output_format=output_format,
            adapter=self._adapters.get("stock_info"),
            module=module,
        )

    def query_analysis_history(
        self,
        stock_code: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 50,
        output_format: str = "new",
        module: str = "unknown",
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """查询历史分析记录"""
        params = {"stock_code": stock_code, "start_date": start, "end_date": end, "limit": limit}

        def executor():
            if self._db_manager is None:
                return []
            return self._fetch_analysis_history(stock_code, start, end, limit)

        return self.query(
            data_type="analysis",
            executor=executor,
            params=params,
            output_format=output_format,
            module=module,
        )

    # ============================================================
    # 适配器管理
    # ============================================================

    def register_adapter(self, name: str, adapter: DTOAdapter):
        """注册自定义适配器"""
        self._adapters[name] = adapter
        logger.info(f"[LegacyGateway] 注册适配器: {name}")

    def get_adapter(self, name: str) -> Optional[DTOAdapter]:
        """获取已注册的适配器"""
        return self._adapters.get(name)

    # ============================================================
    # 可观测性
    # ============================================================

    def get_recent_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的数据请求记录"""
        return [r.to_dict() for r in self._requests[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """获取网关统计信息"""
        total = len(self._requests)
        if total == 0:
            return {"total_requests": 0}

        successful = sum(1 for r in self._requests if r.success)
        avg_latency = (
            sum(r.latency_ms for r in self._requests) / total
            if total > 0 else 0.0
        )

        by_type: Dict[str, int] = {}
        for r in self._requests:
            by_type[r.data_type] = by_type.get(r.data_type, 0) + 1

        return {
            "total_requests": total,
            "success_rate": round(successful / total, 3),
            "avg_latency_ms": round(avg_latency, 1),
            "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])[:10]),
            "health": (
                self._route_engine.get_health_report()
                if self._route_engine else {}
            ),
            "readonly_guard": (
                self._readonly_guard.get_audit_summary()
                if self._readonly_guard else {}
            ),
        }

    def clear_request_log(self):
        """清空请求日志"""
        self._requests.clear()

    # ============================================================
    # 内部实现：数据库操作
    # ============================================================

    def _fetch_kline(
        self,
        stock_code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """从数据库获取 K 线数据"""
        db = self._db_manager
        if db is None:
            return []

        try:
            normalized = stock_code.upper().replace(".SH", "").replace(".SZ", "")
            query = """
                SELECT date, open, high, low, close, volume, amount, pct_chg
                FROM daily_kline
                WHERE stock_code = ?
            """
            params: List[Any] = [normalized]

            if start:
                query += " AND date >= ?"
                params.append(start)
            if end:
                query += " AND date <= ?"
                params.append(end)

            query += " ORDER BY date ASC"

            if hasattr(db, "execute_query"):
                rows = db.execute_query(query, tuple(params))
            elif hasattr(db, "fetch_all"):
                rows = db.fetch_all(query, tuple(params))
            else:
                return []

            return [
                {
                    "date": row[0],
                    "open": float(row[1]) if row[1] else 0.0,
                    "high": float(row[2]) if row[2] else 0.0,
                    "low": float(row[3]) if row[3] else 0.0,
                    "close": float(row[4]) if row[4] else 0.0,
                    "volume": int(row[5]) if row[5] else 0,
                    "amount": float(row[6]) if row[6] else 0.0,
                    "pct_chg": float(row[7]) if row[7] else 0.0,
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"[LegacyGateway] K线查询失败 {stock_code}: {e}")
            return []

    def _fetch_stock_info(self, stock_code: str) -> Dict[str, Any]:
        """从数据库获取股票信息"""
        db = self._db_manager
        if db is None:
            return {}

        try:
            normalized = stock_code.upper()
            query = """
                SELECT code, name, market, industry, list_date
                FROM stocks
                WHERE code = ?
            """
            if hasattr(db, "fetch_one"):
                row = db.fetch_one(query, (normalized,))
            elif hasattr(db, "execute_query"):
                rows = db.execute_query(query, (normalized,))
                row = rows[0] if rows else None
            else:
                return {}

            if row is None:
                return {}

            return {
                "code": row[0] or "",
                "name": row[1] or "",
                "market": row[2] or "",
                "industry": row[3] or "",
                "list_date": row[4] or "",
            }
        except Exception as e:
            logger.warning(f"[LegacyGateway] 股票信息查询失败 {stock_code}: {e}")
            return {}

    def _fetch_analysis_history(
        self,
        stock_code: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """从数据库获取分析历史"""
        db = self._db_manager
        if db is None:
            return []

        try:
            query = """
                SELECT stock_code, analysis_date, ai_prediction, actual_performance,
                       window_return, direction_match, accuracy
                FROM analysis_results
                WHERE 1=1
            """
            params: List[Any] = []

            if stock_code:
                query += " AND stock_code = ?"
                params.append(stock_code.upper())
            if start:
                query += " AND analysis_date >= ?"
                params.append(start)
            if end:
                query += " AND analysis_date <= ?"
                params.append(end)

            query += " ORDER BY analysis_date DESC LIMIT ?"
            params.append(limit)

            if hasattr(db, "execute_query"):
                rows = db.execute_query(query, tuple(params))
            elif hasattr(db, "fetch_all"):
                rows = db.fetch_all(query, tuple(params))
            else:
                return []

            return [
                {
                    "stock_code": row[0],
                    "analysis_date": row[1],
                    "ai_prediction": row[2] or "",
                    "actual_performance": row[3] or "",
                    "window_return": row[4] or 0.0,
                    "direction_match": row[5] or False,
                    "accuracy": row[6] or 0.0,
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"[LegacyGateway] 分析历史查询失败: {e}")
            return []

    # ============================================================
    # 请求日志
    # ============================================================

    def _log_request(self, request: GatewayRequest):
        self._requests.append(request)
        if len(self._requests) > self._max_request_log:
            self._requests = self._requests[-self._max_request_log:]

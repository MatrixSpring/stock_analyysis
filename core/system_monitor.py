# -*- coding: utf-8 -*-
"""
===================================
系统状态监控服务 — core/system_monitor.py
===================================

定时采集：数据源连通性、LLM 模型状态、任务统计、系统资源。
通过 get_monitor_info() 对外暴露监控数据。

使用方式：
    from core.system_monitor import start_monitoring, get_monitor_info
    start_monitoring()
    info = get_monitor_info()
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SystemMonitor:
    """系统状态采集器（后台线程定时刷新）"""

    def __init__(self):
        self.data: Dict[str, Any] = {
            "datasource_status": {},
            "llm_model_status": {},
            "task_stat": {"running": 0, "success": 0, "fail": 0},
            "system_info": {},
            "last_refresh": 0,
            "uptime_seconds": 0,
        }
        self._start_time = time.time()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval = 300  # 5 分钟

    # ---- 启动/停止 ----

    def start(self, interval_seconds: int = 300):
        """启动后台监控线程"""
        if self._running:
            return
        self._interval = interval_seconds
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"[SystemMonitor] 监控服务已启动，间隔 {interval_seconds}s")

    def stop(self):
        """停止监控"""
        self._running = False

    def _monitor_loop(self):
        """后台监控循环"""
        while self._running:
            try:
                self._collect_datasource_status()
                self._collect_llm_status()
                self._collect_system_info()
                self.data["last_refresh"] = int(time.time())
                self.data["uptime_seconds"] = int(time.time() - self._start_time)
            except Exception as e:
                logger.warning(f"[SystemMonitor] 采集异常: {e}")
            time.sleep(self._interval)

    # ---- 数据源检测 ----

    def _collect_datasource_status(self):
        """探测各数据源连通性"""
        sources = {
            "akshare": self._check_akshare,
            "tushare": self._check_tushare,
            "yfinance": self._check_yfinance,
        }
        for name, checker in sources.items():
            try:
                ok, msg = checker()
                self.data["datasource_status"][name] = {
                    "status": "ok" if ok else "error",
                    "msg": msg,
                    "last_check": int(time.time()),
                }
            except Exception as e:
                self.data["datasource_status"][name] = {
                    "status": "error",
                    "msg": str(e)[:100],
                    "last_check": int(time.time()),
                }

    def _check_akshare(self):
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            return (True, "ok") if df is not None and not df.empty else (False, "返回空数据")
        except Exception as e:
            return False, str(e)[:100]

    def _check_tushare(self):
        token = os.getenv("TUSHARE_TOKEN", "")
        if not token:
            return False, "未配置 TUSHARE_TOKEN"
        try:
            import tushare as ts
            pro = ts.pro_api(token)
            df = pro.trade_cal(exchange="SSE", cal_date=datetime.now().strftime("%Y%m%d"))
            return (True, "ok") if df is not None else (False, "返回空数据")
        except Exception as e:
            return False, str(e)[:100]

    def _check_yfinance(self):
        try:
            import yfinance as yf
            ticker = yf.Ticker("AAPL")
            info = ticker.info
            return (True, "ok") if info else (False, "返回空数据")
        except Exception as e:
            return False, str(e)[:100]

    # ---- LLM 状态 ----

    def _collect_llm_status(self):
        """采集 LLM 模型连通性"""
        models = {
            "deepseek-chat": bool(os.getenv("DEEPSEEK_API_KEY")),
            "doubao-seed-code": bool(os.getenv("ARK_API_KEY")),
            "github-models": bool(os.getenv("GITHUB_MODELS_TOKEN")),
        }
        try:
            from core.llm_engine import get_llm_engine
            engine = get_llm_engine()
            llm_stats = engine.get_stats()
        except Exception:
            llm_stats = {}

        for model, configured in models.items():
            self.data["llm_model_status"][model] = {
                "configured": configured,
                "status": "available" if configured else "not_configured",
                "last_check": int(time.time()),
            }
        self.data["llm_stats"] = llm_stats

    # ---- 系统信息 ----

    def _collect_system_info(self):
        """采集系统资源"""
        try:
            import psutil
            self.data["system_info"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
            }
        except ImportError:
            self.data["system_info"] = {"note": "psutil 未安装，无法采集系统资源"}

    # ---- 对外接口 ----

    def get_info(self) -> Dict[str, Any]:
        """获取完整监控数据"""
        return dict(self.data)

    def update_task_stat(self, **kwargs):
        """更新任务统计（由 task_queue 调用）"""
        self.data["task_stat"].update(kwargs)

    def mark_datasource_status(self, name: str, status: str, msg: str = ""):
        self.data["datasource_status"][name] = {
            "status": status,
            "msg": msg,
            "last_check": int(time.time()),
        }


# 全局单例
_monitor_instance: Optional[SystemMonitor] = None


def get_monitor() -> SystemMonitor:
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SystemMonitor()
    return _monitor_instance


def start_monitoring(interval_seconds: int = 300):
    get_monitor().start(interval_seconds)


def get_monitor_info() -> Dict[str, Any]:
    return get_monitor().get_info()

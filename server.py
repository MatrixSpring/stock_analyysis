# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis - FastAPI 后端服务入口
===================================

职责：
1. 提供 RESTful API 服务
2. 配置 CORS 跨域支持
3. 健康检查接口
4. 托管前端静态文件（生产模式）

启动方式：
    uvicorn server:app --reload --host 0.0.0.0 --port 8000
    
    或使用 main.py:
    python main.py --serve-only      # 仅启动 API 服务
    python main.py --serve           # API 服务 + 执行分析
"""

import logging
import os

from src.config import setup_env, get_config
from src.logging_config import setup_logging

# 初始化环境变量与日志
setup_env()

config = get_config()
level_name = (config.log_level or "INFO").upper()
level = getattr(logging, level_name, logging.INFO)

setup_logging(
    log_prefix="api_server",
    console_level=level,
    extra_quiet_loggers=['uvicorn', 'fastapi'],
)

# 从 api.app 导入应用实例
from api.app import app  # noqa: E402

# 初始化统一数据网关（失败不影响主流程）
try:
    from src.adapters import LegacyGateway
    from src.storage import DatabaseManager

    _gw = LegacyGateway.get_instance()
    if not _gw.is_initialized:
        _db = DatabaseManager.get_instance()
        _archive_dir = os.path.join(
            os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data")),
            "archive",
        )
        _gw.init(
            db_manager=_db,
            archive_dir=_archive_dir,
            hot_window_days=int(os.getenv("HOT_DATA_WINDOW_DAYS", "90")),
            enable_readonly_guard=os.getenv("LEGACY_READONLY_GUARD", "true").lower() == "true",
        )
        logging.getLogger("server").info("[DSA] LegacyGateway 初始化完成")
except Exception as _gw_err:
    logging.getLogger("server").warning(f"[DSA] LegacyGateway 初始化跳过: {_gw_err}")

# ---- 新增：启动系统监控（可选，通过 system_config.yaml 灰度开关控制）----

try:
    from core.system_monitor import start_monitoring
    start_monitoring(interval_seconds=300)
    logging.getLogger("server").info("[DSA] SystemMonitor 已启动 (间隔 300s)")
except Exception as _mon_err:
    logging.getLogger("server").debug(f"[DSA] SystemMonitor 跳过: {_mon_err}")

# 导出 app 供 uvicorn 使用
__all__ = ['app']


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

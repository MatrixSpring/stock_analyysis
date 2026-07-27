# -*- coding: utf-8 -*-
"""
===================================
WebUI 启动脚本（兼容旧版入口）
===================================

旧版独立入口。现已统一到 server.py 启动流程。

直接运行 `python webui.py` 将委托给 server.py 统一启动，
确保全局共享：配置初始化、日志、中间件、Session 等。

等效命令：
    python main.py --serve-only
    python server.py
    uvicorn server:app --host 0.0.0.0 --port 8000

Usage:
  python webui.py
  WEBUI_HOST=0.0.0.0 WEBUI_PORT=8000 python webui.py
"""

from __future__ import annotations

import os
import sys
import logging

logger = logging.getLogger(__name__)


def main() -> int:
    """
    启动 Web 服务（委托给 server.py 统一入口）。

    所有旧版环境变量（WEBUI_HOST / WEBUI_PORT / API_HOST / API_PORT）
    自动映射到新版配置，确保向后兼容。
    """

    # 兼容旧版环境变量名
    host = os.getenv("WEBUI_HOST", os.getenv("API_HOST", "127.0.0.1"))
    port = int(os.getenv("WEBUI_PORT", os.getenv("API_PORT", "8000")))

    # 注入到新版环境变量（如果未设置）
    if not os.getenv("API_HOST"):
        os.environ["API_HOST"] = host
    if not os.getenv("API_PORT"):
        os.environ["API_PORT"] = str(port)

    print(f"[DSA] WebUI 启动中 → http://{host}:{port}")
    print(f"[DSA] API 文档 → http://{host}:{port}/docs")
    print(f"[DSA] 已统一到 server.py 引导流程（含 LegacyGateway 初始化）")
    print()

    try:
        # 委托给 server.py — 统一初始化路径
        import uvicorn
        from src.config import setup_env
        from src.logging_config import setup_logging

        setup_env()
        setup_logging(log_prefix="web_server")

        # 在启动时初始化 LegacyGateway（统一数据入口）
        _init_legacy_gateway()

        uvicorn.run(
            "server:app",
            host=host,
            port=port,
            log_level="info",
        )
    except KeyboardInterrupt:
        print("\n[DSA] WebUI 已停止")
    except Exception as e:
        print(f"[DSA] 启动失败: {e}")
        return 1

    return 0


def _init_legacy_gateway():
    """按需初始化统一数据网关，失败不影响主流程启动"""
    try:
        from src.adapters import LegacyGateway
        from src.storage import DatabaseManager

        gw = LegacyGateway.get_instance()
        if gw.is_initialized:
            return

        db = DatabaseManager.get_instance()
        archive_dir = os.path.join(
            os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data")),
            "archive",
        )

        gw.init(
            db_manager=db,
            archive_dir=archive_dir,
            hot_window_days=int(os.getenv("HOT_DATA_WINDOW_DAYS", "90")),
            enable_readonly_guard=os.getenv("LEGACY_READONLY_GUARD", "true").lower() == "true",
        )
        print("[DSA] LegacyGateway 初始化完成")
    except ImportError:
        # adapters 模块导入失败 → 不影响主流程
        pass
    except Exception as e:
        logger.warning(f"[DSA] LegacyGateway 初始化跳过: {e}")


if __name__ == "__main__":
    raise SystemExit(main())

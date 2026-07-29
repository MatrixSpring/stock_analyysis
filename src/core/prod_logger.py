"""结构化 JSON 日志 — 生产环境使用"""

import logging
import sys
from pathlib import Path
from pythonjsonlogger import jsonlogger
from src.config.prod_settings import settings

Path(settings.LOG_DIR).mkdir(exist_ok=True, parents=True)


def setup_logger():
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    json_formatter = jsonlogger.JsonFormatter(log_format)
    logger = logging.getLogger("stock_backend")
    logger.setLevel(settings.LOG_LEVEL)
    logger.propagate = False

    # 控制台
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    # 文件
    file_handler = logging.FileHandler(
        Path(settings.LOG_DIR) / "api.log", encoding="utf-8"
    )
    file_handler.setFormatter(json_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


api_logger = setup_logger()

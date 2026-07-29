import logging
import sys
from pathlib import Path
from src.config.settings import settings

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("stock_analysis")
logger.setLevel(logging.INFO)

# 控制台输出
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)

# 文件输出
file_handler = logging.FileHandler(
    filename=str(LOG_DIR / "app.log"),
    encoding="utf-8"
)
file_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)

if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


def get_logger():
    return logger

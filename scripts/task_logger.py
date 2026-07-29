import logging
from pathlib import Path

LOG_DIR = Path("./logs/task")
LOG_DIR.mkdir(parents=True, exist_ok=True)

task_logger = logging.getLogger("sync_task")
task_logger.setLevel(logging.INFO)

# 文件日志
file_handler = logging.FileHandler(LOG_DIR / "sync_task.log", encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
# 控制台输出
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

task_logger.addHandler(file_handler)
task_logger.addHandler(console_handler)

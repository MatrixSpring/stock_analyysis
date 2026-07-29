import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)


def get_env(key: str, default: Optional[str] = None) -> str:
    val = os.getenv(key)
    if val is None:
        if default is None:
            raise ValueError(f"环境变量 {key} 未配置，请检查 .env")
        return default
    return val


class Settings:
    # 运行环境
    APP_ENV: str = get_env("APP_ENV", "dev")
    TIMEZONE: str = get_env("TIMEZONE", "Asia/Shanghai")

    # 数据库
    DB_PATH: str = str(BASE_DIR / get_env("DB_PATH", "./data/stock.db"))
    DB_TIMEOUT: float = float(get_env("DB_TIMEOUT", "30.0"))

    # Http 请求通用
    REQUEST_TIMEOUT: int = int(get_env("REQUEST_TIMEOUT", "15"))
    REQUEST_RETRY_TIMES: int = int(get_env("REQUEST_RETRY_TIMES", "2"))

    # 豆包 LLM
    DOUBAO_API_KEY: str = get_env("DOUBAO_API_KEY", "")
    DOUBAO_ENDPOINT: str = get_env("DOUBAO_ENDPOINT", "")
    DOUBAO_MODEL_ID: str = get_env("DOUBAO_MODEL_ID", "")

    # DeepSeek LLM
    DEEPSEEK_API_KEY: str = get_env("DEEPSEEK_API_KEY", "")
    DEEPSEEK_ENDPOINT: str = get_env("DEEPSEEK_ENDPOINT", "")
    DEEPSEEK_MODEL_ID: str = get_env("DEEPSEEK_MODEL_ID", "")

    # 数据源
    TUSHARE_TOKEN: str = get_env("TUSHARE_TOKEN", "")


settings = Settings()

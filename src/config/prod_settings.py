"""
生产化配置 — pydantic-settings 读取 .env
与旧版 src/config/settings.py 共存，渐进迁移
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = "dev"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    API_TOKEN: str = ""

    DB_URL: str = "sqlite:///./stock_data.db"
    DB_ECHO: bool = False

    DEFAULT_LLM_PROVIDER: str = "doubao"
    DOUBAO_API_KEY: str = ""
    DOUBAO_ENDPOINT: str = ""
    DOUBAO_MODEL: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_ENDPOINT: str = ""
    DEEPSEEK_MODEL: str = ""

    RATE_LIMIT_ENABLE: bool = True
    RATE_LIMIT_CAPACITY: int = 100
    RATE_LIMIT_REFILL_PER_MIN: int = 30

    ALERT_ENABLE: bool = False
    ALERT_WEBHOOK_DINGDING: str = ""
    ALERT_WEBHOOK_WECOM: str = ""

    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs/api"


settings = Settings()

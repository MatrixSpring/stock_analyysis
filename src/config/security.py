"""鉴权、限流配置"""
from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    enable: bool = True
    capacity: int = 100
    refill_per_min: int = 30


@dataclass
class AuthConfig:
    api_token: str = ""
    enable_auth: bool = True
    whitelist_paths: tuple = ("/health", "/docs", "/openapi.json", "/redoc")

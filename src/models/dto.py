from dataclasses import dataclass
from datetime import date


@dataclass
class StockKlineDTO:
    """K线数据返回DTO"""
    stock_code: str
    stock_name: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class LLMResultDTO:
    """LLM统一返回封装"""
    content: str
    prompt_tokens: int
    completion_tokens: int
    model_name: str

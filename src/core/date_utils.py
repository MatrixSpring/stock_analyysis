from datetime import datetime, timedelta
from src.config.constants import DATE_FORMAT


def str_to_date(date_str: str) -> datetime.date:
    return datetime.strptime(date_str, DATE_FORMAT).date()


def date_to_str(dt: datetime.date) -> str:
    return dt.strftime(DATE_FORMAT)


def get_date_range(days: int, end_date: datetime.date = None):
    """获取往前N天日期区间"""
    if end_date is None:
        end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date

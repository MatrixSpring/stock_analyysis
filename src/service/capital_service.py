import pandas as pd
from src.service.base_service import BaseService
from src.db.capital_repo import capital_repo
from src.core.logger import get_logger
from src.core.tracer import trace_cost

logger = get_logger()


class CapitalService(BaseService):
    @trace_cost("service_query_capital")
    def query_stock_capital(
            self,
            stock_code: str,
            start_date: str,
            end_date: str,
            use_cache: bool = True
    ) -> pd.DataFrame:
        cache_key = self.get_cache_key("capital", stock_code, start_date, end_date)
        if use_cache:
            cache_data = self.cache.get(cache_key)
            if cache_data is not None:
                return cache_data

        df = capital_repo.query_daily_capital(stock_code, start_date, end_date)
        if df.empty:
            logger.warning(f"资金流向无数据 code={stock_code} {start_date} ~ {end_date}")
            return pd.DataFrame()

        # 统一业务清洗
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        # 过滤脏数据
        df = df.dropna(subset=["net_amount"])

        # 缓存5分钟
        if use_cache:
            self.cache.set(cache_key, df, ttl_seconds=300)
        return df

    @trace_cost("calc_capital_accumulate")
    def calc_accumulate_net(self, df: pd.DataFrame, days: int = 5):
        """
        计算N日累计净流入
        :param df: 按日期升序资金dataframe
        :param days: 统计周期
        :return: 新增累计净额字段的df
        """
        if df.empty:
            return df
        df = df.copy()
        df["accumulate_net"] = df["net_amount"].rolling(window=days).sum()
        return df


capital_service = CapitalService()

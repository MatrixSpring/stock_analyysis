import pandas as pd
from src.service.base_service import BaseService
from src.db.stock_repo import stock_repo
from src.core.logger import get_logger
from src.core.exceptions import DataQueryError
from src.core.tracer import trace_cost

logger = get_logger()


class StockService(BaseService):

    @trace_cost("service_query_kline")
    def query_kline(
        self, stock_code: str, start_date: str, end_date: str, use_cache: bool = True
    ) -> pd.DataFrame:
        """
        获取K线+基础清洗
        :param stock_code: 股票代码
        :param start_date: 起始日期 YYYY-MM-DD
        :param end_date: 结束日期 YYYY-MM-DD
        :param use_cache: 是否开启内存缓存
        :return: 清洗完成行情DataFrame
        """
        cache_key = self.get_cache_key("kline", stock_code, start_date, end_date)
        if use_cache:
            cached_df = self.cache.get(cache_key)
            if cached_df is not None:
                return cached_df

        df = stock_repo.query_kline(stock_code, start_date, end_date)
        if df.empty:
            logger.warning(f"未查询到行情数据 code={stock_code} {start_date} ~ {end_date}")
            return pd.DataFrame()

        # 业务层统一数据清洗规则
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        # 剔除异常价格
        df = df[(df["close"] > 0) & (df["volume"] > 0)]

        # 存入缓存，5分钟有效期
        if use_cache:
            self.cache.set(cache_key, df, ttl_seconds=300)
        return df

    @trace_cost("service_get_stock_info")
    def get_stock_info(self, stock_code: str):
        info = stock_repo.get_stock_info(stock_code)
        if not info:
            raise DataQueryError(f"不存在股票代码: {stock_code}")
        return info


stock_service = StockService()

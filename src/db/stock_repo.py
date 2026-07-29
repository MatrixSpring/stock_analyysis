from src.db.base_repo import BaseRepo
from src.core.logger import get_logger
from src.core.data_convert import df_to_dataclass_list
from src.models.db_entity import StockDailyKlineEntity, StockInfoEntity

logger = get_logger()


class StockRepo(BaseRepo):
    def get_stock_info(self, stock_code: str):
        """单支股票基础信息"""
        sql = """
            SELECT stock_code, stock_name, market, industry, list_date
            FROM stock_info WHERE stock_code = ?
        """
        df = self.query_df(sql, params=(stock_code,))
        if df.empty:
            return None
        lst = df_to_dataclass_list(df, StockInfoEntity)
        return lst[0]

    def query_kline(self, stock_code: str, start_date: str, end_date: str):
        """查询日线原始行情数据"""
        sql = """
            SELECT stock_code, trade_date, open, high, low, close, volume, amount
            FROM stock_daily_kline
            WHERE stock_code = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC
        """
        df = self.query_df(sql, params=(stock_code, start_date, end_date))
        return df

    def batch_save_kline(self, df):
        """批量写入日线数据"""
        self.batch_insert(table="stock_daily_kline", df=df)


stock_repo = StockRepo()

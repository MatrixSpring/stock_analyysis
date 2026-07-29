from src.db.base_repo import BaseRepo
from src.core.logger import get_logger
from src.core.data_convert import df_to_dataclass_list
from src.models.db_entity import StockCapitalDailyEntity

logger = get_logger()


class CapitalRepo(BaseRepo):
    def query_daily_capital(self, stock_code: str, start_date: str, end_date: str):
        """查询个股每日资金流向原始数据"""
        sql = """
            SELECT stock_code, trade_date, main_inflow, retail_inflow,
                   big_order, mid_order, small_order, net_amount
            FROM stock_capital_daily
            WHERE stock_code = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date ASC;
        """
        df = self.query_df(sql, params=(stock_code, start_date, end_date))
        return df

    def batch_save_capital(self, df):
        """批量写入资金流向数据"""
        if df.empty:
            return
        self.batch_insert(table="stock_capital_daily", df=df)


capital_repo = CapitalRepo()

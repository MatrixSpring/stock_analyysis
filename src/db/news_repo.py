from src.db.base_repo import BaseRepo
from src.core.logger import get_logger
import pandas as pd

logger = get_logger()


class NewsRepo(BaseRepo):
    def query_stock_news(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """查询指定个股时间段资讯"""
        sql = """
            SELECT news_id, stock_code, publish_date, publish_time, title, content, source, sentiment, industry
            FROM stock_news
            WHERE stock_code = ? AND publish_date BETWEEN ? AND ?
            ORDER BY publish_time DESC;
        """
        df = self.query_df(sql, params=(stock_code, start_date, end_date))
        return df

    def query_industry_news(self, industry_name: str, start_date: str, end_date: str) -> pd.DataFrame:
        """行业资讯批量查询"""
        sql = """
            SELECT news_id, stock_code, publish_date, publish_time, title, content, source, sentiment, industry
            FROM stock_news
            WHERE industry = ? AND publish_date BETWEEN ? AND ?
            ORDER BY publish_time DESC;
        """
        df = self.query_df(sql, params=(industry_name, start_date, end_date))
        return df

    def batch_save_news(self, df: pd.DataFrame):
        """批量写入资讯，自动去重（news_id唯一）"""
        if df.empty:
            return
        self.batch_insert(table="stock_news", df=df)


news_repo = NewsRepo()

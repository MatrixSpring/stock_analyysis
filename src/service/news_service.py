import pandas as pd
from src.service.base_service import BaseService
from src.db.news_repo import news_repo
from src.core.logger import get_logger
from src.core.tracer import trace_cost

logger = get_logger()


class NewsService(BaseService):
    @trace_cost("service_query_stock_news")
    def get_stock_news(
            self,
            stock_code: str,
            start_date: str,
            end_date: str,
            use_cache: bool = True
    ) -> pd.DataFrame:
        cache_key = self.get_cache_key("news_stock", stock_code, start_date, end_date)
        if use_cache:
            cache_data = self.cache.get(cache_key)
            if cache_data is not None:
                return cache_data

        df = news_repo.query_stock_news(stock_code, start_date, end_date)
        if df.empty:
            logger.warning(f"个股无资讯数据 code={stock_code} {start_date} ~ {end_date}")
            return pd.DataFrame()

        # 业务清洗
        df["publish_date"] = pd.to_datetime(df["publish_date"]).dt.date
        df = df.dropna(subset=["title"])

        if use_cache:
            self.cache.set(cache_key, df, ttl_seconds=300)
        return df

    @trace_cost("service_query_industry_news")
    def get_industry_news(
            self,
            industry: str,
            start_date: str,
            end_date: str,
            use_cache: bool = True
    ) -> pd.DataFrame:
        cache_key = self.get_cache_key("news_industry", industry, start_date, end_date)
        if use_cache:
            cache_data = self.cache.get(cache_key)
            if cache_data is not None:
                return cache_data

        df = news_repo.query_industry_news(industry, start_date, end_date)
        if df.empty:
            logger.warning(f"行业无资讯 industry={industry}")
            return pd.DataFrame()

        df["publish_date"] = pd.to_datetime(df["publish_date"]).dt.date
        df = df.dropna(subset=["title"])

        if use_cache:
            self.cache.set(cache_key, df, ttl_seconds=300)
        return df

    @trace_cost("calc_news_sentiment_stat")
    def calc_sentiment_stat(self, df: pd.DataFrame):
        """舆情情感统计：正面/中性/负面数量统计"""
        if df.empty:
            return {}
        positive = len(df[df["sentiment"] > 0.2])
        neutral = len(df[(df["sentiment"] >= -0.2) & (df["sentiment"] <= 0.2)])
        negative = len(df[df["sentiment"] < -0.2])
        avg_sentiment = round(df["sentiment"].mean(), 4)
        return {
            "total": len(df),
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
            "avg_sentiment": avg_sentiment
        }


news_service = NewsService()

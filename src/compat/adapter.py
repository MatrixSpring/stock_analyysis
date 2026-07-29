"""
新旧业务兼容适配器 — 灰度切换，随时回滚
"""
from src.core.logger import get_logger

logger = get_logger()

# ===================== 灰度开关：逐个模块控制 =====================
ENABLE_NEW_STOCK_SERVICE = True
ENABLE_NEW_CAPITAL_SERVICE = True
ENABLE_NEW_NEWS_SERVICE = True
ENABLE_NEW_FAV_SERVICE = True
ENABLE_NEW_BACKTEST_SERVICE = True


class StockServiceAdapter:
    @staticmethod
    def query_kline_data(stock_code: str, start_date: str, end_date: str, use_cache=True):
        if ENABLE_NEW_STOCK_SERVICE:
            logger.info(f"[灰度]使用新版StockService code={stock_code}")
            from src.service.stock_service import stock_service
            return stock_service.query_kline(stock_code, start_date, end_date, use_cache)
        else:
            logger.info(f"[灰度]回退旧版逻辑 code={stock_code}")
            try:
                from OLD_ENTRY.old_stock_logic import old_get_kline
                return old_get_kline(stock_code, start_date, end_date)
            except ImportError:
                logger.warning("旧版逻辑不可用，降级到新版")
                from src.service.stock_service import stock_service
                return stock_service.query_kline(stock_code, start_date, end_date, use_cache)

    @staticmethod
    def get_stock_base_info(stock_code: str):
        if ENABLE_NEW_STOCK_SERVICE:
            from src.service.stock_service import stock_service
            return stock_service.get_stock_info(stock_code)
        else:
            try:
                from OLD_ENTRY.old_stock_logic import old_get_stock_info
                return old_get_stock_info(stock_code)
            except ImportError:
                logger.warning("旧版逻辑不可用，降级到新版")
                from src.service.stock_service import stock_service
                return stock_service.get_stock_info(stock_code)


# ====================== 资金流向适配器 ======================
class CapitalServiceAdapter:
    @staticmethod
    def query_capital_flow(stock_code: str, start_date: str, end_date: str, use_cache=True):
        if ENABLE_NEW_CAPITAL_SERVICE:
            logger.info(f"[灰度]新版CapitalService code={stock_code}")
            from src.service.capital_service import capital_service
            return capital_service.query_stock_capital(stock_code, start_date, end_date, use_cache)
        else:
            logger.info(f"[灰度]旧版资金流向逻辑 code={stock_code}")
            try:
                from OLD_ENTRY.old_capital_logic import old_get_capital_data
                return old_get_capital_data(stock_code, start_date, end_date)
            except ImportError:
                logger.warning("旧版逻辑不可用，降级到新版")
                from src.service.capital_service import capital_service
                return capital_service.query_stock_capital(stock_code, start_date, end_date, use_cache)

    @staticmethod
    def calc_rolling_accumulate(df, days=5):
        if ENABLE_NEW_CAPITAL_SERVICE:
            from src.service.capital_service import capital_service
            return capital_service.calc_accumulate_net(df, days)
        else:
            try:
                from OLD_ENTRY.old_capital_logic import old_calc_accumulate
                return old_calc_accumulate(df, days)
            except ImportError:
                from src.service.capital_service import capital_service
                return capital_service.calc_accumulate_net(df, days)


# ====================== 资讯舆情适配器 ======================
class NewsServiceAdapter:
    @staticmethod
    def get_stock_news(stock_code: str, start_date: str, end_date: str, use_cache=True):
        if ENABLE_NEW_NEWS_SERVICE:
            logger.info(f"[灰度]新版NewsService stock={stock_code}")
            from src.service.news_service import news_service
            return news_service.get_stock_news(stock_code, start_date, end_date, use_cache)
        else:
            logger.info(f"[灰度]旧版资讯逻辑 code={stock_code}")
            try:
                from OLD_ENTRY.old_news_logic import old_get_stock_news
                return old_get_stock_news(stock_code, start_date, end_date)
            except ImportError:
                from src.service.news_service import news_service
                return news_service.get_stock_news(stock_code, start_date, end_date, use_cache)

    @staticmethod
    def get_industry_news(industry: str, start_date: str, end_date: str, use_cache=True):
        if ENABLE_NEW_NEWS_SERVICE:
            from src.service.news_service import news_service
            return news_service.get_industry_news(industry, start_date, end_date, use_cache)
        else:
            try:
                from OLD_ENTRY.old_news_logic import old_get_industry_news
                return old_get_industry_news(industry, start_date, end_date)
            except ImportError:
                from src.service.news_service import news_service
                return news_service.get_industry_news(industry, start_date, end_date, use_cache)

    @staticmethod
    def sentiment_statistic(df):
        if ENABLE_NEW_NEWS_SERVICE:
            from src.service.news_service import news_service
            return news_service.calc_sentiment_stat(df)
        else:
            try:
                from OLD_ENTRY.old_news_logic import old_sentiment_stat
                return old_sentiment_stat(df)
            except ImportError:
                from src.service.news_service import news_service
                return news_service.calc_sentiment_stat(df)


# ====================== 自选股适配器 ======================
class FavoriteAdapter:
    @staticmethod
    def list_favorite():
        if ENABLE_NEW_FAV_SERVICE:
            from src.service.favorite_service import favorite_service
            return favorite_service.list_favorite()
        else:
            try:
                from OLD_ENTRY.old_fav import old_list
                return old_list()
            except ImportError:
                from src.service.favorite_service import favorite_service
                return favorite_service.list_favorite()

    @staticmethod
    def add(code, name):
        if ENABLE_NEW_FAV_SERVICE:
            from src.service.favorite_service import favorite_service
            return favorite_service.add(code, name)

    @staticmethod
    def remove(fav_id):
        if ENABLE_NEW_FAV_SERVICE:
            from src.service.favorite_service import favorite_service
            return favorite_service.remove(fav_id)


# ====================== 回测适配器 ======================
class BacktestAdapter:
    @staticmethod
    def create_task(code, s, e, strategy, params):
        if ENABLE_NEW_BACKTEST_SERVICE:
            from src.service.backtest_service import backtest_service
            return backtest_service.create_backtest_task(code, s, e, strategy, params)

    @staticmethod
    def list_task(code=None):
        if ENABLE_NEW_BACKTEST_SERVICE:
            from src.db.backtest_repo import backtest_repo
            return backtest_repo.list_task(code)

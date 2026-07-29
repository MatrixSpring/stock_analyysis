from src.compat.adapter import NewsServiceAdapter


def test_news_module():
    df = NewsServiceAdapter.get_stock_news("000001", "2026-01-01", "2026-01-30")
    stat = NewsServiceAdapter.sentiment_statistic(df)
    print(f"资讯数量：{len(df)}")
    print("舆情统计", stat)


if __name__ == "__main__":
    test_news_module()

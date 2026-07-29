from src.compat.adapter import CapitalServiceAdapter


def test_capital_module():
    df = CapitalServiceAdapter.query_capital_flow("000001", "2026-01-01", "2026-01-20")
    df_acc = CapitalServiceAdapter.calc_rolling_accumulate(df, days=5)
    print(f"资金数据行数: {len(df_acc)}")
    print(df_acc.head())


if __name__ == "__main__":
    test_capital_module()

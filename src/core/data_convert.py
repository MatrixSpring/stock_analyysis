import pandas as pd
from dataclasses import asdict


def dataclass_list_to_df(obj_list) -> pd.DataFrame:
    if not obj_list:
        return pd.DataFrame()
    data = [asdict(item) for item in obj_list]
    return pd.DataFrame(data)


def df_to_dataclass_list(df: pd.DataFrame, dto_cls):
    if df.empty:
        return []
    records = df.to_dict("records")
    return [dto_cls(**row) for row in records]

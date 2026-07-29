from src.db.base_repo import BaseRepo
from src.core.logger import get_logger
import pandas as pd

logger = get_logger()


class FavoriteRepo(BaseRepo):
    def list_all(self) -> pd.DataFrame:
        sql = """SELECT id,stock_code,stock_name,create_time FROM stock_favorite ORDER BY id DESC"""
        return self.query_df(sql)

    def add_favorite(self, code: str, name: str):
        sql = """
        INSERT OR IGNORE INTO stock_favorite (stock_code,stock_name,create_time)
        VALUES (?,?,datetime('now'))
        """
        self.execute(sql, (code, name))

    def delete_favorite(self, fav_id: int):
        sql = "DELETE FROM stock_favorite WHERE id = ?"
        self.execute(sql, (fav_id,))


favorite_repo = FavoriteRepo()

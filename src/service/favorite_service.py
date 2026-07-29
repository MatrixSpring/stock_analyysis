import pandas as pd
from src.service.base_service import BaseService
from src.db.favorite_repo import favorite_repo


class FavoriteService(BaseService):
    def list_favorite(self) -> pd.DataFrame:
        return favorite_repo.list_all()

    def add(self, code: str, name: str):
        favorite_repo.add_favorite(code, name)

    def remove(self, fav_id: int):
        favorite_repo.delete_favorite(fav_id)


favorite_service = FavoriteService()

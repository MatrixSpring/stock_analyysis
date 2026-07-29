import sqlite3
import pandas as pd
import time
from pathlib import Path
from src.config.settings import settings
from src.core.logger import get_logger
from src.core.exceptions import DataQueryError
from src.core.tracer import trace_cost

logger = get_logger()
LOCK_RETRY_TIMES = 3
LOCK_SLEEP_INTERVAL = 0.3


class BaseRepo:
    def __init__(self):
        self.db_path = settings.DB_PATH
        Path(self.db_path).parent.mkdir(exist_ok=True)

    def _get_conn(self):
        conn = sqlite3.connect(
            self.db_path,
            timeout=settings.DB_TIMEOUT,
            check_same_thread=False
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @trace_cost("db_query")
    def query_df(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        retry = 0
        while retry < LOCK_RETRY_TIMES:
            try:
                conn = self._get_conn()
                df = pd.read_sql(sql, conn, params=params)
                conn.close()
                return df
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    retry += 1
                    logger.warning(f"数据库锁定，重试 {retry}/{LOCK_RETRY_TIMES}")
                    time.sleep(LOCK_SLEEP_INTERVAL)
                    continue
                logger.error(f"数据库查询异常 sql={sql}, err={str(e)}")
                raise DataQueryError(f"查询失败: {str(e)}") from e
            except Exception as e:
                logger.error(f"数据库查询异常 sql={sql}, err={str(e)}")
                raise DataQueryError(f"查询失败: {str(e)}") from e
        raise DataQueryError("数据库持续锁定，多次重试失败")

    @trace_cost("db_execute")
    def execute(self, sql: str, params: tuple = ()) -> int:
        retry = 0
        while retry < LOCK_RETRY_TIMES:
            try:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute(sql, params)
                conn.commit()
                affect_rows = cur.rowcount
                conn.close()
                return affect_rows
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    retry += 1
                    logger.warning(f"数据库锁定，重试 {retry}/{LOCK_RETRY_TIMES}")
                    time.sleep(LOCK_SLEEP_INTERVAL)
                    continue
                logger.error(f"SQL执行异常 sql={sql} err={str(e)}")
                raise DataQueryError(f"执行SQL失败: {str(e)}") from e
            except Exception as e:
                logger.error(f"SQL执行异常 sql={sql} err={str(e)}")
                raise DataQueryError(f"执行SQL失败: {str(e)}") from e
        raise DataQueryError("数据库持续锁定，多次重试失败")

    def batch_insert(self, table: str, df: pd.DataFrame):
        if df.empty:
            return
        try:
            conn = self._get_conn()
            df.to_sql(
                name=table,
                con=conn,
                if_exists="append",
                index=False,
                chunksize=1000
            )
            conn.close()
        except Exception as e:
            logger.error(f"批量写入失败 table={table}, err={str(e)}")
            raise DataQueryError("批量入库失败") from e

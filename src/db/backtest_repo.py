from src.db.base_repo import BaseRepo
import pandas as pd
import json

logger = __import__("logging").getLogger(__name__)


class BacktestRepo(BaseRepo):
    def create_task(self, task_id: str, stock_code: str, start_date: str, end_date: str, strategy: str, params: dict):
        sql = """
        INSERT INTO backtest_task
        (task_id,stock_code,start_date,end_date,strategy_name,params,status,create_time)
        VALUES (?,?,?,?,?,?,?,datetime('now'))
        """
        self.execute(sql, (task_id, stock_code, start_date, end_date, strategy, json.dumps(params), "running"))

    def update_result(self, task_id: str, result_dict: dict):
        sql = """
        UPDATE backtest_task SET
        result=?, total_return=?,max_drawdown=?,win_rate=?,status='finished',finish_time=datetime('now')
        WHERE task_id = ?
        """
        self.execute(sql, (
            json.dumps(result_dict, ensure_ascii=False),
            result_dict.get("total_return"),
            result_dict.get("max_drawdown"),
            result_dict.get("win_rate"),
            task_id
        ))

    def list_task(self, stock_code=None):
        sql = "SELECT * FROM backtest_task "
        args = []
        if stock_code:
            sql += "WHERE stock_code = ? "
            args.append(stock_code)
        sql += "ORDER BY create_time DESC"
        return self.query_df(sql, tuple(args) if args else ())


backtest_repo = BacktestRepo()

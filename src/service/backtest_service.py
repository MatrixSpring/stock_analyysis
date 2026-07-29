import uuid
import json
import pandas as pd
import numpy as np
from src.service.base_service import BaseService
from src.db.backtest_repo import backtest_repo
from src.db.stock_repo import stock_repo
from src.db.capital_repo import capital_repo
from src.core.logger import get_logger
from src.core.alert import alert_client

logger = get_logger()


class BacktestService(BaseService):
    def create_backtest_task(
        self, stock_code: str, start_date: str, end_date: str,
        strategy_name: str, params: dict,
    ):
        task_id = str(uuid.uuid4())
        backtest_repo.create_task(task_id, stock_code, start_date, end_date, strategy_name, params)
        self.run_backtest(task_id, stock_code, start_date, end_date, strategy_name, params)
        return task_id

    def run_backtest(self, task_id, stock_code, s_date, e_date, strategy, params):
        try:
            df_kline = stock_repo.query_kline(stock_code, s_date, e_date)
            df_cap = capital_repo.query_daily_capital(stock_code, s_date, e_date)
            if df_kline.empty:
                raise Exception("缺少K线数据，无法回测")
            df = pd.merge(df_kline, df_cap, how="left", on=["stock_code", "trade_date"])
            df = df.sort_values("trade_date").reset_index(drop=True)

            if strategy == "ma_strategy":
                result = self._strategy_ma(df, params)
            elif strategy == "capital_flow_strategy":
                result = self._strategy_capital(df, params)
            else:
                raise Exception("不存在该策略")

            backtest_repo.update_result(task_id, result)
            logger.info(f"回测任务完成 task:{task_id} code:{stock_code}")
        except Exception as e:
            logger.exception("回测任务异常")
            alert_client.send_msg("回测任务失败", f"task_id:{task_id} err:{str(e)}")

    def _strategy_ma(self, df: pd.DataFrame, params: dict):
        """均线策略：短期均线上穿长期均线买入"""
        fast = params.get("fast_ma", 5)
        slow = params.get("slow_ma", 20)
        df["ma_fast"] = df["close"].rolling(fast).mean()
        df["ma_slow"] = df["close"].rolling(slow).mean()
        df["signal"] = np.where(df["ma_fast"] > df["ma_slow"], 1, 0)

        # 策略收益
        df["pct_change"] = df["close"].pct_change()
        df["strategy_return"] = df["signal"].shift(1) * df["pct_change"]
        # 基准收益：一直持有
        df["bench_return"] = df["pct_change"]

        total_return = float((1 + df["strategy_return"].fillna(0)).cumprod().iloc[-1] - 1) if len(df) > 0 else 0
        bench_total_return = float((1 + df["bench_return"].fillna(0)).cumprod().iloc[-1] - 1) if len(df) > 0 else 0
        excess_return = total_return - bench_total_return

        max_drawdown = self._calc_max_dd(df["strategy_return"])
        signals = df[df["signal"].shift(1) == 1]
        win_rate = float(len(df[df["strategy_return"] > 0]) / max(1, len(signals))) if len(signals) > 0 else 0

        return {
            "total_return": round(total_return, 4),
            "bench_return": round(bench_total_return, 4),
            "excess_return": round(excess_return, 4),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "data": json.loads(df.fillna(0).to_json(orient="records")),
        }

    def _strategy_capital(self, df: pd.DataFrame, params: dict):
        """资金流向策略：持续N日主力净流入买入"""
        roll_days = params.get("roll_days", 3)
        df["roll_main"] = df["main_inflow"].fillna(0).rolling(roll_days).sum()
        df["signal"] = np.where(df["roll_main"] > 0, 1, 0)

        df["pct_change"] = df["close"].pct_change()
        df["strategy_return"] = df["signal"].shift(1) * df["pct_change"]
        # 基准：全程持有
        df["bench_return"] = df["pct_change"]

        total_return = float((1 + df["strategy_return"].fillna(0)).cumprod().iloc[-1] - 1) if len(df) > 0 else 0
        bench_total_return = float((1 + df["bench_return"].fillna(0)).cumprod().iloc[-1] - 1) if len(df) > 0 else 0
        excess_return = total_return - bench_total_return

        max_drawdown = self._calc_max_dd(df["strategy_return"])
        signals = df[df["signal"].shift(1) == 1]
        win_rate = float(len(df[df["strategy_return"] > 0]) / max(1, len(signals))) if len(signals) > 0 else 0

        return {
            "total_return": round(total_return, 4),
            "bench_return": round(bench_total_return, 4),
            "excess_return": round(excess_return, 4),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "data": json.loads(df.fillna(0).to_json(orient="records")),
        }

    def _calc_max_dd(self, series: pd.Series):
        if series.empty:
            return 0.0
        cum = (1 + series.fillna(0)).cumprod()
        running_max = cum.cummax()
        drawdown = (cum - running_max) / running_max
        return float(abs(drawdown.min()))


backtest_service = BacktestService()

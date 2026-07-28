# -*- coding: utf-8 -*-
"""
===================================
升级版回测引擎 — core/backtest/engine.py
===================================

新增能力：
- 滑点模拟（固定/比例/随机）
- 手续费 + 印花税
- 涨跌停无法成交仿真
- 完整绩效指标（夏普/索提诺/卡玛/最大回撤/盈亏比）
- 未来函数检测
- 回测快照持久化（SQLite）

兼容原有选股因子代码，增量改造，不修改历史数据。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.backtest.metrics import PerformanceMetrics

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/backtest_snapshot.db")


# ============================================================
# 配置
# ============================================================

@dataclass
class BacktestConfig:
    """回测仿真参数"""
    commission_rate: float = 0.0003   # 佣金率（默认万三）
    stamp_tax_rate: float = 0.001     # 印花税率（卖出收取 0.1%）
    slippage_type: str = "percent"    # 滑点类型: fixed/percent/random
    slippage_value: float = 0.001     # 滑点值（百分比为 0.1%）
    initial_capital: float = 100000   # 初始资金
    allow_limit_trade: bool = False   # 涨跌停能否交易
    position_size_pct: float = 1.0    # 仓位比例（1=满仓）
    min_commission: float = 5.0       # 最低佣金


# ============================================================
# 回测引擎
# ============================================================

class BacktestEngine:
    """
    升级版事件驱动回测引擎。

    使用方式：
        engine = BacktestEngine()
        result = engine.run(df_signal, signal_col="signal")
        print(result["performance"])
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or _DB_PATH
        self.config = BacktestConfig()
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_snapshot (
                    snapshot_id TEXT PRIMARY KEY,
                    name TEXT,
                    create_time TEXT DEFAULT (datetime('now')),
                    config_json TEXT,
                    performance_json TEXT,
                    signal_count INTEGER,
                    stock_codes TEXT
                )
            """)
            conn.commit()

    # ---- 主入口 ----

    def run(
        self,
        df_signal: pd.DataFrame,
        signal_col: str = "signal",
        config: Optional[BacktestConfig] = None,
        name: str = "",
    ) -> Dict[str, Any]:
        """
        执行回测。

        Args:
            df_signal: K线+信号 DataFrame，必需列: date,open,high,low,close,{signal_col}
            signal_col: 信号列名 (1=买入, -1=卖出, 0=持有)
            config: 回测配置
            name: 回测名称

        Returns:
            {"performance": {...}, "snapshot_id": str, "warnings": [...]}
        """
        cfg = config or self.config
        df = df_signal.copy().reset_index(drop=True)

        # 1. 数据校验
        errors = self._validate_data(df, signal_col)
        if errors:
            return {"performance": None, "errors": errors, "warnings": []}

        # 2. 未来函数检测
        warnings = self._detect_future_function(df, signal_col)

        # 3. 执行仿真
        asset_curve, trades = self._simulate(df, signal_col, cfg)
        asset_df = pd.DataFrame(asset_curve)

        # 4. 计算绩效
        performance = PerformanceMetrics.compute(asset_df)

        # 5. 保存快照
        snapshot_id = f"bt_{uuid.uuid4().hex[:8]}"
        self._save_snapshot(snapshot_id, name, cfg, performance, len(df), trades)

        performance["snapshot_id"] = snapshot_id
        performance["trade_count"] = len(trades)

        return {
            "performance": performance,
            "snapshot_id": snapshot_id,
            "warnings": warnings,
            "trades": trades,
            "asset_curve": asset_curve,
        }

    # ---- 仿真核心 ----

    def _simulate(
        self, df: pd.DataFrame, signal_col: str, cfg: BacktestConfig
    ) -> Tuple[List[Dict], List[Dict]]:
        """事件驱动逐日仿真"""
        capital = cfg.initial_capital
        hold_shares = 0
        asset_curve = []
        trades = []

        for idx, row in df.iterrows():
            signal = int(row[signal_col])
            close = float(row["close"])
            high = float(row["high"])
            low = float(row["low"])
            trade_price = self._apply_slippage(close, cfg)

            # —— 买入信号 ——
            if signal == 1 and hold_shares <= 0:
                if not self._can_trade(row, trade_price, "buy", cfg):
                    pass  # 涨跌停封板
                else:
                    max_shares = (capital * cfg.position_size_pct) / trade_price
                    cost = self._calc_cost(max_shares, trade_price, is_buy=True, cfg=cfg)
                    hold_shares = max_shares
                    capital -= hold_shares * trade_price + cost
                    trades.append({
                        "date": str(row.get("date", idx)),
                        "action": "buy",
                        "price": round(trade_price, 3),
                        "shares": round(hold_shares, 0),
                        "cost": round(cost, 2),
                    })

            # —— 卖出信号 ——
            elif signal == -1 and hold_shares > 0:
                if not self._can_trade(row, trade_price, "sell", cfg):
                    pass
                else:
                    sell_amount = hold_shares * trade_price
                    cost = self._calc_cost(hold_shares, trade_price, is_buy=False, cfg=cfg)
                    capital += sell_amount - cost
                    trades.append({
                        "date": str(row.get("date", idx)),
                        "action": "sell",
                        "price": round(trade_price, 3),
                        "shares": round(hold_shares, 0),
                        "cost": round(cost, 2),
                    })
                    hold_shares = 0

            # 每日资产记录
            market_value = hold_shares * close
            total_asset = capital + market_value
            asset_curve.append({
                "date": str(row.get("date", idx)),
                "asset": round(total_asset, 2),
                "position": round(hold_shares * close / max(total_asset, 1), 4) if total_asset > 0 else 0,
            })

        return asset_curve, trades

    # ---- 滑点 ----

    def _apply_slippage(self, price: float, cfg: BacktestConfig) -> float:
        """模拟滑点"""
        if cfg.slippage_type == "fixed":
            return price + cfg.slippage_value
        elif cfg.slippage_type == "random":
            factor = 1 + np.random.uniform(0, cfg.slippage_value)
            return price * factor
        else:  # percent
            return price * (1 + cfg.slippage_value)

    # ---- 涨跌停检测 ----

    def _can_trade(
        self, row: pd.Series, price: float, direction: str, cfg: BacktestConfig
    ) -> bool:
        """判断能否成交（涨跌停板检测）"""
        if cfg.allow_limit_trade:
            return True

        high = float(row.get("high", 99999))
        low = float(row.get("low", 0))

        if direction == "buy" and price >= high:
            return False  # 涨停无法买入
        if direction == "sell" and price <= low:
            return False  # 跌停无法卖出

        return True

    # ---- 交易成本 ----

    def _calc_cost(
        self, volume: float, price: float, is_buy: bool, cfg: BacktestConfig
    ) -> float:
        """计算交易总成本"""
        turnover = volume * price
        commission = max(turnover * cfg.commission_rate, cfg.min_commission)
        tax = turnover * cfg.stamp_tax_rate if not is_buy else 0
        return commission + tax

    # ---- 未来函数检测 ----

    def _detect_future_function(
        self, df: pd.DataFrame, signal_col: str
    ) -> List[str]:
        """基础未来函数检测"""
        warnings = []
        if signal_col not in df.columns:
            return warnings

        signals = df[signal_col].astype(float)

        # 1. 信号与未来收益高度相关
        future_return = df["close"].pct_change().shift(-1)
        corr = signals.corr(future_return)
        if abs(corr) > 0.8:
            warnings.append(f"⚠️ 信号与次日收益相关系数={corr:.3f}，可能存在未来函数")

        # 2. 信号在涨停日频繁出现
        if "high" in df.columns and "low" in df.columns:
            limit_up = df["high"] == df["low"]
            limit_up_signals = signals[limit_up].abs().sum()
            if limit_up_signals > len(signals) * 0.1:
                warnings.append("⚠️ 大量信号出现在涨跌停日，可能使用了当日不可得信息")

        return warnings

    # ---- 数据校验 ----

    def _validate_data(self, df: pd.DataFrame, signal_col: str) -> List[str]:
        errors = []
        required = ["date", "open", "high", "low", "close", signal_col]
        for col in required:
            if col not in df.columns:
                errors.append(f"缺少必要字段: {col}")
        if df.empty:
            errors.append("回测数据为空")
        if signal_col in df.columns and df[signal_col].nunique() <= 1:
            errors.append("信号列无变化，无法回测")
        return errors

    # ---- 快照持久化 ----

    def _save_snapshot(
        self, sid: str, name: str, cfg: BacktestConfig,
        perf: Dict, signal_count: int, trades: List[Dict],
    ):
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT INTO backtest_snapshot
                       (snapshot_id, name, config_json, performance_json, signal_count)
                       VALUES (?,?,?,?,?)""",
                    (
                        sid, name or sid,
                        json.dumps(cfg.__dict__, ensure_ascii=False, default=str),
                        json.dumps(perf, ensure_ascii=False, default=str),
                        signal_count,
                    ),
                )
                conn.commit()
            logger.info(f"[Backtest] 快照已保存: {sid}")
        except Exception as e:
            logger.warning(f"[Backtest] 快照保存失败: {e}")

    def load_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        """加载历史回测快照"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM backtest_snapshot WHERE snapshot_id=?",
                    (snapshot_id,),
                ).fetchone()
            if row:
                r = dict(row)
                r["config"] = json.loads(r.get("config_json", "{}"))
                r["performance"] = json.loads(r.get("performance_json", "{}"))
                return r
        except Exception as e:
            logger.warning(f"[Backtest] 加载快照失败: {e}")
        return None

    def list_snapshots(self, limit: int = 20) -> List[Dict]:
        """列出回测快照"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT snapshot_id, name, create_time, signal_count "
                    "FROM backtest_snapshot ORDER BY create_time DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def compare_snapshots(self, ids: List[str]) -> Dict[str, Any]:
        """对比多个回测快照"""
        results = {}
        for sid in ids:
            snap = self.load_snapshot(sid)
            if snap:
                results[sid] = {
                    "name": snap.get("name", sid),
                    "total_return": snap["performance"].get("total_return_pct", "?"),
                    "max_drawdown": snap["performance"].get("max_drawdown_pct", "?"),
                    "sharpe": snap["performance"].get("sharpe_ratio", "?"),
                    "win_rate": snap["performance"].get("win_rate_pct", "?"),
                }
        return results

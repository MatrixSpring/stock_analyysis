"""
回测可视化平台 — 滑点/佣金/绩效指标/快照查询
"""

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="回测平台", page_icon="📉", layout="wide")

st.title("📉 策略回测平台")

col1, col2, col3, col4 = st.columns(4)
with col1: commission = st.number_input("佣金率", 0.0001, 0.01, 0.0003, format="%.4f")
with col2: slippage = st.number_input("滑点", 0.0, 0.05, 0.001, format="%.3f")
with col3: stamp_tax = st.number_input("印花税(卖)", 0.0, 0.01, 0.001, format="%.3f")
with col4: init_cap = st.number_input("初始资金", 10000, 10000000, 100000, step=10000)

if st.button("▶ 运行回测", type="primary"):
    try:
        from core.backtest import BacktestEngine, BacktestConfig

        cfg = BacktestConfig(
            commission_rate=commission, slippage_value=slippage,
            stamp_tax_rate=stamp_tax, initial_capital=init_cap,
        )

        np.random.seed(42)
        n = 300
        close = 100 * np.cumprod(1 + np.random.normal(0.0003, 0.012, n))
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=n, freq="B").strftime("%Y-%m-%d"),
            "open": close*0.998, "high": close*1.01,
            "low": close*0.99, "close": close,
        })
        df["ma5"] = df["close"].rolling(5).mean()
        df["ma20"] = df["close"].rolling(20).mean()
        df["signal"] = 0
        df.loc[df["ma5"] > df["ma20"], "signal"] = 1
        df.loc[df["ma5"] < df["ma20"], "signal"] = -1
        df = df.dropna()

        engine = BacktestEngine()
        result = engine.run(df, config=cfg, name=f"回测_{pd.Timestamp.now().strftime('%m%d_%H%M')}")
        perf = result["performance"]

        st.success("回测完成")

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("累计收益", perf["total_return_pct"])
        with c2: st.metric("最大回撤", perf["max_drawdown_pct"])
        with c3: st.metric("夏普比率", f"{perf['sharpe_ratio']:.2f}")
        with c4: st.metric("胜率", perf["win_rate_pct"])

        if result["warnings"]:
            for w in result["warnings"]:
                st.warning(w)

        with st.expander("📋 全部指标"):
            st.json({k: v for k, v in perf.items() if k != "snapshot_id"})

        with st.expander("📂 历史快照"):
            snapshots = engine.list_snapshots(10)
            if snapshots:
                st.dataframe(pd.DataFrame(snapshots), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"回测失败: {e}")

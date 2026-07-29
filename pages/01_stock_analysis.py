"""
个股深度分析 — K线可视化 + 四维量化打分
"""

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="个股分析", page_icon="📈", layout="wide")

st.title("📈 个股深度分析")

code = st.text_input("股票代码", "600519", max_chars=6)
col1, col2, col3 = st.columns(3)
with col1: period = st.selectbox("周期", ["1月", "3月", "6月", "1年"])
with col2: adjust = st.selectbox("复权", ["前复权", "后复权", "不复权"])
with col3: st.button("🔍 开始分析", type="primary")

try:
    from core.quant_score import QuantScorer
    from core.data_adapter import get_data_adapter

    with st.spinner("加载行情数据..."):
        adapter = get_data_adapter()
        df = adapter.get_stock_kline(code, "20260601", "20260729")

    if df is not None and not df.empty:
        scorer = QuantScorer()
        result = scorer.score(df, code=code)

        # K线图表
        st.subheader("📊 K线走势")
        chart_df = pd.DataFrame({
            "date": pd.to_datetime(df["date"]),
            "close": df["close"],
            "ma5": df["close"].rolling(5).mean(),
            "ma20": df["close"].rolling(20).mean(),
        }).dropna()
        st.line_chart(chart_df.set_index("date"), height=300)

        # 四维打分
        st.subheader("🎯 四维量化打分")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("趋势", f"{result.trend_score:.2f}", result.trend_label)
            st.progress(result.trend_score)
        with c2:
            st.metric("资金", f"{result.capital_score:.2f}")
            st.progress(result.capital_score)
        with c3:
            st.metric("估值", f"{result.value_score:.2f}")
            st.progress(result.value_score)
        with c4:
            st.metric("情绪", f"{result.sentiment_score:.2f}")
            st.progress(result.sentiment_score)

        st.metric("综合得分", f"{result.total_score:.2f}")
        st.progress(result.total_score)

        if result.risk_tags:
            st.warning(f"⚠️ 风险提示: {', '.join(result.risk_tags)}")

        with st.expander("📋 详细指标"):
            st.json(result.details)
    else:
        st.info("暂无行情数据，请检查代码或网络")
except Exception as e:
    st.error(f"分析失败: {e}")

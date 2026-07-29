"""
量化异步选股 — 批量扫描 + 任务队列
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="量化选股", page_icon="🔍", layout="wide")

st.title("🔍 量化选股")

col1, col2, col3 = st.columns(3)
with col1: min_score = st.slider("最低综合得分", 0.0, 1.0, 0.3)
with col2: top_n = st.slider("入选数量", 5, 50, 20)
with col3: sector = st.text_input("行业过滤", "", placeholder="留空=全市场")

if st.button("🚀 启动选股", type="primary", use_container_width=True):
    try:
        from core.quant_score import QuantScorer
        from core.stock_selector import StockSelector
        import numpy as np

        with st.spinner("生成模拟选股数据..."):
            stocks_data = {}
            np.random.seed(42)
            for i, code in enumerate(["600519", "000858", "300750", "002475", "601398",
                                        "600036", "000333", "603259", "600809", "002594"]):
                close = 100 * np.cumprod(1 + np.random.normal(0.0005, 0.015, 200))
                df = pd.DataFrame({
                    "date": pd.date_range("2026-01-01", periods=200, freq="B"),
                    "open": close*0.998, "high": close*1.01,
                    "low": close*0.99, "close": close,
                    "volume": np.random.randint(100000, 1000000, 200),
                })
                stocks_data[code] = df

        selector = StockSelector()
        results = selector.screen(
            stocks_data, top_n=top_n, min_score=min_score,
            name_map={
                "600519": "贵州茅台", "000858": "五粮液", "300750": "宁德时代",
                "002475": "立讯精密", "601398": "工商银行", "600036": "招商银行",
                "000333": "美的集团", "603259": "药明康德", "600809": "山西汾酒",
                "002594": "比亚迪",
            },
        )

        if results:
            st.success(f"选出 {len(results)} 只标的")
            df_result = pd.DataFrame([{
                "排名": r.rank, "代码": r.code, "名称": r.name,
                "综合得分": r.total_score, "趋势": r.trend_score,
                "资金": r.capital_score, "估值": r.value_score,
                "情绪": r.sentiment_score, "标签": ", ".join(r.tags),
            } for r in results])
            st.dataframe(df_result, use_container_width=True, hide_index=True)
        else:
            st.info("无标的满足条件，请降低筛选门槛")
    except Exception as e:
        st.error(f"选股失败: {e}")

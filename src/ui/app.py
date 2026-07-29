"""
DSA 量化投研系统 — Streamlit 入口
启动: streamlit run src/ui/app.py
"""

import streamlit as st
from src.config.settings import ARK_MODEL

st.set_page_config(
    page_title="DSA 量化投研系统",
    page_icon="📊",
    layout="wide",
)

st.sidebar.title("📊 DSA 量化平台")
st.sidebar.caption(f"LLM: 豆包 {ARK_MODEL}")

# 导航
page = st.sidebar.radio(
    "导航",
    ["🏠 首页", "📈 个股分析", "💹 资金博弈", "🧠 产业链脑图", "🤖 AI 助手"],
    index=0,
)

if page == "🏠 首页":
    st.title("DSA 量化投研系统")
    st.markdown("""
    ### 工业化分层架构 (UI ← Service ← DB/LLM)

    | 层级 | 职责 | 技术 |
    |------|------|------|
    | **UI** | 页面渲染、用户交互 | Streamlit / React |
    | **Service** | 业务逻辑、指标计算 | Python |
    | **DB** | 原始数据存取 (纯 CRUD) | SQLite |
    | **LLM** | AI 分析、自然语言理解 | 豆包 API + DeepSeek 备用 |

    **当前状态**: 豆包 API ✅ | 产业链脑图 ✅ | 资金博弈 ✅ | 多模型共识 ✅
    """)

elif page == "📈 个股分析":
    st.title("📈 个股分析")
    code = st.text_input("股票代码", "600519")
    if st.button("分析", type="primary"):
        with st.spinner("分析中..."):
            from src.service.stock_service import get_stock_service
            svc = get_stock_service()
            result = svc.get_analysis(code)
            st.metric("股票", result.stock_code)
            if result.ai_comment:
                st.info(result.ai_comment)
            if result.risk_signals:
                for r in result.risk_signals:
                    st.warning(r)
            if result.kline_data:
                st.dataframe([{
                    "日期": b.date, "收盘": b.close, "涨跌%": b.pct_chg,
                    "MA5": b.ma5, "MA10": b.ma10, "MA20": b.ma20,
                } for b in result.kline_data[-10:]], hide_index=True)

elif page == "🤖 AI 助手":
    st.title("🤖 AI 分析助手")
    query = st.text_area("输入你的问题", placeholder="如：帮我分析最近北上资金动向...")
    if st.button("提问", type="primary", disabled=not query):
        with st.spinner("豆包思考中..."):
            from src.service.llm_analysis_service import get_llm_service
            result = get_llm_service().chat(query, professional=True)
            if result.success:
                st.success(result.content)
                st.caption(f"模型: {result.model_used} | 耗时: {result.latency_ms:.0f}ms")
            else:
                st.error(result.error)

else:
    st.info("此页面请通过侧边栏导航访问")

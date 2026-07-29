"""
DSA 量化投研系统 — 首页导航
启动: streamlit run Home.py
"""

import streamlit as st

st.set_page_config(
    page_title="DSA 量化投研系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp { background: #0a0e17; }
h1 { color: #38bdf8 !important; }
.sidebar .sidebar-content { background: #111827; }
</style>
""", unsafe_allow_html=True)

st.title("📊 DSA 量化投研系统")
st.caption("Multi-Market AI-Driven Quantitative Research Platform")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("📈 个股分析", "K线 + 量化打分", help="01_stock_analysis")
    st.metric("🔍 量化选股", "批量异步筛选", help="02_quant_screen")
with col2:
    st.metric("📉 回测平台", "滑点/佣金/绩效指标", help="03_backtest_panel")
    st.metric("🤖 AI 研判", "多模型共识分析", help="04_llm_consensus")
with col3:
    st.metric("🔗 产业链图谱", "力导向拓扑图", help="05_industry_map")
    st.metric("🖥 系统监控", "资源/任务/接口", help="06_system_monitor")

st.markdown("---")
st.info("👈 使用左侧边栏导航切换功能页面")

# 系统状态快照
try:
    from core.system_monitor import get_monitor_info
    info = get_monitor_info()
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("数据源", f"{len(info.get('datasource_status',{}))}个")
    with c2: st.metric("LLM 模型", f"{len(info.get('llm_model_status',{}))}个")
    with c3: st.metric("运行时长", f"{info.get('uptime_seconds',0)//3600}h")
    with c4: st.metric("任务统计", f"{info.get('task_stat',{}).get('success',0)}成功")
except Exception:
    pass

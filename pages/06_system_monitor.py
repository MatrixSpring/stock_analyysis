"""
系统监控面板 — 数据源/LLM/任务/资源
"""

import streamlit as st
import time

st.set_page_config(page_title="系统监控", page_icon="🖥", layout="wide")

st.title("🖥 系统监控面板")

if st.button("🔄 刷新", use_container_width=True):
    st.rerun()

try:
    from core.system_monitor import get_monitor_info
    from core.llm_engine import get_llm_engine
    from core.task_queue import get_task_queue

    info = get_monitor_info()

    # 顶部指标
    c1, c2, c3, c4 = st.columns(4)
    uptime_h = info.get("uptime_seconds", 0) // 3600
    with c1: st.metric("运行时长", f"{uptime_h}h")
    with c2: st.metric("最后刷新", time.strftime("%H:%M", time.localtime(info.get("last_refresh", 0))))
    with c3:
        ds_ok = sum(1 for s in info.get("datasource_status", {}).values() if s.get("status") == "ok")
        ds_total = len(info.get("datasource_status", {}))
        st.metric("数据源", f"{ds_ok}/{ds_total} 正常")
    with c4:
        task_stat = info.get("task_stat", {})
        st.metric("任务", f"{task_stat.get('success', 0)}成功 / {task_stat.get('fail', 0)}失败")

    # 数据源状态
    st.subheader("🔌 数据源状态")
    ds_data = []
    for name, s in info.get("datasource_status", {}).items():
        ds_data.append({
            "数据源": name,
            "状态": "✅ 正常" if s.get("status") == "ok" else "❌ 异常",
            "信息": s.get("msg", "")[:50],
        })
    if ds_data:
        st.dataframe(ds_data, use_container_width=True, hide_index=True)
    else:
        st.caption("后台收集中...")

    # LLM 状态
    st.subheader("🤖 LLM 模型状态")
    try:
        engine = get_llm_engine()
        llm_stats = engine.get_stats()
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("调用次数", llm_stats.get("call_count", 0))
        with c2: st.metric("成功率", f"{llm_stats.get('success_rate', 0)*100:.0f}%")
        with c3: st.metric("缓存命中", llm_stats.get("cache_hits", 0))
        with c4: st.metric("Token 消耗", f"{llm_stats.get('total_tokens', 0):,}")
    except Exception:
        st.caption("LLM 引擎未初始化")

    # 任务队列
    st.subheader("📋 任务队列")
    try:
        tq = get_task_queue()
        tq_stats = tq.get_stats()
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.metric("总数", tq_stats.get("total", 0))
        with c2: st.metric("排队", tq_stats.get("pending", 0))
        with c3: st.metric("运行中", tq_stats.get("running", 0))
        with c4: st.metric("成功", tq_stats.get("success", 0))
        with c5: st.metric("失败", tq_stats.get("failed", 0))
    except Exception:
        st.caption("任务队列未启用（需 Redis）")

    # 系统资源
    st.subheader("💻 系统资源")
    sys_info = info.get("system_info", {})
    if sys_info and "note" not in sys_info:
        c1, c2, c3 = st.columns(3)
        with c1:
            cpu = sys_info.get("cpu_percent", 0)
            st.metric("CPU", f"{cpu}%")
            st.progress(cpu / 100)
        with c2:
            mem = sys_info.get("memory_percent", 0)
            st.metric("内存", f"{mem}%")
            st.progress(mem / 100)
        with c3:
            disk = sys_info.get("disk_percent", 0)
            st.metric("磁盘", f"{disk}%")
            st.progress(disk / 100)
    else:
        st.caption("psutil 未安装，无法采集系统资源 (pip install psutil)")

except Exception as e:
    st.error(f"监控加载失败: {e}")

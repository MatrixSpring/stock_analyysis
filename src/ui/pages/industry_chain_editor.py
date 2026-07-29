"""
产业链节点编辑器 — Streamlit + ECharts 交互式编辑
功能：节点拖拽排序 / 添加删除 / 外部事件输入 / 传导热力图
"""

from __future__ import annotations

import json
import streamlit as st
from datetime import datetime

from src.service.industry_chain_service import (
    ChainNode,
    ExternalEvent,
    get_chain_service,
)

svc = get_chain_service()

st.set_page_config(page_title="产业链编辑器", page_icon="🧠", layout="wide")

# ============================================================
# ECharts 编辑模式 HTML
# ============================================================

EDITOR_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>*{margin:0;padding:0}#chart{width:100%;height:100%;background:#0a0e17}</style>
</head><body><div id="chart"></div><script>
const treeData = __CHAIN_DATA__;
const impacts = __IMPACT_DATA__;

const c = echarts.init(document.getElementById('chart'));

// 热力着色：影响力越高颜色越深
function heatColor(impact) {
    if (!impact || impact === 0) return '#64748B';
    const abs = Math.abs(impact);
    if (abs > 6) return impact > 0 ? '#22c55e' : '#ef4444';
    if (abs > 3) return impact > 0 ? '#86efac' : '#fca5a5';
    return impact > 0 ? '#bbf7d0' : '#fecaca';
}

// 注入影响力到节点
function injectImpacts(node) {
    const hit = impacts.find(i => i.node_name === node.name || i.node_id === node.id);
    if (hit) {
        node.itemStyle = {color: heatColor(hit.final_impact)};
        node.label = {formatter: '{b}\\n↓' + hit.final_impact.toFixed(1), fontSize: 11};
    }
    (node.children || []).forEach(injectImpacts);
}
injectImpacts(treeData);

c.setOption({
    tooltip: {
        trigger:'item',
        formatter: function(p) {
            const s = p.data.stocks || [];
            const hit = impacts.find(i => i.node_name === p.name);
            let tip = '<b>' + p.name + '</b>';
            if (hit) tip += '<br/>影响力: ' + hit.final_impact.toFixed(1) + ' (距离' + hit.distance + '层)';
            if (s.length) tip += '<br/>成分股: ' + s.join(', ');
            return tip;
        }
    },
    series:[{
        type:'tree', data:[treeData],
        top:'5%', left:'5%', bottom:'5%', right:'5%',
        symbol:'roundRect', symbolSize:12,
        orient:'LR', expandAndCollapse:true,
        initialTreeDepth:4,
        label:{position:'right',verticalAlign:'middle',align:'left',fontSize:12,color:'#e2e8f0'},
        lineStyle:{color:'rgba(148,163,184,0.3)',width:2,curveness:0.5},
        emphasis:{focus:'descendant',lineStyle:{color:'#f472b6',width:3}},
    }],
});

c.on('click', function(p) {
    window.parent.postMessage({
        type:'node_click',
        node_id: p.data.id || '',
        node_name: p.name,
        stocks: p.data.stocks || [],
        segment: p.data.segment || '',
    }, '*');
});

window.addEventListener('resize', () => c.resize());
</script></body></html>
"""

# ============================================================
# Streamlit 页面
# ============================================================

st.title("🧠 产业链节点编辑器")
st.caption("业界方案：ECharts tree + BFS 传导引擎 + LLM 事件解析 → 对标同花顺 iFinD 产业链模块")

# 侧边栏
with st.sidebar:
    st.header("📋 产业链列表")
    chains = svc.list_chains()
    if not chains:
        if st.button("➕ 新建产业链"):
            svc.create_chain("新产业链")
            st.rerun()
    else:
        selected_chain = st.selectbox("选择", chains, key="chain_select")

    st.divider()
    st.header("🔧 操作")
    new_chain_name = st.text_input("新建产业链名称", placeholder="输入名称")

col_main, col_side = st.columns([3, 1])

with col_main:
    if chains:
        chain = svc.load_chain(selected_chain)
        st.subheader(f"📊 {selected_chain}")

        # 渲染 ECharts 树图
        tree_data = svc.export_eCharts_data(selected_chain)
        # 检查是否有缓存的 impact 数据
        impact_data = st.session_state.get("last_impact", [])
        html = EDITOR_HTML.replace("__CHAIN_DATA__", json.dumps(tree_data, ensure_ascii=False))
        html = html.replace("__IMPACT_DATA__", json.dumps(impact_data, ensure_ascii=False))
        st.components.v1.html(html, height=520, scrolling=False)

        # 节点列表
        st.divider()
        st.subheader("📝 节点列表")
        nodes = chain.get("nodes", {})
        if nodes:
            col_h1, col_h2, col_h3 = st.columns(3)
            segments = {"upstream": "🔵 上游", "midstream": "🟡 中游", "downstream": "🟢 下游"}
            for seg, label in segments.items():
                seg_nodes = {k: v for k, v in nodes.items() if v.get("segment") == seg}
                st.caption(f"{label} ({len(seg_nodes)}个)")
                for nid, n in list(seg_nodes.items())[:5]:
                    st.text(f"  • {n['name']} — 成分股: {', '.join(n.get('stock_codes', []))}")

with col_side:
    st.header("➕ 添加节点")
    with st.form("add_node"):
        node_name = st.text_input("节点名称")
        node_segment = st.selectbox("区段", ["upstream", "midstream", "downstream"])
        node_stocks = st.text_input("成分股（逗号分隔）", placeholder="600519,000858")
        node_weight = st.slider("权重", 0.5, 3.0, 1.0, 0.1)
        if st.form_submit_button("添加", type="primary"):
            node = ChainNode(
                id=f"node_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                name=node_name,
                segment=node_segment,
                stock_codes=[s.strip() for s in node_stocks.split(",") if s.strip()],
                weight=node_weight,
            )
            svc.add_node(selected_chain, node)
            st.rerun()

    st.divider()
    st.header("⚡ 外部事件影响")
    with st.form("ext_event"):
        event_title = st.text_input("事件标题", placeholder="如：硅料上涨20%")
        event_direction = st.selectbox("方向", ["positive", "negative"])
        event_strength = st.slider("强度", 1, 10, 5)
        event_radius = st.selectbox("传导层级", [1, 2, 3], index=1)
        event_decay = st.slider("衰减率", 0.1, 0.5, 0.2, 0.05)
        if st.form_submit_button("⚡ 计算传导", type="primary"):
            all_nodes = list(chain.get("nodes", {}).keys())
            if all_nodes:
                event = ExternalEvent(
                    event_id=f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    title=event_title,
                    direction=event_direction,
                    impact_strength=event_strength,
                    target_nodes=all_nodes[:5],  # 默认目标：前5个节点
                    impact_radius=event_radius,
                    decay_rate=event_decay,
                )
                results = svc.calculate_event_impact(selected_chain, event)
                st.session_state["last_impact"] = [
                    {
                        "node_id": r.node_id,
                        "node_name": r.node_name,
                        "final_impact": r.final_impact,
                        "distance": r.distance,
                    }
                    for r in results
                ]
                st.success(f"传导完成：{len(results)} 个节点受影响")
                st.rerun()

    # 删除节点
    st.divider()
    st.header("🗑️ 删除节点")
    nodes = chain.get("nodes", {})
    if nodes:
        del_target = st.selectbox("选择要删除的节点", list(nodes.keys()),
                                   format_func=lambda x: nodes[x]["name"])
        if st.button("确认删除", type="secondary"):
            svc.delete_node(selected_chain, del_target)
            st.rerun()

    # LLM 自动解析
    st.divider()
    st.header("🤖 LLM 自动解析")
    event_text = st.text_area("事件描述", placeholder="粘贴新闻，AI 自动识别影响节点和强度...")
    if st.button("AI 解析", disabled=not event_text):
        with st.spinner("豆包分析中..."):
            from src.llm import llm_client
            prompt = f"""分析以下事件对产业链的影响，返回JSON:
事件: {event_text}
产业链节点: {json.dumps(list(nodes.keys())[:10], ensure_ascii=False)}
输出: {{"affected_nodes":["节点ID"],"direction":"positive|negative","strength":1-10,"summary":""}}"""
            res = llm_client.chat(prompt, system_prompt="你是产业链分析专家。只返回纯净JSON。")
            if res.content:
                try:
                    parsed = json.loads(res.content)
                    st.json(parsed)
                except json.JSONDecodeError:
                    st.text(res.content[:300])

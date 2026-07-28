# -*- coding: utf-8 -*-
"""
===================================
三栏主工作台 — pages/main_workspace.py
===================================

左侧栏 (30%): 事件输入池 + 审核工作台
中间栏 (40%): 交互式产业链传导图谱 (ECharts iframe)
右侧栏 (30%): 五大状态实时面板

所有数据从 GlobalState 统一读取，保证一处变更全界面同步。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List

import streamlit as st

from core.global_state import GlobalState, EventItem
from core.event_analyzer import EventAnalyzer
from core.message_bus import MessageBus, JS_MESSAGE_BUS_TEMPLATE

logger = logging.getLogger(__name__)

# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="DSA 投研工作台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 自定义 CSS：三栏固定布局 + 暗色主题
st.markdown("""
<style>
/* 全局暗色主题 */
.stApp { background: #0a0e17; color: #e2e8f0; }

/* 三栏布局 */
.main-workspace {
    display: flex;
    gap: 12px;
    height: calc(100vh - 80px);
    padding: 8px;
}
.col-left, .col-mid, .col-right {
    border-radius: 10px;
    overflow-y: auto;
    padding: 12px;
}
.col-left { flex: 0 0 28%; background: #111827; }
.col-mid  { flex: 0 0 44%; background: #0d1117; }
.col-right { flex: 0 0 28%; background: #111827; }

/* 区块标题 */
.section-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e293b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* 事件卡片 */
.event-card {
    padding: 8px 10px;
    margin: 4px 0;
    border-radius: 6px;
    border: 1px solid #1e293b;
    font-size: 0.82rem;
    cursor: pointer;
    transition: all 0.2s;
}
.event-card:hover { border-color: #38bdf8; background: #1a2332; }
.event-card.active { border-color: #38bdf8; background: #172033; }

/* 状态标签 */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
}
.badge-positive { background: #065f46; color: #6ee7b7; }
.badge-negative { background: #7f1d1d; color: #fca5a5; }
.badge-neutral  { background: #334155; color: #cbd5e1; }
.badge-pending  { background: #713f12; color: #fcd34d; }
.badge-confirmed { background: #064e3b; color: #6ee7b7; }
.badge-invalid  { background: #3f3f46; color: #a1a1aa; }

/* 面板 */
.panel-block {
    background: #0d1117;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 10px;
    margin-bottom: 8px;
}
.panel-block h4 {
    margin: 0 0 6px 0;
    font-size: 0.85rem;
    color: #e2e8f0;
}
.panel-value {
    font-size: 1.1rem;
    font-weight: 700;
    color: #38bdf8;
}
.panel-detail {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 2px;
}

/* iframe 容器 */
.iframe-container {
    width: 100%;
    height: calc(100vh - 200px);
    border: 1px solid #1e293b;
    border-radius: 8px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 初始化全局状态
# ============================================================

def _init_session():
    """初始化 session_state 中的全局引用"""
    if "global_state" not in st.session_state:
        st.session_state.global_state = GlobalState.get_instance()
    if "event_analyzer" not in st.session_state:
        st.session_state.event_analyzer = EventAnalyzer()
    if "message_bus" not in st.session_state:
        st.session_state.message_bus = MessageBus()
    if "active_event_id" not in st.session_state:
        st.session_state.active_event_id = None

_init_session()
gs: GlobalState = st.session_state.global_state
analyzer: EventAnalyzer = st.session_state.event_analyzer
bus: MessageBus = st.session_state.message_bus


# ============================================================
# 页面头部
# ============================================================

st.markdown("""
<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;
            border-bottom:1px solid #1e293b;margin-bottom:8px;">
    <div>
        <span style="font-size:1.2rem;font-weight:800;color:#38bdf8;">📊 DSA 投研工作台</span>
        <span style="font-size:0.75rem;color:#64748b;margin-left:12px;">产业链传导仿真 · 多因子联动</span>
    </div>
    <div>
        <span style="font-size:0.75rem;color:#64748b;">
            待审核: <b style="color:#fcd34d;">{pending}</b> &nbsp;
            已确认: <b style="color:#6ee7b7;">{confirmed}</b>
        </span>
    </div>
</div>
""".format(
    pending=len(gs.get_pending_events()),
    confirmed=len(gs.get_confirmed_events()),
), unsafe_allow_html=True)


# ============================================================
# 三栏布局
# ============================================================

col_left, col_mid, col_right = st.columns([28, 44, 28])


# ============================================================
# 左栏：事件输入 + 事件列表 + 审核控制
# ============================================================

with col_left:

    # --- 新闻输入区 ---
    st.markdown('<div class="section-title">📰 事件输入</div>', unsafe_allow_html=True)

    news_text = st.text_area(
        "粘贴新闻/政策/公告/纪要",
        height=120,
        placeholder="例如：据供应链消息，苹果上调Q3 iPhone新机订单指引...",
        label_visibility="collapsed",
        key="news_input",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        parse_btn = st.button("🔍 启动影响解析", use_container_width=True, type="primary")
    with c2:
        uploaded_file = st.file_uploader(
            "📎 PDF/截图",
            type=["pdf", "png", "jpg", "jpeg"],
            label_visibility="collapsed",
            key="file_uploader",
        )

    if parse_btn and news_text.strip():
        with st.spinner("LLM 解析中..."):
            result = analyzer.parse_news(news_text.strip())
            if result["success"]:
                st.session_state.active_event_id = result["event_id"]
                st.success(f"✅ 解析完成 — {result['link_count']} 条传导链路已生成")
                st.rerun()
            else:
                st.error(f"❌ 解析失败: {result['error']}")

    if uploaded_file is not None:
        st.info("📎 文件已上传，OCR 解析功能开发中...")

    st.markdown("---")

    # --- 事件列表 ---
    st.markdown('<div class="section-title">📋 事件列表</div>', unsafe_allow_html=True)

    all_events = list(gs.events.values())
    all_events.sort(key=lambda e: e.created_at, reverse=True)

    if not all_events:
        st.markdown(
            '<div style="color:#64748b;font-size:0.8rem;text-align:center;padding:20px;">'
            '暂无事件，请粘贴新闻启动解析</div>',
            unsafe_allow_html=True,
        )

    for event in all_events:
        # 方向图标和颜色
        dir_icon = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(event.direction, "⚪")
        status_badge = {
            "pending": '<span class="badge badge-pending">待审核</span>',
            "confirmed": '<span class="badge badge-confirmed">已生效</span>',
            "invalid": '<span class="badge badge-invalid">废弃</span>',
        }.get(event.audit_status, "")

        is_active = st.session_state.active_event_id == event.event_id
        active_class = "active" if is_active else ""

        st.markdown(f"""
        <div class="event-card {active_class}" id="event-{event.event_id}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span>{dir_icon} <b>{event.title[:30]}</b></span>
                {status_badge}
            </div>
            <div style="color:#64748b;font-size:0.7rem;margin-top:4px;">
                {event.source_type} · 强度 {event.strength}/10 · {event.created_at[:16]}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 操作按钮
        ec1, ec2, ec3 = st.columns([1, 1, 1])
        with ec1:
            if st.button("📊 查看图谱", key=f"view_{event.event_id}", use_container_width=True):
                st.session_state.active_event_id = event.event_id
                st.rerun()
        with ec2:
            if event.audit_status == "pending":
                if st.button("✅ 确认", key=f"confirm_{event.event_id}", use_container_width=True):
                    analyzer.confirm_event(event.event_id)
                    st.rerun()
        with ec3:
            if st.button("🗑 废弃", key=f"invalid_{event.event_id}", use_container_width=True):
                analyzer.invalidate_event(event.event_id)
                st.rerun()

    st.markdown("---")

    # --- 审核控制面板 ---
    st.markdown('<div class="section-title">🔧 审核控制台</div>', unsafe_allow_html=True)

    active_event_id = st.session_state.active_event_id
    if active_event_id and active_event_id in gs.events:
        event = gs.events[active_event_id]

        # 冲击强度滑块
        new_strength = st.slider(
            "冲击强度",
            min_value=1, max_value=10,
            value=event.strength,
            key=f"strength_{active_event_id}",
        )
        if new_strength != event.strength:
            gs.update_event(active_event_id, strength=new_strength)

        # 影响周期
        cycle_options = ["short", "middle", "long"]
        cycle_labels = ["短期 (1~5日)", "中期 (6~20日)", "长期 (20日+)"]
        current_cycle = cycle_options.index(event.time_cycle) if event.time_cycle in cycle_options else 1
        new_cycle = st.selectbox(
            "影响周期",
            options=cycle_options,
            index=current_cycle,
            format_func=lambda x: cycle_labels[cycle_options.index(x)],
            key=f"cycle_{active_event_id}",
        )
        if new_cycle != event.time_cycle:
            gs.update_event(active_event_id, time_cycle=new_cycle)

        # 链路编辑
        st.markdown("**传导链路编辑**")
        for lid in event.transfer_links:
            if lid in gs.transfer_links:
                link = gs.transfer_links[lid]
                from_n = gs.industry_nodes.get(link.from_node)
                to_n = gs.industry_nodes.get(link.to_node)
                from_name = from_n.name if from_n else "?"
                to_name = to_n.name if to_n else "?"

                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.caption(f"{from_name} → {to_name}")
                with col_b:
                    new_link_strength = st.slider(
                        f"{from_name}→{to_name}",
                        min_value=1, max_value=10,
                        value=int(link.strength),
                        label_visibility="collapsed",
                        key=f"link_str_{lid}",
                    )
                    if new_link_strength != link.strength:
                        gs.update_transfer_link(lid, strength=new_link_strength)

        # 审核备注
        audit_note = st.text_area(
            "审核备注",
            value=event.parsed_json.get("audit_note", ""),
            height=60,
            key=f"audit_note_{active_event_id}",
        )

        # 审核操作
        ac1, ac2 = st.columns(2)
        with ac1:
            if st.button("✅ 审核通过", use_container_width=True, type="primary",
                         disabled=event.audit_status != "pending"):
                analyzer.confirm_event(active_event_id)
                st.rerun()
        with ac2:
            if st.button("❌ 驳回结论", use_container_width=True,
                         disabled=event.audit_status != "pending"):
                analyzer.invalidate_event(active_event_id)
                st.rerun()

    else:
        st.markdown(
            '<div style="color:#64748b;font-size:0.8rem;text-align:center;padding:20px;">'
            '选择左侧事件卡片以加载审核面板</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# 中栏：产业链传导图谱 (ECharts iframe)
# ============================================================

with col_mid:
    st.markdown('<div class="section-title">🔗 产业链传导图谱</div>', unsafe_allow_html=True)

    # 构建图谱数据
    nodes_data = []
    links_data = []
    active_event = gs.events.get(st.session_state.active_event_id) if st.session_state.active_event_id else None

    if active_event:
        related_node_ids = set()
        for lid in active_event.transfer_links:
            if lid in gs.transfer_links:
                link = gs.transfer_links[lid]
                related_node_ids.add(link.from_node)
                related_node_ids.add(link.to_node)

        # 包含事件源节点
        for nid in list(gs.industry_nodes.keys()):
            node = gs.industry_nodes[nid]
            if nid in related_node_ids or node.node_type == "event":
                nodes_data.append({
                    "id": nid,
                    "name": node.name,
                    "type": node.node_type,
                    "symbolSize": 50 if node.node_type == "event" else 35,
                })

        for lid in active_event.transfer_links:
            if lid in gs.transfer_links:
                link = gs.transfer_links[lid]
                color = "#22c55e" if link.direction == "positive" else "#ef4444"
                if link.audit_status == "pending":
                    color = "#64748b"  # 灰色预览
                links_data.append({
                    "source": link.from_node,
                    "target": link.to_node,
                    "label": link.logic_text[:20],
                    "lineStyle": {
                        "color": color,
                        "width": max(1, link.strength / 2),
                    },
                    "strength": link.strength,
                    "direction": link.direction,
                    "link_id": lid,
                })

    chain_html = _build_echarts_iframe(nodes_data, links_data)
    st.components.v1.html(chain_html, height=600, scrolling=False)

    # 图例
    st.caption("🟢 利好传导 | 🔴 利空传导 | ⚫ 灰色=待审核 | 线宽=强度")


# ============================================================
# 右栏：五大状态面板
# ============================================================

with col_right:
    _render_state_panels(gs)


# ============================================================
# 工具函数
# ============================================================

def _build_echarts_iframe(nodes: list, links: list) -> str:
    """构建 ECharts 传导图谱 iframe HTML"""
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    links_json = json.dumps(links, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#0d1117;overflow:hidden}}
  #chart{{width:100%;height:100vh}}
</style></head><body>
<div id="chart"></div>
<script>
{JS_MESSAGE_BUS_TEMPLATE}
const chart = echarts.init(document.getElementById('chart'));
const nodes = {nodes_json};
const links = {links_json};

const option = {{
  backgroundColor: '#0d1117',
  tooltip: {{
    formatter: function(p) {{
      if (p.dataType === 'edge') {{
        return '<b>' + (p.data.label || '') + '</b><br/>' +
               '强度: ' + (p.data.strength || '?') + '/10<br/>' +
               '方向: ' + (p.data.direction || '?');
      }}
      return '<b>' + p.name + '</b>';
    }}
  }},
  animation: true,
  series: [{{
    type: 'graph',
    layout: 'force',
    force: {{ repulsion: 300, edgeLength: [120, 280], gravity: 0.1 }},
    roam: true,
    draggable: true,
    data: nodes,
    links: links,
    edgeSymbol: ['none', 'arrow'],
    edgeSymbolSize: [0, 12],
    emphasis: {{ focus: 'adjacency' }},
    categories: [
      {{ name: '事件源头', itemStyle: {{ color: '#f59e0b' }} }},
      {{ name: '上市公司', itemStyle: {{ color: '#3b82f6' }} }},
      {{ name: '上游企业', itemStyle: {{ color: '#22c55e' }} }},
      {{ name: '下游客户', itemStyle: {{ color: '#f97316' }} }}
    ],
    label: {{ show: true, fontSize: 10, color: '#e2e8f0' }},
    lineStyle: {{ curveness: 0.2, opacity: 0.7 }},
  }}]
}};

// 按节点 type 映射到 category
nodes.forEach(function(n) {{
  var catMap = {{ event:0, company:1, upstream:2, downstream:3 }};
  n.category = catMap[n.type] !== undefined ? catMap[n.type] : 1;
}});

chart.setOption(option);

// 双击连线：通过 MessageBus 通知 Streamlit 编辑
chart.on('dblclick', function(params) {{
  if (params.dataType === 'edge' && params.data && params.data.link_id) {{
    MessageBus.send('edit_link', {{ link_id: params.data.link_id }});
  }}
}});

// 窗口自适应
window.addEventListener('resize', function() {{ chart.resize(); }});

// 监听来自后端的图谱更新
MessageBus.on('update_graph', function(payload) {{
  if (payload.nodes) {{ option.series[0].data = payload.nodes; }}
  if (payload.links) {{ option.series[0].links = payload.links; }}
  chart.setOption(option, true);
}});
</script></body></html>"""


def _render_state_panels(gs: GlobalState):
    """渲染右侧五大状态面板"""
    st.markdown('<div class="section-title">📊 状态面板</div>', unsafe_allow_html=True)

    # 当前聚焦标的
    focus_code = gs.focus_stock_code or next(iter(gs.stock_state.keys()), None)
    stock = gs.get_stock(focus_code) if focus_code else None

    # 📈 股票状态面板
    with st.expander("📈 股票状态", expanded=True):
        if stock and stock.name:
            st.markdown(f"""
            <div class="panel-block">
                <h4>{stock.name} ({stock.code})</h4>
                <div class="panel-value">支撑: {stock.support_price} | 压力: {stock.resistance_price}</div>
                <div class="panel-detail">趋势: {stock.trend} | 波动率: {stock.volatility}%</div>
                <div class="panel-detail">乐观: {stock.optimistic_target} | 基准: {stock.base_target} | 悲观: {stock.pessimistic_target}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("选择标的以查看详情")

    # 💰 资金博弈面板
    with st.expander("💰 资金博弈 & 资金压力", expanded=False):
        cap = gs.capital_state
        risk_color = {"low": "#22c55e", "mid": "#f59e0b", "high": "#ef4444"}.get(cap.margin_risk_level, "#64748b")
        st.markdown(f"""
        <div class="panel-block">
            <div>融资风险: <b style="color:{risk_color}">{cap.margin_risk_level}</b></div>
            <div>北向情绪: <b>{cap.north_bound_sentiment}</b></div>
            <div>筹码集中度: <b>{cap.chip_concentration}</b></div>
            <div>资金流向: <b>{cap.sector_flow}</b></div>
            <div>平仓压力: <b>{cap.liquidation_pressure:.1%}</b></div>
        </div>
        """, unsafe_allow_html=True)

    # 🏭 产业链状态面板
    with st.expander("🏭 产业链状态", expanded=False):
        node_count = len(gs.industry_nodes)
        link_count = len(gs.transfer_links)
        st.markdown(f"""
        <div class="panel-block">
            <div>节点: <b>{node_count}</b> | 传导链路: <b>{link_count}</b></div>
        </div>
        """, unsafe_allow_html=True)
        for nid, node in list(gs.industry_nodes.items())[:10]:
            type_icon = {"event": "🟡", "company": "🔵", "upstream": "🟢", "downstream": "🟠"}.get(node.node_type, "⚪")
            st.caption(f"{type_icon} {node.name}")

    # 🧠 预期状态面板
    with st.expander("🧠 市场预期", expanded=False):
        exp = gs.expect_state
        st.markdown(f"""
        <div class="panel-block">
            <div>景气度: <b>{exp.prosperity_stage}</b></div>
            <div>预期修正: <b>{exp.estimate_revision}</b></div>
            <div>市场分歧: <b>{exp.divergence_level}</b></div>
            <div class="panel-detail">{exp.valuation_narrative}</div>
        </div>
        """, unsafe_allow_html=True)

    # 📋 推演汇总面板
    with st.expander("📋 推演汇总", expanded=True):
        pending_count = len(gs.get_pending_events())
        confirmed_count = len(gs.get_confirmed_events())
        st.markdown(f"""
        <div class="panel-block">
            <div>待审核事件: <b style="color:#fcd34d;">{pending_count}</b></div>
            <div>已生效事件: <b style="color:#6ee7b7;">{confirmed_count}</b></div>
            <hr style="border-color:#1e293b;margin:6px 0;">
        </div>
        """, unsafe_allow_html=True)

        # 显示已生效事件的影响
        for event in gs.get_confirmed_events()[:5]:
            dir_icon = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(event.direction, "⚪")
            st.caption(f"{dir_icon} {event.title[:40]} — 强度 {event.strength}/10")

        if pending_count + confirmed_count == 0:
            st.caption("暂无事件数据")

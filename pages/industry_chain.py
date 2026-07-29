"""
产业链三区脑图 — ECharts 交互式可视化
启动: streamlit run Home.py → 侧边栏选择「产业链脑图」
"""

from __future__ import annotations

import json
import streamlit as st
from core.industry_graph import get_industry_engine

st.set_page_config(page_title="产业链脑图", page_icon="🧠", layout="wide")

engine = get_industry_engine()

# ============================================================
# HTML Template: ECharts Mind Map
# ============================================================

MINDMAP_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <style>
        * { margin: 0; padding: 0; }
        #chart { width: 100vw; height: 100vh; background: #0a0e17; }
    </style>
</head>
<body>
    <div id="chart"></div>
    <script>
        const data = __CHAIN_DATA__;

        // 三区配色：上游(蓝) → 中游(金) → 下游(绿)
        const colorMap = {
            upstream: '#38bdf8',
            midstream: '#fbbf24',
            downstream: '#34d399'
        };

        // 构建 ECharts 树图数据
        function buildTreeData(chain) {
            const children = [];

            // 上游
            if (chain.upstream && chain.upstream.length) {
                children.push({
                    name: '上游供给',
                    itemStyle: { color: colorMap.upstream },
                    children: chain.upstream.map(n => ({
                        name: n,
                        itemStyle: { color: colorMap.upstream },
                        symbolSize: 8,
                        stocks: (chain.key_stocks || {})[n] || [],
                    }))
                });
            }

            // 中游
            if (chain.midstream && chain.midstream.length) {
                children.push({
                    name: '中游制造',
                    itemStyle: { color: colorMap.midstream },
                    children: chain.midstream.map(n => ({
                        name: n,
                        itemStyle: { color: colorMap.midstream },
                        symbolSize: 8,
                        stocks: (chain.key_stocks || {})[n] || [],
                    }))
                });
            }

            // 下游
            if (chain.downstream && chain.downstream.length) {
                children.push({
                    name: '下游应用',
                    itemStyle: { color: colorMap.downstream },
                    children: chain.downstream.map(n => ({
                        name: n,
                        itemStyle: { color: colorMap.downstream },
                        symbolSize: 8,
                        stocks: (chain.key_stocks || {})[n] || [],
                    }))
                });
            }

            return {
                name: chain.name || '产业链',
                itemStyle: { color: '#f472b6' },
                children: children,
            };
        }

        const treeData = buildTreeData(data);

        const chart = echarts.init(document.getElementById('chart'));

        chart.setOption({
            tooltip: {
                trigger: 'item',
                formatter: function(params) {
                    const stocks = params.data.stocks;
                    if (stocks && stocks.length) {
                        return `<b>${params.name}</b><br/>成分股: ${stocks.join(', ')}`;
                    }
                    return `<b>${params.name}</b>`;
                }
            },
            series: [{
                type: 'tree',
                data: [treeData],
                top: '5%',
                left: '8%',
                bottom: '5%',
                right: '8%',
                symbol: 'roundRect',
                symbolSize: 10,
                orient: 'LR',
                expandAndCollapse: true,
                initialTreeDepth: 3,
                label: {
                    position: 'right',
                    verticalAlign: 'middle',
                    align: 'left',
                    fontSize: 13,
                    color: '#e2e8f0',
                },
                leaves: {
                    label: {
                        position: 'right',
                        verticalAlign: 'middle',
                        align: 'left',
                        fontSize: 12,
                        color: '#94a3b8',
                    }
                },
                lineStyle: {
                    color: 'rgba(148,163,184,0.3)',
                    width: 2,
                    curveness: 0.5,
                },
                itemStyle: {
                    borderColor: 'rgba(255,255,255,0.1)',
                },
                emphasis: {
                    focus: 'descendant',
                    lineStyle: {
                        color: '#f472b6',
                        width: 3,
                    }
                },
            }],
        });

        // 响应式缩放
        window.addEventListener('resize', () => chart.resize());

        // 点击节点联动 K 线消息
        chart.on('click', function(params) {
            const stocks = params.data.stocks || [];
            if (stocks.length) {
                window.parent.postMessage({
                    type: 'node_click',
                    node: params.name,
                    stocks: stocks,
                }, '*');
            }
        });
    </script>
</body>
</html>
"""

# ============================================================
# Streamlit UI
# ============================================================

st.title("🧠 产业链三区脑图")
st.caption("上游供给 → 中游制造 → 下游应用 ｜ 点击节点查看成分股 ｜ 支持拖拽、缩放、折叠")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    industry = st.selectbox(
        "选择产业链",
        engine.list_industries(),
        index=0,
    )

with col2:
    chain = engine.get_industry_chain(industry)
    capital = chain.get("capital_flow_score", 0) if chain else 0
    st.metric("资金热度", f"{capital:.1f}/10", delta=None)

with col3:
    stocks = engine.get_related_stocks(industry, "all") if chain else []
    st.metric("关联标的", f"{len(stocks)} 只")

# 渲染脑图
if chain:
    html = MINDMAP_HTML.replace("__CHAIN_DATA__", json.dumps(chain, ensure_ascii=False))
    st.components.v1.html(html, height=600, scrolling=False)

    # 成分股明细
    st.divider()
    st.subheader("📋 各环节成分股明细")

    tabs = st.tabs(["上游供给", "中游制造", "下游应用"])

    for tab, direction, label in zip(
        tabs,
        ["upstream", "midstream", "downstream"],
        ["上游供给", "中游制造", "下游应用"],
    ):
        with tab:
            segments = chain.get(direction, [])
            key_stocks = chain.get("key_stocks", {})

            if not segments:
                st.info(f"暂无{label}数据")
                continue

            for seg in segments:
                codes = key_stocks.get(seg, [])
                st.markdown(f"**{seg}** — {', '.join(codes) if codes else '待补充'}")

    # LLM 分析入口
    st.divider()
    st.subheader("🤖 AI 产业链传导推演")
    event_input = st.text_area(
        "输入事件（如：硅料涨价20%）",
        placeholder="输入行业事件，AI 自动推演传导路径和受影响标的...",
    )

    if st.button("🔄 AI 推演传导", type="primary", disabled=not event_input):
        with st.spinner("豆包 AI 推演中..."):
            from llm.gateway import get_gateway
            gw = get_gateway()
            result = gw.simulate_chain(
                {"industry": industry, "event": event_input},
                [],
            )
            if result.success and result.data:
                st.json(result.data)
            else:
                st.error(f"推演失败: {result.error}")
else:
    st.warning("暂无产业链数据")

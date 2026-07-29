"""
产业链拓扑图谱 — ECharts 力导向图
"""

import streamlit as st
import json

st.set_page_config(page_title="产业链图谱", page_icon="🔗", layout="wide")

st.title("🔗 产业链传导图谱")

# 模拟产业链数据
nodes = [
    {"name": "光伏补贴新政", "category": 0, "symbolSize": 55},
    {"name": "隆基绿能", "category": 1, "symbolSize": 40},
    {"name": "通威股份", "category": 2, "symbolSize": 35},
    {"name": "阳光电源", "category": 1, "symbolSize": 35},
    {"name": "福斯特", "category": 2, "symbolSize": 30},
    {"name": "国家能源局", "category": 0, "symbolSize": 45},
    {"name": "宁德时代", "category": 1, "symbolSize": 42},
    {"name": "先导智能", "category": 2, "symbolSize": 32},
    {"name": "天赐材料", "category": 2, "symbolSize": 30},
    {"name": "比亚迪", "category": 1, "symbolSize": 40},
]
links = [
    {"source": "光伏补贴新政", "target": "隆基绿能", "label": "装机需求↑"},
    {"source": "隆基绿能", "target": "通威股份", "label": "硅料需求"},
    {"source": "隆基绿能", "target": "阳光电源", "label": "逆变器"},
    {"source": "隆基绿能", "target": "福斯特", "label": "封装材料"},
    {"source": "国家能源局", "target": "宁德时代", "label": "储能政策"},
    {"source": "宁德时代", "target": "先导智能", "label": "设备采购"},
    {"source": "宁德时代", "target": "天赐材料", "label": "电解液"},
    {"source": "宁德时代", "target": "比亚迪", "label": "竞争对标"},
]

chart_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>*{{margin:0;padding:0}}body{{background:#0d1117}}</style></head><body>
<div id="chart" style="width:100%;height:600px"></div>
<script>
var chart = echarts.init(document.getElementById('chart'));
var option = {{
  backgroundColor: '#0d1117',
  tooltip: {{ formatter: function(p) {{ return p.dataType === 'edge' ? p.data.label || '' : '<b>'+p.name+'</b>'; }} }},
  legend: [{{
    data: ['事件/政策', '核心企业', '上下游'],
    textStyle: {{ color: '#e2e8f0' }},
  }}],
  series: [{{
    type: 'graph', layout: 'force', roam: true, draggable: true,
    force: {{ repulsion: 400, edgeLength: [150, 350], gravity: 0.08 }},
    data: {json.dumps(nodes, ensure_ascii=False)},
    links: {json.dumps(links, ensure_ascii=False)},
    categories: [
      {{ name: '事件/政策', itemStyle: {{ color: '#f59e0b' }} }},
      {{ name: '核心企业', itemStyle: {{ color: '#3b82f6' }} }},
      {{ name: '上下游', itemStyle: {{ color: '#22c55e' }} }},
    ],
    label: {{ show: true, fontSize: 10, color: '#e2e8f0' }},
    edgeSymbol: ['none', 'arrow'], edgeSymbolSize: [0, 10],
    lineStyle: {{ color: '#4b5563', curveness: 0.2, opacity: 0.6 }},
    emphasis: {{ focus: 'adjacency', lineStyle: {{ width: 4 }} }},
  }}]
}};
chart.setOption(option);
window.addEventListener('resize', function(){{ chart.resize(); }});
</script></body></html>"""

st.components.v1.html(chart_html, height=620)

st.caption("🟡 政策/事件 | 🔵 核心企业 | 🟢 上下游 | 拖拽节点 | 滚轮缩放")
st.markdown("---")
st.info("💡 提示：P2 将增加节点点击详情、传导选股、舆情面板等交互功能")

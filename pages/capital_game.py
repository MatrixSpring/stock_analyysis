"""
多维度资金博弈分析 — Streamlit + ECharts
覆盖：北向资金 / 龙虎榜 / 分时主力 / 板块轮动
"""

from __future__ import annotations

import json
import streamlit as st
from datetime import datetime
from core.capital_flow import get_capital_engine

st.set_page_config(page_title="资金博弈", page_icon="💹", layout="wide")

engine = get_capital_engine()

# ============================================================
# ECharts 资金博弈仪表盘 HTML
# ============================================================

CAPITAL_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>*{margin:0;padding:0}#chart{width:100%;height:100%;background:#0a0e17}</style>
</head>
<body><div id="chart"></div>
<script>
const report = __REPORT_DATA__;
const c = echarts.init(document.getElementById('chart'));

// ---- 北向资金趋势 (左上) ----
const northGrid = { left:'5%', top:'7%', width:'42%', height:'40%' };
const northX = report.north_bound_5d.map(r => r.date.slice(5));
const northY = report.north_bound_5d.map(r => r.net_inflow);

// ---- 席位拆解饼图 (右上) ----
const seatGrid = { left:'52%', top:'7%', width:'43%', height:'40%' };
const seatData = Object.entries(report.seat_type_breakdown || {}).map(([k,v]) => ({name:k,value:v}));
const seatColors = {'机构专用':'#34d399','游资':'#fbbf24','北向':'#38bdf8','量化':'#a78bfa','其他':'#64748B'};

// ---- 分时资金柱状图 (左下) ----
const flowGrid = { left:'5%', top:'52%', width:'42%', height:'40%' };
const flow = report.intraday_flow || {};

// ---- 板块轮动 (右下) ----
const sectorGrid = { left:'52%', top:'52%', width:'43%', height:'40%' };
const sectors = report.sector_rotation_5d || [];
const sectorNames = [...new Set(sectors.map(s => s.sector))];
const sectorInflows = sectorNames.map(n =>
    sectors.filter(s => s.sector === n).reduce((a,b) => a + b.capital_inflow, 0)
);

c.setOption({
    backgroundColor: '#0a0e17',
    title: [
        { text:'北向资金 5日趋势', left:'5%', top:'1%', textStyle:{color:'#e2e8f0',fontSize:14} },
        { text:'龙虎榜席位拆解', left:'52%', top:'1%', textStyle:{color:'#e2e8f0',fontSize:14} },
        { text:'分时资金流向 (万元)', left:'5%', top:'46%', textStyle:{color:'#e2e8f0',fontSize:14} },
        { text:'板块资金轮动 (5日汇总)', left:'52%', top:'46%', textStyle:{color:'#e2e8f0',fontSize:14} },
    ],
    grid: [northGrid, flowGrid],
    xAxis: [
        { gridIndex:0, data:northX, axisLabel:{color:'#94A3B8',fontSize:10}, axisLine:{lineStyle:{color:'#334155'}} },
        { gridIndex:1, data:['主力净流入','散户净流入','大单','超大单'], axisLabel:{color:'#94A3B8',fontSize:10} },
    ],
    yAxis: [
        { gridIndex:0, axisLabel:{color:'#94A3B8',fontSize:10,formatter:'{value}亿'}, splitLine:{lineStyle:{color:'rgba(255,255,255,0.05)'}} },
        { gridIndex:1, axisLabel:{color:'#94A3B8',fontSize:10}, splitLine:{lineStyle:{color:'rgba(255,255,255,0.05)'}} },
    ],
    series: [
        // 北向柱状图
        {
            type:'bar', xAxisIndex:0, yAxisIndex:0,
            data: northY.map(v => ({
                value: v,
                itemStyle: { color: v >= 0 ? '#34d399' : '#ef4444' }
            })),
            barWidth: '50%',
        },
        // 分时资金柱状图
        {
            type:'bar', xAxisIndex:1, yAxisIndex:1,
            data: [
                { value: flow.main_force_inflow || 0, itemStyle:{color:'#fbbf24'} },
                { value: flow.retail_inflow || 0, itemStyle:{color:'#94A3B8'} },
                { value: flow.big_order_inflow || 0, itemStyle:{color:'#38bdf8'} },
                { value: flow.super_big_inflow || 0, itemStyle:{color:'#a78bfa'} },
            ],
            barWidth: '45%',
        },
    ],
});

// 饼图 (席位拆解)
const pieChart = echarts.init(document.createElement('div'));
pieChart.setOption({
    tooltip:{trigger:'item'},
    series:[{
        type:'pie', radius:['40%','70%'], center:['50%','50%'],
        data: seatData,
        label:{color:'#94A3B8',fontSize:10},
        itemStyle:{borderColor:'#0a0e17',borderWidth:2},
    }],
    color: seatData.map(d => seatColors[d.name] || '#64748B'),
});
c.setOption({}, true);

// 合并 pieChart 到主图
setTimeout(() => {
    const pieDom = document.createElement('div');
    pieDom.style.cssText = 'position:absolute;left:52%;top:7%;width:43%;height:40%';
    document.getElementById('chart').appendChild(pieDom);
    pieChart.setOption({}, true);
    pieChart.resize({width:pieDom.clientWidth, height:pieDom.clientHeight});
}, 100);

window.addEventListener('resize', () => c.resize());
</script></body></html>
"""

# ============================================================
# Streamlit UI
# ============================================================

st.title("💹 多维度资金博弈分析")
st.caption("北向资金趋势 ｜ 龙虎榜席位拆解 ｜ 分时主力散户对比 ｜ 板块资金轮动")

# 输入区
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    stock_code = st.text_input("股票代码", "600519", placeholder="输入代码如 600519")
with col2:
    stock_name = st.text_input("股票名称（可选）", "贵州茅台", placeholder="可选")
with col3:
    analyze_btn = st.button("🔍 多维度分析", type="primary", use_container_width=True)

if analyze_btn:
    with st.spinner("正在拉取资金数据..."):
        report = engine.multi_dimension_report(stock_code, stock_name)

    # 综合评分
    score = report.composite_score
    score_color = "#34d399" if score >= 65 else ("#fbbf24" if score >= 40 else "#ef4444")
    score_label = "资金面偏多" if score >= 65 else ("资金面中性" if score >= 40 else "资金面偏空")

    st.markdown(f"""
    <div style="background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px;display:flex;align-items:center;gap:24px">
        <div style="text-align:center">
            <div style="font-size:48px;font-weight:800;color:{score_color}">{score:.0f}</div>
            <div style="font-size:12px;color:#94A3B8">综合评分</div>
        </div>
        <div>
            <div style="font-size:18px;font-weight:700;color:{score_color}">{score_label}</div>
            <div style="font-size:13px;color:#94A3B8">北向趋势：{report.north_bound_trend}</div>
            <div style="font-size:13px;color:#94A3B8">主力占比：{report.intraday_flow.main_force_ratio if report.intraday_flow else 0:.1f}%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 风险信号
    if report.risk_signals:
        for risk in report.risk_signals:
            st.warning(f"⚠️ {risk}")

    # 四象限仪表盘
    report_dict = {
        "north_bound_5d": [
            {"date": r.date, "net_inflow": r.net_inflow}
            for r in report.north_bound_5d
        ],
        "seat_type_breakdown": report.seat_type_breakdown,
        "intraday_flow": {
            "main_force_inflow": report.intraday_flow.main_force_inflow if report.intraday_flow else 0,
            "retail_inflow": report.intraday_flow.retail_inflow if report.intraday_flow else 0,
            "big_order_inflow": report.intraday_flow.big_order_inflow if report.intraday_flow else 0,
            "super_big_inflow": report.intraday_flow.super_big_inflow if report.intraday_flow else 0,
            "main_force_ratio": report.intraday_flow.main_force_ratio if report.intraday_flow else 0,
        },
        "sector_rotation_5d": [
            {"sector": s.sector, "capital_inflow": s.capital_inflow, "momentum_score": s.momentum_score}
            for s in report.sector_rotation_5d
        ],
    }
    html = CAPITAL_DASHBOARD_HTML.replace("__REPORT_DATA__", json.dumps(report_dict, ensure_ascii=False))
    st.components.v1.html(html, height=550, scrolling=False)

    # 明细表
    st.divider()
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📊 北向资金明细")
        if report.north_bound_5d:
            st.dataframe(
                [(r.date, f"{r.net_inflow:+.2f}亿") for r in report.north_bound_5d],
                column_config={"0": "日期", "1": "净流入"},
                hide_index=True,
            )

    with c2:
        st.subheader("🐉 龙虎榜最近上榜")
        if report.recent_dragon_tiger:
            st.dataframe(
                [(r.date, f"{r.buy_amount:.0f}万", f"{r.sell_amount:.0f}万", f"{r.net_amount:+.0f}万", r.reason)
                 for r in report.recent_dragon_tiger[:5]],
                column_config={"0": "日期", "1": "买入", "2": "卖出", "3": "净额", "4": "原因"},
                hide_index=True,
            )
        else:
            st.info("近期无龙虎榜上榜记录")

    # AI 解读
    st.divider()
    st.subheader("🤖 AI 资金博弈解读")
    if st.button("🔄 豆包 AI 解读资金面"):
        with st.spinner("AI 分析中..."):
            from llm.gateway import get_gateway
            gw = get_gateway()
            context = {
                "股票": f"{stock_name}({stock_code})",
                "北向趋势": report.north_bound_trend,
                "综合评分": report.composite_score,
                "主力资金": f"{report.intraday_flow.main_force_inflow if report.intraday_flow else 0:.0f}万",
                "风险信号": report.risk_signals,
            }
            result = gw.chat(
                f"请用2-3句话总结这个股票的资金面状况，给出操作建议：\n{json.dumps(context, ensure_ascii=False)}",
                context, professional=True,
            )
            if result.success:
                st.success(result.raw_text if result.raw_text else "分析完成")
            else:
                st.error(f"AI 调用失败: {result.error}")

/**
 * 盘面一：全局资金流向桑基拓扑盘面
 * 市场总池→六大资金主体→一级行业→二级赛道→细分题材→终端
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { DashboardCard } from '../../components/dashboard/DashboardCard';

// 静态演示数据（后端 API 就绪后替换为实时数据）
const DEMO_SANKEY = {
  nodes: [
    { name: '市场总流动性' },  { name: '北向资金' }, { name: '公募基金' },
    { name: '私募基金' },      { name: '一线游资' }, { name: '散户资金' },
    { name: '社保汇金' },      { name: '科技赛道' }, { name: '新能源赛道' },
    { name: '消费赛道' },      { name: '金融赛道' }, { name: '医药赛道' },
    { name: '科创算力' },      { name: '光伏储能' }, { name: '白酒家电' },
    { name: '券商银行' },      { name: '创新药械' }, { name: '沉淀资金' },
    { name: '出逃资金' },
  ],
  links: [
    { source: '市场总流动性', target: '北向资金', value: 860 },   { source: '市场总流动性', target: '公募基金', value: 1240 },
    { source: '市场总流动性', target: '私募基金', value: 680 },   { source: '市场总流动性', target: '一线游资', value: 420 },
    { source: '市场总流动性', target: '散户资金', value: 2180 },  { source: '市场总流动性', target: '社保汇金', value: 340 },
    { source: '北向资金', target: '科技赛道', value: 320 },       { source: '公募基金', target: '新能源赛道', value: 480 },
    { source: '私募基金', target: '消费赛道', value: 260 },       { source: '一线游资', target: '科技赛道', value: 180 },
    { source: '散户资金', target: '金融赛道', value: 420 },       { source: '社保汇金', target: '医药赛道', value: 140 },
    { source: '科技赛道', target: '科创算力', value: 280 },       { source: '新能源赛道', target: '光伏储能', value: 340 },
    { source: '消费赛道', target: '白酒家电', value: 160 },       { source: '金融赛道', target: '券商银行', value: 220 },
    { source: '医药赛道', target: '创新药械', value: 90 },        { source: '科创算力', target: '沉淀资金', value: 180 },
    { source: '光伏储能', target: '沉淀资金', value: 220 },       { source: '白酒家电', target: '出逃资金', value: 80 },
    { source: '券商银行', target: '出逃资金', value: 110 },
  ],
};

export default function FundFlowTopology() {
  const sankeyRef = useRef<HTMLDivElement>(null);
  const [updateTime] = useState(new Date().toLocaleTimeString());

  const render = useCallback(async () => {
    if (!sankeyRef.current) return;
    const echarts = (await import('echarts')).default;
    const chart = echarts.init(sankeyRef.current, undefined as any);
    chart.setOption({
      tooltip: { trigger: 'item', triggerOn: 'mousemove' },
      series: [{
        type: 'sankey', left: 30, top: 20, right: 30, bottom: 20,
        nodeWidth: 12, nodeGap: 14, layoutIterations: 32,
        data: DEMO_SANKEY.nodes, links: DEMO_SANKEY.links,
        lineStyle: { color: 'source', curveness: 0.45, opacity: 0.8 },
        label: { show: true, color: '#e5e6eb', fontSize: 11 },
      }],
    });
    return () => chart.dispose();
  }, []);

  useEffect(() => { render(); }, [render]);

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: 20 }}>
      <DashboardCard title="资金流向桑基拓扑" subtitle={`全链路资金流转 · 更新 ${updateTime}`}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 16 }}>
          {[
            { n: '市场总流动性', v: '8926亿', c: '#1677FF' },
            { n: '主力沉淀', v: '1246亿', c: '#00B42A' },
            { n: '短线游击', v: '387亿', c: '#FF7D00' },
            { n: '北向配置', v: '86亿', c: '#722ED1' },
            { n: '散户跟风', v: '218亿', c: '#F53F3F' },
          ].map(d => (
            <div key={d.n} style={{ background: '#151A28', borderRadius: 8, padding: 12, textAlign: 'center', borderLeft: `3px solid ${d.c}` }}>
              <div style={{ fontSize: 11, color: '#86909C' }}>{d.n}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>{d.v}</div>
            </div>
          ))}
        </div>
        <div ref={sankeyRef} style={{ height: 420 }} />
      </DashboardCard>
    </div>
  );
}

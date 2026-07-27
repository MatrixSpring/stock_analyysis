/** 盘面五：全产业链动态节点异动图谱 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { DashboardCard } from '../../components/dashboard/DashboardCard';

export default function IndustryChainTopology() {
  const ref = useRef<HTMLDivElement>(null);

  const render = useCallback(async () => {
    if (!ref.current) return;
    const echarts = (await import('echarts')).default;
    const chart = echarts.init(ref.current);
    chart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'graph', layout: 'force', roam: true,
        force: { repulsion: 180, edgeLength: 90, gravity: 0.06 },
        label: { show: true, color: '#fff', fontSize: 11 },
        edgeSymbol: ['none', 'arrow'],
        data: [
          { name: '科创科技(85%)', symbolSize: 55, itemStyle: { color: '#1677FF' } },
          { name: '高端制造(72%)', symbolSize: 45, itemStyle: { color: '#00B42A' } },
          { name: '新能源(68%)', symbolSize: 42, itemStyle: { color: '#722ED1' } },
          { name: '大消费(45%)', symbolSize: 35, itemStyle: { color: '#FF7D00' } },
          { name: '周期资源(38%)', symbolSize: 28, itemStyle: { color: '#F53F3F' } },
          { name: 'AI算力', symbolSize: 30 }, { name: '光模块', symbolSize: 25 },
          { name: '光伏组件', symbolSize: 25 }, { name: '储能', symbolSize: 22 },
          { name: '白酒家电', symbolSize: 20 }, { name: '钢铁水泥', symbolSize: 18 },
        ],
        links: [
          { source: '科创科技(85%)', target: 'AI算力' }, { source: '科创科技(85%)', target: '光模块' },
          { source: '高端制造(72%)', target: 'AI算力' },  { source: '新能源(68%)', target: '光伏组件' },
          { source: '新能源(68%)', target: '储能' },       { source: '大消费(45%)', target: '白酒家电' },
          { source: '周期资源(38%)', target: '钢铁水泥' }, { source: '科创科技(85%)', target: '新能源(68%)' },
        ],
      }],
    });
    return () => chart.dispose();
  }, []);

  useEffect(() => { render(); }, [render]);
  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: 20 }}>
      <DashboardCard title="产业链动态节点异动图谱" subtitle="五大集群全链路监测">
        <div style={{display:'flex',height:24,borderRadius:6,overflow:'hidden',marginBottom:16}}>
          {[{n:'科创',w:85,c:'#1677FF'},{n:'制造',w:72,c:'#00B42A'},{n:'新能源',w:68,c:'#722ED1'},{n:'消费',w:45,c:'#FF7D00'},{n:'周期',w:38,c:'#F53F3F'}].map(d=>(
            <div key={d.n} style={{width:`${d.w}%`,background:d.c,display:'flex',alignItems:'center',justifyContent:'center',color:'#fff',fontSize:11}}>{d.n} {d.w}%</div>
          ))}
        </div>
        <div ref={ref} style={{ height: 420 }} />
      </DashboardCard>
    </div>
  );
}

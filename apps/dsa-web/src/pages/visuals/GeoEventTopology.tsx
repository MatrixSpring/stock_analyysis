/** 盘面三：地缘政策事件传导拓扑 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { DashboardCard } from '../../components/dashboard/DashboardCard';

export default function GeoEventTopology() {
  const ref = useRef<HTMLDivElement>(null);
  const [updateTime] = useState(new Date().toLocaleTimeString());

  const render = useCallback(async () => {
    if (!ref.current) return;
    const echarts = (await import('echarts')).default;
    const chart = echarts.init(ref.current);
    chart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'graph', layout: 'force', roam: true,
        force: { repulsion: 250, edgeLength: 120, gravity: 0.05 },
        label: { show: true, color: '#fff', fontSize: 11 },
        edgeSymbol: ['none', 'arrow'],
        data: [
          { name: '地缘冲突', symbolSize: 50, itemStyle: { color: '#F53F3F' } },
          { name: '产业政策', symbolSize: 45, itemStyle: { color: '#1677FF' } },
          { name: '气候政策', symbolSize: 40, itemStyle: { color: '#00B42A' } },
          { name: '国际贸易', symbolSize: 35, itemStyle: { color: '#FF7D00' } },
          { name: '能源安全', symbolSize: 30 }, { name: '自主可控', symbolSize: 30 },
          { name: '光伏储能', symbolSize: 25 }, { name: '芯片制造', symbolSize: 25 },
          { name: '军工防御', symbolSize: 22 }, { name: '出口制造', symbolSize: 20 },
        ],
        links: [
          { source: '地缘冲突', target: '能源安全' }, { source: '地缘冲突', target: '军工防御' },
          { source: '产业政策', target: '自主可控' },   { source: '产业政策', target: '芯片制造' },
          { source: '气候政策', target: '光伏储能' },   { source: '国际贸易', target: '出口制造' },
          { source: '能源安全', target: '光伏储能' },   { source: '自主可控', target: '芯片制造' },
        ],
      }],
    });
    return () => chart.dispose();
  }, []);

  useEffect(() => { render(); }, [render]);
  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: 20 }}>
      <DashboardCard title="地缘宏观事件传导拓扑" subtitle={`事件→赛道→节点全链路 · ${updateTime}`}>
        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:10,marginBottom:14}}>
          {[{n:'重度冲击',v:'1个',c:'#F53F3F'},{n:'中度影响',v:'3个',c:'#FF7D00'},{n:'轻度脉冲',v:'5个',c:'#00B42A'}].map(d=>(
            <div key={d.n} style={{padding:10,borderRadius:6,background:`${d.c}18`,color:d.c,textAlign:'center',fontSize:12}}>{d.n}: {d.v}</div>
          ))}
        </div>
        <div ref={ref} style={{ height: 400 }} />
      </DashboardCard>
    </div>
  );
}

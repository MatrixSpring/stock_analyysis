/** 盘面二：六大参与者力导向博弈图谱 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { DashboardCard } from '../../components/dashboard/DashboardCard';

export default function ParticipantGraph() {
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
        force: { repulsion: 200, edgeLength: 100, gravity: 0.08 },
        label: { show: true, color: '#fff', fontSize: 12 },
        edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 8,
        data: [
          { name: '北向资金', symbolSize: 60, category: 0 }, { name: '公募基金', symbolSize: 50, category: 0 },
          { name: '一线游资', symbolSize: 45, category: 1 }, { name: '私募基金', symbolSize: 35, category: 1 },
          { name: '社保汇金', symbolSize: 30, category: 2 }, { name: '散户资金', symbolSize: 25, category: 2 },
        ],
        links: [
          { source: '北向资金', target: '公募基金' }, { source: '公募基金', target: '社保汇金' },
          { source: '一线游资', target: '私募基金' }, { source: '私募基金', target: '散户资金' },
          { source: '北向资金', target: '一线游资' },  { source: '公募基金', target: '私募基金' },
        ],
        categories: [{ name: '机构长线' }, { name: '游资中短线' }, { name: '散户跟随' }],
      }],
    });
    return () => chart.dispose();
  }, []);

  useEffect(() => { render(); }, [render]);

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: 20 }}>
      <DashboardCard title="参与者博弈力导向图谱" subtitle={`六大主体博弈结构 · ${updateTime}`}>
        <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
          {[ {n:'主导资金',v:'北向+公募',c:'#1677FF'},{n:'市场节奏',v:'机构趋势',c:'#00B42A'},{n:'主力胜率',v:'68%',c:'#FF7D00'} ].map(d=>(
            <div key={d.n} style={{flex:1,padding:10,borderRadius:6,background:`${d.c}18`,color:d.c,textAlign:'center',fontSize:13}}>{d.n}: <b>{d.v}</b></div>
          ))}
        </div>
        <div ref={ref} style={{ height: 400 }} />
      </DashboardCard>
    </div>
  );
}

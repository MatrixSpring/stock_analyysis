/** 盘面四：全维度分层数据树状拓扑 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { DashboardCard } from '../../components/dashboard/DashboardCard';

const TREE_DATA = {
  name: '市场全局',
  children: [
    { name: '趋势维度(78分)', children: [{ name: '均线多头排列' }, { name: '动量偏强(0.72)' }] },
    { name: '资金维度(82分)', children: [{ name: '主力净流入' }, { name: '北向持续加仓' }] },
    { name: '风险维度(35分)',  children: [{ name: '波动可控' }, { name: '无系统性风险' }] },
    { name: '情绪维度(68分)', children: [{ name: '温和偏暖' }, { name: '赚钱效应中等' }] },
    { name: '政策维度(72分)', children: [{ name: '利好落地期' }, { name: '产业政策密集' }] },
    { name: '筹码维度(62分)', children: [{ name: '筹码集中度提升' }, { name: '套牢盘下降' }] },
  ],
};

export default function DimensionTree() {
  const ref = useRef<HTMLDivElement>(null);
  const render = useCallback(async () => {
    if (!ref.current) return;
    const echarts = (await import('echarts')).default;
    const chart = echarts.init(ref.current);
    chart.setOption({
      tooltip: { trigger: 'item' },
      series: [{ type: 'tree', data: [TREE_DATA], top: 10, left: 10, bottom: 10, right: '25%',
        symbolSize: 10, label: { color: '#fff', fontSize: 12 },
        leaves: { label: { position: 'right' } }, expandAndCollapse: true,
      }],
    });
    return () => chart.dispose();
  }, []);

  useEffect(() => { render(); }, [render]);
  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: 20 }}>
      <DashboardCard title="全维度分层数据树状拓扑" subtitle="六大维度自动分层归类">
        <div style={{display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:8,marginBottom:14}}>
          {[{n:'趋势',s:78,c:'#00B42A'},{n:'资金',s:82,c:'#1677FF'},{n:'风险',s:35,c:'#FF7D00'},{n:'情绪',s:68,c:'#00B42A'},{n:'政策',s:72,c:'#1677FF'},{n:'筹码',s:62,c:'#722ED1'}].map(d=>(
            <div key={d.n} style={{padding:10,borderRadius:6,background:'#151A28',textAlign:'center',borderTop:`2px solid ${d.c}`}}>
              <div style={{fontSize:11,color:'#86909C'}}>{d.n}</div><div style={{fontSize:16,fontWeight:700,color:'#fff'}}>{d.s}</div>
            </div>
          ))}
        </div>
        <div ref={ref} style={{ height: 420 }} />
      </DashboardCard>
    </div>
  );
}

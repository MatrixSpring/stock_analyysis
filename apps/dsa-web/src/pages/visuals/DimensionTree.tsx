import { useEffect, useState, useCallback } from 'react';
import { useECharts } from '../../hooks/useECharts';
import { DashboardCard } from '../../components/dashboard/DashboardCard';

const TREE = {name:'市场全局',children:[{name:'趋势(78分)',children:[{name:'均线多头'},{name:'动量偏强(0.72)'}]},{name:'资金(82分)',children:[{name:'主力净流入'},{name:'北向持续加仓'}]},{name:'风险(35分)',children:[{name:'波动可控'},{name:'无系统性风险'}]},{name:'情绪(68分)',children:[{name:'温和偏暖'},{name:'赚钱效应中等'}]},{name:'政策(72分)',children:[{name:'利好落地期'},{name:'产业政策密集'}]},{name:'筹码(62分)',children:[{name:'筹码集中度↑'},{name:'套牢盘↓'}]}]};

export default function DimensionTree() {
  const { setDomRef, render } = useECharts();
  const [t] = useState(new Date().toLocaleTimeString());
  useEffect(() => { render({series:[{type:'tree',data:[TREE],top:10,left:10,bottom:10,right:'25%',symbolSize:10,label:{color:'#fff',fontSize:12},leaves:{label:{position:'right'}},expandAndCollapse:true}]}); }, [render]);
  return (<div style={{maxWidth:1400,margin:'0 auto',padding:20}}><DashboardCard title="全维度分层树状拓扑" subtitle={`六大维度自动归类 · ${t}`}><div style={{display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:8,marginBottom:14}}>{[{n:'趋势',s:78,c:'#00B42A'},{n:'资金',s:82,c:'#1677FF'},{n:'风险',s:35,c:'#FF7D00'},{n:'情绪',s:68,c:'#00B42A'},{n:'政策',s:72,c:'#1677FF'},{n:'筹码',s:62,c:'#722ED1'}].map(d=>(<div key={d.n} style={{padding:10,borderRadius:6,background:'#151A28',textAlign:'center',borderTop:`2px solid ${d.c}`}}><div style={{fontSize:11,color:'#86909C'}}>{d.n}</div><div style={{fontSize:16,fontWeight:700,color:'#fff'}}>{d.s}</div></div>))}</div><div ref={setDomRef} style={{height:420}} /></DashboardCard></div>);
}

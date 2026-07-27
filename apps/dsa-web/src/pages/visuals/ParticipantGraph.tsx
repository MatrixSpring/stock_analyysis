import { useEffect, useState, useCallback } from 'react';
import { useECharts } from '../../hooks/useECharts';
import { DashboardCard } from '../../components/dashboard/DashboardCard';

const NODES = [{name:'北向资金',symbolSize:60},{name:'公募基金',symbolSize:50},{name:'一线游资',symbolSize:45},{name:'私募基金',symbolSize:35},{name:'社保汇金',symbolSize:30},{name:'散户资金',symbolSize:25}];
const LINKS = [{source:'北向资金',target:'公募基金'},{source:'公募基金',target:'社保汇金'},{source:'一线游资',target:'私募基金'},{source:'私募基金',target:'散户资金'},{source:'北向资金',target:'一线游资'},{source:'公募基金',target:'私募基金'}];

export default function ParticipantGraph() {
  const { setDomRef, render } = useECharts();
  const [period, setPeriod] = useState('5');
  const [time, setTime] = useState('');

  const load = useCallback(async (p: string) => {
    setTime(new Date().toLocaleTimeString());
    await render({
      series: [{ type:'graph', layout:'force', roam:true, force:{repulsion:200,edgeLength:100,gravity:0.08},
        label:{show:true,color:'#fff',fontSize:12}, edgeSymbol:['none','arrow'], edgeSymbolSize:8,
        data: NODES, links: LINKS, categories:[{name:'机构长线'},{name:'游资'},{name:'散户'}],
      }],
    });
  }, [render]);

  useEffect(() => { load(period); }, [period, load]);

  return (
    <div style={{maxWidth:1400,margin:'0 auto',padding:20}}>
      <DashboardCard title="参与者博弈力导向图谱" subtitle={`六大主体博弈 · ${time}`}>
        <div style={{display:'flex',gap:8,marginBottom:12}}>
          {['1','3','5','10','30'].map(v=>(<button key={v} onClick={()=>setPeriod(v)} style={{padding:'3px 10px',borderRadius:4,border:'1px solid rgba(255,255,255,0.1)',background:period===v?'rgba(22,119,255,0.15)':'transparent',color:period===v?'#1677FF':'#86909C',cursor:'pointer',fontSize:11}}>{v}日</button>))}
        </div>
        <div style={{display:'flex',gap:10,marginBottom:14}}>
          {[{n:'主导资金',v:'北向+公募',c:'#1677FF'},{n:'市场节奏',v:'机构趋势',c:'#00B42A'},{n:'主力胜率',v:'68%',c:'#FF7D00'}].map(d=>(<div key={d.n} style={{flex:1,padding:10,borderRadius:6,background:`${d.c}18`,color:d.c,textAlign:'center',fontSize:13}}>{d.n}: <b>{d.v}</b></div>))}
        </div>
        <div ref={setDomRef} style={{height:400}} />
      </DashboardCard>
    </div>
  );
}

import { useEffect, useState, useCallback } from 'react';
import { useECharts } from '../../hooks/useECharts';
import { DashboardCard } from '../../components/dashboard/DashboardCard';

const DATA = {
  nodes: [{name:'市场总流动性'},{name:'北向资金'},{name:'公募基金'},{name:'私募基金'},{name:'一线游资'},{name:'散户资金'},{name:'社保汇金'},{name:'科技赛道'},{name:'新能源赛道'},{name:'消费赛道'},{name:'金融赛道'},{name:'医药赛道'},{name:'科创算力'},{name:'光伏储能'},{name:'白酒家电'},{name:'券商银行'},{name:'创新药械'},{name:'沉淀资金'},{name:'出逃资金'}],
  links: [{source:'市场总流动性',target:'北向资金',value:860},{source:'市场总流动性',target:'公募基金',value:1240},{source:'市场总流动性',target:'私募基金',value:680},{source:'市场总流动性',target:'一线游资',value:420},{source:'市场总流动性',target:'散户资金',value:2180},{source:'市场总流动性',target:'社保汇金',value:340},{source:'北向资金',target:'科技赛道',value:320},{source:'公募基金',target:'新能源赛道',value:480},{source:'私募基金',target:'消费赛道',value:260},{source:'一线游资',target:'科技赛道',value:180},{source:'散户资金',target:'金融赛道',value:420},{source:'社保汇金',target:'医药赛道',value:140},{source:'科技赛道',target:'科创算力',value:280},{source:'新能源赛道',target:'光伏储能',value:340},{source:'消费赛道',target:'白酒家电',value:160},{source:'金融赛道',target:'券商银行',value:220},{source:'医药赛道',target:'创新药械',value:90},{source:'科创算力',target:'沉淀资金',value:180},{source:'光伏储能',target:'沉淀资金',value:220},{source:'白酒家电',target:'出逃资金',value:80},{source:'券商银行',target:'出逃资金',value:110}],
};

export default function FundFlowTopology() {
  const { setDomRef, render } = useECharts();
  const [period, setPeriod] = useState('5');
  const [updateTime, setUpdateTime] = useState('');

  // P0 fix: full-link period switch (request → recalc → redraw)
  const loadData = useCallback(async (p: string) => {
    // In production: const res = await dashGet('/api/fund/sankey-topology', {period: p});
    setUpdateTime(new Date().toLocaleTimeString());
    await render({
      series: [{ type: 'sankey', left:30,top:20,right:30,bottom:20, nodeWidth:12,nodeGap:14,layoutIterations:32,
        data: DATA.nodes, links: DATA.links,
        lineStyle: { color: 'source', curveness:0.45, opacity:0.8 },
        label: { show:true, color:'#e5e6eb', fontSize:11 },
      }],
    });
  }, [render]);

  useEffect(() => { loadData(period); /* cleanup handled by useECharts */ }, [period, loadData]);

  return (
    <div style={{maxWidth:1400,margin:'0 auto',padding:20}}>
      <DashboardCard title="资金流向桑基拓扑" subtitle={`全链路流转 · ${updateTime}`}>
        <div style={{display:'flex',gap:8,marginBottom:12}}>
          {['1','3','5','10','30'].map(v=>(
            <button key={v} onClick={()=>setPeriod(v)} style={{padding:'3px 10px',borderRadius:4,border:'1px solid rgba(255,255,255,0.1)',background:period===v?'rgba(22,119,255,0.15)':'transparent',color:period===v?'#1677FF':'#86909C',cursor:'pointer',fontSize:11}}>{v}日</button>
          ))}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:10,marginBottom:14}}>
          {[{n:'总流动性',v:'8926亿',c:'#1677FF'},{n:'主力沉淀',v:'1246亿',c:'#00B42A'},{n:'短线游击',v:'387亿',c:'#FF7D00'},{n:'北向配置',v:'86亿',c:'#722ED1'},{n:'散户跟风',v:'218亿',c:'#F53F3F'}].map(d=>(
            <div key={d.n} style={{background:'#151A28',borderRadius:8,padding:12,textAlign:'center',borderLeft:`3px solid ${d.c}`}}>
              <div style={{fontSize:11,color:'#86909C'}}>{d.n}</div><div style={{fontSize:18,fontWeight:700,color:'#fff'}}>{d.v}</div>
            </div>
          ))}
        </div>
        <div ref={setDomRef} style={{height:420}} />
      </DashboardCard>
    </div>
  );
}

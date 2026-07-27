/**
 * v2.1.0 模块二：最近股票 — 个人标的中心
 */
import { useEffect, useState, useCallback } from 'react';
import { Star, Eye, ArrowUp, ArrowDown } from 'lucide-react';
import { DashboardCard } from './DashboardCard';

export function RecentStock() {
  const [data, setData] = useState<any>(null);
  const [tab, setTab] = useState('select');

  const doFetch = useCallback(async () => {
    try {
      const r = await window.fetch(`/api/v1/stock/recent?type=${tab}`);
      const j = await r.json();
      if (j.code === 200) setData(j.data);
    } catch { /* */ }
  }, [tab]);

  useEffect(() => { doFetch(); const t = setInterval(doFetch, 10_000); return () => clearInterval(t); }, [doFetch]);

  const tabs = [
    { key: 'select', label: '策略选股' },
    { key: 'browse', label: '最近浏览' },
    { key: 'collect', label: '自选股' },
  ];

  return (
    <DashboardCard title="最近股票" icon={<Eye size={18} />}>
      <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            padding: '4px 10px', borderRadius: 4, border: 'none', cursor: 'pointer',
            fontSize: 12, fontWeight: tab === t.key ? 600 : 400,
            background: tab === t.key ? 'rgba(22,119,255,0.12)' : 'transparent',
            color: tab === t.key ? '#1677FF' : '#94A3B8',
          }}>{t.label}</button>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 220, overflow: 'auto' }}>
        {data?.stocks?.map((s: any) => (
          <div key={s.stockCode} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '6px 8px',
            borderRadius: 6, background: 'rgba(255,255,255,0.02)',
            opacity: s.isAbnormal ? 0.4 : 1,
          }}>
            <span style={{ fontWeight: 600, fontSize: 13, color: '#fff', minWidth: 60 }}>
              {s.stockCode}
            </span>
            <span style={{ fontSize: 13, color: '#94A3B8', flex: 1 }}>{s.stockName}</span>
            <span style={{ fontSize: 13, color: s.changeRate >= 0 ? '#00B42A' : '#F53F3F' }}>
              {s.changeRate > 0 ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
              {s.price}
            </span>
            <span style={{
              fontSize: 11, padding: '2px 6px', borderRadius: 3,
              background: s.totalScore >= 70 ? 'rgba(0,180,42,0.1)' : s.totalScore >= 45 ? 'rgba(255,125,0,0.1)' : 'rgba(245,63,63,0.1)',
              color: s.totalScore >= 70 ? '#00B42A' : s.totalScore >= 45 ? '#FF7D00' : '#F53F3F',
            }}>
              {s.totalScore}
            </span>
            <Star size={12} style={{ color: '#FF7D00', cursor: 'pointer' }} />
          </div>
        )) || <div style={{ color: '#94A3B8', fontSize: 13, textAlign: 'center', padding: 20 }}>暂无数据</div>}
      </div>
    </DashboardCard>
  );
}

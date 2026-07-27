/**
 * v2.1.0 模块一：市场趋势 — 指数走势 + 趋势评分 + 行业热度
 */
import { useEffect, useState, useCallback } from 'react';
import { TrendingUp, BarChart3 } from 'lucide-react';
import { DashboardCard } from './DashboardCard';

export function MarketTrend() {
  const [data, setData] = useState<any>(null);

  const fetch = useCallback(async () => {
    try {
      const r = await fetch('/api/v1/market/trend');
      const j = await r.json();
      if (j.code === 200) setData(j.data);
    } catch { /* */ }
  }, []);

  useEffect(() => { fetch(); const t = setInterval(fetch, 10_000); return () => clearInterval(t); }, [fetch]);

  const s = data?.trendScore ?? 50;
  const scoreColor = s >= 70 ? '#00B42A' : s >= 55 ? '#1677FF' : s >= 45 ? '#FF7D00' : '#F53F3F';

  return (
    <DashboardCard title="市场趋势" subtitle={data?.trendStatus ?? '加载中'} icon={<TrendingUp size={18} />}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 12 }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          border: `4px solid ${scoreColor}`, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          fontSize: 20, fontWeight: 700, color: scoreColor,
        }}>
          {Math.round(s)}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, color: '#94A3B8' }}>综合趋势评分</div>
          <div style={{ display: 'flex', gap: 12, marginTop: 4 }}>
            {data?.indexList?.slice(0, 4).map((idx: any) => (
              <span key={idx.code} style={{
                fontSize: 12, color: idx.changePct >= 0 ? '#00B42A' : '#F53F3F',
              }}>
                {idx.name} {idx.changePct > 0 ? '+' : ''}{idx.changePct}%
              </span>
            ))}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 12, color: '#94A3B8', marginBottom: 4 }}>
        <BarChart3 size={12} style={{ display: 'inline', marginRight: 4 }} />
        行业热度 TOP{data?.industryHotList?.length || 0}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {data?.industryHotList?.slice(0, 10).map((ind: any, i: number) => (
          <span key={ind.name} style={{
            padding: '3px 8px', borderRadius: 4, fontSize: 11,
            background: i < 3 ? 'rgba(22,119,255,0.12)' : 'rgba(255,255,255,0.04)',
            color: i < 3 ? '#1677FF' : '#94A3B8',
          }}>
            {ind.name} {ind.boomScore}
          </span>
        ))}
      </div>
    </DashboardCard>
  );
}

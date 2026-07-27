/**
 * v2.1.0 模块一：市场趋势
 * 布局：70/30 左右分栏 — 左侧指数趋势图 + 右侧双仪表盘 + 底部行业热度
 */
import { useEffect, useState, useCallback } from 'react';
import { TrendingUp, Activity } from 'lucide-react';
import { DashboardCard } from './DashboardCard';

const TIME_RANGES = [
  { key: '1d', label: '1日' },
  { key: '3d', label: '3日' },
  { key: '7d', label: '7日' },
  { key: '15d', label: '15日' },
  { key: '30d', label: '30日' },
];

export function MarketTrend() {
  const [data, setData] = useState<any>(null);
  const [timeRange, setTimeRange] = useState('7d');

  const doFetch = useCallback(async () => {
    try {
      const r = await window.fetch(`/api/v1/market/trend?timeRange=${timeRange}`);
      const j = await r.json();
      if (j.code === 200) setData(j.data);
    } catch { /* */ }
  }, [timeRange]);

  useEffect(() => { doFetch(); const t = setInterval(doFetch, 10_000); return () => clearInterval(t); }, [doFetch]);

  const s = data?.trendScore ?? 50;
  const scoreColor = s >= 70 ? '#00B42A' : s >= 55 ? '#1677FF' : s >= 45 ? '#FF7D00' : '#F53F3F';

  return (
    <DashboardCard title="市场趋势" subtitle={data?.trendStatus ?? '加载中'} icon={<TrendingUp size={18} />}>
      {/* 时间维度切换 */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 10 }}>
        {TIME_RANGES.map(t => (
          <button key={t.key} onClick={() => setTimeRange(t.key)} style={{
            padding: '2px 8px', borderRadius: 3, border: 'none', cursor: 'pointer',
            fontSize: 11, fontWeight: timeRange === t.key ? 600 : 400,
            background: timeRange === t.key ? 'rgba(22,119,255,0.15)' : 'transparent',
            color: timeRange === t.key ? '#1677FF' : '#64748B',
          }}>{t.label}</button>
        ))}
      </div>

      {/* 70/30 左右分栏 */}
      <div style={{ display: 'flex', gap: 14 }}>
        {/* 左 70%: 指数迷你趋势 */}
        <div style={{ flex: 7 }}>
          <div style={{
            height: 100, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(22,119,255,0.04)', border: '1px solid rgba(22,119,255,0.08)',
          }}>
            <span style={{ fontSize: 12, color: '#475569' }}>
              指数趋势图 ({timeRange}) — 沪深300 上证 创业板
            </span>
          </div>
          {/* 四大指数变化 */}
          <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
            {data?.indexList?.slice(0, 4).map((idx: any) => (
              <span key={idx.code} style={{
                fontSize: 11,
                color: (idx.changePct ?? 0) >= 0 ? '#00B42A' : '#F53F3F',
              }}>
                <span style={{ color: '#94A3B8' }}>{idx.name}</span>{' '}
                {(idx.changePct ?? 0) > 0 ? '+' : ''}{idx.changePct?.toFixed?.(1) ?? '--'}%
              </span>
            ))}
          </div>
        </div>

        {/* 右 30%: 双仪表盘 */}
        <div style={{ flex: 3, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 60, height: 60, borderRadius: '50%',
            border: `4px solid ${scoreColor}`, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            fontSize: 18, fontWeight: 700, color: scoreColor,
          }}>
            {Math.round(s)}
          </div>
          <span style={{ fontSize: 11, color: '#94A3B8' }}>趋势评分</span>
          <span style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 3,
            background: `${scoreColor}18`, color: scoreColor, fontWeight: 600,
          }}>
            {data?.trendStatus || '--'}
          </span>
        </div>
      </div>

      {/* 底部: 行业热度 TOP8 */}
      <div style={{ marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: 8 }}>
        <div style={{ fontSize: 11, color: '#64748B', marginBottom: 6 }}>
          <Activity size={11} style={{ display: 'inline', marginRight: 3 }} />
          行业热度
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {data?.industryHotList?.slice(0, 8).map((ind: any, i: number) => (
            <span key={ind.name} style={{
              padding: '3px 7px', borderRadius: 3, fontSize: 10,
              background: i < 3 ? 'rgba(22,119,255,0.1)' : 'rgba(255,255,255,0.03)',
              color: i < 3 ? '#1677FF' : '#94A3B8',
              fontWeight: i < 3 ? 600 : 400,
            }}>
              {ind.name} {ind.boomScore}
            </span>
          ))}
        </div>
      </div>
    </DashboardCard>
  );
}

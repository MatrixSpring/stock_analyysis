/**
 * v2.1.0 模块四：国家长线赛道
 */
import { useEffect, useState, useCallback } from 'react';
import { Landmark, TrendingUp } from 'lucide-react';
import { DashboardCard } from './DashboardCard';

export function PolicyTrack() {
  const [data, setData] = useState<any>(null);

  const doFetch = useCallback(async () => {
    try {
      const r = await window.fetch('/api/v1/policy/track');
      const j = await r.json();
      if (j.code === 200) setData(j.data);
    } catch { /* */ }
  }, []);

  useEffect(() => { doFetch(); const t = setInterval(doFetch, 60_000); return () => clearInterval(t); }, [doFetch]);

  return (
    <DashboardCard title="国家长线赛道" subtitle="政策锚定 · 长线价值" icon={<Landmark size={18} />}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8 }}>
        {data?.tracks?.map((t: any) => {
          const barColor = t.boomScore >= 70 ? '#00B42A' : t.boomScore >= 50 ? '#1677FF' : '#FF7D00';
          return (
            <div key={t.trackName} style={{
              padding: 10, borderRadius: 6, cursor: 'pointer',
              background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>{t.trackName}</span>
                <TrendingUp size={12} style={{ color: barColor }} />
              </div>
              <div style={{ fontSize: 10, color: '#94A3B8', marginBottom: 6 }}>{t.policyDesc}</div>
              {/* Score bar */}
              <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${Math.min(100, t.boomScore)}%`,
                  background: barColor, transition: 'width 0.3s',
                }} />
              </div>
              <div style={{ fontSize: 11, color: barColor, marginTop: 3, fontWeight: 600 }}>
                {t.boomScore}/100
              </div>
            </div>
          );
        }) || <div style={{ color: '#94A3B8', fontSize: 13, padding: 20, textAlign: 'center' }}>加载赛道数据...</div>}
      </div>
    </DashboardCard>
  );
}

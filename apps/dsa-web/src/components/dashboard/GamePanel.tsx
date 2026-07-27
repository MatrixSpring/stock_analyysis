/**
 * v2.1.0 模块五+六：资金博弈 — 短线 + 长线
 */
import { useEffect, useState, useCallback } from 'react';
import { Zap, Clock } from 'lucide-react';
import { DashboardCard } from './DashboardCard';

export function GameShort() {
  const [data, setData] = useState<any>(null);

  const doFetch = useCallback(async () => {
    try {
      const r = await window.fetch('/api/v1/game/short');
      const j = await r.json();
      if (j.code === 200) setData(j.data);
    } catch { /* */ }
  }, []);

  useEffect(() => { doFetch(); const t = setInterval(doFetch, 10_000); return () => clearInterval(t); }, [doFetch]);

  const score = data?.gameScore ?? 50;
  const scoreColor = score >= 70 ? '#00B42A' : score >= 50 ? '#1677FF' : '#FF7D00';

  return (
    <DashboardCard title="短线博弈" subtitle="日内资金异动" icon={<Zap size={18} />}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
        <div style={{
          width: 48, height: 48, borderRadius: '50%', border: `3px solid ${scoreColor}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 16, fontWeight: 700, color: scoreColor,
        }}>
          {Math.round(score)}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, color: '#94A3B8', marginBottom: 4 }}>主力资金 TOP5</div>
          {data?.mainFundList?.slice(0, 5).map((s: any) => (
            <div key={s.code} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
              <span style={{ color: '#fff' }}>{s.code}</span>
              <span style={{ color: s.mainNetIn >= 0 ? '#00B42A' : '#F53F3F' }}>
                {s.mainNetIn > 0 ? '+' : ''}{(s.mainNetIn / 10000).toFixed(1)}万
              </span>
            </div>
          ))}
        </div>
      </div>
    </DashboardCard>
  );
}

export function GameLong() {
  const [data, setData] = useState<any>(null);

  const doFetch = useCallback(async () => {
    try {
      const r = await window.fetch('/api/v1/game/long');
      const j = await r.json();
      if (j.code === 200) setData(j.data);
    } catch { /* */ }
  }, []);

  useEffect(() => { doFetch(); const t = setInterval(doFetch, 30_000); return () => clearInterval(t); }, [doFetch]);

  const score = data?.baseGameScore ?? 50;
  const scoreColor = score >= 70 ? '#00B42A' : score >= 50 ? '#1677FF' : '#FF7D00';

  return (
    <DashboardCard title="长线博弈" subtitle="赛道轮动·机构偏好" icon={<Clock size={18} />}>
      <div style={{ fontSize: 24, fontWeight: 700, color: scoreColor, marginBottom: 8 }}>
        {Math.round(score)}<span style={{ fontSize: 13, color: '#94A3B8' }}>/100</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {data?.industryRotateList?.slice(0, 5).map((ind: any) => (
          <div key={ind.name} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: '#94A3B8' }}>{ind.name}</span>
            <span style={{ color: ind.boomScore >= 65 ? '#00B42A' : '#94A3B8', fontWeight: 600 }}>
              {ind.boomScore}
            </span>
          </div>
        ))}
      </div>
    </DashboardCard>
  );
}

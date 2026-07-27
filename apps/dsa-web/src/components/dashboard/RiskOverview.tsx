/**
 * v2.1.0 模块三：风险可视化 — 饼图 + 预警列表 + 运维状态
 */
import { useEffect, useState, useCallback } from 'react';
import { ShieldAlert, AlertTriangle } from 'lucide-react';
import { DashboardCard } from './DashboardCard';

const riskColors: Record<string, string> = {
  '数据残缺': '#FF7D00', '成交量不足': '#F53F3F', '财务异常': '#1677FF',
  'ST风险': '#FF7D00', '接口异常': '#F53F3F',
};

export function RiskOverview() {
  const [data, setData] = useState<any>(null);

  const doFetch = useCallback(async () => {
    try {
      const r = await window.fetch('/api/v1/risk/overview');
      const j = await r.json();
      if (j.code === 200) setData(j.data);
    } catch { /* */ }
  }, []);

  useEffect(() => { doFetch(); const t = setInterval(doFetch, 10_000); return () => clearInterval(t); }, [doFetch]);

  const stats = data?.riskStat || {};
  const total = Object.values(stats).reduce((a: number, b: any) => a + (b as number), 0) || 1;
  const sys = data?.systemRisk || {};

  // Simple inline "pie chart" as colored bar segments
  const entries = Object.entries(stats).filter(([, v]) => (v as number) > 0) as [string, number][];

  return (
    <DashboardCard title="风险监控" icon={<ShieldAlert size={18} />}>
      {/* Bar segments */}
      <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', marginBottom: 10 }}>
        {entries.map(([k, v]) => (
          <div key={k} style={{
            width: `${(v / total) * 100}%`, height: '100%',
            background: riskColors[k] || '#94A3B8',
          }} />
        ))}
        {!entries.length && <div style={{ width: '100%', background: 'rgba(255,255,255,0.05)' }} />}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10, fontSize: 11 }}>
        {entries.map(([k, v]) => (
          <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 3, color: '#94A3B8' }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: riskColors[k] }} />
            {k}:{v}
          </span>
        ))}
      </div>

      {/* System health */}
      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#94A3B8' }}>
        <span>缓存命中: <b style={{ color: sys.cacheHitRate > 50 ? '#00B42A' : '#FF7D00' }}>{sys.cacheHitRate}%</b></span>
        <span>
          接口失败率:{' '}
          <b style={{ color: sys.interfaceFailRate < 5 ? '#00B42A' : '#F53F3F' }}>
            {sys.interfaceFailRate}%
          </b>
        </span>
        <span>
          黑名单: <b style={{ color: '#FF7D00' }}>{data?.blackListCount ?? 0}</b>
        </span>
      </div>

      {sys.interfaceFailRate > 3 && (
        <div style={{
          marginTop: 8, padding: '6px 10px', borderRadius: 4, fontSize: 11,
          background: 'rgba(245,63,63,0.08)', color: '#F53F3F',
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <AlertTriangle size={12} /> 接口异常率偏高，请检查网络或数据源
        </div>
      )}
    </DashboardCard>
  );
}

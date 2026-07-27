/**
 * v2.1.0 全局系统状态栏 — 顶部常驻，实时展示系统运行状态
 */
import { useEffect, useState, useCallback } from 'react';
import { Activity, Server, Database, Shield } from 'lucide-react';

interface SystemStatus {
  systemVersion: string;
  runTime: string;
  cacheHitRate: number;
  interfaceSuccessRate: number;
  blackListNum: number;
  systemStatus: 'normal' | 'warn' | 'error';
}

const statusConfig = {
  normal: { color: '#00B42A', bg: 'rgba(0,180,42,0.1)', label: '正常' },
  warn: { color: '#FF7D00', bg: 'rgba(255,125,0,0.1)', label: '告警' },
  error: { color: '#F53F3F', bg: 'rgba(245,63,63,0.1)', label: '异常' },
};

export function SystemStatusBar() {
  const [status, setStatus] = useState<SystemStatus | null>(null);

  const doFetchStatus = useCallback(async () => {
    try {
      const res = await window.fetch('/api/v1/system/status');
      const json = await res.json();
      if (json.code === 200) setStatus(json.data);
    } catch { /* degraded */ }
  }, []);

  useEffect(() => {
    doFetchStatus();
    const t = setInterval(doFetchStatus, 60_000);
    return () => clearInterval(t);
  }, [doFetchStatus]);

  const cfg = status ? statusConfig[status.systemStatus] : statusConfig.normal;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 18,
      padding: '6px 20px', fontSize: 12,
      background: 'rgba(21,26,40,0.85)', backdropFilter: 'blur(8px)',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      color: '#94A3B8', flexWrap: 'wrap',
    }}>
      <span style={{ color: '#fff', fontWeight: 600, marginRight: 8 }}>
        DSA {status?.systemVersion || '2.1.0'}
      </span>

      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Activity size={12} /> {status?.runTime || '--'}
      </span>

      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Database size={12} /> 缓存 {status?.cacheHitRate ?? '--'}%
      </span>

      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Server size={12} /> 接口 {status?.interfaceSuccessRate ?? '--'}%
      </span>

      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Shield size={12} /> 黑名单 {status?.blackListNum ?? 0}
      </span>

      <span style={{
        marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
        padding: '2px 10px', borderRadius: 4, fontSize: 11,
        background: cfg.bg, color: cfg.color, fontWeight: 600,
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%', background: cfg.color,
          animation: status?.systemStatus === 'error' ? 'pulse 1.5s infinite' : undefined,
        }} />
        {cfg.label}
      </span>
    </div>
  );
}

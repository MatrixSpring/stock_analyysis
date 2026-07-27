import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { colors } from '../theme/tokens';
import apiClient from '../api';

interface GatewayStats {
  status?: string;
  total_requests?: number;
  success_rate?: number;
  avg_latency_ms?: number;
  by_type?: Record<string, number>;
  health?: Record<string, any>;
  readonly_guard?: {
    total_blocked: number;
    total_attempts: number;
    guard_enabled: boolean;
  };
}

const LEGACY_LINKS = [
  { path: '/', label: '首页仪表盘', desc: '原系统首页总览' },
  { path: '/chat', label: 'AI 对话', desc: 'Agent 聊天分析' },
  { path: '/portfolio', label: '投资组合', desc: '持仓管理与分析' },
  { path: '/backtest', label: '回测', desc: '历史回测评估' },
  { path: '/alerts', label: '告警', desc: '系统告警通知' },
  { path: '/settings', label: '设置', desc: '系统参数配置' },
  { path: '/screening', label: '选股筛选', desc: '股票筛选器' },
  { path: '/decision-signals', label: '决策信号', desc: '交易信号面板' },
  { path: '/usage', label: '用量统计', desc: 'Token 使用统计' },
];

const LegacyHubPage: React.FC = () => {
  const navigate = useNavigate();
  const [gatewayStats, setGatewayStats] = useState<GatewayStats | null>(null);

  useEffect(() => {
    const fetchGatewayStats = async () => {
      try {
        const resp = await apiClient.get('/api/v1/health/gateway');
        setGatewayStats(resp.data);
      } catch {
        // Gateway stats unavailable — not a critical error
      }
    };
    fetchGatewayStats();
  }, []);

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#fff', margin: '0 0 8px' }}>
          旧版历史功能
        </h1>
        <p style={{ fontSize: 14, color: '#94A3B8', margin: 0 }}>
          历史功能归档页。已完全适配新版管理后台架构，所有数据访问统一通过 LegacyGateway 网关。
          旧模块仅支持只读回溯查询，写入操作已被拦截。
        </p>
      </div>

      {/* Gateway 状态 */}
      {gatewayStats && gatewayStats.status === 'ok' && (
        <div style={{
          background: colors.card, borderRadius: 10, padding: 20, marginBottom: 20,
          border: '1px solid rgba(56, 189, 248, 0.15)', boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
        }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: '#38bdf8', marginBottom: 16 }}>
            统一数据网关 (LegacyGateway) 运行状态
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
            <StatTile label="总请求数" value={String(gatewayStats.total_requests ?? 0)} />
            <StatTile label="成功率" value={`${((gatewayStats.success_rate ?? 1) * 100).toFixed(1)}%`} />
            <StatTile label="平均延迟" value={`${(gatewayStats.avg_latency_ms ?? 0).toFixed(1)}ms`} />
            <StatTile
              label="写拦截"
              value={String(gatewayStats.readonly_guard?.total_blocked ?? 0)}
              color={gatewayStats.readonly_guard?.guard_enabled ? '#22c55e' : '#f59e0b'}
            />
          </div>
          {gatewayStats.by_type && Object.keys(gatewayStats.by_type).length > 0 && (
            <div style={{ fontSize: 12, color: '#64748B' }}>
              数据类型分布: {Object.entries(gatewayStats.by_type).map(([k, v]) => `${k}(${v})`).join(' · ')}
            </div>
          )}
        </div>
      )}

      {/* 功能入口 */}
      <div style={{
        background: colors.card, borderRadius: 10, padding: 20, marginBottom: 20,
        border: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
      }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: '#fff', marginBottom: 12 }}>
          旧版功能入口
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {LEGACY_LINKS.map((link) => (
            <div
              key={link.path}
              onClick={() => navigate(link.path)}
              style={{
                padding: '14px 16px', borderRadius: 8, cursor: 'pointer',
                background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 600, color: '#CBD5E1', marginBottom: 4 }}>
                {link.label}
              </div>
              <div style={{ fontSize: 12, color: '#64748B' }}>{link.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 使用说明 */}
      <div style={{
        background: colors.card, borderRadius: 10, padding: 20,
        border: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
      }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: '#fff', marginBottom: 8 }}>使用建议</h3>
        <p style={{ fontSize: 14, color: '#CBD5E1', lineHeight: 1.8, margin: 0 }}>
          ✅ 日常实盘、策略迭代、风控管控、投研分析请使用新版四大核心模块。
          <br />
          📋 本页仅供历史数据查阅、旧版回测日志归档。
          <br />
          🔒 旧模块所有写入操作已被 ReadOnlyGuard 拦截，保证数据安全。
        </p>
      </div>
    </div>
  );
};

const StatTile: React.FC<{ label: string; value: string; color?: string }> = ({
  label, value, color = '#38bdf8',
}) => (
  <div style={{
    padding: '10px 12px', borderRadius: 8,
    background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
  }}>
    <div style={{ fontSize: 11, color: '#64748B', marginBottom: 4 }}>{label}</div>
    <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
  </div>
);

export default LegacyHubPage;

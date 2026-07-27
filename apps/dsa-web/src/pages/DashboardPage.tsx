/**
 * v2.1.0 商用首页仪表盘
 *
 * 布局：顶部悬浮状态栏 + 2行×3列自适应六宫格 + 底部传统工具入口
 * 规格：模块等比例缩放 / 深色主题 #0F131E / 8px 卡片圆角 / 20px 内边距
 */
import { Link } from 'react-router-dom';
import {
  BarChart3, Clock, TrendingUp, Shield, Star, Settings,
  Zap, AlertTriangle,
} from 'lucide-react';
import {
  SystemStatusBar, MarketTrend, RecentStock,
  RiskOverview, PolicyTrack, GameShort, GameLong,
  ModuleNavigator,
} from '../components/dashboard';

function LegacyToolsBar() {
  const tools = [
    { to: '/', icon: TrendingUp, label: '策略选股' },
    { to: '/backtest', icon: BarChart3, label: '回测' },
    { to: '/stock-screening', icon: Zap, label: 'K线查询' },
    { to: '/strategy-center', icon: Clock, label: '传统指标' },
    { to: '/history', icon: Star, label: '历史记录' },
    { to: '/portfolio', icon: Shield, label: '自选股' },
    { to: '/alerts', icon: AlertTriangle, label: '告警' },
    { to: '/settings', icon: Settings, label: '设置' },
    { to: '/auto-strategy', icon: Zap, label: '全自动策略中心' },
  ];

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
      padding: '14px 20px', borderRadius: 8, marginTop: 16,
      background: 'rgba(21,26,40,0.4)', border: '1px solid rgba(255,255,255,0.04)',
    }}>
      <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600, marginRight: 4 }}>
        传统工具
      </span>
      {tools.map(t => (
        <Link key={t.to} to={t.to} style={{
          display: 'flex', alignItems: 'center', gap: 5, fontSize: 12,
          color: '#94A3B8', textDecoration: 'none',
          transition: 'color 0.15s',
        }}
          onMouseEnter={e => (e.currentTarget.style.color = '#1677FF')}
          onMouseLeave={e => (e.currentTarget.style.color = '#94A3B8')}
        >
          <t.icon size={14} />
          {t.label}
        </Link>
      ))}
      <span style={{ marginLeft: 'auto', fontSize: 10, color: '#475569' }}>
        算法 v2.1.0 统一驱动
      </span>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <div style={{ background: '#0F131E', color: '#fff', minHeight: '100vh' }}>
      {/* === 顶部悬浮状态栏 === */}
      <SystemStatusBar />

      <div style={{ maxWidth: 1600, margin: '0 auto', padding: '16px 24px' }}>
        {/* === 页面标题 === */}
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 2, letterSpacing: -0.3 }}>
          量化决策终端
        </h1>
        <p style={{ fontSize: 13, color: '#64748B', marginBottom: 14 }}>
          短中长线交易 · 政策赛道 · 资金博弈 · 全维度风控
        </p>

        <ModuleNavigator />

        {/* === 第一行：市场趋势 + 最近股票 + 风险监控 === */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 14, marginBottom: 14,
        }}>
          <MarketTrend />
          <RecentStock />
          <RiskOverview />
        </div>

        {/* === 第二行：国家长线 + 短期博弈 + 长远博弈 === */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 14, marginBottom: 14,
        }}>
          <PolicyTrack />
          <GameShort />
          <GameLong />
        </div>

        {/* === 底部：传统工具入口 === */}
        <LegacyToolsBar />
      </div>

      {/* 响应式样式 */}
      <style>{`
        @media (max-width: 1200px) {
          .dashboard-grid { grid-template-columns: repeat(2, 1fr) !important; }
        }
        @media (max-width: 768px) {
          .dashboard-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

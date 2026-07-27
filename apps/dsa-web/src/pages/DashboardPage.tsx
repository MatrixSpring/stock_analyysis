/**
 * v2.1.0 商用首页仪表盘 — 六大核心模块 + 系统状态栏
 */
import type React from 'react';
import {
  SystemStatusBar, MarketTrend, RecentStock,
  RiskOverview, PolicyTrack, GameShort, GameLong,
} from '../components/dashboard';

export default function DashboardPage() {
  return (
    <div style={{ background: '#0F131E', color: '#fff', minHeight: '100vh' }}>
      <SystemStatusBar />
      <div style={{ maxWidth: 1440, margin: '0 auto', padding: '16px 20px' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
          量化决策终端
        </h1>
        <p style={{ fontSize: 13, color: '#94A3B8', marginBottom: 16 }}>
          短中长线交易 · 政策赛道 · 资金博弈 · 全维度风控
        </p>

        {/* Row 1: 市场趋势 + 最近股票 */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 12 }}>
          <MarketTrend />
          <RecentStock />
        </div>

        {/* Row 2: 风险监控 + 政策赛道 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12, marginBottom: 12 }}>
          <RiskOverview />
          <PolicyTrack />
        </div>

        {/* Row 3: 短线博弈 + 长线博弈 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <GameShort />
          <GameLong />
        </div>

        {/* 传统工具入口 */}
        <div style={{
          marginTop: 16, padding: '12px 16px', borderRadius: 8,
          background: 'rgba(21,26,40,0.5)', border: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: '#94A3B8',
        }}>
          <span>传统量化工具</span>
          <a href="/" style={{ color: '#1677FF', textDecoration: 'none' }}>策略选股</a>
          <a href="/backtest" style={{ color: '#1677FF', textDecoration: 'none' }}>回测</a>
          <a href="/portfolio" style={{ color: '#1677FF', textDecoration: 'none' }}>自选</a>
          <a href="/alerts" style={{ color: '#1677FF', textDecoration: 'none' }}>告警</a>
          <a href="/settings" style={{ color: '#1677FF', textDecoration: 'none' }}>设置</a>
          <span style={{ marginLeft: 'auto', fontSize: 11 }}>算法 v2.1.0 统一驱动</span>
        </div>
      </div>
    </div>
  );
}

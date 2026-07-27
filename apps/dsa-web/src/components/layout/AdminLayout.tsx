import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import SidebarMenu from './SidebarMenu';
import { colors } from '../../theme/tokens';

const PAGE_TITLES: Record<string, string> = {
  '/old': '旧版历史功能',
  '/strategy-center': '全自动策略中心',
  '/game-engine': '多资金博弈引擎',
  '/research-platform': '分层投研分析台',
  '/risk-performance': '智能风控绩效台',
};

const AdminLayout: React.FC = () => {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] || '量化投研中台';

  return (
    <div style={{ display: 'flex', width: '100%', height: '100vh', overflow: 'hidden', background: colors.bg }}>
      <SidebarMenu />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <header style={{
          height: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 24px', background: 'rgba(30,41,59,0.8)',
          borderBottom: `1px solid ${colors.border}`, flexShrink: 0,
        }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: colors.text }}>{title}</span>
          <span />
        </header>
        <main style={{ flex: 1, padding: 24, overflowY: 'auto', overflowX: 'hidden' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;

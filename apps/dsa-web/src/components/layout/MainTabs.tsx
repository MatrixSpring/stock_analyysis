/**
 * 全局顶部 Tab 导航栏 — 4 大业务模块 + 旧版功能
 * 完全增量开发，不修改旧路由/旧组件
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Brain, Gamepad2, FileSearch, ShieldCheck, Archive } from 'lucide-react';
import { colors } from '../../theme/tokens';

interface TabDef {
  id: string; label: string; path: string; icon: React.ReactNode;
}

const TABS: TabDef[] = [
  { id: 'strategy',  label: '全自动策略中心',  path: '/strategy-center',  icon: <Brain size={16} /> },
  { id: 'game',      label: '多资金博弈引擎',  path: '/game-engine',      icon: <Gamepad2 size={16} /> },
  { id: 'research',  label: '分层投研分析台',  path: '/research-platform', icon: <FileSearch size={16} /> },
  { id: 'risk',      label: '智能风控绩效台',  path: '/risk-performance',  icon: <ShieldCheck size={16} /> },
  { id: 'legacy',    label: '历史分析/旧版',    path: '/',                 icon: <Archive size={16} /> },
];

const TAB_STORAGE_KEY = 'dsa_active_tab';

const MainTabs: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [active, setActive] = useState<string>(() => {
    return localStorage.getItem(TAB_STORAGE_KEY) || 'strategy';
  });

  // Sync active tab with current route
  useEffect(() => {
    const matched = TABS.find((t) => location.pathname.startsWith(t.path) && t.path !== '/');
    if (matched) {
      setActive(matched.id);
      localStorage.setItem(TAB_STORAGE_KEY, matched.id);
    } else if (location.pathname === '/' || location.pathname.startsWith('/home')) {
      setActive('legacy');
      localStorage.setItem(TAB_STORAGE_KEY, 'legacy');
    }
  }, [location.pathname]);

  const handleTabClick = (tab: TabDef) => {
    setActive(tab.id);
    localStorage.setItem(TAB_STORAGE_KEY, tab.id);
    navigate(tab.path);
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 0,
      background: colors.card, borderBottom: `1px solid ${colors.border}`,
      padding: '0 16px', height: 44, overflowX: 'auto', flexShrink: 0,
    }}>
      {TABS.map((tab) => {
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '10px 18px', border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: isActive ? 600 : 400,
              color: isActive ? colors.primary : colors.textSecondary,
              background: isActive ? colors.primary + '14' : 'transparent',
              borderBottom: isActive ? `2px solid ${colors.primary}` : '2px solid transparent',
              transition: 'all 0.15s', whiteSpace: 'nowrap',
              borderRadius: '4px 4px 0 0',
            }}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
};

export default MainTabs;

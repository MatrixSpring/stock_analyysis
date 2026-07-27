import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { colors } from '../../theme/tokens';

const MENU_ITEMS = [
  { path: '/old', name: '旧版历史功能', icon: '🕰' },
  { path: '/strategy-center', name: '全自动策略中心', icon: '◈' },
  { path: '/game-engine', name: '多资金博弈引擎', icon: '◆' },
  { path: '/research-platform', name: '分层投研分析台', icon: '◇' },
  { path: '/risk-performance', name: '智能风控绩效台', icon: '◆' },
];

const STORAGE_KEY = 'admin_menu_path';

const SidebarMenu: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [active, setActive] = useState(() =>
    localStorage.getItem(STORAGE_KEY) || '/strategy-center',
  );

  // Redirect / to cached/default
  useEffect(() => {
    if (location.pathname === '/') {
      navigate(active, { replace: true });
    }
  }, []);

  useEffect(() => {
    const m = MENU_ITEMS.find((i) => location.pathname === i.path || (i.path !== '/' && location.pathname.startsWith(i.path)));
    if (m) {
      setActive(m.path);
      localStorage.setItem(STORAGE_KEY, m.path);
    }
  }, [location.pathname]);

  const handleClick = (path: string) => {
    setActive(path);
    localStorage.setItem(STORAGE_KEY, path);
    navigate(path);
  };

  return (
    <aside style={{
      width: 220, height: '100vh', display: 'flex', flexDirection: 'column',
      background: 'rgba(30,41,59,0.95)', backdropFilter: 'blur(10px)',
      borderRight: `1px solid ${colors.border}`, flexShrink: 0,
    }}>
      {/* Logo — click to home */}
      <div
        onClick={() => handleClick('/strategy-center')}
        style={{
          height: 70, display: 'flex', alignItems: 'center', justifyContent: 'center',
          borderBottom: `1px solid ${colors.border}`, cursor: 'pointer',
          transition: 'opacity 0.2s',
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.85'; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1'; }}
      >
        <span style={{ fontSize: 18, fontWeight: 700, color: '#fff', letterSpacing: 1 }}>
          量化交易中台
        </span>
      </div>

      {/* Menu */}
      <nav style={{ flex: 1, padding: '16px 8px' }}>
        {MENU_ITEMS.map((item) => {
          const isActive = active === item.path;
          return (
            <div
              key={item.path}
              onClick={() => handleClick(item.path)}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '14px 16px', borderRadius: 8, marginBottom: 8,
                cursor: 'pointer', transition: 'all 0.3s', fontSize: 14,
                background: isActive ? colors.primary : 'transparent',
                color: isActive ? '#fff' : '#CBD5E1',
                boxShadow: isActive ? `0 4px 12px ${colors.primary}59` : 'none',
                fontWeight: isActive ? 600 : 400,
              }}
            >
              <span style={{ fontSize: 18, width: 20, textAlign: 'center' }}>{item.icon}</span>
              <span>{item.name}</span>
            </div>
          );
        })}
      </nav>
    </aside>
  );
};

export default SidebarMenu;

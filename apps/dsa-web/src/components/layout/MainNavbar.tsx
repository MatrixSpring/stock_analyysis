import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { colors } from '../../theme/tokens';

interface NavItem {
  path: string; name: string; icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: '/strategy-center', name: '全自动策略中心', icon: '◈' },
  { path: '/game-engine', name: '多资金博弈引擎', icon: '◆' },
  { path: '/research-platform', name: '分层投研分析台', icon: '◇' },
  { path: '/risk-performance', name: '智能风控绩效台', icon: '◆' },
];

const NAV_STORAGE_KEY = 'dsa_nav_path';

const MainNavbar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [active, setActive] = useState(() =>
    NAV_ITEMS.find((n) => location.pathname.startsWith(n.path))?.path || NAV_ITEMS[0].path,
  );

  // Redirect / to first tab
  useEffect(() => {
    if (location.pathname === '/') {
      const cached = localStorage.getItem(NAV_STORAGE_KEY);
      navigate(cached || '/strategy-center', { replace: true });
    }
  }, [location.pathname, navigate]);

  // Sync active state
  useEffect(() => {
    const matched = NAV_ITEMS.find((n) => location.pathname.startsWith(n.path));
    if (matched) {
      setActive(matched.path);
      localStorage.setItem(NAV_STORAGE_KEY, matched.path);
    }
  }, [location.pathname]);

  const handleNav = (path: string) => {
    setActive(path);
    localStorage.setItem(NAV_STORAGE_KEY, path);
    navigate(path);
  };

  return (
    <nav style={{
      width: '100%', height: 64, display: 'flex', alignItems: 'center',
      background: 'rgba(30,41,59,0.85)', backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      position: 'sticky', top: 0, zIndex: 999, padding: '0 2%',
    }}>
      {/* Brand */}
      <span style={{
        fontSize: 18, fontWeight: 600, color: '#fff',
        letterSpacing: 1, marginRight: 40,
      }}>
        量化投研交易中台
      </span>

      {/* Main nav */}
      <div style={{ display: 'flex', gap: 8, flex: 1 }}>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.path}
            onClick={() => handleNav(item.path)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 18px', borderRadius: 6, cursor: 'pointer',
              border: 'none', fontSize: 14, fontWeight: active === item.path ? 600 : 400,
              color: active === item.path ? '#fff' : '#CBD5E1',
              background: active === item.path ? colors.primary : 'transparent',
              boxShadow: active === item.path ? `0 2px 8px ${colors.primary}4D` : 'none',
              transition: 'all 0.25s',
            }}
          >
            <span style={{ fontSize: 16 }}>{item.icon}</span>
            <span>{item.name}</span>
          </button>
        ))}
      </div>

      {/* Legacy link */}
      <button
        onClick={() => { navigate('/'); }}
        style={{
          padding: '8px 16px', borderRadius: 6, cursor: 'pointer', border: 'none',
          fontSize: 13, opacity: 0.75, color: location.pathname === '/' ? '#fff' : '#CBD5E1',
          background: location.pathname === '/' ? '#475569' : 'transparent',
        }}
      >
        旧版历史功能
      </button>
    </nav>
  );
};

export default MainNavbar;

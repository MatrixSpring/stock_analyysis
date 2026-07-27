/**
 * v3.0 全模块导航器 — 一键访问所有高阶功能模块
 */
import type React from 'react';
import { Link } from 'react-router-dom';
import { TrendingUp, GitGraph, MessageSquare, DollarSign, BarChart3, Bot, Globe, Shield, Settings, Zap } from 'lucide-react';

interface NavItem { to: string; icon: React.ElementType; label: string; desc: string; color: string }

const MODULES: NavItem[] = [
  { to: '/dashboard', icon: TrendingUp, label: '量化决策终端', desc: '六宫格仪表盘 · 短中长线决策', color: '#1677FF' },
  { to: '/visuals/fund-flow', icon: GitGraph, label: '资金流向拓扑', desc: '桑基图 · 全链路资金流转', color: '#36CFC9' },
  { to: '/visuals/participant', icon: DollarSign, label: '参与者博弈图谱', desc: '力导向图 · 六大主体博弈', color: '#722ED1' },
  { to: '/visuals/geo-event', icon: Globe, label: '地缘事件传导', desc: '事件→赛道→节点传导', color: '#FAAD14' },
  { to: '/visuals/dimension-tree', icon: GitGraph, label: '维度分层树', desc: '六大维度层级展开', color: '#1677FF' },
  { to: '/visuals/industry-chain', icon: GitGraph, label: '产业链异动', desc: '五大集群动态监测', color: '#36CFC9' },
  { to: '/backtest', icon: BarChart3, label: '量化回测', desc: '策略验证 · 因子评测', color: '#F53F3F' },
  { to: '/alerts', icon: Shield, label: '风险告警', desc: '实时预警 · 风控溯源', color: '#FAAD14' },
  { to: '/portfolio', icon: DollarSign, label: '自选组合', desc: '持仓管理 · 收益跟踪', color: '#1677FF' },
  { to: '/settings', icon: Settings, label: '系统设置', desc: '数据源 · LLM · 通知', color: '#94A3B8' },
];

export const ModuleNavigator: React.FC = () => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10, marginBottom: 16 }}>
    {MODULES.map(m => (
      <Link key={m.to} to={m.to} style={{ textDecoration: 'none' }}>
        <div style={{
          padding: '14px 16px', borderRadius: 8, cursor: 'pointer',
          background: 'rgba(21,26,40,0.6)', border: `1px solid rgba(255,255,255,0.05)`,
          borderLeft: `3px solid ${m.color}`, transition: 'all 0.2s',
        }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(21,26,40,0.9)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(21,26,40,0.6)'; e.currentTarget.style.transform = ''; }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <m.icon size={16} style={{ color: m.color }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>{m.label}</span>
          </div>
          <div style={{ fontSize: 11, color: '#64748B' }}>{m.desc}</div>
        </div>
      </Link>
    ))}
  </div>
);

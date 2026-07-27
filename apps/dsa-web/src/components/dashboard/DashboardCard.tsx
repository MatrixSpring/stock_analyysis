/**
 * v2.1.0 通用仪表盘卡片组件 — 统一圆角/阴影/hover效果
 */
import type { ReactNode } from 'react';

interface Props {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  children: ReactNode;
  style?: React.CSSProperties;
  variant?: 'primary' | 'secondary';
}

export function DashboardCard({ title, subtitle, icon, children, style, variant = 'primary' }: Props) {
  const isSecondary = variant === 'secondary';
  return (
    <div style={{
      background: isSecondary ? 'rgba(21,26,40,0.5)' : '#151A28',
      borderRadius: 8,
      padding: 20,
      boxShadow: '0 2px 12px rgba(0,0,0,0.2)',
      border: '1px solid rgba(255,255,255,0.06)',
      transition: 'transform 0.15s, box-shadow 0.15s',
      cursor: 'default',
      ...style,
    }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)';
        (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.transform = '';
        (e.currentTarget as HTMLElement).style.boxShadow = '0 2px 12px rgba(0,0,0,0.2)';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12, gap: 8 }}>
        {icon && <span style={{ color: '#1677FF' }}>{icon}</span>}
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#fff' }}>{title}</h3>
          {subtitle && <span style={{ fontSize: 12, color: '#94A3B8' }}>{subtitle}</span>}
        </div>
      </div>
      {children}
    </div>
  );
}

/**
 * DSA Design Tokens — 专业量化深色主题
 * 对标：同花顺iFinD / 通达信专业版 / 量化策略后台
 */
export const colors = {
  primary: '#165DFF',
  success: '#00B42A',
  danger: '#F53F3F',
  warning: '#FF7D00',
  bg: '#0F172A',
  card: '#1E293B',
  text: '#FFFFFF',
  textSecondary: '#94A3B8',
  border: 'rgba(255,255,255,0.1)',
  hover: 'rgba(255,255,255,0.05)',
} as const;

export const statusColors = {
  bull: '#00B42A',
  shake: '#165DFF',
  drop: '#FF7D00',
  ice: '#F53F3F',
  active: '#00B42A',
  degraded: '#FF7D00',
  stopped: '#6B7280',
  fused: '#F53F3F',
} as const;

export const typography = {
  title: '18px',
  subtitle: '16px',
  body: '14px',
  caption: '12px',
} as const;

export const spacing = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 } as const;
export const radius = { sm: 4, md: 8, lg: 12 } as const;

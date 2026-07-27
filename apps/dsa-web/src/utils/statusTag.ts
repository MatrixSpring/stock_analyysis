/** 全局动态状态标签 */
export const STATUS_TAG_MAP: Record<string, { text: string; color: string }> = {
  up_continue: { text: '持续走强', color: '#00b42a' },
  up_flash: { text: '短期异动', color: '#ff7d00' },
  trend_reverse: { text: '趋势反转', color: '#722ed1' },
  policy_good: { text: '政策利好', color: '#00b42a' },
  geo_safe: { text: '地缘避险', color: '#ff7d00' },
  fund_out: { text: '资金出逃', color: '#f53f3f' },
  risk_up: { text: '风险加剧', color: '#f53f3f' },
  risk_down: { text: '风险缓释', color: '#00b42a' },
};

export function getAutoStatusTag(val: number, type: 'trend' | 'risk' = 'trend'): string {
  if (type === 'trend') {
    if (val > 0.6) return 'up_continue';
    if (val > 0.2) return 'up_flash';
    if (val < -0.6) return 'fund_out';
  }
  if (type === 'risk') {
    return val > 0.5 ? 'risk_up' : 'risk_down';
  }
  return '';
}

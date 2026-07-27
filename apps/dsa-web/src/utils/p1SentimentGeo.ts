/** P1-2: 舆情情绪量化 + 地缘事件生命周期 + 联动映射 */

/** 舆情情绪量化打分 */
export function calcPublicOpinionScore(positive: number, negative: number, neutral: number) {
  const total = positive + negative + neutral;
  if (total === 0) return { score: 50, hot: 0, tag: '情绪平稳' };
  const score = Math.floor(((positive - negative) / total) * 50 + 50);
  const hot = Math.min(100, Math.floor(total / 10));
  let tag = '情绪中性';
  if (score >= 70) tag = '情绪乐观·利好溢价';
  else if (score >= 55) tag = '情绪偏暖';
  else if (score <= 30) tag = '情绪悲观·利空压制';
  else if (score <= 45) tag = '情绪偏冷';
  return { score, hot, tag };
}

/** 异动三级分级 */
export function getFlashLevel(val: number) {
  if (val >= 80) return { level: 3, color: '#f53f3f', text: '重度异动' };
  if (val >= 50) return { level: 2, color: '#ff7d00', text: '中度异动' };
  return { level: 1, color: '#2378dd', text: '轻度异动' };
}

/** 节点视觉样式 (异动高亮 + 常态弱化) */
export function handleNodeVisualStyle<T extends { flashValue?: number; weight?: number }>(nodes: T[]) {
  return nodes.map(n => {
    const f = getFlashLevel(n.flashValue ?? 0);
    return { ...n, itemStyle: { color: f.color, opacity: f.level === 1 ? 0.65 : 1 }, symbolSize: (n.weight ?? 10) * (f.level === 1 ? 0.9 : 1), flashText: f.text };
  });
}

/** 地缘事件 → 商品/板块联动映射 */
export const GEO_LINK_MAP: Record<string, { commodity: string[]; sector: string[]; trend: string }> = {
  geo_war: { commodity: ['原油','天然气','黄金'], sector: ['能源油气','贵金属','军工'], trend: '短期利多能源、避险板块' },
  trade_policy: { commodity: ['工业金属','农产品'], sector: ['进出口贸易','制造业'], trend: '改变产业链成本，影响细分利润' },
  energy_policy: { commodity: ['原油','煤炭','电力'], sector: ['新能源','传统能源','储能'], trend: '重塑能源供需格局' },
};

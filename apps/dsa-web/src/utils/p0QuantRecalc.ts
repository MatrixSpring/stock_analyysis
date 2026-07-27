/** P0-2: 量化动态重算 + 事件衰减模型 */

/** 动态分位重算 */
export function calcQuantilePercent(history: number[], current: number): number {
  if (!history.length) return 50;
  const sorted = [...history].sort((a, b) => a - b);
  let c = 0; sorted.forEach(v => { if (current > v) c++; });
  return Math.floor((c / sorted.length) * 100);
}

/** 博弈胜率动态重算 */
export function calcGameWinRate(recentWins: { win: boolean }[]): number {
  if (!recentWins.length) return 50;
  return Math.floor((recentWins.filter(w => w.win).length / recentWins.length) * 100);
}

/** 事件强度动态衰减 (线性+尾部平滑) */
export function calcEventDecayPower(initPower: number, startTime: number, decayDays = 7): number {
  const passed = (Date.now() - startTime) / 86400000;
  if (passed <= 0) return initPower;
  if (passed >= decayDays) return 0;
  return Math.floor(initPower * (1 - passed / decayDays));
}

/** 事件生命周期阶段 */
export function getEventCycleStage(initPower: number, startTime: number, decayDays = 7) {
  const passed = (Date.now() - startTime) / 86400000;
  const r = passed / decayDays;
  if (r <= 0.2) return { stage: '发酵期', desc: '情绪升温，潜在冲击扩大' };
  if (r <= 0.5) return { stage: '高潮期', desc: '情绪顶点，盘面冲击最强' };
  if (r <= 0.85) return { stage: '降温期', desc: '情绪边际弱化' };
  return { stage: '消退期', desc: '事件影响基本消化' };
}

/** P3: 分类型事件自适应衰减周期 */
export function getEventDecayDayByType(type: string): number {
  const m: Record<string,number> = { geo_war:14, trade_policy:10, industry_policy:30, hot_spread:5, macro_notice:20 };
  return m[type] ?? 7;
}

/** P3: 分赛道舆情敏感度加权 */
export function getOpinionScoreByIndustry(type: string, baseScore: number): number {
  let w = 1;
  if (['new_energy','ai_tech'].includes(type)) w = 1.2;
  if (['coal','petroleum','metal'].includes(type)) w = 0.8;
  return clipScore(baseScore * w);
}
function clipScore(v: number){ return Math.max(0, Math.min(100, v)); }

/**
 * DSA 量化精细化计算工具 (对标 QMT/PTrade)
 * 分位计算 / 偏离度 / 波动率 / 动量 / 博弈胜率 / 风险等级
 */

/** 当前值在历史数组中的分位 (0-1) */
export function getQuantile(val: number, history: number[] = []): number {
  if (!history.length) return 0.5;
  let count = 0;
  for (const item of history) if (val > item) count++;
  return +(count / history.length).toFixed(2);
}

/** 偏离均值幅度 */
export function getDeviation(val: number, history: number[] = []): number {
  if (!history.length) return 0;
  const avg = history.reduce((a, b) => a + b, 0) / history.length;
  if (avg === 0) return 0;
  return +(((val - avg) / avg).toFixed(2));
}

/** 波动率 */
export function getVolatility(data: number[] = []): number {
  if (data.length < 5) return 0;
  const avg = data.reduce((a, b) => a + b, 0) / data.length;
  const variance = data.reduce((s, v) => s + (v - avg) ** 2, 0) / data.length;
  return +Math.sqrt(variance).toFixed(2);
}

/** 趋势动量强度 0-1 */
export function getMomentum(data: number[] = []): number {
  if (data.length < 3) return 0;
  return +Math.min(Math.abs((data.at(-1)! - data[0]) / data.length) * 10, 1).toFixed(2);
}

/** 博弈胜率 0-100 */
export function getGameWinRate(mainFund: number, retailFund: number): number {
  const total = Math.abs(mainFund) + Math.abs(retailFund);
  if (total === 0) return 50;
  return Math.round((Math.abs(mainFund) / total) * 100);
}

/** 四级风险等级 */
export function getRiskLevel(score: number) {
  if (score < 30) return { level: 1, text: '低风险', color: '#00b42a' };
  if (score < 50) return { level: 2, text: '可控风险', color: '#1677ff' };
  if (score < 70) return { level: 3, text: '中风险', color: '#ff7d00' };
  return { level: 4, text: '高风险', color: '#f53f3f' };
}

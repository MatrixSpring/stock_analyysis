/** P3: 高阶宏观定价 + 主力三维判定 + 分时态智能降噪 */

/** 高阶宏观金融量化传导模型 (实际利率/期限利差/波动率溢价) */
export function calcAdvancedMacroLink(usd: { cnyOffshoreRate: number }, bond: { nominalYield: number; inflationExpect: number; y10: number; y2: number }, oil: { volIndex: number }, gold: { volIndex: number }) {
  const realRate = bond.nominalYield - bond.inflationExpect;
  const termSpread = bond.y10 - bond.y2;
  const cnyPressure = usd.cnyOffshoreRate > 7.2 ? 80 : usd.cnyOffshoreRate > 7.0 ? 50 : 20;
  return {
    techSuppressScore: Math.min(100, realRate * 15),
    economyRecessScore: Math.min(100, Math.max(0, -termSpread * 20)),
    crossCapitalPressure: cnyPressure,
    energyPremium: oil.volIndex > 30 ? 70 : 30,
    safePremium: gold.volIndex > 25 ? 65 : 25,
  };
}

/** P3: 分时态智能降噪 (趋势市轻过滤，震荡市重过滤) */
export function smartSmoothFinanceData(list: number[], style?: { isBull?: boolean; isBear?: boolean; isShock?: boolean }): number[] {
  if (!list || list.length <= 3) return list;
  let sigma = 2;
  if (style?.isBull || style?.isBear) sigma = 1.2;
  if (style?.isShock) sigma = 2.5;
  const avg = list.reduce((a, b) => a + b, 0) / list.length;
  const std = Math.sqrt(list.reduce((s, v) => s + (v - avg) ** 2, 0) / list.length);
  return list.filter(v => v >= avg - std * sigma && v <= avg + std * sigma);
}

/** P3: 主力行为三维判定 (筹码/换手/量能) */
export function calcFullMainBehavior(sectors: { name: string; fundStay: number; crowd: number; turnover: number; volumeRatio: number; chipCost: { diff: number } }[]) {
  return sectors.map(s => {
    let action = '观望震荡', prob = 50;
    if (s.fundStay < 30 && s.turnover < 0.03 && s.chipCost.diff < 0.05) { action = '主力缩量洗盘，潜伏机会'; prob = 80; }
    else if (s.fundStay > 70 && s.turnover > 0.15 && s.crowd > 80) { action = '主力高位换手出货，风险累积'; prob = 85; }
    else if (s.fundStay > 60 && s.crowd < 40) { action = '主力持续加仓'; prob = 75; }
    return { ...s, mainAction: action, rotateProb: prob };
  });
}

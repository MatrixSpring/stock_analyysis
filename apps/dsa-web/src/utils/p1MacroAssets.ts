/** P1-3: 宏观资产底盘 + 跨境资金压力分级 */

export const MACRO_ASSET_TYPES = ['gold','crude_oil','natural_gas','coal','copper','aluminum','usd_index','cny_usd','eur_usd','gbp_usd','us10_bond','us2_bond','china10_bond','cn_us_spread','north_flow','south_flow','global_cap_pressure'];

export function getCapitalPressure(rate: number) {
  if (rate > 0.8) return { level: 5, text: '极致流入·流动性宽松' };
  if (rate > 0.3) return { level: 4, text: '温和流入' };
  if (rate > -0.3) return { level: 3, text: '资金平衡' };
  if (rate > -0.8) return { level: 2, text: '温和流出' };
  return { level: 1, text: '极致流出·流动性收紧' };
}

export function formatMacroAssetData(raw: any[]) {
  return raw.map(item => {
    const r = Number(item.changeRate ?? 0);
    const p = getCapitalPressure(r);
    return { ...item, changeRate: r, pressureLevel: p.level, pressureText: p.text };
  });
}

export const MACRO_BASIC_LINK: Record<string,{long:string;short:string}> = {
  gold: { long: '贵金属、避险', short: '高估值成长' },
  crude_oil: { long: '油气、化工、储能', short: '高耗能制造' },
  usd_index: { long: '出口型企业', short: '外资重仓成长' },
  us10_bond: { long: '红利、价值', short: '科创、新能源' },
};

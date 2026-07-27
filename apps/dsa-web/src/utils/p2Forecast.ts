/** P2: 全周期预测引擎 + 全维度联动 + 情绪周期 + 主力预判 + 产业景气 */

type Cycle = 'w1' | 'd15' | 'm1' | 'm6' | 'y1';

const CYCLE_WEIGHTS: Record<Cycle, Record<string,number>> = {
  w1:  { fund:0.45, game:0.35, opinion:0.12, macro:0.04, industry:0.04 },
  d15: { fund:0.35, game:0.25, opinion:0.25, macro:0.10, industry:0.05 },
  m1:  { fund:0.20, game:0.15, opinion:0.25, macro:0.20, industry:0.20 },
  m6:  { fund:0.10, game:0.05, opinion:0.10, macro:0.35, industry:0.40 },
  y1:  { fund:0.05, game:0.05, opinion:0.05, macro:0.45, industry:0.40 },
};

const RANGE_MAP: Record<Cycle, {best:string;normal:string;bad:string}> = {
  w1:  { best:'上涨0~3%', normal:'震荡±1.5%', bad:'下跌0~2.5%' },
  d15: { best:'上涨2~6%', normal:'震荡±3%', bad:'下跌2~5%' },
  m1:  { best:'上涨4~10%', normal:'震荡±5%', bad:'下跌3~8%' },
  m6:  { best:'上涨12~25%', normal:'震荡±10%', bad:'下跌8~18%' },
  y1:  { best:'上涨25~50%', normal:'震荡±20%', bad:'下跌15~30%' },
};

interface FactorData { fundFactor:{score:number}; gameFactor:{score:number}; opinionFactor:{score:number}; macroFactor:{score:number}; industryFactor:{score:number} }

function clip(v:number){ return Math.max(0,Math.min(100,Number(v)||50)); }
function getRange(score:number, r:Record<string,string>){ return score>=65?{level:'乐观区间',text:r.best}:score>=40?{level:'震荡区间',text:r.normal}:{level:'悲观区间',text:r.bad}; }
function getTurnPoint(score:number){ return score>75?'短期强势延续，拐点延后':score<30?'弱势延续，反弹拐点临近':'区间震荡，等待因子催化变盘'; }

/** P2-1: 五周期统一预测 */
export function getFullCycleForecast(factors: FactorData, cycle: Cycle = 'w1') {
  const w = CYCLE_WEIGHTS[cycle];
  const scores = { fund:clip(factors.fundFactor.score), game:clip(factors.gameFactor.score), opinion:clip(factors.opinionFactor.score), macro:clip(factors.macroFactor.score), industry:clip(factors.industryFactor.score) };
  const total = Math.floor(scores.fund*w.fund + scores.game*w.game + scores.opinion*w.opinion + scores.macro*w.macro + scores.industry*w.industry);
  return { cycle, upProb:total, downProb:100-total, totalScore:total, rangeInfo:getRange(total,RANGE_MAP[cycle]), turnPoint:getTurnPoint(total), factorRatio:{ fund:+(scores.fund*w.fund).toFixed(1), game:+(scores.game*w.game).toFixed(1), opinion:+(scores.opinion*w.opinion).toFixed(1), macro:+(scores.macro*w.macro).toFixed(1), industry:+(scores.industry*w.industry).toFixed(1) }, forecastTime:new Date().toLocaleString() };
}

/** P2-2: 大宗商品 → 产业链量化传导 */
export function calcCommodityIndustryLink(oilRate: number, goldRate: number) {
  return { energyChemScore: clip(50+oilRate*8), manufactureScore: clip(50-oilRate*6), safeScore: clip(50+goldRate*10), growthScore: clip(50-goldRate*7) };
}

/** P2-2: 外汇+美债 → 流动性估值传导 */
export function calcMacroLiquidityLink(usdRate: number, bondRate: number) {
  return { northPressure: clip(50+usdRate*9), techValPressure: clip(50+bondRate*12), valueBenefit: clip(50-bondRate*8) };
}

/** P2-3: 市场情绪周期推演 */
export function calcMarketEmotionCycle(list: number[]) {
  const latest = list.at(-1)??50; const avg5 = list.slice(-5).reduce((a,b)=>a+b,0)/5||50; const avg10 = list.slice(-10).reduce((a,b)=>a+b,0)/10||50;
  let stage='',tip='';
  if (latest<25&&avg5<30){stage='周期冰点';tip='未来3-7天大概率迎来情绪修复窗口';}
  else if(latest<45&&avg5<50){stage='修复回暖期';tip='情绪持续抬升，15天内延续修复';}
  else if(latest>75&&avg5>70){stage='情绪亢奋期';tip='短线高位风险累积，7-15天出现分歧退潮';}
  else if(latest>55&&avg5<avg10){stage='滞涨分歧期';tip='多头动能衰减，即将震荡或退潮';}
  else{stage='震荡平衡期';tip='无明确方向，等待催化拐点';}
  return { cycleStage:stage, previewTip:tip, nowScore:latest, avg5, avg10 };
}

/** P2-4: 主力行为+板块轮动预判 */
export function calcMainBehaviorForecast(sectors: {name:string;crowd:number;fundStay:number}[]) {
  return sectors.map(s=>{
    const prob = s.crowd<30&&s.fundStay>60?85:s.crowd>75?25:50;
    const action = s.fundStay>70&&s.crowd<40?'主力潜伏加仓':s.fundStay<30&&s.crowd>80?'主力获利出逃':'观望震荡';
    return {name:s.name,rotateProb:prob,mainAction:action,tip:prob>70?'未来1-15天高轮动机会':'短期持续性较弱'};
  }).sort((a,b)=>b.rotateProb-a.rotateProb);
}

/** P2-5: 产业链三期景气拐点 */
export function calcIndustryProsperity(base:{stock:number;price:number;policy:number;demand:number;inventory:number}) {
  const {stock,price,policy,demand,inventory}=base;
  const short=clip(price*0.4+demand*0.3+inventory*0.3); const mid=clip(policy*0.4+price*0.25+demand*0.35); const long=clip(policy*0.5+stock*0.3+demand*0.2);
  const tag=(v:number)=>v>70?'高景气上行':v>45?'中性震荡':'景气下行';
  return {short:{score:short,tag:tag(short),cycle:'1月'},mid:{score:mid,tag:tag(mid),cycle:'半年'},long:{score:long,tag:tag(long),cycle:'1年'},turnTip:short<40&&mid>60?'短期底部，中期拐点向上':'趋势延续'};
}

/** P3: 市场风格自适应动态权重 */
interface MarketFactor { isBull?:boolean; isBear?:boolean; isShock?:boolean; isThemeHot?:boolean; isValueStyle?:boolean }

export function getMarketStyleAdaptiveWeight(cycle: Cycle, mf: MarketFactor) {
  const base = { ...CYCLE_WEIGHTS[cycle] };
  if (mf.isBull)      { base.fund+=0.10; base.industry+=0.05; base.opinion-=0.05; }
  if (mf.isBear)      { base.macro+=0.10; base.opinion+=0.05; base.fund-=0.05; }
  if (mf.isShock)     { base.fund+=0.02; base.game+=0.03; base.opinion+=0.03; }
  if (mf.isThemeHot)  { base.game+=0.08; base.opinion+=0.07; base.industry-=0.05; }
  if (mf.isValueStyle){ base.industry+=0.10; base.macro+=0.05; base.game-=0.05; }
  const t = Object.values(base).reduce((a:number,b:number)=>a+b,0);
  (Object.keys(base) as (keyof typeof base)[]).forEach(k => { base[k] = +((base[k] / t).toFixed(2)); });
  return base;
}

/** P3: 行情联动实时预测刷新 */
export function refreshForecastRealTime(marketData: any, renderFn: (opt: any) => void) {
  const cycles: Cycle[] = ['w1','d15','m1','m6','y1'];
  const results: Record<string,any> = {};
  cycles.forEach(c => { results[c] = getFullCycleForecast(marketData.factors, c); });
  renderFn({ cycles: results, history: marketData.history });
}

/** P3: 产业链基本面穿透打分 */
export function calcIndustryFundamentalScore(fin: { revenueRate:number; profitRate:number; grossRate:number; roe:number; inventoryRate:number }) {
  return Math.floor(fin.revenueRate*0.25 + fin.profitRate*0.3 + fin.grossRate*0.2 + fin.roe*0.15 + (100-fin.inventoryRate)*0.1);
}

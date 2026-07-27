/** P0-3: 数据溯源 + 智能降噪 */

/** 节点挂载溯源信息 */
export function attachNodeTrace<T extends Record<string,any>>(nodes: T[], sourceApi: string, confidence = 3, updateTs?: number): (T & {source:string;updateTs:number;confidenceStar:number;confidenceText:string})[] {
  return nodes.map(n => ({...n, source: sourceApi, updateTs: updateTs ?? Date.now(), confidenceStar: confidence, confidenceText: '★'.repeat(confidence) + '☆'.repeat(5-confidence) }));
}

/** 金融时序降噪 (2σ 过滤极端异常值) */
export function smoothFinanceData(list: number[], sigma = 2): number[] {
  if (list.length <= 3) return list;
  const avg = list.reduce((a, b) => a + b, 0) / list.length;
  const std = Math.sqrt(list.reduce((s, v) => s + (v-avg)**2, 0) / list.length);
  return list.filter(v => v >= avg - std*sigma && v <= avg + std*sigma);
}

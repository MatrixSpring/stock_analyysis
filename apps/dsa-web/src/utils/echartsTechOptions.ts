/**
 * v3.0 ECharts 科技美化 Option 生成器（框架无关，React/Vue 通用）
 * 修复：图谱廉价纯色、预测静态僵硬、因子归因无分层、情绪无仪表盘
 */

/** 科技感拓扑图谱 — 渐变球体节点 + 流光链路 + 异动呼吸发光 */
export function getTechGraphOption(nodes: any[] = [], links: any[] = []) {
  const colors = [
    'radial-gradient(circle, #4096ff 0%, #1677ff 100%)',
    'radial-gradient(circle, #36cfc9 0%, #1cb8a8 100%)',
    'radial-gradient(circle, #faad14 0%, #d48806 100%)',
    'radial-gradient(circle, #f53f3f 0%, #cf1322 100%)',
  ];
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', backgroundColor: 'rgba(18,28,48,0.95)', borderColor: '#1677ff', borderWidth: 1, textStyle: { color: '#e5e6eb' }, padding: 12 },
    series: [{
      type: 'graph', layout: 'force', roam: true, zoom: 1.1,
      force: { repulsion: 280, edgeLength: 80, gravity: 0.1 },
      itemStyle: { shadowBlur: 20, shadowColor: '#1677ff' },
      lineStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: 'rgba(22,119,255,0.2)' }, { offset: 0.5, color: 'rgba(22,119,255,0.7)' }, { offset: 1, color: 'rgba(22,119,255,0.2)' }] }, width: 1.5, curveness: 0.2 },
      label: { show: true, color: '#fff', fontSize: 11 },
      data: nodes.map((n: any) => ({ ...n, symbolSize: n.symbolSize ?? 20, itemStyle: n.flashLevel > 1 ? { ...n.itemStyle, shadowBlur: 30, shadowColor: n.color ?? '#faad14' } : n.itemStyle })),
      links: links.map((l: any) => ({ ...l, lineStyle: { width: Math.min(4, (l.value ?? 1) / 100 + 1), opacity: 0.7 } })),
    }],
  };
}

/** 科技感预测走势图 — 双色渐变置信区间 + 拐点脉冲标记 */
export function getTechForecastOption(history: { x: string[]; y: number[]; optimisticLine: number[]; pessimisticLine: number[]; turnPointArr: [string, number][] }) {
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(18,28,48,0.95)', borderColor: '#1677ff', textStyle: { color: '#e5e6eb' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '12%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: history.x, axisLine: { lineStyle: { color: 'rgba(64,150,255,0.2)' } } },
    yAxis: { type: 'value', scale: true, axisLine: { lineStyle: { color: 'rgba(64,150,255,0.2)' } }, splitLine: { lineStyle: { color: 'rgba(64,150,255,0.1)' } } },
    series: [
      { name: '历史走势', type: 'line', data: history.y, smooth: true, lineStyle: { color: '#1677ff', width: 2 }, symbol: 'none' },
      { name: '乐观区间', type: 'line', data: history.optimisticLine, smooth: true, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(54,207,201,0.25)' }, { offset: 1, color: 'rgba(54,207,201,0)' }] } }, lineStyle: { opacity: 0 } },
      { name: '悲观区间', type: 'line', data: history.pessimisticLine, smooth: true, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(245,63,63,0.25)' }, { offset: 1, color: 'rgba(245,63,63,0)' }] } }, lineStyle: { opacity: 0 } },
      { name: '变盘拐点', type: 'scatter', data: history.turnPointArr, symbolSize: 14, itemStyle: { color: '#faad14', shadowBlur: 25, shadowColor: '#faad14' } },
    ],
  };
}

/** 五大因子归因雷达图 — 发光渐变 */
export function getTechRadarOption(factorData: { name: string; value: number[] }[]) {
  return {
    backgroundColor: 'transparent',
    tooltip: { backgroundColor: 'rgba(18,28,48,0.95)', borderColor: '#1677ff' },
    radar: { indicator: [{ name: '资金博弈', max: 100 }, { name: '情绪博弈', max: 100 }, { name: '舆情地缘', max: 100 }, { name: '宏观流动性', max: 100 }, { name: '产业景气', max: 100 }], axisLine: { lineStyle: { color: 'rgba(64,150,255,0.2)' } }, splitLine: { lineStyle: { color: 'rgba(64,150,255,0.15)' } }, splitArea: { show: false } },
    series: [{ type: 'radar', data: factorData, areaStyle: { color: 'rgba(22,119,255,0.18)' }, lineStyle: { color: '#1677ff', width: 2 }, itemStyle: { color: '#1677ff', shadowBlur: 15, shadowColor: '#1677ff' } }],
  };
}

/** 情绪周期仪表盘 — 七阶进度 + 红橙绿渐变 */
export function getEmotionGaugeOption(score: number) {
  return {
    backgroundColor: 'transparent',
    series: [{ type: 'gauge', startAngle: 200, endAngle: -20, radius: '88%', progress: { show: true, width: 12 }, axisLine: { lineStyle: { color: [[0.25, '#f53f3f'], [0.55, '#faad14'], [1, '#36cfc9']], width: 12 } }, pointer: { width: 4 }, detail: { fontSize: 18, fontWeight: 'bold', color: '#fff' }, data: [{ value: score }] }],
  };
}

/** 图表过渡刷新 — 修复静态不刷新 Bug */
export function refreshChartWithTransition(chart: any, option: any) {
  chart?.setOption(option, { notMerge: true, lazyUpdate: false });
  chart?.resize();
}

/** 多模型共识对比图表 — 共识主线高亮发光 + 子模型差异化浅色曲线 */
export function getMultiModelChartOption(
  modelList: { name: string; data: number[] }[],
  consensusData: number[],
) {
  const colors = ['#36C9A8', '#FFB845', '#9254DE', '#F85454'];
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(14,20,32,0.95)', borderColor: '#2388FF', textStyle: { color: '#E5E6EB' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    legend: { textStyle: { color: '#86909C' } },
    xAxis: { type: 'category', axisLine: { lineStyle: { color: 'rgba(35,136,255,0.15)' } }, splitLine: { show: false } },
    yAxis: { max: 1, min: 0, axisLine: { lineStyle: { color: 'rgba(35,136,255,0.15)' } }, splitLine: { lineStyle: { color: 'rgba(35,136,255,0.1)' } } },
    series: [
      { name: '多模型共识', type: 'line', data: consensusData, smooth: true, lineStyle: { color: '#2388FF', width: 3 }, shadowBlur: 15, shadowColor: 'rgba(35,136,255,0.5)' },
      ...modelList.map((m, i) => ({ name: m.name, type: 'line', data: m.data, smooth: true, lineStyle: { color: colors[i % 4], width: 1.5, opacity: 0.8 }, symbol: 'none' })),
    ],
  };
}

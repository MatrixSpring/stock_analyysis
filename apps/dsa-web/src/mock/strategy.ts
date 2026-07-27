/** Mock 数据统一管理 — 对接后端时替换此文件即可 */

import type {
  StrategyItem, GameSwitchItem, WeightItem,
  RiskLogItem, PerformanceItem, WarnItem, CostFormItem,
} from '../types';

export const strategyListMock: StrategyItem[] = [
  { id: '1', name: '李义恩长线主升', status: 'run', statusText: '运行中', weight: '25%', iterTime: 'day', lastIter: '2026-07-25', matchCycle: '主升/震荡', score: 92 },
  { id: '2', name: '语菠萝短线情绪', status: 'run', statusText: '运行中', weight: '20%', iterTime: 'day', lastIter: '2026-07-25', matchCycle: '震荡/退潮', score: 88 },
  { id: '3', name: '逍遥龙头博弈', status: 'bad', statusText: '劣化预警', weight: '15%', iterTime: 'day', lastIter: '2026-07-24', matchCycle: '主升', score: 76 },
  { id: '4', name: '公募机构策略', status: 'run', statusText: '运行中', weight: '22%', iterTime: 'day', lastIter: '2026-07-25', matchCycle: '全周期', score: 94 },
  { id: '5', name: '国家队护盘策略', status: 'stop', statusText: '已停用', weight: '18%', iterTime: 'day', lastIter: '2026-07-20', matchCycle: '冰点', score: 65 },
];

export const gameSwitchMock: Record<string, GameSwitchItem[]> = {
  li: [
    { name: '长线产业潜伏布局', status: true, rate: '63%' },
    { name: '主升趋势持股穿越', status: true, rate: '65%' },
    { name: '中线赛道低吸滚动', status: false, rate: '58%' },
  ],
  bo: [
    { name: '情绪冰点低吸博弈', status: true, rate: '61%' },
    { name: '短线连板套利', status: false, rate: '55%' },
    { name: '题材轮动快进快出', status: true, rate: '59%' },
  ],
  fund: [
    { name: '机构抱团中线持有', status: true, rate: '66%' },
    { name: '季报预期提前布局', status: true, rate: '64%' },
  ],
};

export const weightListMock: WeightItem[] = [
  { name: '公募机构策略', value: 28 }, { name: '李义恩长线策略', value: 25 },
  { name: '语菠萝短线策略', value: 20 }, { name: '逍遥龙头策略', value: 15 },
  { name: '其他辅助策略', value: 12 },
];

export const riskLogMock: RiskLogItem[] = [
  { time: '2026-07-24 14:22', type: '小幅回撤', desc: '短线波动加大', action: '降仓5%' },
  { time: '2026-07-22 10:10', type: '情绪分歧', desc: '市场一致性减弱', action: '暂停新开仓' },
];

export const performanceMock: PerformanceItem[] = [
  { name: '公募机构策略', score: 94, winRate: '66%', ratio: 1.82, draw: '2.8%', count: 412, status: '优质', tag: 'success' },
  { name: '李义恩长线主升', score: 92, winRate: '63%', ratio: 1.75, draw: '3.2%', count: 386, status: '优质', tag: 'success' },
  { name: '语菠萝短线情绪', score: 88, winRate: '61%', ratio: 1.68, draw: '3.8%', count: 520, status: '正常', tag: 'primary' },
  { name: '逍遥龙头博弈', score: 76, winRate: '55%', ratio: 1.42, draw: '5.6%', count: 286, status: '劣化', tag: 'warning' },
  { name: '国家队护盘策略', score: 65, winRate: '52%', ratio: 1.30, draw: '6.2%', count: 192, status: '偏弱', tag: 'danger' },
];

export const warnListMock: WarnItem[] = [
  { name: '逍遥龙头博弈', desc: '近期震荡周期胜率下滑，建议降低权重' },
  { name: '国家队护盘策略', desc: '非极端行情适配性差，建议日常停用' },
];

export const costFormMock: CostFormItem = { slip: 0.08, fee: 0.02, tax: 0.1 };

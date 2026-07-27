/** 业务枚举 — 清零魔法变量 */

import type { MarketCycleType, StrategyStatusType, TagType } from '../types';

export const STRATEGY_STATUS: Record<StrategyStatusType, { text: string; tag: TagType }> = {
  run: { text: '运行中', tag: 'success' },
  stop: { text: '已停用', tag: 'danger' },
  bad: { text: '劣化预警', tag: 'warning' },
};

export const MARKET_CYCLE: Record<MarketCycleType, string> = {
  TREND: '主升', SHAKE: '震荡', DROP: '退潮', ICE: '冰点',
};

export const ITER_CYCLE_TEXT: Record<string, string> = {
  day: '每日迭代', twoDay: '隔日迭代', week: '每周迭代',
};

export const WEIGHT_RULE = { MIN: 0, MAX: 100, SUM_LIMIT: 100 } as const;

export const RISK_THRESHOLD = {
  DROP_1: 1, DROP_2: 2, DROP_3: 3, FUSE_DROP: 5, LOSS_COUNT: 3,
} as const;

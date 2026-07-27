/** 全局多周期切换 Hook (1/3/5/10/30日) */
import { useState, useCallback } from 'react';

export const PERIOD_OPTIONS = [
  { label: '1日', value: '1' },
  { label: '3日', value: '3' },
  { label: '5日', value: '5' },
  { label: '10日', value: '10' },
  { label: '30日', value: '30' },
] as const;

export function usePeriodSwitch(defaultPeriod = '5') {
  const [period, setPeriod] = useState(defaultPeriod);
  const periodParams = { period };
  return { period, setPeriod, periodParams, options: PERIOD_OPTIONS };
}

/**
 * v2.1.0 分级动态刷新 Hook（React 版）
 * 地缘/政策 30s | 行业/博弈 10s | 个股行情 3s
 * 自带清理 + 容错兜底
 */
import { useEffect, useRef, useCallback } from 'react';

type RefreshFn = () => void | Promise<void>;

interface TierConfig {
  macro?: RefreshFn;    // 地缘、政策 30s
  industry?: RefreshFn; // 行业、博弈 10s
  stock?: RefreshFn;    // 个股行情 3s
}

export function useTieredRefresh({ macro, industry, stock }: TierConfig) {
  const timers = useRef<{ macro: any; industry: any; stock: any }>({
    macro: null, industry: null, stock: null,
  });

  const startAll = useCallback(() => {
    // 立即执行一次
    macro?.();
    industry?.();
    stock?.();

    if (macro) timers.current.macro = setInterval(macro, 30_000);
    if (industry) timers.current.industry = setInterval(industry, 10_000);
    if (stock) timers.current.stock = setInterval(stock, 3_000);
  }, [macro, industry, stock]);

  useEffect(() => {
    const delay = setTimeout(startAll, 300);
    return () => {
      clearTimeout(delay);
      const t = timers.current;
      if (t.macro) clearInterval(t.macro);
      if (t.industry) clearInterval(t.industry);
      if (t.stock) clearInterval(t.stock);
    };
  }, [startAll]);
}

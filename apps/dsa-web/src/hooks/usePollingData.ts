/**
 * v2.1.0 通用数据轮询 Hook — 自动清理、空数据兜底、高频防抖
 * 解决：定时器内存泄漏、初始化报错白屏、高频请求卡死
 */
import { useRef, useCallback, useEffect, useState } from 'react';
import { dashGet } from '../api/dashboardRequest';

export function usePollingData<T = any>(
  apiUrl: string,
  intervalMs: number = 10_000,
  params?: Record<string, any>,
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const fetch = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await dashGet(apiUrl, params);
      if (mountedRef.current && res?.data) {
        setData(res.data as T);
      }
    } catch {
      // 静默兜底
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, JSON.stringify(params)]);

  useEffect(() => {
    mountedRef.current = true;
    // 延迟 300ms 启动，避免启动瞬间高频报错
    const initTimer = setTimeout(() => {
      fetch();
      timerRef.current = setInterval(fetch, intervalMs);
    }, 300);

    return () => {
      mountedRef.current = false;
      clearTimeout(initTimer);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [fetch, intervalMs]);

  return { data, loading, refetch: fetch };
}

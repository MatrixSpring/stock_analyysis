/**
 * P0 统一 ECharts 渲染 Hook
 * 修复：resize 重绘 / 实例销毁 / 空数据兜底 / Tooltip z-level
 */
import { useEffect, useRef, useCallback } from 'react';

export function useECharts() {
  const chartRef = useRef<any>(null);
  const domRef = useRef<HTMLDivElement | null>(null);

  const setDomRef = useCallback((node: HTMLDivElement | null) => { domRef.current = node; }, []);

  const render = useCallback(async (option: any) => {
    if (!domRef.current) return;
    const hasData = option?.series?.[0]?.data?.length > 0
      || option?.series?.[0]?.nodes?.length > 0
      || option?.series?.[0]?.links?.length > 0;
    if (!hasData) {
      domRef.current.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#86909C;font-size:13px">暂无数据</div>';
      return;
    }
    if (chartRef.current) { chartRef.current.dispose(); chartRef.current = null; }
    const echarts = (await import('echarts')).default;
    chartRef.current = echarts.init(domRef.current);
    chartRef.current.setOption({ ...option, tooltip: { ...(option.tooltip||{}), backgroundColor:'rgba(10,15,30,0.98)', borderColor:'#2378dd', textStyle:{color:'#fff'} } }, true);
  }, []);

  useEffect(() => {
    const onResize = () => chartRef.current?.resize();
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); chartRef.current?.dispose(); chartRef.current = null; };
  }, []);

  return { setDomRef, render };
}

/**
 * v2.1.0 仪表盘专用请求封装 — 超时兜底 + 空数据容错 + 断网静默降级
 * 解决白屏卡死：任何异常都返回合法空数据，不阻断页面渲染
 */
import axios from 'axios';

const dashService = axios.create({
  baseURL: import.meta.env?.VITE_API_BASE_URL || '/api',
  timeout: 5000, // 5秒超时兜底（仪表盘接口需快速响应）
  headers: { 'Content-Type': 'application/json;charset=UTF-8' },
});

/** 空数据兜底模板 */
function fallbackData() {
  return { code: 200, msg: 'fallback', data: {}, timestamp: Date.now() };
}

// 响应拦截：三层兜底
dashService.interceptors.response.use(
  (res) => res.data || fallbackData(),
  (_error) => {
    // 超时/断网/500 → 全部静默返回空数据，不抛异常，不阻塞页面
    return Promise.resolve(fallbackData());
  },
);

export async function dashGet<T = any>(url: string, params?: Record<string, any>): Promise<T> {
  return dashService.get(url, { params }) as unknown as T;
}

export default dashService;

/** Axios 统一请求封装 — 对标工业级 API 层 */

import axios from 'axios';
import type { AxiosResponse } from 'axios';

const service = axios.create({
  baseURL: import.meta.env?.VITE_API_BASE_URL || '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json;charset=UTF-8' },
});

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('dsa_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  (error) => {
    const msg = error.response?.data?.message || error.message || 'request failed';
    if (error.response?.status === 401) {
      localStorage.removeItem('dsa_token');
      window.location.href = '/login';
    }
    console.error(`[API] ${msg}`);
    return Promise.reject(error);
  },
);

// 类型化请求方法
export async function apiGet<T = any>(url: string, params?: Record<string, any>): Promise<T> {
  return service.get(url, { params }) as unknown as T;
}

export async function apiPost<T = any>(url: string, data?: Record<string, any>): Promise<T> {
  return service.post(url, data) as unknown as T;
}

export async function apiPut<T = any>(url: string, data?: Record<string, any>): Promise<T> {
  return service.put(url, data) as unknown as T;
}

export default service;

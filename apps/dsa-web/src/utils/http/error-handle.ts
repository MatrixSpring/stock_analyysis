/**
 * ===================================
 * 统一前端异常处理 — utils/http/error-handle.ts
 * ===================================
 *
 * 标准化后端返回格式的解析与错误处理。
 * 配合后端 utils/exception_handler.py 使用。
 *
 * 统一返回格式：
 *   { code: 0, msg: "ok", data: {...} }
 *
 * 错误码分类：
 *   0     = 成功
 *   1xxx  = 参数/权限异常
 *   2xxx  = 数据源异常
 *   3xxx  = LLM 调用异常
 *   4xxx  = 任务异常
 *   5xxx  = 系统内部异常
 */

export interface ApiResponse<T = any> {
  code: number;
  msg: string;
  data: T;
}

export class ApiError extends Error {
  code: number;

  constructor(code: number, msg: string) {
    super(msg);
    this.code = code;
    this.name = 'ApiError';
  }
}

/**
 * 解析 API 响应，异常时抛出 ApiError
 */
export function handleResponse<T>(res: ApiResponse<T>): T {
  if (res.code !== 0) {
    throw new ApiError(res.code, res.msg || '请求异常');
  }
  return res.data;
}

/**
 * 安全解析响应，异常时返回默认值
 */
export function safeHandleResponse<T>(
  res: ApiResponse<T>,
  fallback: T,
): T {
  try {
    return handleResponse(res);
  } catch {
    return fallback;
  }
}

/**
 * 根据错误码生成用户友好提示
 */
export function getErrorMessage(code: number): string {
  const messages: Record<number, string> = {
    1001: '请求参数无效，请检查输入',
    1002: '请求资源不存在',
    1003: '登录已过期，请重新登录',
    1004: '请求过于频繁，请稍后重试',
    2001: '数据源异常，已自动切换备选源',
    2002: '暂无数据',
    3001: 'AI 分析超时，请稍后重试',
    3002: 'AI 服务鉴权失败，请检查密钥配置',
    3003: 'AI 服务限流，请稍后重试',
    3004: 'AI 输出解析失败，请精简输入重试',
    4001: '任务不存在或已过期',
    4002: '任务执行失败',
    5001: '服务器内部异常，请稍后重试',
    5002: '系统配置错误',
    5003: '数据库异常',
  };
  return messages[code] || `未知错误 (${code})`;
}

/**
 * Fetch 包装器 — 自动处理 API 响应格式
 */
export async function apiFetch<T = any>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    throw new ApiError(res.status, `HTTP ${res.status}: ${res.statusText}`);
  }

  const json: ApiResponse<T> = await res.json();
  return handleResponse(json);
}

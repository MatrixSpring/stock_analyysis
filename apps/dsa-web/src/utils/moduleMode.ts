/** 模块精简/详细模式本地缓存 */
const KEY = 'dsa_module_mode';

export function getModuleMode(): Record<string, boolean> {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; }
}

export function setModuleMode(name: string, detail: boolean) {
  const m = getModuleMode();
  m[name] = detail;
  localStorage.setItem(KEY, JSON.stringify(m));
}

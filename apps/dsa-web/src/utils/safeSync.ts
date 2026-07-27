/**
 * v2.1.0 防死循环同步锁
 * 解决新旧模块数据双向同步导致的递归卡死问题
 */
export function createSafeSync() {
  let locked = false;

  return function safeSync(fn: () => void) {
    if (locked) return;
    locked = true;
    // 异步解锁，避免同步递归
    Promise.resolve().then(() => {
      try { fn(); } catch { /* silent */ }
      locked = false;
    });
  };
}

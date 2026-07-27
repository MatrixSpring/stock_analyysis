/** 全局操作二次确认 Hook — 防误操作（批量迭代/权重重置等高危操作） */

import { useCallback } from 'react';

interface ConfirmOptions {
  title?: string;
  description: string;
  onConfirm: () => void;
  onCancel?: () => void;
}

export function useConfirm() {
  const confirm = useCallback((opts: ConfirmOptions) => {
    const ok = window.confirm(`${opts.title || '操作确认'}\n\n${opts.description}`);
    if (ok) {
      opts.onConfirm();
    } else {
      opts.onCancel?.();
    }
    return ok;
  }, []);

  return { confirm };
}

/** 危险操作二次确认（带醒目标记） */
export function useDangerConfirm() {
  const { confirm } = useConfirm();
  return {
    confirmDanger: (desc: string, action: () => void) =>
      confirm({ title: '⚠️ 危险操作', description: desc, onConfirm: action }),
  };
}

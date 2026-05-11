/**
 * 通用 debounce 工具（手写，不引 lodash 依赖）。
 *
 * 替代 3 处独立 debounce 实现（见 JIRA-frontend-hook-utility-extraction.md A.2.2）：
 * - useSettings.ts:78 私有 debounce
 * - usePerformanceOptimization.ts:62 多键 debounce
 * - App.tsx:354 inline setTimeout
 *
 * 行为：
 * - 重复调用：仅最后一次（按 waitMs 窗口）触发 fn
 * - cancel(): 阻止当前 pending 触发（不会再执行 fn）
 * - flush(): 立即触发当前 pending 的 fn（含最后一次入参）
 * - waitMs <= 0：通过 setTimeout(0) 推到下一 tick 触发（非同步，避免破坏调用方对"延迟"语义的依赖）
 */
export interface DebouncedFn<Args extends unknown[]> {
  (...args: Args): void;
  cancel: () => void;
  flush: () => void;
}

export function debounce<Args extends unknown[]>(
  fn: (...args: Args) => void,
  waitMs: number,
): DebouncedFn<Args> {
  let timerId: ReturnType<typeof setTimeout> | null = null;
  let lastArgs: Args | null = null;

  const invoke = () => {
    if (lastArgs === null) return;
    const args = lastArgs;
    lastArgs = null;
    timerId = null;
    fn(...args);
  };

  const debounced = ((...args: Args): void => {
    lastArgs = args;
    if (timerId !== null) {
      clearTimeout(timerId);
    }
    timerId = setTimeout(invoke, Math.max(0, waitMs));
  }) as DebouncedFn<Args>;

  debounced.cancel = () => {
    if (timerId !== null) {
      clearTimeout(timerId);
      timerId = null;
    }
    lastArgs = null;
  };

  debounced.flush = () => {
    if (timerId !== null) {
      clearTimeout(timerId);
      invoke();
    }
  };

  return debounced;
}

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
 * - waitMs <= 0：clamp 到 0，仍走 setTimeout(0)。注意此时 fn 进入 macrotask 队列
 *   （**不是** microtask）——浏览器实际有 ≥4 ms clamp，且会在 Promise.resolve()
 *   等 microtask 之后才触发。若调用方依赖与 microtask 的相对顺序，需另用 queueMicrotask。
 */
export interface DebouncedFn<Args extends unknown[]> {
  (...args: Args): void;
  cancel: () => void;
  flush: () => void;
}

export function debounce<Args extends unknown[]>(
  fn: (...args: Args) => void,
  waitMs: number
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
    // 注意：invoke() 内部会把 timerId / lastArgs 重置为 null，
    // 因此 flush 后无 pending；fn 内若 re-entrant 调 debounced()，
    // 新 args 在 invoke() 的 `lastArgs = null` 之后赋值，下一轮窗口正常工作。
    if (timerId !== null) {
      clearTimeout(timerId);
      invoke();
    }
  };

  return debounced;
}

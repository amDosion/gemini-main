/**
 * 全局未处理异常兜底
 * 
 * 捕获所有未处理的 Promise rejection 和运行时错误，
 * 通过 Toast 统一展示给用户。
 */

type ErrorNotifier = (message: string) => void;

let _notifier: ErrorNotifier | null = null;

/** 注册 Toast 通知函数（在 App 挂载后调用） */
export function registerGlobalErrorNotifier(notifier: ErrorNotifier): void {
  _notifier = notifier;
}

/** 从错误对象提取用户友好的消息 */
function extractMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '未知错误';
}

/** 判断是否为可忽略的错误（网络断开、用户取消等） */
function isIgnorable(error: unknown): boolean {
  const msg = extractMessage(error).toLowerCase();
  return (
    msg.includes('aborted') ||
    msg.includes('cancelled') ||
    msg.includes('the user aborted') ||
    msg.includes('signal') ||
    msg.includes('network error') ||
    msg.includes('failed to fetch') ||
    msg.includes('load failed')
  );
}

/** 初始化全局错误监听 */
export function initGlobalErrorHandlers(): void {
  // 未处理的 Promise rejection
  window.addEventListener('unhandledrejection', (event) => {
    if (isIgnorable(event.reason)) {
      event.preventDefault();
      return;
    }
    const message = extractMessage(event.reason);
    _notifier?.(message);
    event.preventDefault();
  });

  // 未捕获的同步错误
  window.addEventListener('error', (event) => {
    if (isIgnorable(event.error)) return;
    const message = extractMessage(event.error);
    _notifier?.(message);
  });
}

/** 统一错误上报（替代分散的 console.error/warn） */
export function reportError(context: string, error: unknown): void {
  const message = extractMessage(error);
  if (isIgnorable(error)) return;
  _notifier?.(`${context}: ${message}`);
}

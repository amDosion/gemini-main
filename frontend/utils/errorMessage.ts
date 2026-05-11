/**
 * 统一错误归一化工具。
 *
 * 替代 23+ 处 `err instanceof Error ? err.message : String(err)` 三元式
 * （见 JIRA-frontend-hook-utility-extraction.md A.2.1）。
 *
 * 行为：
 * - Error 实例 → err.message
 * - string → 原样返回
 * - null / undefined → fallback ?? 'Unknown error'
 * - { message: string } 鸭子类型（axios-like） → err.message
 * - 其他（含循环引用对象） → String(err)（不用 JSON.stringify 避免循环引用）
 */
export function getErrorMessage(err: unknown, fallback?: string): string {
  if (err == null) {
    return fallback ?? 'Unknown error';
  }
  if (err instanceof Error) {
    return err.message;
  }
  if (typeof err === 'string') {
    return err;
  }
  // axios-like 鸭子类型：{ message: string }
  if (typeof err === 'object' && 'message' in err) {
    const message = (err as { message: unknown }).message;
    if (typeof message === 'string') {
      return message;
    }
  }
  return String(err);
}

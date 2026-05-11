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
 * - { message: string } **自有属性**鸭子类型（axios-like） → err.message
 *   注意：用 hasOwnProperty 而非 `in`，避免原型链上的 message 被误识别
 * - { message: undefined } 或 message 非 string → 走 String(err) 兜底（保持
 *   "只有 message 真是 string 才采纳"的严格语义）
 * - 其他（含循环引用对象 / Symbol / BigInt / number / boolean） → String(err)
 *   （不用 JSON.stringify 避免循环引用 + Symbol 抛错）
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
  // axios-like 鸭子类型：自有属性 { message: string }（不走原型链）
  if (typeof err === 'object' && Object.prototype.hasOwnProperty.call(err, 'message')) {
    const message = (err as { message: unknown }).message;
    if (typeof message === 'string') {
      return message;
    }
  }
  return String(err);
}

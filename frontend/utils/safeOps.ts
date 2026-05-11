/**
 * 统一安全操作工具
 */

/**
 * 安全 JSON 解析，失败返回 fallback。
 *
 * **重载（按 type-design-analyzer 反馈，强制类型安全）**：
 *
 * 1. 提供 `guard` 时：解析成功后由 guard 验证，T 由 guard 类型保证（运行时强类型）
 * 2. 不提供 `guard` 时：返回 `unknown`，调用方必须自行 narrow（避免类型逃逸）
 *
 * @example
 *   // 有 guard：T 类型由 isRecord 强保证
 *   const obj = safeJsonParse(raw, null, isRecord);  // UnknownRecord | null
 *   const arr = safeJsonParse(raw, [], Array.isArray); // unknown[]
 *
 *   // 无 guard：返回 unknown，调用方 narrow
 *   const data = safeJsonParse(raw, null);  // unknown
 *   if (data && typeof data === 'object' && 'foo' in data) {...}
 */
export function safeJsonParse<T>(text: string, fallback: T, guard: (v: unknown) => v is T): T;
export function safeJsonParse(text: string, fallback: unknown): unknown;
export function safeJsonParse(
  text: string,
  fallback: unknown,
  guard?: (v: unknown) => boolean
): unknown {
  try {
    const parsed = JSON.parse(text) as unknown;
    if (guard && !guard(parsed)) return fallback;
    return parsed;
  } catch {
    return fallback;
  }
}

/** 安全读取 localStorage */
export function safeLocalGet(key: string, fallback: string = ''): string {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

/** 安全写入 localStorage */
export function safeLocalSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // storage full or blocked
  }
}

/** 安全复制到剪贴板 */
export async function safeCopyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * 统一安全操作工具
 */

/**
 * 安全 JSON 解析，失败返回 fallback。
 *
 * @param text - 待解析字符串（空字符串 / 非 JSON / 解析后不符合 guard 均视为失败）
 * @param fallback - 失败时返回的值
 * @param guard - 可选类型守卫，解析成功后用其验证结果；失败返回 fallback。
 *   guard 可以 narrow 到 T 的子类型（如 T=UnknownRecord|null 时 guard 是 isRecord 返回 UnknownRecord）；
 *   返回类型始终是 T（调用方若需更窄类型，请在外部再次 narrow）。
 *
 * @remarks
 * **类型安全注意**：若调用方指定具体 T（如 `safeJsonParse<MyType>(raw, fallback)`）但**不提供** guard，
 * 返回值的 T 仅是类型声明，无运行时验证；JSON.parse 可能产生与 T 结构不符的数据。建议为非平凡 T 始终配 guard。
 *
 * @example
 *   const obj = safeJsonParse(raw, null, isRecord);  // UnknownRecord | null
 *   const arr = safeJsonParse(raw, [], Array.isArray); // unknown[]
 */
export function safeJsonParse<T = unknown>(
  text: string,
  fallback: T,
  guard?: (v: unknown) => v is T
): T {
  try {
    const parsed = JSON.parse(text) as unknown;
    if (guard && !guard(parsed)) return fallback;
    return parsed as T;
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

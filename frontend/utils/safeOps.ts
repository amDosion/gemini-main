/**
 * 统一安全操作工具
 */

/** 安全 JSON 解析，失败返回 fallback */
export function safeJsonParse<T = unknown>(text: string, fallback: T): T {
  try {
    return JSON.parse(text) as T;
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

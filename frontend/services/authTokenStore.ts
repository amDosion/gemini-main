const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

function getStorage(): Storage | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  return getStorage()?.getItem(ACCESS_TOKEN_KEY) ?? null;
}

export function setAccessToken(token: string): void {
  getStorage()?.setItem(ACCESS_TOKEN_KEY, token);
}

export function removeAccessToken(): void {
  getStorage()?.removeItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return getStorage()?.getItem(REFRESH_TOKEN_KEY) ?? null;
}

export function setRefreshToken(token: string): void {
  getStorage()?.setItem(REFRESH_TOKEN_KEY, token);
}

export function removeRefreshToken(): void {
  getStorage()?.removeItem(REFRESH_TOKEN_KEY);
}

export function getAuthorizationHeader(token: string | null = getAccessToken()): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function withAuthorization(
  headers: HeadersInit = {},
  options: { skipAuth?: boolean; token?: string | null } = {}
): Headers {
  const finalHeaders = new Headers(headers);
  if (options.skipAuth) {
    return finalHeaders;
  }

  const token = options.token ?? getAccessToken();
  if (token) {
    finalHeaders.set('Authorization', `Bearer ${token}`);
  }
  return finalHeaders;
}

/** 同步 access_token 到 cookie（用于 EventSource 等场景） */
export function syncTokenToCookie(token: string | null, expiresIn: number = 86400): void {
  if (typeof document === 'undefined') return;
  if (token) {
    const expires = new Date(Date.now() + expiresIn * 1000).toUTCString();
    document.cookie = `access_token=${token}; expires=${expires}; path=/; SameSite=Lax`;
  } else {
    document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; SameSite=Lax';
  }
}

/** 确保 cookie 与 localStorage 中的 token 一致 */
export function ensureTokenSync(): void {
  const token = getAccessToken();
  syncTokenToCookie(token);
}

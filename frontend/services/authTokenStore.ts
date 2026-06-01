const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

let accessTokenMemory: string | null = null;

function getBrowserStorage(name: 'localStorage' | 'sessionStorage'): Storage | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    return window[name];
  } catch {
    return null;
  }
}

function removeLegacyToken(key: string): void {
  getBrowserStorage('localStorage')?.removeItem(key);
  getBrowserStorage('sessionStorage')?.removeItem(key);
}

export function clearLegacyAuthTokens(): void {
  removeLegacyToken(ACCESS_TOKEN_KEY);
  removeLegacyToken(REFRESH_TOKEN_KEY);
}

export function getAccessToken(): string | null {
  return accessTokenMemory;
}

export function setAccessToken(token: string): void {
  accessTokenMemory = token;
  removeLegacyToken(ACCESS_TOKEN_KEY);
}

export function removeAccessToken(): void {
  accessTokenMemory = null;
  removeLegacyToken(ACCESS_TOKEN_KEY);
}

export function removeRefreshToken(): void {
  removeLegacyToken(REFRESH_TOKEN_KEY);
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

clearLegacyAuthTokens();

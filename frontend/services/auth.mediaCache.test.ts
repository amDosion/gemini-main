// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  broadcastLogout: vi.fn(),
  broadcastTokenRefresh: vi.fn(),
  clearPrivateClientCaches: vi.fn(),
  fetchWithTimeout: vi.fn(),
  listenLogout: vi.fn(),
  listenTokenRefresh: vi.fn(),
  getPrivateCacheUserScope: vi.fn(),
  readJsonResponse: vi.fn(),
  setPrivateCacheUserScope: vi.fn(),
}));

vi.mock('./authSync', () => ({
  broadcastLogout: mocks.broadcastLogout,
  broadcastTokenRefresh: mocks.broadcastTokenRefresh,
  listenLogout: mocks.listenLogout,
  listenTokenRefresh: mocks.listenTokenRefresh,
}));

vi.mock('./privateClientCache', () => ({
  clearPrivateClientCaches: mocks.clearPrivateClientCaches,
}));

vi.mock('./http', () => ({
  fetchWithTimeout: mocks.fetchWithTimeout,
  parseHttpError: vi.fn(async () => ({ message: 'request failed', status: 500 })),
  readJsonResponse: mocks.readJsonResponse,
}));

vi.mock('./privateCacheScope', () => ({
  getPrivateCacheUserScope: mocks.getPrivateCacheUserScope,
  setPrivateCacheUserScope: mocks.setPrivateCacheUserScope,
}));

import { authService } from './auth';
import {
  getAccessToken,
  removeAccessToken,
  removeRefreshToken,
  setAccessToken,
} from './authTokenStore';

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('authService media cache privacy cleanup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    removeAccessToken();
    removeRefreshToken();
    mocks.fetchWithTimeout.mockResolvedValue(new Response(null, { status: 204 }));
    mocks.clearPrivateClientCaches.mockResolvedValue(undefined);
    mocks.getPrivateCacheUserScope.mockReturnValue('anonymous');
  });

  it('clears shared and legacy media caches on logout', async () => {
    window.localStorage.setItem('access_token', 'access-token');
    window.localStorage.setItem('refresh_token', 'refresh-token');

    await authService.logout();

    expect(window.localStorage.getItem('access_token')).toBeNull();
    expect(window.localStorage.getItem('refresh_token')).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(mocks.setPrivateCacheUserScope).toHaveBeenCalledWith(null);
    expect(mocks.clearPrivateClientCaches).toHaveBeenCalledTimes(1);
    expect(mocks.broadcastLogout).toHaveBeenCalledTimes(1);
  });

  it('clears previous user media caches and scopes new media entries after login succeeds', async () => {
    setAccessToken('stale-before-login');
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
    mocks.readJsonResponse.mockResolvedValue({
      user: {
        id: 'user-2',
        email: 'u2@example.com',
        name: null,
        status: 'active',
      },
      expiresIn: 3600,
    });

    await authService.login({ email: 'u2@example.com', password: 'password' });

    expect(getAccessToken()).toBeNull();
    expect(window.localStorage.getItem('access_token')).toBeNull();
    expect(window.localStorage.getItem('refresh_token')).toBeNull();
    expect(mocks.setPrivateCacheUserScope).toHaveBeenCalledWith('user-2');
    expect(mocks.clearPrivateClientCaches).toHaveBeenCalledTimes(1);
    expect(mocks.fetchWithTimeout).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        method: 'POST',
        skipAuth: true,
        withAuth: true,
      })
    );
    const headers = new Headers(mocks.fetchWithTimeout.mock.calls[0][1].headers);
    expect(headers.has('Authorization')).toBe(false);
  });

  it('does not persist hasActiveProfile in global localStorage after authenticated responses', async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
    mocks.readJsonResponse.mockResolvedValue({
      user: {
        id: 'user-with-profile',
        email: 'profile@example.com',
        name: null,
        status: 'active',
        hasActiveProfile: true,
      },
      expiresIn: 3600,
      hasActiveProfile: true,
    });

    try {
      await authService.login({ email: 'profile@example.com', password: 'password' });

      expect(window.localStorage.getItem('has_active_profile')).toBeNull();
      expect(setItemSpy).not.toHaveBeenCalledWith('has_active_profile', expect.any(String));
    } finally {
      setItemSpy.mockRestore();
    }
  });

  it('returns register hasActiveProfile without persisting it globally', async () => {
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
    mocks.readJsonResponse.mockResolvedValue({
      user: {
        id: 'registered-user',
        email: 'registered@example.com',
        name: null,
        status: 'active',
      },
      expiresIn: 3600,
      hasActiveProfile: false,
    });

    const user = await authService.register({
      email: 'registered@example.com',
      password: 'password123',
      confirmPassword: 'password123',
    });

    expect(user.hasActiveProfile).toBe(false);
    expect(window.localStorage.getItem('has_active_profile')).toBeNull();
  });

  it('clears local private session state without broadcasting when requested by token recovery paths', async () => {
    window.localStorage.setItem('access_token', 'expired-access-token');
    window.localStorage.setItem('refresh_token', 'expired-refresh-token');

    await authService.clearLocalPrivateSessionState();

    expect(window.localStorage.getItem('access_token')).toBeNull();
    expect(window.localStorage.getItem('refresh_token')).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(mocks.setPrivateCacheUserScope).toHaveBeenCalledWith(null);
    expect(mocks.clearPrivateClientCaches).toHaveBeenCalledTimes(1);
    expect(mocks.broadcastLogout).not.toHaveBeenCalled();
  });

  it('clears old private caches before switching the cache scope back to anonymous', async () => {
    mocks.getPrivateCacheUserScope.mockReturnValue('user-before-logout');

    await authService.clearLocalPrivateSessionState();

    expect(mocks.clearPrivateClientCaches).toHaveBeenCalledTimes(1);
    expect(mocks.setPrivateCacheUserScope).toHaveBeenCalledWith(null);
    expect(mocks.clearPrivateClientCaches.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.setPrivateCacheUserScope.mock.invocationCallOrder[0]
    );
  });

  it('logs out through cookie auth without sending a stale bearer token', async () => {
    setAccessToken('stale-before-logout');
    mocks.fetchWithTimeout.mockResolvedValue(new Response(null, { status: 204 }));

    await authService.logout();

    expect(mocks.fetchWithTimeout).toHaveBeenCalledWith(
      '/api/auth/logout',
      expect.objectContaining({
        method: 'POST',
        skipAuth: true,
        withAuth: true,
      })
    );
    const headers = new Headers(mocks.fetchWithTimeout.mock.calls[0][1].headers);
    expect(headers.has('Authorization')).toBe(false);
  });

  it('scopes media cache to the current user returned by cookie-first auth', async () => {
    setAccessToken('stale-memory-access-token');
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
    mocks.readJsonResponse.mockResolvedValue({
      id: 'cookie-user',
      email: 'cookie@example.com',
      name: null,
      status: 'active',
    });

    const user = await authService.getCurrentUser(true);

    expect(user?.id).toBe('cookie-user');
    expect(mocks.setPrivateCacheUserScope).toHaveBeenCalledWith('cookie-user');
    expect(mocks.fetchWithTimeout).toHaveBeenCalledWith(
      '/api/auth/me',
      expect.objectContaining({
        method: 'GET',
        skipAuth: true,
        withAuth: true,
      })
    );
    const headers = new Headers(mocks.fetchWithTimeout.mock.calls[0][1].headers);
    expect(headers.has('Authorization')).toBe(false);
  });

  it('clears anonymous private caches before adopting a cookie-authenticated user scope', async () => {
    mocks.getPrivateCacheUserScope.mockReturnValue('anonymous');
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
    mocks.readJsonResponse.mockResolvedValue({
      id: 'cookie-user-from-anonymous',
      email: 'cookie-anonymous@example.com',
      name: null,
      status: 'active',
    });

    const user = await authService.getCurrentUser(true);

    expect(user?.id).toBe('cookie-user-from-anonymous');
    expect(mocks.clearPrivateClientCaches).toHaveBeenCalledTimes(1);
    expect(mocks.setPrivateCacheUserScope).toHaveBeenCalledWith('cookie-user-from-anonymous');
  });

  it('clears private caches when cookie auth can no longer resolve the current user', async () => {
    setAccessToken('stale-memory-access-token');
    mocks.fetchWithTimeout.mockResolvedValue(new Response(null, { status: 401 }));

    const user = await authService.getCurrentUser(true);

    expect(user).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(mocks.setPrivateCacheUserScope).toHaveBeenCalledWith(null);
    expect(mocks.clearPrivateClientCaches).toHaveBeenCalledTimes(1);
  });

  it('clears old private caches before switching to a different authenticated user from cookie auth', async () => {
    mocks.getPrivateCacheUserScope.mockReturnValue('user-1');
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
    mocks.readJsonResponse.mockResolvedValue({
      id: 'user-2',
      email: 'u2@example.com',
      name: null,
      status: 'active',
    });

    const user = await authService.getCurrentUser(true);

    expect(user?.id).toBe('user-2');
    expect(mocks.clearPrivateClientCaches).toHaveBeenCalledTimes(1);
    expect(mocks.setPrivateCacheUserScope).toHaveBeenCalledWith('user-2');
  });

  it('does not adopt a stale current-user response after local private session state is cleared', async () => {
    const staleResponse = createDeferred<Response>();
    mocks.fetchWithTimeout.mockReturnValueOnce(staleResponse.promise);
    mocks.readJsonResponse.mockResolvedValueOnce({
      id: 'stale-user',
      email: 'stale@example.com',
      name: null,
      status: 'active',
    });

    const pendingUser = authService.getCurrentUser(true);
    await Promise.resolve();

    await authService.clearLocalPrivateSessionState();
    mocks.setPrivateCacheUserScope.mockClear();
    mocks.clearPrivateClientCaches.mockClear();

    staleResponse.resolve(new Response('{}', { status: 200 }));

    await expect(pendingUser).resolves.toBeNull();
    expect(mocks.setPrivateCacheUserScope).not.toHaveBeenCalledWith('stale-user');
    expect(mocks.clearPrivateClientCaches).not.toHaveBeenCalled();
  });

  it('refreshes through httpOnly cookie when no JS refresh token is available', async () => {
    setAccessToken('stale-access-token');
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
    mocks.readJsonResponse.mockResolvedValue({
      expiresIn: 900,
    });

    const refreshed = await authService.refreshToken();

    expect(refreshed).toBe(true);
    expect(getAccessToken()).toBeNull();
    expect(mocks.broadcastTokenRefresh).toHaveBeenCalledWith();
    expect(mocks.fetchWithTimeout).toHaveBeenCalledWith(
      '/api/auth/refresh',
      expect.objectContaining({
        method: 'POST',
        skipAuth: true,
        withAuth: true,
      })
    );
    const headers = new Headers(mocks.fetchWithTimeout.mock.calls[0][1].headers);
    expect(headers.has('Authorization')).toBe(false);
  });

});

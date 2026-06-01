// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getAccessToken,
  removeAccessToken,
  removeRefreshToken,
  setAccessToken,
} from './authTokenStore';

describe('authTokenStore', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    removeAccessToken();
    removeRefreshToken();
  });

  it('keeps access token in memory and removes legacy JS-visible tokens', () => {
    window.localStorage.setItem('access_token', 'legacy-access');
    window.localStorage.setItem('refresh_token', 'legacy-refresh');
    window.sessionStorage.setItem('access_token', 'session-legacy-access');
    window.sessionStorage.setItem('refresh_token', 'session-legacy-refresh');

    setAccessToken('memory-access');
    removeRefreshToken();

    expect(getAccessToken()).toBe('memory-access');
    expect(window.localStorage.getItem('access_token')).toBeNull();
    expect(window.localStorage.getItem('refresh_token')).toBeNull();
    expect(window.sessionStorage.getItem('access_token')).toBeNull();
    expect(window.sessionStorage.getItem('refresh_token')).toBeNull();
  });

  it('clears memory access token and legacy localStorage tokens together', () => {
    setAccessToken('memory-access');
    window.localStorage.setItem('access_token', 'legacy-access');
    window.localStorage.setItem('refresh_token', 'legacy-refresh');
    window.sessionStorage.setItem('access_token', 'session-legacy-access');
    window.sessionStorage.setItem('refresh_token', 'session-legacy-refresh');

    removeAccessToken();
    removeRefreshToken();

    expect(getAccessToken()).toBeNull();
    expect(window.localStorage.getItem('access_token')).toBeNull();
    expect(window.localStorage.getItem('refresh_token')).toBeNull();
    expect(window.sessionStorage.getItem('access_token')).toBeNull();
    expect(window.sessionStorage.getItem('refresh_token')).toBeNull();
  });

  it('removes JS-visible legacy tokens as soon as the token store loads', async () => {
    removeAccessToken();
    removeRefreshToken();
    vi.resetModules();

    window.localStorage.setItem('access_token', 'legacy-access-on-load');
    window.localStorage.setItem('refresh_token', 'legacy-refresh-on-load');
    window.sessionStorage.setItem('access_token', 'session-legacy-access-on-load');
    window.sessionStorage.setItem('refresh_token', 'session-legacy-refresh-on-load');

    await import('./authTokenStore');

    expect(window.localStorage.getItem('access_token')).toBeNull();
    expect(window.localStorage.getItem('refresh_token')).toBeNull();
    expect(window.sessionStorage.getItem('access_token')).toBeNull();
    expect(window.sessionStorage.getItem('refresh_token')).toBeNull();
  });
});

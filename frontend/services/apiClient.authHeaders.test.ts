// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';
import { getAuthHeaders } from './apiClient';
import { removeAccessToken, setAccessToken } from './authTokenStore';

describe('apiClient auth header helpers', () => {
  beforeEach(() => {
    window.localStorage.clear();
    removeAccessToken();
  });

  it('uses cookie-first auth headers by default for manual same-origin requests', () => {
    setAccessToken('memory-access-token');

    expect(getAuthHeaders()).toEqual({});
  });

  it('can opt in to bearer headers for non-browser API clients', () => {
    setAccessToken('memory-access-token');

    expect(getAuthHeaders({ includeBearer: true })).toEqual({
      Authorization: 'Bearer memory-access-token',
    });
  });
});

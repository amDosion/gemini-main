// @vitest-environment jsdom

import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  initialize: vi.fn(),
  reportError: vi.fn(),
}));

vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: mocks.apiGet,
  },
}));

vi.mock('../services/LLMFactory', () => ({
  LLMFactory: {
    initialize: mocks.initialize,
  },
}));

vi.mock('../utils/globalErrorHandler', () => ({
  reportError: mocks.reportError,
}));

import { useInitData } from './useInitData';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
};

describe('useInitData cache lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setPrivateCacheUserScope(null);
  });

  it('does not restore stale init data when auth-driven loading is disabled before a critical request resolves', async () => {
    const deferredCritical = createDeferred<any>();
    mocks.apiGet.mockImplementation((url: string) => {
      if (url === '/api/init/critical') {
        return deferredCritical.promise;
      }
      return Promise.resolve({});
    });

    const { result, rerender } = renderHook(
      ({ shouldLoad }) => useInitData(shouldLoad),
      { initialProps: { shouldLoad: true } }
    );

    await waitFor(() => {
      expect(mocks.apiGet).toHaveBeenCalledWith(
        '/api/init/critical',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    rerender({ shouldLoad: false });

    expect(result.current.criticalData).toBeNull();
    expect(result.current.initData).toBeNull();

    await act(async () => {
      deferredCritical.resolve({
        profiles: [{ id: 'old-user-profile' }],
        activeProfileId: 'old-user-profile',
      });
      await deferredCritical.promise;
      await Promise.resolve();
    });

    expect(result.current.criticalData).toBeNull();
    expect(result.current.initData).toBeNull();
    expect(mocks.initialize).not.toHaveBeenCalled();
  });

  it('reloads init data when the authenticated private cache scope changes while loading remains enabled', async () => {
    const firstCritical = createDeferred<any>();
    const secondCritical = createDeferred<any>();
    const criticalRequests = [firstCritical, secondCritical];
    let criticalRequestIndex = 0;

    mocks.apiGet.mockImplementation((url: string) => {
      if (url === '/api/init/critical') {
        const request = criticalRequests[criticalRequestIndex];
        criticalRequestIndex += 1;
        return request.promise;
      }
      return Promise.resolve({});
    });

    setPrivateCacheUserScope('user-1');

    const { result } = renderHook(() => useInitData(true));

    await waitFor(() => {
      expect(criticalRequestIndex).toBe(1);
    });

    await act(async () => {
      firstCritical.resolve({
        profiles: [{ id: 'user-1-profile' }],
        activeProfileId: 'user-1-profile',
      });
      await firstCritical.promise;
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.criticalData?.activeProfileId).toBe('user-1-profile');
    });

    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    await waitFor(() => {
      expect(criticalRequestIndex).toBe(2);
    });
    expect(result.current.criticalData).toBeNull();
    expect(result.current.initData).toBeNull();

    await act(async () => {
      secondCritical.resolve({
        profiles: [{ id: 'user-2-profile' }],
        activeProfileId: 'user-2-profile',
      });
      await secondCritical.promise;
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.criticalData?.activeProfileId).toBe('user-2-profile');
    });
  });
});

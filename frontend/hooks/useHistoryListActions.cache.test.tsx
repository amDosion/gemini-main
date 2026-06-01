// @vitest-environment jsdom
import { cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager } from '../services/CacheManager';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';
import {
  readCachedHistoryPreference,
  readCachedHistoryStates,
} from '../services/sessionCache';
import { useHistoryListActions } from './useHistoryListActions';

const {
  getSessionHistoryStatesMock,
  getSessionHistoryPreferenceMock,
  updateSessionHistoryStateMock,
  updateSessionHistoryPreferenceMock,
} = vi.hoisted(() => ({
  getSessionHistoryStatesMock: vi.fn(),
  getSessionHistoryPreferenceMock: vi.fn(),
  updateSessionHistoryStateMock: vi.fn(),
  updateSessionHistoryPreferenceMock: vi.fn(),
}));

vi.mock('../services/db', () => ({
  db: {
    getSessionHistoryStates: getSessionHistoryStatesMock,
    getSessionHistoryPreference: getSessionHistoryPreferenceMock,
    updateSessionHistoryState: updateSessionHistoryStateMock,
    updateSessionHistoryPreference: updateSessionHistoryPreferenceMock,
  },
}));

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('useHistoryListActions session cache', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
    getSessionHistoryStatesMock.mockReset();
    getSessionHistoryPreferenceMock.mockReset();
    updateSessionHistoryStateMock.mockReset();
    updateSessionHistoryPreferenceMock.mockReset();
  });

  it('reuses cached favorite state and preference when returning to a session', async () => {
    getSessionHistoryStatesMock.mockImplementation((sessionId: string) => {
      if (sessionId === 'session-a') {
        return Promise.resolve([{ messageId: 'a-1', isFavorite: true }]);
      }
      if (sessionId === 'session-b') {
        return Promise.resolve([]);
      }
      throw new Error(`Unexpected sessionId: ${sessionId}`);
    });
    getSessionHistoryPreferenceMock.mockImplementation((sessionId: string) => {
      if (sessionId === 'session-a') {
        return Promise.resolve({ showFavoritesOnly: true });
      }
      if (sessionId === 'session-b') {
        return Promise.resolve({ showFavoritesOnly: false });
      }
      throw new Error(`Unexpected sessionId: ${sessionId}`);
    });

    const { result, rerender } = renderHook(
      ({ sessionId }) =>
        useHistoryListActions({
          sessionId,
          items: [
            { id: 'a-1' },
            { id: 'b-1' },
          ],
        }),
      { initialProps: { sessionId: 'session-a' as string | null } }
    );

    await waitFor(() => {
      expect(result.current.isFavorite('a-1')).toBe(true);
      expect(result.current.showFavoritesOnly).toBe(true);
    });

    rerender({ sessionId: 'session-b' });
    await waitFor(() => {
      expect(result.current.isFavorite('a-1')).toBe(false);
      expect(result.current.showFavoritesOnly).toBe(false);
    });

    rerender({ sessionId: 'session-a' });
    await waitFor(() => {
      expect(result.current.isFavorite('a-1')).toBe(true);
      expect(result.current.showFavoritesOnly).toBe(true);
    });

    expect(getSessionHistoryStatesMock).toHaveBeenCalledTimes(2);
    expect(getSessionHistoryPreferenceMock).toHaveBeenCalledTimes(2);
    expect(getSessionHistoryStatesMock).toHaveBeenCalledWith('session-a');
    expect(getSessionHistoryStatesMock).toHaveBeenCalledWith('session-b');
  });

  it('does not write history cache into a new private scope when an old request resolves late', async () => {
    setPrivateCacheUserScope('user-1');
    const statesRequest = createDeferred<Array<{ messageId: string; isFavorite: boolean }>>();
    const preferenceRequest = createDeferred<{ showFavoritesOnly: boolean }>();
    getSessionHistoryStatesMock.mockReturnValueOnce(statesRequest.promise);
    getSessionHistoryPreferenceMock.mockReturnValueOnce(preferenceRequest.promise);
    getSessionHistoryStatesMock.mockResolvedValueOnce([]);
    getSessionHistoryPreferenceMock.mockResolvedValueOnce({ showFavoritesOnly: false });

    renderHook(() =>
      useHistoryListActions({
        sessionId: 'session-a',
        items: [{ id: 'a-1' }],
      })
    );

    await waitFor(() => {
      expect(getSessionHistoryStatesMock).toHaveBeenCalledTimes(1);
      expect(getSessionHistoryPreferenceMock).toHaveBeenCalledTimes(1);
    });

    cacheManager.clearAll();
    setPrivateCacheUserScope('user-2');
    statesRequest.resolve([{ messageId: 'a-1', isFavorite: true }]);
    preferenceRequest.resolve({ showFavoritesOnly: true });

    await statesRequest.promise;
    await preferenceRequest.promise;

    await waitFor(() => {
      expect(getSessionHistoryStatesMock).toHaveBeenCalledTimes(2);
      expect(getSessionHistoryPreferenceMock).toHaveBeenCalledTimes(2);
    });
    expect(readCachedHistoryStates('session-a')).toEqual([]);
    expect(readCachedHistoryPreference('session-a')).toEqual({ showFavoritesOnly: false });
  });

  it('clears loaded favorite state and reloads the same session when private scope changes', async () => {
    setPrivateCacheUserScope('user-1');
    getSessionHistoryStatesMock
      .mockResolvedValueOnce([{ messageId: 'a-1', isFavorite: true }])
      .mockResolvedValueOnce([{ messageId: 'a-1', isFavorite: false }]);
    getSessionHistoryPreferenceMock
      .mockResolvedValueOnce({ showFavoritesOnly: true })
      .mockResolvedValueOnce({ showFavoritesOnly: false });

    const { result } = renderHook(() =>
      useHistoryListActions({
        sessionId: 'session-a',
        items: [{ id: 'a-1' }],
      })
    );

    await waitFor(() => {
      expect(result.current.isFavorite('a-1')).toBe(true);
      expect(result.current.showFavoritesOnly).toBe(true);
    });

    setPrivateCacheUserScope('user-2');

    await waitFor(() => {
      expect(result.current.isFavorite('a-1')).toBe(false);
      expect(result.current.showFavoritesOnly).toBe(false);
    });
    await waitFor(() => {
      expect(getSessionHistoryStatesMock).toHaveBeenCalledTimes(2);
      expect(getSessionHistoryPreferenceMock).toHaveBeenCalledTimes(2);
    });
  });
});

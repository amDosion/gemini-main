// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager } from '../services/CacheManager';
import { apiClient } from '../services/apiClient';
import { db } from '../services/db';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';
import type { AppMode, ChatSession } from '../types/types';
import { useSessions } from './useSessions';

vi.mock('../services/db', () => ({
  db: {
    saveSession: vi.fn(),
    deleteSession: vi.fn(),
    getSessions: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const createSession = (id: string, mode: AppMode = 'chat'): ChatSession => ({
  id,
  title: id,
  mode,
  createdAt: Date.now(),
  messages: [],
});

const apiGetMock = vi.mocked(apiClient.get);
const saveSessionMock = vi.mocked(db.saveSession);

const emptyPage = { sessions: [], total: 0, hasMore: false, nextCursor: null };

beforeEach(() => {
  cacheManager.clearAll();
  setPrivateCacheUserScope(null);
  apiGetMock.mockReset();
  apiGetMock.mockResolvedValue(emptyPage);
  saveSessionMock.mockReset();
  saveSessionMock.mockResolvedValue(undefined as never);
});

afterEach(() => {
  cleanup();
  cacheManager.clearAll();
  setPrivateCacheUserScope(null);
  vi.restoreAllMocks();
});

describe('useSessions saveSessionToDb error surfacing (F2)', () => {
  it('logs persistence failures that are not caused by component unmount', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    saveSessionMock.mockRejectedValueOnce(new Error('backend 500: write failed'));

    const { result } = renderHook(() => useSessions('chat'));
    act(() => {
      result.current.createNewSession();
    });

    await waitFor(() => expect(errorSpy).toHaveBeenCalled());
  });

  it('stays silent when the failure is a component-unmount cancellation', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    saveSessionMock.mockRejectedValueOnce(new Error('Request aborted due to component unmount'));

    const { result } = renderHook(() => useSessions('chat'));
    act(() => {
      result.current.createNewSession();
    });

    // Give the rejected promise a chance to be handled.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(errorSpy).not.toHaveBeenCalled();
  });
});

describe('useSessions loadMoreSessions null safety (F3)', () => {
  it('does not throw when a paginated response omits the sessions array', async () => {
    apiGetMock.mockResolvedValueOnce({
      sessions: [createSession('s1')],
      total: 1,
      hasMore: true,
      nextCursor: null,
    });

    const { result } = renderHook(() => useSessions('chat'));
    await act(async () => {
      await result.current.refreshSessions({ force: true });
    });
    await waitFor(() => expect(result.current.hasMoreSessions).toBe(true));

    // Malformed page: hasMore true but no sessions key at all. The unguarded
    // `result.sessions.length` throws a TypeError that the C-6 catch swallows,
    // leaving hasMoreSessions stuck true => infinite re-fetch loop on scroll.
    apiGetMock.mockResolvedValueOnce({ hasMore: true } as never);

    await act(async () => {
      await result.current.loadMoreSessions();
    });

    // A page with no sessions must settle pagination, not loop forever.
    expect(result.current.hasMoreSessions).toBe(false);
    // Existing sessions are preserved; the malformed page added nothing.
    expect(result.current.sessions).toHaveLength(1);
  });
});

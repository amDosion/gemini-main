// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager } from '../services/CacheManager';
import { apiClient } from '../services/apiClient';
import { clearPrivateMemoryCaches } from '../services/privateClientCache';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';
import {
  getCurrentSessionIdCacheKey,
  readCachedSessionsForMode,
  readCurrentSessionIdForMode,
  writeCachedSessionsForMode,
  writeCurrentSessionIdForMode,
} from '../services/sessionCache';
import { Role, type ChatSession, type Message } from '../types/types';
import type { Attachment } from '../types/types';
import type { AppMode } from '../types/types';
import { recoverSessionAttachmentUrl, useSessions } from './useSessions';

vi.mock('../services/db', () => ({
  db: {
    saveSession: vi.fn(),
    deleteSession: vi.fn(),
    getSessions: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({
      sessions: [],
      total: 0,
      hasMore: false,
      nextCursor: null,
    }),
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

describe('useSessions private cache scope', () => {
  beforeEach(() => {
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
    apiGetMock.mockReset();
    apiGetMock.mockResolvedValue({
      sessions: [],
      total: 0,
      hasMore: false,
      nextCursor: null,
    });
  });

  afterEach(() => {
    cleanup();
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
  });

  it('resubscribes to the current user session cache after private cache reset', async () => {
    setPrivateCacheUserScope('user-1');
    const userOneSession = createSession('user-1-session');
    writeCachedSessionsForMode('chat', [userOneSession]);

    const hook = renderHook(() => useSessions('chat'));

    await waitFor(() => {
      expect(hook.result.current.sessions).toEqual([userOneSession]);
    });

    setPrivateCacheUserScope('user-2');
    act(() => {
      clearPrivateMemoryCaches();
    });

    await waitFor(() => {
      expect(hook.result.current.sessions).toEqual([]);
    });

    const userTwoSession = createSession('user-2-session');
    act(() => {
      writeCachedSessionsForMode('chat', [userTwoSession]);
    });

    await waitFor(() => {
      expect(hook.result.current.sessions).toEqual([userTwoSession]);
    });
  });

  it('clears local pagination state when private cache scope changes', async () => {
    setPrivateCacheUserScope('user-1');
    const userOneSession = createSession('user-1-session');

    const hook = renderHook(() =>
      useSessions('chat', {
        sessions: [userOneSession],
        sessionsMode: 'chat',
        sessionsHasMore: true,
      })
    );

    await waitFor(() => {
      expect(hook.result.current.sessions).toEqual([userOneSession]);
      expect(hook.result.current.hasMoreSessions).toBe(true);
    });

    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    expect(hook.result.current.sessions).toEqual([]);
    expect(hook.result.current.hasMoreSessions).toBe(false);
    expect(hook.result.current.isLoadingMore).toBe(false);
  });

  it('does not expose a stale current session id when the cached mode list is empty', () => {
    writeCachedSessionsForMode('chat', []);
    writeCurrentSessionIdForMode('chat', 'removed-session');

    const hook = renderHook(() => useSessions('chat'));

    expect(hook.result.current.sessions).toEqual([]);
    expect(hook.result.current.currentSessionId).toBeNull();
  });

  it('does not mutate the current-session cache while deriving a stale current id', () => {
    writeCachedSessionsForMode('chat', []);
    writeCurrentSessionIdForMode('chat', 'removed-session');

    const currentSessionNotifications: Array<string | null> = [];
    const unsubscribe = cacheManager.subscribe<string | null>(
      getCurrentSessionIdCacheKey('chat'),
      (value) => {
        currentSessionNotifications.push(value);
      }
    );

    try {
      const hook = renderHook(() => useSessions('chat'));

      expect(hook.result.current.sessions).toEqual([]);
      expect(hook.result.current.currentSessionId).toBeNull();
      expect(currentSessionNotifications).toEqual([]);
    } finally {
      unsubscribe();
    }
  });

  it('loads initial mode sessions without auto-selecting the latest session', async () => {
    const olderSession = { ...createSession('older-session', 'chat'), createdAt: 1 };
    const latestSession = { ...createSession('latest-session', 'chat'), createdAt: 2 };

    const hook = renderHook(() =>
      useSessions('chat', {
        sessions: [olderSession, latestSession],
        sessionsMode: 'chat',
        sessionsHasMore: false,
      })
    );

    await waitFor(() => {
      expect(hook.result.current.sessions.map((session) => session.id)).toEqual([
        'latest-session',
        'older-session',
      ]);
    });

    expect(hook.result.current.currentSessionId).toBeNull();
    expect(readCurrentSessionIdForMode('chat')).toBeNull();
    expect(apiGetMock).not.toHaveBeenCalledWith(expect.stringMatching(/^\/api\/sessions\//));
  });

  it('restores an explicitly selected cached session when it is still in the mode list', async () => {
    const olderSession = { ...createSession('older-session', 'chat'), createdAt: 1 };
    const latestSession = { ...createSession('latest-session', 'chat'), createdAt: 2 };
    writeCurrentSessionIdForMode('chat', 'older-session');

    const hook = renderHook(() =>
      useSessions('chat', {
        sessions: [olderSession, latestSession],
        sessionsMode: 'chat',
        sessionsHasMore: false,
      })
    );

    await waitFor(() => {
      expect(hook.result.current.currentSessionId).toBe('older-session');
    });
    expect(readCurrentSessionIdForMode('chat')).toBe('older-session');
  });

  it('reuses cached empty mode lists instead of refetching when a mode is revisited', async () => {
    const chatSession = createSession('chat-session', 'chat');

    const { result, rerender } = renderHook(
      ({ mode }) =>
        useSessions(mode, {
          sessions: [chatSession],
          sessionsMode: 'chat',
          sessionsHasMore: false,
        }),
      { initialProps: { mode: 'chat' as AppMode } }
    );

    await waitFor(() => {
      expect(result.current.sessions).toEqual([chatSession]);
    });

    rerender({ mode: 'image-gen' });

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(result.current.sessions).toEqual([]);
      expect(result.current.isLoading).toBe(false);
    });

    rerender({ mode: 'chat' });
    await waitFor(() => {
      expect(result.current.sessions).toEqual([chatSession]);
    });

    rerender({ mode: 'image-gen' });
    await waitFor(() => {
      expect(result.current.sessions).toEqual([]);
      expect(result.current.isLoading).toBe(false);
    });

    expect(apiGetMock).toHaveBeenCalledTimes(1);
  });

  it('recovers stale blob attachment urls from cloudUrl before caching sessions', () => {
    const attachment = {
      id: 'att-cloud',
      name: 'result.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/stale-result',
      cloudUrl: '/api/storage/local-files/2026/05/31/result.png',
      tempUrl: 'https://temporary.example.com/result.png',
      uploadStatus: 'completed',
    } satisfies Attachment;

    expect(recoverSessionAttachmentUrl(attachment)).toMatchObject({
      url: '/api/storage/local-files/2026/05/31/result.png',
      cloudUrl: '/api/storage/local-files/2026/05/31/result.png',
      uploadStatus: 'completed',
    });
  });

  it('recovers stale blob attachment urls from relative storage tempUrl when cloudUrl is missing', () => {
    const attachment = {
      id: 'att-temp-storage',
      name: 'result.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/stale-result',
      tempUrl: '/api/storage/local-files/2026/05/31/temp-result.png',
      uploadStatus: 'completed',
    } satisfies Attachment;

    expect(recoverSessionAttachmentUrl(attachment)).toMatchObject({
      url: '/api/storage/local-files/2026/05/31/temp-result.png',
      cloudUrl: '/api/storage/local-files/2026/05/31/temp-result.png',
      uploadStatus: 'completed',
    });
  });

  it('recovers stale blob attachment urls from fileUri when cloudUrl and tempUrl are missing', () => {
    const attachment = {
      id: 'att-file-uri',
      name: 'result.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/stale-file-uri',
      fileUri: '/api/storage/local-files/2026/05/31/file-uri-result.png',
      uploadStatus: 'completed',
    } satisfies Attachment;

    expect(recoverSessionAttachmentUrl(attachment)).toMatchObject({
      url: '/api/storage/local-files/2026/05/31/file-uri-result.png',
      cloudUrl: '/api/storage/local-files/2026/05/31/file-uri-result.png',
      uploadStatus: 'completed',
    });
  });

  it('recovers stale blob attachment urls from local fileUri before remote tempUrl', () => {
    const attachment = {
      id: 'att-file-uri-over-temp',
      name: 'result.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/stale-file-uri-over-temp',
      tempUrl: 'https://temporary.example.com/generated-temp.png',
      fileUri: '/api/storage/local-files/2026/05/31/file-uri-over-temp.png',
      uploadStatus: 'completed',
    } satisfies Attachment;

    expect(recoverSessionAttachmentUrl(attachment)).toMatchObject({
      url: '/api/storage/local-files/2026/05/31/file-uri-over-temp.png',
      cloudUrl: '/api/storage/local-files/2026/05/31/file-uri-over-temp.png',
      uploadStatus: 'completed',
    });
  });

  it('recovers temporary data attachment urls through the shared durable url preference', () => {
    const attachment = {
      id: 'att-data-url',
      name: 'result.png',
      mimeType: 'image/png',
      url: 'data:image/png;base64,abc',
      cloudUrl: '/api/storage/local-files/2026/05/31/data-result.png',
      uploadStatus: 'completed',
    } satisfies Attachment;

    expect(recoverSessionAttachmentUrl(attachment)).toMatchObject({
      url: '/api/storage/local-files/2026/05/31/data-result.png',
      cloudUrl: '/api/storage/local-files/2026/05/31/data-result.png',
      uploadStatus: 'completed',
    });
  });

  it('moves a session to the target mode cache when updated messages change its mode', async () => {
    const chatSession = createSession('session-mode-move', 'chat');
    const imageMessage: Message = {
      id: 'image-message',
      role: Role.MODEL,
      content: 'generated image',
      attachments: [],
      timestamp: Date.now(),
      mode: 'image-gen',
    };

    const { result } = renderHook(() =>
      useSessions('chat', {
        sessions: [chatSession],
        sessionsMode: 'chat',
        sessionsHasMore: false,
      })
    );

    await waitFor(() => {
      expect(result.current.sessions).toEqual([chatSession]);
      expect(result.current.currentSessionId).toBeNull();
    });

    act(() => {
      result.current.updateSessionMessages('session-mode-move', [imageMessage]);
    });

    await waitFor(() => {
      expect(readCachedSessionsForMode('chat')).toEqual([]);
      expect(readCurrentSessionIdForMode('chat')).toBeNull();
      expect(readCachedSessionsForMode('image-gen')?.[0]).toMatchObject({
        id: 'session-mode-move',
        mode: 'image-gen',
        messages: [imageMessage],
      });
    });
  });
});

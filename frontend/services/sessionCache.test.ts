import { beforeEach, describe, expect, it } from 'vitest';
import { CACHE_DOMAINS, cacheManager } from './CacheManager';
import {
  getCurrentSessionIdCacheKey,
  getSessionListCacheKey,
  readCachedHistoryPreference,
  readCachedHistoryStates,
  readCachedSessionsForMode,
  readCurrentSessionIdForMode,
  removeSessionFromCaches,
  selectCurrentSessionIdForMode,
  upsertSessionInCaches,
  writeCachedHistoryPreference,
  writeCachedHistoryStates,
  writeCachedSessionsForMode,
  writeCurrentSessionIdForMode,
} from './sessionCache';
import { ChatSession } from '../types/types';
import { setPrivateCacheUserScope } from './privateCacheScope';

const createSession = (id: string, mode: ChatSession['mode']): ChatSession => ({
  id,
  title: id,
  mode,
  createdAt: Date.now(),
  messages: [],
});

describe('sessionCache', () => {
  beforeEach(() => {
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
  });

  it('keeps session lists isolated per mode', () => {
    const chatSession = createSession('chat-session', 'chat');
    const imageSession = createSession('image-session', 'image-gen');

    writeCachedSessionsForMode('chat', [chatSession]);
    writeCachedSessionsForMode('image-gen', [imageSession]);

    expect(readCachedSessionsForMode('chat')).toEqual([chatSession]);
    expect(readCachedSessionsForMode('image-gen')).toEqual([imageSession]);
  });

  it('filters mismatched sessions when reading and writing a mode cache', () => {
    const chatSession = createSession('chat-session', 'chat');
    const imageSession = createSession('image-session', 'image-gen');

    writeCachedSessionsForMode('chat', [imageSession, chatSession]);

    expect(readCachedSessionsForMode('chat')).toEqual([chatSession]);
  });

  it('clears a current-session pointer that no longer exists after writing a mode list', () => {
    const remainingSession = createSession('remaining-session', 'chat');

    writeCurrentSessionIdForMode('chat', 'removed-session');
    writeCachedSessionsForMode('chat', [remainingSession]);

    expect(readCurrentSessionIdForMode('chat')).toBeNull();
  });

  it('self-heals a current-session pointer written after the mode list when it is stale', () => {
    const remainingSession = createSession('remaining-session', 'chat');

    writeCachedSessionsForMode('chat', [remainingSession]);
    writeCurrentSessionIdForMode('chat', 'removed-session');

    expect(readCurrentSessionIdForMode('chat')).toBeNull();
  });

  it('does not select the newest session when no explicit current-session pointer exists', () => {
    const olderSession = { ...createSession('older-session', 'chat'), createdAt: 1 };
    const latestSession = { ...createSession('latest-session', 'chat'), createdAt: 2 };

    expect(selectCurrentSessionIdForMode('chat', [latestSession, olderSession])).toBeNull();
  });

  it('returns an explicit current-session pointer when it is still in the mode list', () => {
    const olderSession = { ...createSession('older-session', 'chat'), createdAt: 1 };
    const latestSession = { ...createSession('latest-session', 'chat'), createdAt: 2 };

    writeCachedSessionsForMode('chat', [latestSession, olderSession]);
    writeCurrentSessionIdForMode('chat', 'older-session');

    expect(selectCurrentSessionIdForMode('chat', [latestSession, olderSession])).toBe(
      'older-session'
    );
  });

  it('removes a deleted session from every cached mode and current-session pointer', () => {
    const chatSession = createSession('chat-session', 'chat');
    const imageSession = createSession('image-session', 'image-gen');

    writeCachedSessionsForMode('chat', [chatSession]);
    writeCachedSessionsForMode('image-gen', [imageSession]);
    writeCurrentSessionIdForMode('chat', 'chat-session');
    writeCurrentSessionIdForMode('image-gen', 'image-session');

    removeSessionFromCaches('image-session');

    expect(readCachedSessionsForMode('chat')).toEqual([chatSession]);
    expect(readCachedSessionsForMode('image-gen')).toEqual([]);
    expect(readCurrentSessionIdForMode('chat')).toBe('chat-session');
    expect(readCurrentSessionIdForMode('image-gen')).toBeNull();
  });

  it('upserts sessions only into their mode partition', () => {
    const imageSession = createSession('image-session', 'image-gen');

    upsertSessionInCaches(imageSession);

    expect(readCachedSessionsForMode('image-gen')).toEqual([imageSession]);
    expect(cacheManager.get<ChatSession[]>(CACHE_DOMAINS.SESSIONS)).toBeNull();
  });

  it('moves an upserted session out of stale mode partitions', () => {
    const originalChatSession = createSession('moved-session', 'chat');
    const updatedImageSession = {
      ...originalChatSession,
      mode: 'image-gen' as const,
      title: 'moved-session-image',
    };

    writeCachedSessionsForMode('chat', [originalChatSession]);
    writeCurrentSessionIdForMode('chat', 'moved-session');

    upsertSessionInCaches(updatedImageSession);

    expect(readCachedSessionsForMode('chat')).toEqual([]);
    expect(readCurrentSessionIdForMode('chat')).toBeNull();
    expect(readCachedSessionsForMode('image-gen')).toEqual([updatedImageSession]);
  });

  it('moves a stale-mode session only inside the current private user scope', () => {
    const sharedId = 'shared-moved-session';
    const userOneSession = createSession(sharedId, 'chat');
    const userTwoOriginalSession = createSession(sharedId, 'chat');
    const userTwoUpdatedSession = {
      ...userTwoOriginalSession,
      mode: 'image-gen' as const,
      title: 'shared-moved-session-image',
    };

    setPrivateCacheUserScope('user-1');
    writeCachedSessionsForMode('chat', [userOneSession]);
    writeCurrentSessionIdForMode('chat', sharedId);

    setPrivateCacheUserScope('user-2');
    writeCachedSessionsForMode('chat', [userTwoOriginalSession]);
    writeCurrentSessionIdForMode('chat', sharedId);

    upsertSessionInCaches(userTwoUpdatedSession);

    expect(readCachedSessionsForMode('chat')).toEqual([]);
    expect(readCurrentSessionIdForMode('chat')).toBeNull();
    expect(readCachedSessionsForMode('image-gen')).toEqual([userTwoUpdatedSession]);

    setPrivateCacheUserScope('user-1');

    expect(readCachedSessionsForMode('chat')).toEqual([userOneSession]);
    expect(readCurrentSessionIdForMode('chat')).toBe(sharedId);
  });

  it('keeps session lists and current pointers isolated per user scope', () => {
    const userOneSession = createSession('user-one-chat', 'chat');
    const userTwoSession = createSession('user-two-chat', 'chat');

    setPrivateCacheUserScope('user-1');
    writeCachedSessionsForMode('chat', [userOneSession]);
    writeCurrentSessionIdForMode('chat', 'user-one-chat');
    const userOneListKey = getSessionListCacheKey('chat');
    const userOneCurrentKey = getCurrentSessionIdCacheKey('chat');

    setPrivateCacheUserScope('user-2');
    writeCachedSessionsForMode('chat', [userTwoSession]);
    writeCurrentSessionIdForMode('chat', 'user-two-chat');
    const userTwoListKey = getSessionListCacheKey('chat');
    const userTwoCurrentKey = getCurrentSessionIdCacheKey('chat');

    expect(userOneListKey).not.toBe(userTwoListKey);
    expect(userOneCurrentKey).not.toBe(userTwoCurrentKey);
    expect(readCachedSessionsForMode('chat')).toEqual([userTwoSession]);
    expect(readCurrentSessionIdForMode('chat')).toBe('user-two-chat');

    setPrivateCacheUserScope('user-1');

    expect(readCachedSessionsForMode('chat')).toEqual([userOneSession]);
    expect(readCurrentSessionIdForMode('chat')).toBe('user-one-chat');
  });

  it('removes a deleted session only from the current private user scope', () => {
    const sharedId = 'same-session-id';
    const userOneSession = createSession(sharedId, 'chat');
    const userTwoSession = createSession(sharedId, 'chat');

    setPrivateCacheUserScope('user-1');
    writeCachedSessionsForMode('chat', [userOneSession]);
    writeCurrentSessionIdForMode('chat', sharedId);

    setPrivateCacheUserScope('user-2');
    writeCachedSessionsForMode('chat', [userTwoSession]);
    writeCurrentSessionIdForMode('chat', sharedId);

    removeSessionFromCaches(sharedId);

    expect(readCachedSessionsForMode('chat')).toEqual([]);
    expect(readCurrentSessionIdForMode('chat')).toBeNull();

    setPrivateCacheUserScope('user-1');

    expect(readCachedSessionsForMode('chat')).toEqual([userOneSession]);
    expect(readCurrentSessionIdForMode('chat')).toBe(sharedId);
  });

  it('clears cached history state and preference for a deleted session in the current private scope', () => {
    const sessionId = 'session-with-history-cache';

    writeCachedHistoryStates(sessionId, [
      { messageId: 'message-1', isFavorite: true, updatedAt: 1 },
    ]);
    writeCachedHistoryPreference(sessionId, {
      showFavoritesOnly: true,
      updatedAt: 2,
    });

    removeSessionFromCaches(sessionId);

    expect(readCachedHistoryStates(sessionId)).toBeNull();
    expect(readCachedHistoryPreference(sessionId)).toBeNull();
  });
});

import { ChatSession, AppMode } from '../types/types';
import type { SessionHistoryPreference, SessionHistoryState } from './db';
import { cacheManager } from './CacheManager';
import { normalizeChatSession } from './sessionNormalizer';
import { scopedPrivateCacheKey, scopedPrivateCachePrefix } from './privateCacheScope';

const SESSION_CACHE_TTL_MS = 30 * 60 * 1000;
const SESSION_HISTORY_CACHE_TTL_MS = 30 * 60 * 1000;

export const SESSION_LIST_BY_MODE_PREFIX = 'sessions:mode:';
export const CURRENT_SESSION_ID_BY_MODE_PREFIX = 'currentSessionId:mode:';
export const SESSION_HAS_MORE_BY_MODE_PREFIX = 'sessions:hasMore:mode:';
export const SESSION_HISTORY_STATES_PREFIX = 'sessionHistoryStates:';
export const SESSION_HISTORY_PREFERENCE_PREFIX = 'sessionHistoryPreference:';

cacheManager.setTTL(SESSION_LIST_BY_MODE_PREFIX, SESSION_CACHE_TTL_MS);
cacheManager.setTTL(CURRENT_SESSION_ID_BY_MODE_PREFIX, SESSION_CACHE_TTL_MS);
cacheManager.setTTL(SESSION_HAS_MORE_BY_MODE_PREFIX, SESSION_CACHE_TTL_MS);
cacheManager.setTTL(SESSION_HISTORY_STATES_PREFIX, SESSION_HISTORY_CACHE_TTL_MS);
cacheManager.setTTL(SESSION_HISTORY_PREFERENCE_PREFIX, SESSION_HISTORY_CACHE_TTL_MS);

export const getSessionMode = (session: Pick<ChatSession, 'mode'>): AppMode =>
  (session.mode || 'chat') as AppMode;

export const isSessionInMode = (session: Pick<ChatSession, 'mode'>, mode: AppMode): boolean =>
  getSessionMode(session) === mode;

export const filterSessionsForMode = (
  mode: AppMode,
  sessions: ChatSession[]
): ChatSession[] =>
  sessions
    .map(normalizeChatSession)
    .filter((session) => isSessionInMode(session, mode));

export const getSessionListCacheKey = (mode: AppMode): string =>
  scopedPrivateCacheKey(SESSION_LIST_BY_MODE_PREFIX, mode);

export const getCurrentSessionIdCacheKey = (mode: AppMode): string =>
  scopedPrivateCacheKey(CURRENT_SESSION_ID_BY_MODE_PREFIX, mode);

export const getSessionHasMoreCacheKey = (mode: AppMode): string =>
  scopedPrivateCacheKey(SESSION_HAS_MORE_BY_MODE_PREFIX, mode);

export const getSessionHistoryStatesCacheKey = (sessionId: string): string =>
  scopedPrivateCacheKey(SESSION_HISTORY_STATES_PREFIX, sessionId);

export const getSessionHistoryPreferenceCacheKey = (sessionId: string): string =>
  scopedPrivateCacheKey(SESSION_HISTORY_PREFERENCE_PREFIX, sessionId);

export const readCachedSessionsForMode = (mode: AppMode): ChatSession[] | null => {
  const cached = cacheManager.get<ChatSession[]>(getSessionListCacheKey(mode));
  if (cached === null) return null;
  return filterSessionsForMode(mode, cached);
};

export const writeCachedSessionsForMode = (mode: AppMode, sessions: ChatSession[]): void => {
  const modeSessions = filterSessionsForMode(mode, sessions);
  const currentSessionId = readRawCurrentSessionIdForMode(mode);
  if (currentSessionId && !modeSessions.some((session) => session.id === currentSessionId)) {
    writeCurrentSessionIdForMode(mode, null);
  }
  cacheManager.set(getSessionListCacheKey(mode), modeSessions);
};

export const updateCachedSessionsForMode = (
  mode: AppMode,
  updater: (sessions: ChatSession[]) => ChatSession[]
): ChatSession[] => {
  const current = readCachedSessionsForMode(mode) ?? [];
  const next = updater(current);
  writeCachedSessionsForMode(mode, next);
  return next;
};

const readRawCurrentSessionIdForMode = (mode: AppMode): string | null =>
  cacheManager.get<string | null>(getCurrentSessionIdCacheKey(mode));

const resolveCurrentSessionIdForMode = (
  mode: AppMode,
  options: { repairStale?: boolean } = {}
): string | null => {
  const currentSessionId = readRawCurrentSessionIdForMode(mode);
  if (!currentSessionId) return null;

  const modeSessions = readCachedSessionsForMode(mode);
  if (
    modeSessions !== null &&
    !modeSessions.some((session) => session.id === currentSessionId)
  ) {
    if (options.repairStale) {
      writeCurrentSessionIdForMode(mode, null);
    }
    return null;
  }

  return currentSessionId;
};

export const peekCurrentSessionIdForMode = (mode: AppMode): string | null =>
  resolveCurrentSessionIdForMode(mode);

export const readCurrentSessionIdForMode = (mode: AppMode): string | null =>
  resolveCurrentSessionIdForMode(mode, { repairStale: true });

export const writeCurrentSessionIdForMode = (mode: AppMode, sessionId: string | null): void => {
  cacheManager.set(getCurrentSessionIdCacheKey(mode), sessionId);
};

export const selectCurrentSessionIdForMode = (
  mode: AppMode,
  sessions: ChatSession[]
): string | null => {
  const cachedSessionId = readCurrentSessionIdForMode(mode);
  if (cachedSessionId && sessions.some((session) => session.id === cachedSessionId)) {
    return cachedSessionId;
  }
  return null;
};

export const writeSessionHasMoreForMode = (mode: AppMode, hasMore: boolean): void => {
  cacheManager.set(getSessionHasMoreCacheKey(mode), hasMore);
};

export const readSessionHasMoreForMode = (mode: AppMode): boolean | null =>
  cacheManager.get<boolean>(getSessionHasMoreCacheKey(mode));

export const groupSessionsByMode = (
  sessions: ChatSession[]
): Partial<Record<AppMode, ChatSession[]>> => {
  return sessions.reduce<Partial<Record<AppMode, ChatSession[]>>>((groups, session) => {
    const mode = getSessionMode(session);
    groups[mode] = [...(groups[mode] || []), session];
    return groups;
  }, {});
};

interface RemoveSessionFromScopedCachesOptions {
  exceptMode?: AppMode;
}

const removeSessionIdFromScopedCaches = (
  sessionId: string,
  options: RemoveSessionFromScopedCachesOptions = {}
): void => {
  const scopedListPrefix = scopedPrivateCachePrefix(SESSION_LIST_BY_MODE_PREFIX);
  const scopedCurrentSessionPrefix = scopedPrivateCachePrefix(CURRENT_SESSION_ID_BY_MODE_PREFIX);
  const removeAssociatedHistory = options.exceptMode === undefined;

  for (const [cacheKey, sessions] of cacheManager.getEntriesByPrefix<ChatSession[]>(
    scopedListPrefix
  )) {
    const cachedMode = cacheKey.slice(scopedListPrefix.length) as AppMode;
    if (cachedMode === options.exceptMode) continue;

    const nextSessions = sessions.filter((item) => item.id !== sessionId);
    if (nextSessions.length !== sessions.length) {
      cacheManager.set(cacheKey, nextSessions);
    }
  }

  for (const [cacheKey, currentSessionId] of cacheManager.getEntriesByPrefix<string | null>(
    scopedCurrentSessionPrefix
  )) {
    const cachedMode = cacheKey.slice(scopedCurrentSessionPrefix.length) as AppMode;
    if (cachedMode !== options.exceptMode && currentSessionId === sessionId) {
      cacheManager.set(cacheKey, null);
    }
  }

  if (removeAssociatedHistory) {
    cacheManager.remove(getSessionHistoryStatesCacheKey(sessionId));
    cacheManager.remove(getSessionHistoryPreferenceCacheKey(sessionId));
  }
};

export const upsertSessionInCaches = (session: ChatSession): void => {
  const normalizedSession = normalizeChatSession(session);
  const mode = getSessionMode(normalizedSession);
  removeSessionIdFromScopedCaches(normalizedSession.id, { exceptMode: mode });

  const upsert = (sessions: ChatSession[]): ChatSession[] => {
    const exists = sessions.some((item) => item.id === normalizedSession.id);
    if (!exists) {
      return [normalizedSession, ...sessions];
    }
    return sessions.map((item) => (item.id === normalizedSession.id ? normalizedSession : item));
  };

  updateCachedSessionsForMode(mode, upsert);
};

export const removeSessionFromCaches = (sessionId: string): void => {
  removeSessionIdFromScopedCaches(sessionId);
};

export const readCachedHistoryStates = (sessionId: string): SessionHistoryState[] | null =>
  cacheManager.get<SessionHistoryState[]>(getSessionHistoryStatesCacheKey(sessionId));

export const writeCachedHistoryStates = (
  sessionId: string,
  states: SessionHistoryState[]
): void => {
  cacheManager.set(getSessionHistoryStatesCacheKey(sessionId), states);
};

export const upsertCachedHistoryState = (
  sessionId: string,
  state: SessionHistoryState
): void => {
  const current = readCachedHistoryStates(sessionId) ?? [];
  const exists = current.some((item) => item.messageId === state.messageId);
  const next = exists
    ? current.map((item) => (item.messageId === state.messageId ? state : item))
    : [...current, state];
  writeCachedHistoryStates(sessionId, next);
};

export const readCachedHistoryPreference = (
  sessionId: string
): SessionHistoryPreference | null =>
  cacheManager.get<SessionHistoryPreference>(getSessionHistoryPreferenceCacheKey(sessionId));

export const writeCachedHistoryPreference = (
  sessionId: string,
  preference: SessionHistoryPreference
): void => {
  cacheManager.set(getSessionHistoryPreferenceCacheKey(sessionId), preference);
};

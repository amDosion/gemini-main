import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { AppMode, Attachment, ChatSession, Message, Role } from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { db } from '../services/db';
// cleanAttachmentsForDb removed — backend authoritative cleansing in
// routers/user/sessions.py upsert path (Sprint 2 PR-1, commit b0bd8ee)
import { useCacheStatus, CacheStatusInfo } from './useCacheStatus';
import { apiClient } from '../services/apiClient';
import { useCacheSubscription } from './useCacheSubscription';
import {
  getCurrentSessionIdCacheKey,
  getSessionListCacheKey,
  getSessionMode,
  peekCurrentSessionIdForMode,
  readCachedSessionsForMode,
  readCurrentSessionIdForMode,
  readSessionHasMoreForMode,
  removeSessionFromCaches,
  selectCurrentSessionIdForMode,
  filterSessionsForMode,
  updateCachedSessionsForMode,
  upsertSessionInCaches,
  writeCachedSessionsForMode,
  writeCurrentSessionIdForMode,
  writeSessionHasMoreForMode,
} from '../services/sessionCache';
import { normalizeChatSession } from '../services/sessionNormalizer';
import { getPrivateCacheUserScope } from '../services/privateCacheScope';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from '../services/privateCacheInvalidation';
import { usePrivateCacheScopeRevision } from './usePrivateCacheScopeRevision';
export { recoverSessionAttachmentUrl } from '../services/sessionNormalizer';

type UpdateSessionMessagesStrategy = 'replace' | 'merge-by-id';
const SESSION_PAGE_SIZE = 20;

interface UpdateSessionMessagesOptions {
  strategy?: UpdateSessionMessagesStrategy;
}

interface RefreshSessionsOptions {
  force?: boolean;
}

interface SessionsPageResponse {
  sessions: ChatSession[];
  total?: number | null;
  hasMore: boolean;
  nextCursor?: string | null;
}

const mergeMessagesById = (existingMessages: Message[], incomingMessages: Message[]): Message[] => {
  if (existingMessages.length === 0) {
    return incomingMessages;
  }

  if (incomingMessages.length === 0) {
    return existingMessages;
  }

  const incomingById = new Map(incomingMessages.map((message) => [message.id, message]));
  const existingIds = new Set(existingMessages.map((message) => message.id));
  const merged = existingMessages.map((message) => incomingById.get(message.id) || message);

  for (const message of incomingMessages) {
    if (!existingIds.has(message.id)) {
      merged.push(message);
    }
  }

  return merged;
};

const hasOutOfModeSessions = (mode: AppMode, sessions: ChatSession[]): boolean =>
  sessions.some((session) => getSessionMode(normalizeChatSession(session)) !== mode);

// Newest-first ordering, used everywhere session lists are materialized. Returns
// a new array; the input is never mutated.
const sortSessionsByCreatedAtDesc = (sessions: ChatSession[]): ChatSession[] =>
  [...sessions].sort((a, b) => b.createdAt - a.createdAt);

export const useSessions = (
  appMode: AppMode,
  initialData?: {
    sessions: ChatSession[];
    sessionsMode?: AppMode;
    sessionsHasMore?: boolean;
  }
) => {
  // ✅ 使用 ref 跟踪上一次的 appMode，用于检测 mode 切换
  const prevAppModeRef = useRef<AppMode>(appMode);
  const appModeRef = useRef<AppMode>(appMode);
  // The cache key value embeds the private-cache user scope internally, so it
  // MUST be a useMemo dependency: when the scope changes (user switch / private
  // cache reset) the key has to recompute so the subscription re-points to the
  // new user's partition. Removing it leaves the hook subscribed to the previous
  // scope's key. (Reverts an incorrect hooks-contexts-10 change.)
  const privateCacheUserScope = getPrivateCacheUserScope();

  const sessionListCacheKey = useMemo(
    () => getSessionListCacheKey(appMode),
    [appMode, privateCacheUserScope]
  );
  const currentSessionIdCacheKey = useMemo(
    () => getCurrentSessionIdCacheKey(appMode),
    [appMode, privateCacheUserScope]
  );

  // ✅ Sessions and currentSessionId use only per-mode cache partitions.
  const rawModeSessions = useCacheSubscription<ChatSession[]>(sessionListCacheKey, []);
  const sessions = useMemo(
    () => filterSessionsForMode(appMode, rawModeSessions),
    [appMode, rawModeSessions]
  );

  const rawCurrentSessionId = useCacheSubscription<string | null>(currentSessionIdCacheKey, null);
  const currentSessionId = useMemo(() => {
    if (!rawCurrentSessionId) {
      return null;
    }
    const guardedSessionId = peekCurrentSessionIdForMode(appMode);
    return guardedSessionId === rawCurrentSessionId ? rawCurrentSessionId : guardedSessionId;
  }, [appMode, rawCurrentSessionId, sessions]);

  // ✅ UI state remains as useState
  const [isLoading, setIsLoading] = useState(false);
  const [hasMoreSessions, setHasMoreSessions] = useState(false); // ✅ 是否还有更多会话
  const [isLoadingMore, setIsLoadingMore] = useState(false); // ✅ 是否正在加载更多
  // hooks-contexts-9: surface load-more failures so the UI can offer a retry
  // affordance instead of failing silently. hasMore stays true on error (see
  // loadMoreSessions catch), so the user can still trigger another attempt.
  const [loadMoreError, setLoadMoreError] = useState(false);

  // ✅ B-3 / C-3: race-guard. Per-mode data cache is global via sessionCache.
  const refreshSeqRef = useRef(0);
  const activeRefreshModeRef = useRef<AppMode | null>(null);
  const activeRefreshScopeRef = useRef<string | null>(null);
  const emptyModeRepairAttemptRef = useRef<Partial<Record<AppMode, boolean>>>({});

  // ✅ 使用 ref 标记是否已经从 initialData 初始化过，避免无限循环
  const isInitializedFromPropsRef = useRef(false);

  // ✅ 使用 ref 保存 cacheStatus 的方法，避免循环依赖
  const cacheStatusRef = useRef<{
    updateStatus: (fromCache: boolean, isStale: boolean, timestamp: number) => void;
  } | null>(null);

  // 缓存状态 Hook（不传递 refreshFn，避免循环依赖）
  const cacheStatus = useCacheStatus(sessionListCacheKey);

  const applyModeSessions = useCallback(
    (mode: AppMode, nextSessions: ChatSession[], fallbackHasMore = false) => {
      writeCachedSessionsForMode(mode, nextSessions);
      const nextSessionId = selectCurrentSessionIdForMode(mode, nextSessions);
      writeCurrentSessionIdForMode(mode, nextSessionId);

      const cachedHasMore = readSessionHasMoreForMode(mode);
      setHasMoreSessions(cachedHasMore ?? fallbackHasMore);
      setIsLoading(false);
    },
    []
  );

  useEffect(() => {
    appModeRef.current = appMode;
  }, [appMode]);

  const setCurrentSessionId = useCallback(
    (sessionId: string | null) => {
      if (sessionId) {
        const modeSessions = readCachedSessionsForMode(appMode) ?? sessions;
        const belongsToMode = modeSessions.some((session) => session.id === sessionId);
        if (!belongsToMode) {
          return;
        }
      }
      writeCurrentSessionIdForMode(appMode, sessionId);
    },
    [appMode, sessions]
  );

  const selectLatestSessionForMode = useCallback((mode: AppMode) => {
    const modeSessions = readCachedSessionsForMode(mode) ?? [];
    const latestSession = sortSessionsByCreatedAtDesc(modeSessions)[0];
    writeCurrentSessionIdForMode(mode, latestSession?.id ?? null);
    return Boolean(latestSession);
  }, []);

  useEffect(() => {
    if (sessions.length === 0) {
      return;
    }

    const hasValidCurrentSession =
      currentSessionId !== null && sessions.some((session) => session.id === currentSessionId);
    if (hasValidCurrentSession) {
      return;
    }

    const latestSession = sortSessionsByCreatedAtDesc(sessions)[0];
    if (latestSession) {
      writeCurrentSessionIdForMode(appMode, latestSession.id);
    }
  }, [appMode, currentSessionId, sessions]);

  const updateSessionsForCurrentMode = useCallback(
    (updater: (prev: ChatSession[]) => ChatSession[]) => {
      updateCachedSessionsForMode(appMode, updater);
    },
    [appMode]
  );

  const prepareSessions = useCallback((sourceSessions: ChatSession[]) => {
    const recoveredSessions = sourceSessions.map(normalizeChatSession);

    return sortSessionsByCreatedAtDesc(recoveredSessions);
  }, []);

  const fetchSessionsPage = useCallback(async (mode: AppMode, offset: number) => {
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(SESSION_PAGE_SIZE),
      mode,
    });
    return apiClient.get<SessionsPageResponse>(`/api/init/sessions/more?${params.toString()}`);
  }, []);

  const fetchFirstSessionsPage = useCallback(
    async (mode: AppMode) => {
      const result = (await fetchSessionsPage(mode, 0)) || {
        sessions: [],
        total: 0,
        hasMore: false,
        nextCursor: null,
      };
      const resultSessions = result.sessions || [];

      if (!hasOutOfModeSessions(mode, resultSessions)) {
        return result;
      }

      try {
        const fallbackSessions = await db.getSessions(mode);
        return {
          sessions: fallbackSessions,
          total: fallbackSessions.length,
          hasMore: false,
          nextCursor: null,
        };
      } catch {
        return {
          ...result,
          sessions: filterSessionsForMode(mode, resultSessions),
        };
      }
    },
    [fetchSessionsPage]
  );

  // ✅ 保存 cacheStatus 的方法到 ref
  useEffect(() => {
    cacheStatusRef.current = {
      updateStatus: cacheStatus.updateStatus,
    };
  }, [cacheStatus.updateStatus]);

  // 刷新会话列表（强制从后端获取，按当前 appMode 过滤）
  // ✅ B-3 / C-3: race-guard + per-mode cache
  const refreshSessions = useCallback(
    async (options: RefreshSessionsOptions = {}) => {
      const requestedMode = appMode;
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      const requestScope = lifecycleSnapshot.userScope;
      const force = Boolean(options.force);

      if (!force) {
        const cached = readCachedSessionsForMode(requestedMode);
        if (cached !== null) {
          applyModeSessions(requestedMode, cached);
          cacheStatusRef.current?.updateStatus(true, false, Date.now());
          return;
        }
      }

      if (
        activeRefreshModeRef.current === requestedMode &&
        activeRefreshScopeRef.current === requestScope
      ) {
        return;
      }
      activeRefreshModeRef.current = requestedMode;
      activeRefreshScopeRef.current = requestScope;

      // 单调 token: 旧 fetch resolve 时若 seq 不匹配则丢弃
      const seq = ++refreshSeqRef.current;

      try {
        setIsLoading(true);
        const result = await fetchFirstSessionsPage(requestedMode);

        // race-guard: mode 已切换或有更新的 fetch,丢弃本次结果
        if (
          seq !== refreshSeqRef.current ||
          requestedMode !== appModeRef.current ||
          !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
        ) {
          return;
        }

        const preparedSessions = prepareSessions(
          (result.sessions || []).map((session) => ({
            ...session,
            messages: session.messages || [],
          }))
        );
        writeSessionHasMoreForMode(requestedMode, !!result.hasMore);
        applyModeSessions(requestedMode, preparedSessions, !!result.hasMore);
        // ✅ 使用 ref 调用 updateStatus，避免依赖 cacheStatus
        cacheStatusRef.current?.updateStatus(false, false, Date.now());
      } finally {
        if (
          activeRefreshModeRef.current === requestedMode &&
          activeRefreshScopeRef.current === requestScope
        ) {
          activeRefreshModeRef.current = null;
          activeRefreshScopeRef.current = null;
        }
        // 仅当本次请求仍是最新时清 loading
        if (seq === refreshSeqRef.current && requestedMode === appModeRef.current) {
          setIsLoading(false);
        }
      }
    },
    [appMode, applyModeSessions, fetchFirstSessionsPage, prepareSessions]
  ); // ✅ 移除 cacheStatus 依赖

  // ✅ 滚动加载更多会话
  const isLoadingMoreRef = useRef(false);

  usePrivateCacheScopeRevision(() => {
    refreshSeqRef.current += 1;
    activeRefreshModeRef.current = null;
    activeRefreshScopeRef.current = null;
    emptyModeRepairAttemptRef.current = {};
    isLoadingMoreRef.current = false;
    setIsLoading(false);
    setHasMoreSessions(false);
    setIsLoadingMore(false);
    setLoadMoreError(false);
  });

  const loadMoreSessions = useCallback(async () => {
    if (isLoadingMoreRef.current || isLoadingMore || !hasMoreSessions) return;

    try {
      const requestedMode = appMode;
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      isLoadingMoreRef.current = true;
      setIsLoadingMore(true);
      // Clear any prior failure when a new attempt begins.
      setLoadMoreError(false);
      const offset = sessions.length;
      const result = await fetchSessionsPage(requestedMode, offset);

      if (!isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)) {
        return;
      }

      // 防御性兜底：分页响应可能缺失 sessions 字段（与 fetchFirstSessionsPage 同款保护）。
      // 缺失时按"空页"处理，避免 TypeError 被下方 catch 静默吞掉而使 hasMore 永久卡死。
      const pageSessions = result?.sessions || [];
      if (pageSessions.length > 0) {
        // ✅ 滚动加载的会话 messages 为空数组，需要准备
        const preparedSessions = prepareSessions(
          pageSessions.map((s) => ({
            ...s,
            messages: s.messages || [], // 确保 messages 存在
          }))
        );
        updateCachedSessionsForMode(requestedMode, (prev) => [...prev, ...preparedSessions]);
        writeSessionHasMoreForMode(requestedMode, result.hasMore);
        if (requestedMode === appModeRef.current) {
          setHasMoreSessions(result.hasMore);
        }
      } else {
        // ✅ 业务返回空数组 → 真没了
        writeSessionHasMoreForMode(requestedMode, false);
        if (requestedMode === appModeRef.current) {
          setHasMoreSessions(false);
        }
      }
    } catch (error) {
      // C-6 / hooks-contexts-9: On network error, intentionally keep hasMore=true so
      // the user can retry by scrolling again — pagination must not be permanently
      // closed by a transient failure. Surface the error via loadMoreError so the UI
      // can show a retry affordance, and log it so it is observable in devtools.
      console.error('[useSessions] loadMoreSessions failed:', error);
      setLoadMoreError(true);
    } finally {
      isLoadingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [
    appMode,
    sessions.length,
    hasMoreSessions,
    isLoadingMore,
    fetchSessionsPage,
    prepareSessions,
  ]);

  // ? 处理 initialData：恢复 Blob URL 和设置 currentSessionId
  // ?? 优先使用 initData.sessions，缺失时回退到 /sessions
  // ✅ Sprint 3 Phase B: 只在首次（isInitializedFromPropsRef 未置位）执行；
  // 之后 appMode 切换由专门的 mode-switch effect 处理，避免两个 effect 竞争 mode cache 写入
  useEffect(() => {
    if (isInitializedFromPropsRef.current) {
      return;
    }

    if (initialData?.sessions === undefined) {
      return;
    }

    isInitializedFromPropsRef.current = true;
    const declaredMode = initialData.sessionsMode;
    const preparedSessions = prepareSessions(initialData.sessions);

    if (declaredMode) {
      const declaredModeSessions = preparedSessions.filter(
        (session) => (session.mode || 'chat') === declaredMode
      );
      writeCachedSessionsForMode(declaredMode, declaredModeSessions);
      if (initialData.sessionsHasMore !== undefined) {
        writeSessionHasMoreForMode(declaredMode, initialData.sessionsHasMore);
      }

      if (declaredMode === appMode) {
        applyModeSessions(appMode, declaredModeSessions, initialData.sessionsHasMore ?? false);
        return;
      }

      const cachedCurrentModeSessions = readCachedSessionsForMode(appMode);
      if (cachedCurrentModeSessions !== null) {
        applyModeSessions(appMode, cachedCurrentModeSessions);
        return;
      }

      writeCurrentSessionIdForMode(appMode, null);
      setHasMoreSessions(false);
      refreshSessions();
      return;
    }

    const cachedCurrentModeSessions = readCachedSessionsForMode(appMode);
    if (cachedCurrentModeSessions !== null) {
      applyModeSessions(appMode, cachedCurrentModeSessions);
      return;
    }

    const provisionalSessions = preparedSessions.filter(
      (session) => (session.mode || 'chat') === appMode
    );
    if (provisionalSessions.length === 0) {
      writeCurrentSessionIdForMode(appMode, null);
      setHasMoreSessions(false);
      refreshSessions();
      return;
    }

    applyModeSessions(appMode, provisionalSessions, false);
    setHasMoreSessions(false);
    refreshSessions();
  }, [
    appMode,
    applyModeSessions,
    initialData?.sessions,
    initialData?.sessionsMode,
    initialData?.sessionsHasMore,
    prepareSessions,
    refreshSessions,
  ]);

  // 后端 PR-1 (b0bd8ee) 在 upsert 时权威清洗 blob/base64 attachments，前端无需
  // 预清洗，直接持久化原始 session。
  const prepareSessionForDb = useCallback((session: ChatSession): ChatSession => session, []);

  // Save session to database (with error handling for offline mode)
  // 使用 cachedDb 实现写穿透
  const saveSessionToDb = useCallback(
    async (session: ChatSession) => {
      try {
        await db.saveSession(prepareSessionForDb(session));
      } catch (error) {
        // 组件卸载 / 请求取消导致的失败是预期的（React Strict Mode 双重渲染或卸载），静默忽略
        if (error instanceof Error && error.message.includes('component unmount')) {
          return;
        }
        // 其他失败（后端不可用、写入异常等）会导致会话无法持久化。
        // Sessions 仍在内存中工作，但持久化丢失必须可观测，不能静默吞掉。
        console.error('[useSessions] Failed to persist session to database:', error);
      }
    },
    [prepareSessionForDb]
  );

  // Delete session from database
  // 使用 cachedDb 实现删除并失效缓存
  const deleteSessionFromDb = useCallback(async (sessionId: string) => {
    await db.deleteSession(sessionId);
  }, []);

  const createNewSession = useCallback(
    (personaId?: string) => {
      const newSession: ChatSession = {
        id: uuidv4(),
        title: 'New Chat',
        messages: [],
        createdAt: Date.now(),
        mode: appMode, // ✅ Sprint 3 Phase B: per-mode 隔离——使用当前 appMode（不再硬编码 'chat'）
        personaId: personaId, // 保存当前激活的 persona
      };

      updateSessionsForCurrentMode((prev) => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);

      // Save to database (async, non-blocking)
      saveSessionToDb(newSession);

      return newSession;
    },
    [appMode, saveSessionToDb, updateSessionsForCurrentMode, setCurrentSessionId]
  );

  // ✅ Sprint 3 Phase B: 监听 appMode 变化——切 mode 时重置 currentSessionId 并按新 mode 重拉列表
  // 首次渲染（prevAppModeRef.current === appMode）跳过，由 initialSessions effect 处理首屏
  //
  // ref-mirror refreshSessions：useEffect deps 仅含 appMode；refreshSessions useCallback
  // 引用变化（含 appMode 自身导致的 rebuild）不再触发重 fire（修复同类 mount 重复 fetch）
  const refreshSessionsRef = useRef(refreshSessions);
  refreshSessionsRef.current = refreshSessions;
  useEffect(() => {
    if (prevAppModeRef.current === appMode) {
      return;
    }
    prevAppModeRef.current = appMode;
    const cachedSessions = readCachedSessionsForMode(appMode);
    if (cachedSessions !== null) {
      applyModeSessions(appMode, cachedSessions);
      return;
    }
    writeCurrentSessionIdForMode(appMode, null);
    refreshSessionsRef.current();
  }, [appMode, applyModeSessions]);

  useEffect(() => {
    if (!isInitializedFromPropsRef.current) {
      return;
    }

    if (sessions.length > 0) {
      emptyModeRepairAttemptRef.current[appMode] = false;
      return;
    }

    if (currentSessionId || isLoading) {
      return;
    }

    const repairTimer = globalThis.setTimeout(() => {
      const cachedSessions = readCachedSessionsForMode(appMode);
      const cachedCurrentSessionId = readCurrentSessionIdForMode(appMode);

      if (cachedSessions !== null || cachedCurrentSessionId) {
        return;
      }

      if (
        activeRefreshModeRef.current === appMode &&
        activeRefreshScopeRef.current === getPrivateCacheUserScope()
      ) {
        return;
      }

      if (emptyModeRepairAttemptRef.current[appMode]) {
        return;
      }

      emptyModeRepairAttemptRef.current[appMode] = true;
      refreshSessionsRef.current();
    }, 0);

    return () => globalThis.clearTimeout(repairTimer);
  }, [appMode, currentSessionId, isLoading, sessions.length]);

  const updateSessionMessages = useCallback(
    (sessionId: string, newMessages: Message[], options?: UpdateSessionMessagesOptions) => {
      const strategy = options?.strategy || 'replace';
      let movedSession: ChatSession | null = null;

      updateSessionsForCurrentMode((prev) => {
        const updated = prev.map((s) => {
          if (s.id === sessionId) {
            const nextMessages =
              strategy === 'merge-by-id'
                ? mergeMessagesById(s.messages || [], newMessages)
                : newMessages;
            let title = s.title;
            // Auto-generate title from first user message
            if (s.title === 'New Chat' && nextMessages.length > 0) {
              const firstUserMsg = nextMessages.find((m) => m.role === Role.USER);
              if (firstUserMsg) {
                title =
                  firstUserMsg.content.slice(0, 30) +
                  (firstUserMsg.content.length > 30 ? '...' : '');
              }
            }

            // Determine mode from the last message that has a mode property, fallback to existing or 'chat'
            const lastMsgWithMode = [...nextMessages].reverse().find((m) => m.mode);
            const currentMode = lastMsgWithMode?.mode || s.mode || 'chat';

            // 直接传 raw nextMessages — 后端 PR-1 (b0bd8ee) 在 upsert 时
            // 权威清洗 blob/base64 URL,前端无需根据 mode 做条件预清洗。
            const updatedSession = { ...s, title, messages: nextMessages, mode: currentMode };

            // Save to database (async, non-blocking)
            saveSessionToDb(updatedSession);

            if (currentMode !== appMode) {
              movedSession = updatedSession;
            }

            return updatedSession;
          }
          return s;
        });

        return updated;
      });

      if (movedSession) {
        upsertSessionInCaches(movedSession);
      }
    },
    [appMode, saveSessionToDb, updateSessionsForCurrentMode]
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      const currentModeSessions = readCachedSessionsForMode(appMode) ?? sessions;
      removeSessionFromCaches(sessionId);
      const remainingSessions =
        readCachedSessionsForMode(appMode) ??
        currentModeSessions.filter((session) => session.id !== sessionId);

      // If deleting current session, switch to another or clear
      if (currentSessionId === sessionId) {
        setCurrentSessionId(remainingSessions.length > 0 ? remainingSessions[0].id : null);
      }

      // Delete from database
      await deleteSessionFromDb(sessionId);
    },
    [appMode, currentSessionId, deleteSessionFromDb, sessions, setCurrentSessionId]
  );

  const updateSessionPersona = useCallback(
    (sessionId: string, personaId: string) => {
      updateSessionsForCurrentMode((prev) => {
        const updated = prev.map((s) => {
          if (s.id === sessionId) {
            const updatedSession = { ...s, personaId };

            // Save to database (async, non-blocking)
            saveSessionToDb(updatedSession);

            return updatedSession;
          }
          return s;
        });

        return updated;
      });
    },
    [saveSessionToDb, updateSessionsForCurrentMode]
  );

  const updateSessionTitle = useCallback(
    (sessionId: string, newTitle: string) => {
      updateSessionsForCurrentMode((prev) => {
        const updated = prev.map((s) => {
          if (s.id === sessionId) {
            const updatedSession = { ...s, title: newTitle };

            // Save to database (async, non-blocking)
            saveSessionToDb(updatedSession);

            return updatedSession;
          }
          return s;
        });

        return updated;
      });
    },
    [saveSessionToDb, updateSessionsForCurrentMode]
  );

  const getSession = useCallback(
    (id: string) => {
      return sessions.find((s) => s.id === id);
    },
    [sessions]
  );

  return {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    selectLatestSessionForMode,
    createNewSession,
    updateSessionMessages,
    updateSessionPersona,
    updateSessionTitle,
    deleteSession,
    getSession,
    isLoading,
    // 缓存相关
    cacheStatus,
    refreshSessions,
    // ✅ 滚动加载相关
    hasMoreSessions,
    isLoadingMore,
    loadMoreSessions,
    // hooks-contexts-9: true when the last loadMoreSessions attempt failed; the
    // UI can use this to render a retry affordance (hasMore remains true).
    loadMoreError,
  };
};

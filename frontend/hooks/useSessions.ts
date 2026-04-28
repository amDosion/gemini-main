import { useState, useEffect, useCallback, useRef } from 'react';
import { AppMode, ChatSession, Message, Role } from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { db } from '../services/db';
// cleanAttachmentsForDb removed — backend authoritative cleansing in
// routers/user/sessions.py upsert path (Sprint 2 PR-1, commit b0bd8ee)
import { useCacheStatus, CacheStatusInfo } from './useCacheStatus';
import { apiClient } from '../services/apiClient';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import { useCacheSubscription, useCacheUpdater } from './useCacheSubscription';

type UpdateSessionMessagesStrategy = 'replace' | 'merge-by-id';

interface UpdateSessionMessagesOptions {
  strategy?: UpdateSessionMessagesStrategy;
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

// Set long TTL for sessions - they are long-lived data
cacheManager.setTTL(CACHE_DOMAINS.SESSIONS, 30 * 60 * 1000); // 30 minutes
cacheManager.setTTL(CACHE_DOMAINS.CURRENT_SESSION_ID, 30 * 60 * 1000); // 30 minutes

export const useSessions = (
  appMode: AppMode,
  initialData?: {
    sessions: ChatSession[];
    sessionsHasMore?: boolean;
  }
) => {
  // ✅ 使用 initialData 初始化状态（如果提供）
  // ✅ Sprint 3 Phase B: per-mode 隔离——initialData.sessions 来自 /api/init 全量列表，
  // 这里按当前 appMode 过滤，作为首屏；切 mode 后由 effect 重新调用 db.getSessions(mode)
  const initialSessions = initialData?.sessions
    ? initialData.sessions.filter((s) => (s.mode || 'chat') === appMode)
    : undefined;
  // ✅ 使用 ref 跟踪上一次的 appMode，用于检测 mode 切换
  const prevAppModeRef = useRef<AppMode>(appMode);

  // ✅ Sessions and currentSessionId now use CacheManager
  const sessions = useCacheSubscription<ChatSession[]>(CACHE_DOMAINS.SESSIONS, []);
  const { set: setSessions, update: updateSessions } = useCacheUpdater<ChatSession[]>(
    CACHE_DOMAINS.SESSIONS,
    []
  );

  const currentSessionId = useCacheSubscription<string | null>(
    CACHE_DOMAINS.CURRENT_SESSION_ID,
    null
  );
  const { set: setCurrentSessionId } = useCacheUpdater<string | null>(
    CACHE_DOMAINS.CURRENT_SESSION_ID,
    null
  );

  // ✅ UI state remains as useState
  const [isLoading, setIsLoading] = useState(false);
  const [hasMoreSessions, setHasMoreSessions] = useState(false); // ✅ 是否还有更多会话
  const [isLoadingMore, setIsLoadingMore] = useState(false); // ✅ 是否正在加载更多

  // ✅ 使用 ref 标记是否已经从 initialData 初始化过，避免无限循环
  const isInitializedFromPropsRef = useRef(false);

  // ✅ 使用 ref 保存 cacheStatus 的方法，避免循环依赖
  const cacheStatusRef = useRef<{
    updateStatus: (fromCache: boolean, isStale: boolean, timestamp: number) => void;
  } | null>(null);

  // 缓存状态 Hook（不传递 refreshFn，避免循环依赖）
  const cacheStatus = useCacheStatus('sessions');

  const prepareSessions = useCallback((sourceSessions: ChatSession[]) => {
    const recoveredSessions = sourceSessions.map((session) => {
      if (!session.messages || session.messages.length === 0) {
        return session;
      }

      const recoveredMessages = session.messages.map((message) => {
        if (!message.attachments || message.attachments.length === 0) {
          return message;
        }

        const recoveredAttachments = message.attachments.map((att) => {
          // 检查 url 是否是 Blob URL（页面刷新后已失效）
          if (att.url && att.url.startsWith('blob:')) {
            // 如果有 tempUrl（云存储 URL），使用它替代失效的 Blob URL
            if (att.tempUrl && att.tempUrl.startsWith('http')) {
              return {
                ...att,
                url: att.tempUrl, // 替换为云存储 URL
                uploadStatus: 'completed' as const,
              };
            } else {
              // 没有有效的 tempUrl，保持原状（可能需要重新生成）
              return att;
            }
          }

          // 其他类型的 URL（Base64, HTTP）不需要恢复
          return att;
        });

        return {
          ...message,
          attachments: recoveredAttachments,
        };
      });

      return {
        ...session,
        messages: recoveredMessages,
      };
    });

    return [...recoveredSessions].sort((a, b) => b.createdAt - a.createdAt);
  }, []);

  // ✅ 保存 cacheStatus 的方法到 ref
  useEffect(() => {
    cacheStatusRef.current = {
      updateStatus: cacheStatus.updateStatus,
    };
  }, [cacheStatus.updateStatus]);

  // 刷新会话列表（强制从后端获取，按当前 appMode 过滤）
  const refreshSessions = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await db.getSessions(appMode);
      const preparedSessions = prepareSessions(result);
      setSessions(preparedSessions);
      // Use updater to read current value for conditional logic
      const currentId = cacheManager.get<string | null>(CACHE_DOMAINS.CURRENT_SESSION_ID);
      if (preparedSessions.length > 0) {
        if (currentId === null) {
          setCurrentSessionId(preparedSessions[0].id);
        }
      } else {
        setCurrentSessionId(null);
      }
      // ✅ 使用 ref 调用 updateStatus，避免依赖 cacheStatus
      // db.getSessions() 在数组对象上额外挂了 cache 元数据（JS 允许 array.foo = bar），
      // 但 TS 声明的返回类型只到 ChatSession[]——这里 cast 仅修复类型，不改运行时。
      const cacheMeta = result as ChatSession[] & {
        fromCache?: boolean;
        isStale?: boolean;
        timestamp?: number;
      };
      cacheStatusRef.current?.updateStatus(
        cacheMeta.fromCache,
        cacheMeta.isStale,
        cacheMeta.timestamp
      );
    } finally {
      setIsLoading(false);
    }
  }, [appMode, prepareSessions, setSessions, setCurrentSessionId]); // ✅ 移除 cacheStatus 依赖

  // ✅ 从 initialData 中获取 sessionsHasMore
  useEffect(() => {
    if (initialData?.sessionsHasMore !== undefined) {
      setHasMoreSessions(initialData.sessionsHasMore);
    }
  }, [initialData?.sessionsHasMore]);

  // ✅ 滚动加载更多会话
  const isLoadingMoreRef = useRef(false);
  const loadMoreSessions = useCallback(async () => {
    if (isLoadingMoreRef.current || isLoadingMore || !hasMoreSessions) return;

    try {
      isLoadingMoreRef.current = true;
      setIsLoadingMore(true);
      const offset = sessions.length;
      const result = await apiClient.get<{
        sessions: ChatSession[];
        total: number;
        hasMore: boolean;
      }>(`/api/init/sessions/more?offset=${offset}&limit=20`);

      if (result.sessions.length > 0) {
        // ✅ 滚动加载的会话 messages 为空数组，需要准备
        const preparedSessions = prepareSessions(
          result.sessions.map((s) => ({
            ...s,
            messages: s.messages || [], // 确保 messages 存在
          }))
        );
        updateSessions((prev) => [...prev, ...preparedSessions]);
        setHasMoreSessions(result.hasMore);
      } else {
        setHasMoreSessions(false);
      }
    } catch (error) {
      setHasMoreSessions(false);
    } finally {
      isLoadingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [sessions.length, hasMoreSessions, isLoadingMore, prepareSessions, updateSessions]);

  // ? 处理 initialData：恢复 Blob URL 和设置 currentSessionId
  // ?? 优先使用 initData.sessions，缺失时回退到 /sessions
  // ✅ Sprint 3 Phase B: 只在首次（isInitializedFromPropsRef 未置位）执行；
  // 之后 appMode 切换由专门的 mode-switch effect 处理，避免两个 effect 竞争 setSessions
  useEffect(() => {
    if (isInitializedFromPropsRef.current) {
      return;
    }

    if (initialSessions === undefined) {
      setSessions([]);
      setCurrentSessionId(null);
      return;
    }

    if (initialSessions.length > 0) {
      // 标记为已初始化
      isInitializedFromPropsRef.current = true;

      const preparedSessions = prepareSessions(initialSessions);
      setSessions(preparedSessions);

      // Restore the most recent session if available
      if (preparedSessions.length > 0) {
        const currentId = cacheManager.get<string | null>(CACHE_DOMAINS.CURRENT_SESSION_ID);
        if (currentId === null) {
          setCurrentSessionId(preparedSessions[0].id);
        }
      } else {
        setCurrentSessionId(null);
      }
      return;
    }

    // 初始会话为空时，回退到 sessions API
    isInitializedFromPropsRef.current = true;
    refreshSessions();
  }, [initialSessions, prepareSessions]); // ✅ 移除 refreshSessions 依赖，避免无限循环

  const prepareSessionForDb = useCallback((session: ChatSession): ChatSession => {
    if (!session.messages || session.messages.length === 0) {
      return session;
    }

    const cleanedMessages = session.messages.map((message) => {
      if (!message.attachments || message.attachments.length === 0) {
        return message;
      }

      // 直接传原始 attachments,后端 PR-1 在 upsert 时权威清洗 blob/base64
      return message;
    });

    return {
      ...session,
      messages: cleanedMessages,
    };
  }, []);

  // Save session to database (with error handling for offline mode)
  // 使用 cachedDb 实现写穿透
  const saveSessionToDb = useCallback(
    async (session: ChatSession) => {
      try {
        await db.saveSession(prepareSessionForDb(session));
      } catch (error) {
        // Silently fail - 可能是后端不可用或组件卸载导致请求取消
        // Sessions 仍然会在内存中工作，只是不会持久化
        if (error instanceof Error && error.message.includes('component unmount')) {
          // React Strict Mode 双重渲染或组件卸载导致，忽略
          return;
        }
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

      updateSessions((prev) => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);

      // Save to database (async, non-blocking)
      saveSessionToDb(newSession);

      return newSession;
    },
    [appMode, saveSessionToDb, updateSessions, setCurrentSessionId]
  );

  // ✅ Sprint 3 Phase B: 监听 appMode 变化——切 mode 时重置 currentSessionId 并按新 mode 重拉列表
  // 首次渲染（prevAppModeRef.current === appMode）跳过，由 initialSessions effect 处理首屏
  useEffect(() => {
    if (prevAppModeRef.current === appMode) {
      return;
    }
    prevAppModeRef.current = appMode;
    // 立刻清空 currentSessionId，避免短暂显示其它 mode 的标题
    setCurrentSessionId(null);
    // 按新 mode 重拉列表；refreshSessions 内部会在列表非空时设置最近一条为 current
    refreshSessions();
  }, [appMode, refreshSessions, setCurrentSessionId]);

  const updateSessionMessages = useCallback(
    (sessionId: string, newMessages: Message[], options?: UpdateSessionMessagesOptions) => {
      const strategy = options?.strategy || 'replace';

      updateSessions((prev) => {
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

            return updatedSession;
          }
          return s;
        });

        return updated;
      });
    },
    [saveSessionToDb, updateSessions]
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      // Remove from memory and get remaining sessions
      let remainingSessions: ChatSession[] = [];
      updateSessions((prev) => {
        remainingSessions = prev.filter((s) => s.id !== sessionId);
        return remainingSessions;
      });

      // If deleting current session, switch to another or clear
      if (currentSessionId === sessionId) {
        setCurrentSessionId(remainingSessions.length > 0 ? remainingSessions[0].id : null);
      }

      // Delete from database
      await deleteSessionFromDb(sessionId);
    },
    [currentSessionId, deleteSessionFromDb, updateSessions, setCurrentSessionId]
  );

  const updateSessionPersona = useCallback(
    (sessionId: string, personaId: string) => {
      updateSessions((prev) => {
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
    [saveSessionToDb, updateSessions]
  );

  const updateSessionTitle = useCallback(
    (sessionId: string, newTitle: string) => {
      updateSessions((prev) => {
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
    [saveSessionToDb, updateSessions]
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
  };
};

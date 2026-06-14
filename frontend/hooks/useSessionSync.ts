import { useCallback, useEffect, useRef } from 'react';
import { ChatSession, Message, ModelConfig, AppMode } from '../types/types';
import { llmService } from '../services/llmService';
import { apiClient } from '../services/apiClient';
import { skipModeRestoreFlag } from '../contexts/SessionContext';
import { upsertSessionInCaches } from '../services/sessionCache';
import { normalizeChatSession } from '../services/sessionNormalizer';
import { setModeMessages } from './modeMessageStore';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from '../services/privateCacheInvalidation';
import { isAppMode } from '../utils/appModes';

interface UseSessionSyncProps {
  currentSessionId: string | null;
  sessions: ChatSession[];
  activeModelConfig?: ModelConfig;
  setAppMode: (mode: AppMode) => void;
}

const deriveMode = (storedMode: AppMode | undefined, msgs: Message[]): AppMode => {
  if (isAppMode(storedMode)) return storedMode;
  return [...msgs].reverse().map((m) => m.mode).find(isAppMode) ?? 'chat';
};

/**
 * 会话同步 Hook
 * 处理会话切换时的消息加载和模式恢复
 *
 * ✅ 支持按需加载消息：如果 session.messages 为空，调用 /api/sessions/{session_id} 加载完整消息（不能分页）
 */
export const useSessionSync = ({
  currentSessionId,
  sessions,
  activeModelConfig,
  setAppMode,
}: UseSessionSyncProps) => {
  const prevSessionIdRef = useRef<string | null>(null);
  const prevModelConfigRef = useRef<typeof activeModelConfig>(undefined);
  const sessionsRef = useRef(sessions);
  const currentSessionIdRef = useRef<string | null>(currentSessionId);
  const activeModelConfigRef = useRef<typeof activeModelConfig>(activeModelConfig);
  const loadingMessagesRef = useRef<Set<string>>(new Set()); // ✅ 跟踪正在加载的会话
  const loadingSessionIdRef = useRef<string | null>(null);
  const fetchRequestSeqRef = useRef(0);
  const fetchAbortControllerRef = useRef<AbortController | null>(null);
  // ✅ B-9: 最后一次成功 fetch 过 messages 的 sessionId,避免首帧抖动重复 fetch
  const lastFetchedSessionRef = useRef<string | null>(null);

  // 将 props 镜像到对应 ref，合并为单个 effect 减少每次渲染调度的 effect 数量。
  useEffect(() => {
    sessionsRef.current = sessions;
    currentSessionIdRef.current = currentSessionId;
    activeModelConfigRef.current = activeModelConfig;
  }, [sessions, currentSessionId, activeModelConfig]);

  const cancelInFlightFetch = useCallback(() => {
    const controller = fetchAbortControllerRef.current;
    if (controller) {
      controller.abort();
      fetchAbortControllerRef.current = null;
    }

    const loadingSessionId = loadingSessionIdRef.current;
    if (loadingSessionId) {
      loadingMessagesRef.current.delete(loadingSessionId);
      loadingSessionIdRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      // 不 abort fetch on unmount：StrictMode 双 mount 触发 abort → re-mount 重新 fetch
      // 在 Network tab 看到 (canceled)。fetch 内部已 sequence check（fetchRequestSeqRef）
      // 防 stale result 覆盖；cancelInFlightFetch 仍在 user-action session switch 时调用。
      loadingMessagesRef.current.clear();
    };
  }, []);

  useEffect(() => {
    // 恢复会话模式：优先使用存储模式，否则回退到最后一条带 mode 的消息，再退回 'chat'。
    // gen 模式切换时通过 skipModeRestoreFlag 跳过本轮恢复。
    const restoreMode = (storedMode: AppMode | undefined, msgs: Message[]) => {
      if (skipModeRestoreFlag.current) {
        skipModeRestoreFlag.current = false;
        return;
      }
      setAppMode(deriveMode(storedMode, msgs));
    };

    if (currentSessionId) {
      // Use sessionsRef.current instead of getSession to avoid unnecessary triggers
      const session = sessionsRef.current.find((s) => s.id === currentSessionId);
      if (session) {
        // Only load messages when session actually switches
        const isSessionSwitch = prevSessionIdRef.current !== currentSessionId;
        if (isSessionSwitch) {
          if (session.messages && session.messages.length > 0) {
            cancelInFlightFetch();

            // ✅ 会话已有消息（例如已缓存的显式选择会话），直接使用
            setModeMessages(deriveMode(session.mode, session.messages), session.messages);

            // 检查是否跳过 mode 恢复（gen 模式下的会话切换）
            restoreMode(session.mode, session.messages);

            // Update llmService
            const latestModelConfig = activeModelConfigRef.current;
            if (latestModelConfig) {
              llmService.startNewChat(session.messages, latestModelConfig);
              prevModelConfigRef.current = latestModelConfig;
            }
          } else {
            // ✅ 会话没有消息，按需加载（完整消息，不能分页）
            // ✅ B-9: 同一 sessionId 已 fetch 过则跳过,避免首帧抖动重复请求
            if (lastFetchedSessionRef.current === currentSessionId) {
              prevSessionIdRef.current = currentSessionId;
              return;
            }
            if (!loadingMessagesRef.current.has(currentSessionId)) {
              fetchRequestSeqRef.current += 1;
              const requestSeq = fetchRequestSeqRef.current;
              cancelInFlightFetch();
              const abortController = new AbortController();
              const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
              fetchAbortControllerRef.current = abortController;
              loadingMessagesRef.current.add(currentSessionId);
              loadingSessionIdRef.current = currentSessionId;

              apiClient
                .get<ChatSession>(`/api/sessions/${currentSessionId}`, {
                  signal: abortController.signal,
                })
                .then((rawFullSession) => {
                  const isStaleRequest =
                    requestSeq !== fetchRequestSeqRef.current ||
                    currentSessionIdRef.current !== currentSessionId ||
                    !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot);
                  if (isStaleRequest) {
                    return;
                  }

                  const fullSession = normalizeChatSession(rawFullSession);

                  // ✅ 更新 sessionsRef 中的会话数据
                  const sessionIndex = sessionsRef.current.findIndex(
                    (s) => s.id === currentSessionId
                  );
                  if (sessionIndex !== -1) {
                    // Immutable update instead of direct mutation
                    const updatedSessions = [...sessionsRef.current];
                    updatedSessions[sessionIndex] = fullSession;
                    sessionsRef.current = updatedSessions;
                  }
                  upsertSessionInCaches(fullSession);

                  // ✅ 设置消息和模式
                  const fullMessages = fullSession.messages || [];
                  setModeMessages(deriveMode(fullSession.mode, fullMessages), fullMessages);

                  // 检查是否跳过 mode 恢复
                  restoreMode(fullSession.mode, fullMessages);

                  // Update llmService
                  const latestModelConfig = activeModelConfigRef.current;
                  if (latestModelConfig) {
                    llmService.startNewChat(fullMessages, latestModelConfig);
                    prevModelConfigRef.current = latestModelConfig;
                  }
                  // ✅ B-9: 标记此 sessionId 已 fetch 过
                  lastFetchedSessionRef.current = currentSessionId;
                })
                .catch((err) => {
                  const isAbortError = err?.name === 'AbortError' || abortController.signal.aborted;
                  const isStaleRequest =
                    requestSeq !== fetchRequestSeqRef.current ||
                    currentSessionIdRef.current !== currentSessionId ||
                    !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot);
                  if (isAbortError || isStaleRequest) {
                    return;
                  }

                  setModeMessages(deriveMode(session.mode, session.messages), []);
                })
                .finally(() => {
                  loadingMessagesRef.current.delete(currentSessionId);
                  if (loadingSessionIdRef.current === currentSessionId) {
                    loadingSessionIdRef.current = null;
                  }
                  if (fetchAbortControllerRef.current === abortController) {
                    fetchAbortControllerRef.current = null;
                  }
                });
            }
          }

          prevSessionIdRef.current = currentSessionId;
        }

        // Only update llmService when model actually changes (not during session switch)
        const isModelSwitch = prevModelConfigRef.current?.id !== activeModelConfig?.id;
        const latestModelConfig = activeModelConfigRef.current;
        if (!isSessionSwitch && isModelSwitch && latestModelConfig) {
          llmService.startNewChat(session.messages || [], latestModelConfig);
          prevModelConfigRef.current = latestModelConfig;
        }
      }
    }
  }, [activeModelConfig, cancelInFlightFetch, currentSessionId, sessions, setAppMode]);
};

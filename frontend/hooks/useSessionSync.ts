
import { useCallback, useEffect, useRef, Dispatch, SetStateAction } from 'react';
import { ChatSession, Message, ModelConfig, AppMode } from '../types/types';
import { llmService } from '../services/llmService';
import { apiClient } from '../services/apiClient';
import { skipModeRestoreFlag } from '../contexts/SessionContext';

interface UseSessionSyncProps {
  currentSessionId: string | null;
  sessions: ChatSession[];
  activeModelConfig?: ModelConfig;
  setMessages: (messages: Message[]) => void;
  setAppMode: Dispatch<SetStateAction<AppMode>>;
}

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
  setMessages,
  setAppMode
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

  // Sync sessions to ref
  useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    activeModelConfigRef.current = activeModelConfig;
  }, [activeModelConfig]);

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
      cancelInFlightFetch();
      loadingMessagesRef.current.clear();
    };
  }, [cancelInFlightFetch]);

  useEffect(() => {
    if (currentSessionId) {
      // Use sessionsRef.current instead of getSession to avoid unnecessary triggers
      const session = sessionsRef.current.find(s => s.id === currentSessionId);
      if (session) {
        // Only load messages when session actually switches
        const isSessionSwitch = prevSessionIdRef.current !== currentSessionId;
        if (isSessionSwitch) {
          if (session.messages && session.messages.length > 0) {
            cancelInFlightFetch();

            // ✅ 会话已有消息（第一个会话或已缓存的），直接使用
            setMessages(session.messages);

            // 检查是否跳过 mode 恢复（gen 模式下的会话切换）
            if (skipModeRestoreFlag.current) {
              skipModeRestoreFlag.current = false;
            } else {
              const storedMode = session.mode;
              if (storedMode) {
                setAppMode(storedMode as AppMode);
              } else {
                const lastMsg = [...session.messages].reverse().find(m => m.mode);
                const restoredMode = lastMsg?.mode || 'chat';
                setAppMode(restoredMode as AppMode);
              }
            }

            // Update llmService
            const latestModelConfig = activeModelConfigRef.current;
            if (latestModelConfig) {
              llmService.startNewChat(session.messages, latestModelConfig);
              prevModelConfigRef.current = latestModelConfig;
            }
          } else {
            // ✅ 会话没有消息，按需加载（完整消息，不能分页）
            if (!loadingMessagesRef.current.has(currentSessionId)) {
              fetchRequestSeqRef.current += 1;
              const requestSeq = fetchRequestSeqRef.current;
              cancelInFlightFetch();
              const abortController = new AbortController();
              fetchAbortControllerRef.current = abortController;
              loadingMessagesRef.current.add(currentSessionId);
              loadingSessionIdRef.current = currentSessionId;

              apiClient.get<ChatSession>(`/api/sessions/${currentSessionId}`, { signal: abortController.signal })
                .then(fullSession => {
                  const isStaleRequest =
                    requestSeq !== fetchRequestSeqRef.current ||
                    currentSessionIdRef.current !== currentSessionId;
                  if (isStaleRequest) {
                    return;
                  }

                  // ✅ 更新 sessionsRef 中的会话数据
                  const sessionIndex = sessionsRef.current.findIndex(s => s.id === currentSessionId);
                  if (sessionIndex !== -1) {
                    sessionsRef.current[sessionIndex] = fullSession;
                  }
                  
                  // ✅ 设置消息和模式
                  const fullMessages = fullSession.messages || [];
                  setMessages(fullMessages);
                  
                  // 检查是否跳过 mode 恢复
                  if (skipModeRestoreFlag.current) {
                    skipModeRestoreFlag.current = false;
                  } else {
                    const storedMode = fullSession.mode;
                    if (storedMode) {
                      setAppMode(storedMode as AppMode);
                    } else {
                      const lastMsg = [...fullMessages].reverse().find(m => m.mode);
                      const restoredMode = lastMsg?.mode || 'chat';
                      setAppMode(restoredMode as AppMode);
                    }
                  }

                  // Update llmService
                  const latestModelConfig = activeModelConfigRef.current;
                  if (latestModelConfig) {
                    llmService.startNewChat(fullMessages, latestModelConfig);
                    prevModelConfigRef.current = latestModelConfig;
                  }
                })
                .catch(err => {
                  const isAbortError =
                    err?.name === 'AbortError' ||
                    abortController.signal.aborted;
                  const isStaleRequest =
                    requestSeq !== fetchRequestSeqRef.current ||
                    currentSessionIdRef.current !== currentSessionId;
                  if (isAbortError || isStaleRequest) {
                    return;
                  }

                  console.error('[useSessionSync] 加载会话消息失败:', err);
                  setMessages([]);
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
  }, [activeModelConfig, cancelInFlightFetch, currentSessionId, setMessages, setAppMode]);
};

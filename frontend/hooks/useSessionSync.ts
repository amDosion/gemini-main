
import { useEffect, useRef, Dispatch, SetStateAction } from 'react';
import { ChatSession, Message, ModelConfig, AppMode } from '../types/types';
import { llmService } from '../services/llmService';
import { apiClient } from '../services/apiClient';

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
  const loadingMessagesRef = useRef<Set<string>>(new Set()); // ✅ 跟踪正在加载的会话

  // Sync sessions to ref
  useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  useEffect(() => {
    if (currentSessionId) {
      // Use sessionsRef.current instead of getSession to avoid unnecessary triggers
      const session = sessionsRef.current.find(s => s.id === currentSessionId);
      if (session) {
        // Only load messages when session actually switches
        const isSessionSwitch = prevSessionIdRef.current !== currentSessionId;
        if (isSessionSwitch) {
          if (session.messages && session.messages.length > 0) {
            // ✅ 会话已有消息（第一个会话或已缓存的），直接使用
            setMessages(session.messages);

            const storedMode = session.mode;
            if (storedMode) {
              setAppMode(storedMode as AppMode);
            } else {
              const lastMsg = [...session.messages].reverse().find(m => m.mode);
              setAppMode((lastMsg?.mode || 'chat') as AppMode);
            }

            // Update llmService
            if (activeModelConfig) {
              llmService.startNewChat(session.messages, activeModelConfig);
              prevModelConfigRef.current = activeModelConfig;
            }
          } else {
            // ✅ 会话没有消息，按需加载（完整消息，不能分页）
            if (!loadingMessagesRef.current.has(currentSessionId)) {
              loadingMessagesRef.current.add(currentSessionId);
              
              apiClient.get<ChatSession>(`/api/sessions/${currentSessionId}`)
                .then(fullSession => {
                  // ✅ 更新 sessionsRef 中的会话数据
                  const sessionIndex = sessionsRef.current.findIndex(s => s.id === currentSessionId);
                  if (sessionIndex !== -1) {
                    sessionsRef.current[sessionIndex] = fullSession;
                  }
                  
                  // ✅ 设置消息和模式
                  setMessages(fullSession.messages || []);
                  
                  const storedMode = fullSession.mode;
                  if (storedMode) {
                    setAppMode(storedMode as AppMode);
                  } else {
                    const lastMsg = [...(fullSession.messages || [])].reverse().find(m => m.mode);
                    setAppMode((lastMsg?.mode || 'chat') as AppMode);
                  }

                  // Update llmService
                  if (activeModelConfig) {
                    llmService.startNewChat(fullSession.messages || [], activeModelConfig);
                    prevModelConfigRef.current = activeModelConfig;
                  }
                  
                  loadingMessagesRef.current.delete(currentSessionId);
                })
                .catch(err => {
                  console.error('[useSessionSync] 加载会话消息失败:', err);
                  setMessages([]);
                  loadingMessagesRef.current.delete(currentSessionId);
                });
            }
          }
          
          prevSessionIdRef.current = currentSessionId;
        }

        // Only update llmService when model actually changes (not during session switch)
        const isModelSwitch = prevModelConfigRef.current?.id !== activeModelConfig?.id;
        if (!isSessionSwitch && isModelSwitch && activeModelConfig) {
          llmService.startNewChat(session.messages || [], activeModelConfig);
          prevModelConfigRef.current = activeModelConfig;
        }
      }
    }
  }, [currentSessionId, activeModelConfig, setMessages, setAppMode]);
};

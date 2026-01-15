
import { useEffect, useRef, Dispatch, SetStateAction } from 'react';
import { ChatSession, Message, ModelConfig, AppMode } from '../types/types';
import { llmService } from '../services/llmService';

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
          setMessages(session.messages);

          const storedMode = session.mode;
          if (storedMode) {
            setAppMode(storedMode as AppMode);
          } else {
            const lastMsg = [...session.messages].reverse().find(m => m.mode);
            setAppMode((lastMsg?.mode || 'chat') as AppMode);
          }
          prevSessionIdRef.current = currentSessionId;
        }

        // Only update llmService when session switches or model actually changes
        const isModelSwitch = prevModelConfigRef.current?.id !== activeModelConfig?.id;
        if ((isSessionSwitch || isModelSwitch) && activeModelConfig) {
          llmService.startNewChat(session.messages, activeModelConfig);
          prevModelConfigRef.current = activeModelConfig;
        }
      }
    }
  }, [currentSessionId, activeModelConfig, setMessages, setAppMode]);
};

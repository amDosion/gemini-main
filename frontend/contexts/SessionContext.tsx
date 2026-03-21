import React, { createContext, useContext, useCallback } from 'react';
import { ChatSession } from '../types/types';
import { CacheStatusInfo } from '../hooks/useCacheStatus';

/**
 * 模块级共享 ref：当 gen 模式下切换会话时设为 true，
 * useSessionSync 读取后重置为 false，从而跳过 mode 恢复。
 */
export const skipModeRestoreFlag = { current: false };

interface SessionContextValue {
  sessions: ChatSession[];
  currentSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession?: (id: string) => void;
  onUpdateSessionTitle?: (id: string, newTitle: string) => void;
  cacheStatus?: CacheStatusInfo;
  onRefreshSessions?: () => void;
  hasMoreSessions?: boolean;
  isLoadingMore?: boolean;
  loadMoreSessions?: () => void;
  /** 切换会话但不恢复该会话的 mode（用于 gen 模式下的会话切换） */
  onSelectSessionKeepMode: (id: string) => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export const useSessionContext = () => {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSessionContext must be used within SessionProvider');
  return ctx;
};

interface SessionProviderProps {
  children: React.ReactNode;
  sessions: ChatSession[];
  currentSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession?: (id: string) => void;
  onUpdateSessionTitle?: (id: string, newTitle: string) => void;
  cacheStatus?: CacheStatusInfo;
  onRefreshSessions?: () => void;
  hasMoreSessions?: boolean;
  isLoadingMore?: boolean;
  loadMoreSessions?: () => void;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({
  children,
  onSelectSession,
  ...rest
}) => {
  const onSelectSessionKeepMode = useCallback((id: string) => {
    skipModeRestoreFlag.current = true;
    onSelectSession(id);
  }, [onSelectSession]);

  const value: SessionContextValue = {
    ...rest,
    onSelectSession,
    onSelectSessionKeepMode,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
};

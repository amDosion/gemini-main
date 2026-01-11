
import { useState, useEffect, useCallback, useRef } from 'react';
import { ChatSession, Message, Role } from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { db } from '../services/db';
import { cachedDb } from '../services/cachedDb';
import { cleanAttachmentsForDb } from './handlers/attachmentUtils';
import { useCacheStatus, CacheStatusInfo } from './useCacheStatus';

export const useSessions = (
  initialData?: {
    sessions: ChatSession[];
  }
) => {
  // ✅ 使用 initialData 初始化状态（如果提供）
  const initialSessions = initialData?.sessions;
  const [sessions, setSessions] = useState<ChatSession[]>(
    initialSessions || []
  );
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // ✅ 使用 ref 标记是否已经从 initialData 初始化过，避免无限循环
  const isInitializedFromPropsRef = useRef(false);

  // ✅ 使用 ref 保存 cacheStatus 的方法，避免循环依赖
  const cacheStatusRef = useRef<{
    updateStatus: (fromCache: boolean, isStale: boolean, timestamp: number) => void;
  } | null>(null);

  // 缓存状态 Hook（不传递 refreshFn，避免循环依赖）
  const cacheStatus = useCacheStatus('sessions');

  const prepareSessions = useCallback((sourceSessions: ChatSession[]) => {
    const recoveredSessions = sourceSessions.map(session => {
      if (!session.messages || session.messages.length === 0) {
        return session;
      }
      
      const recoveredMessages = session.messages.map(message => {
        if (!message.attachments || message.attachments.length === 0) {
          return message;
        }
        
        const recoveredAttachments = message.attachments.map(att => {
          // 检查 url 是否是 Blob URL（页面刷新后已失效）
          if (att.url && att.url.startsWith('blob:')) {
            console.log('[useSessions] 检测到失效的 Blob URL，尝试恢复:', {
              attachmentId: att.id?.substring(0, 8) + '...',
              hasTempUrl: !!att.tempUrl,
              tempUrlType: att.tempUrl?.startsWith('http') ? 'HTTP' : 'Other'
            });
            
            // 如果有 tempUrl（云存储 URL），使用它替代失效的 Blob URL
            if (att.tempUrl && att.tempUrl.startsWith('http')) {
              console.log('[useSessions] ? 使用 tempUrl 恢复显示');
              return {
                ...att,
                url: att.tempUrl, // 替换为云存储 URL
                uploadStatus: 'completed' as const
              };
            } else {
              console.log('[useSessions] ?? 无有效 tempUrl，保持原状');
              // 没有有效的 tempUrl，保持原状（可能需要重新生成）
              return att;
            }
          }
          
          // 其他类型的 URL（Base64, HTTP）不需要恢复
          return att;
        });
        
        return {
          ...message,
          attachments: recoveredAttachments
        };
      });
      
      return {
        ...session,
        messages: recoveredMessages
      };
    });

    return [...recoveredSessions].sort((a, b) => b.createdAt - a.createdAt);
  }, []);

  // ✅ 保存 cacheStatus 的方法到 ref
  useEffect(() => {
    cacheStatusRef.current = {
      updateStatus: cacheStatus.updateStatus
    };
  }, [cacheStatus.updateStatus]);

  // 刷新会话列表（强制从后端获取）
  const refreshSessions = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await cachedDb.refreshSessions();
      const preparedSessions = prepareSessions(result.data);
      setSessions(preparedSessions);
      setCurrentSessionId(prev => (
        preparedSessions.length > 0 ? (prev ?? preparedSessions[0].id) : null
      ));
      // ✅ 使用 ref 调用 updateStatus，避免依赖 cacheStatus
      cacheStatusRef.current?.updateStatus(result.fromCache, result.isStale, result.timestamp);
    } catch (error) {
      console.error('Failed to refresh sessions:', error);
    } finally {
      setIsLoading(false);
    }
  }, [prepareSessions]); // ✅ 移除 cacheStatus 依赖

  // ? 处理 initialData：恢复 Blob URL 和设置 currentSessionId
  // ?? 优先使用 initData.sessions，缺失时回退到 /sessions
  useEffect(() => {
    console.log('[useSessions] useEffect triggered:', {
      hasInitialSessions: initialSessions !== undefined,
      sessionsCount: initialSessions?.length || 0,
      isAlreadyInitialized: isInitializedFromPropsRef.current,
      timestamp: new Date().toISOString()
    });

    if (initialSessions === undefined) {
      console.log('[useSessions] initialData not ready, resetting state');
      isInitializedFromPropsRef.current = false;
      setSessions([]);
      setCurrentSessionId(null);
      return;
    }

    if (initialSessions.length > 0) {
      // 标记为已初始化
      isInitializedFromPropsRef.current = true;

      const preparedSessions = prepareSessions(initialSessions);
      console.log('[useSessions] Setting recovered sessions:', {
        count: preparedSessions.length,
        firstSessionId: preparedSessions[0]?.id?.substring(0, 8) + '...',
        timestamp: new Date().toISOString()
      });

      setSessions(preparedSessions);

      // Restore the most recent session if available
      if (preparedSessions.length > 0) {
        console.log('[useSessions] Setting currentSessionId to:', preparedSessions[0].id.substring(0, 8) + '...');
        setCurrentSessionId(prev => prev ?? preparedSessions[0].id);
      } else {
        setCurrentSessionId(null);
      }
      return;
    }

    if (isInitializedFromPropsRef.current) {
      console.log('[useSessions] Already initialized from props, skipping fallback');
      return;
    }

    // 初始会话为空时，回退到 sessions API
    isInitializedFromPropsRef.current = true;
    console.log('[useSessions] No sessions in initData, refreshing from backend');
    refreshSessions();
  }, [initialSessions, prepareSessions]); // ✅ 移除 refreshSessions 依赖，避免无限循环

  const prepareSessionForDb = useCallback((session: ChatSession): ChatSession => {
    if (!session.messages || session.messages.length === 0) {
      return session;
    }

    const cleanedMessages = session.messages.map(message => {
      if (!message.attachments || message.attachments.length === 0) {
        return message;
      }

      return {
        ...message,
        attachments: cleanAttachmentsForDb(message.attachments, false)
      };
    });

    return {
      ...session,
      messages: cleanedMessages
    };
  }, []);

  // Save session to database (with error handling for offline mode)
  // 使用 cachedDb 实现写穿透
  const saveSessionToDb = useCallback(async (session: ChatSession) => {
    try {
      await cachedDb.saveSession(prepareSessionForDb(session));
    } catch (error) {
      // Silently fail - 可能是后端不可用或组件卸载导致请求取消
      // Sessions 仍然会在内存中工作，只是不会持久化
      if (error instanceof Error && error.message.includes('component unmount')) {
        // React Strict Mode 双重渲染或组件卸载导致，忽略
        return;
      }
      console.warn('Failed to save session to database (using memory-only mode):', error);
    }
  }, [prepareSessionForDb]);

  // Delete session from database
  // 使用 cachedDb 实现删除并失效缓存
  const deleteSessionFromDb = useCallback(async (sessionId: string) => {
    try {
      await cachedDb.deleteSession(sessionId);
    } catch (error) {
      console.warn('Failed to delete session from database:', error);
    }
  }, []);

  const createNewSession = useCallback((personaId?: string) => {
    const newSession: ChatSession = {
      id: uuidv4(),
      title: 'New Chat',
      messages: [],
      createdAt: Date.now(),
      mode: 'chat', // Default mode
      personaId: personaId // 保存当前激活的 persona
    };
    
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    
    // Save to database (async, non-blocking)
    saveSessionToDb(newSession);
    
    return newSession;
  }, [saveSessionToDb]);

  const updateSessionMessages = useCallback((sessionId: string, newMessages: Message[]) => {
    setSessions(prev => {
      const updated = prev.map(s => {
        if (s.id === sessionId) {
          let title = s.title;
          // Auto-generate title from first user message
          if (s.title === 'New Chat' && newMessages.length > 0) {
            const firstUserMsg = newMessages.find(m => m.role === Role.USER);
            if (firstUserMsg) {
              title = firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '');
            }
          }
          
          // Determine mode from the last message that has a mode property, fallback to existing or 'chat'
          const lastMsgWithMode = [...newMessages].reverse().find(m => m.mode);
          const currentMode = lastMsgWithMode?.mode || s.mode || 'chat';

          // ✅ 根据会话模式判断是否需要清理附件
          // 图片模式（image-outpainting、image-edit、image-gen）需要清理 Blob URL 和 Base64 URL
          // 因为这些模式都有异步上传任务，清理后 URL 为空，等待后端上传完成后更新
          const needsCleanSession = currentMode === 'image-outpainting' || 
                                    currentMode === 'image-edit' || 
                                    currentMode === 'image-gen';
          
          const cleanedMessages = needsCleanSession 
            ? newMessages.map(msg => {
                if (msg.attachments) {
                  return {
                    ...msg,
                    attachments: cleanAttachmentsForDb(msg.attachments, false)
                  };
                }
                return msg;
              })
            : newMessages;

          const updatedSession = { ...s, title, messages: cleanedMessages, mode: currentMode };
          
          // Save to database (async, non-blocking)
          saveSessionToDb(updatedSession);
          
          return updatedSession;
        }
        return s;
      });
      
      return updated;
    });
  }, [saveSessionToDb]);

  const deleteSession = useCallback(async (sessionId: string) => {
    // Remove from memory and get remaining sessions
    let remainingSessions: ChatSession[] = [];
    setSessions(prev => {
      remainingSessions = prev.filter(s => s.id !== sessionId);
      return remainingSessions;
    });
    
    // If deleting current session, switch to another or clear
    if (currentSessionId === sessionId) {
      setCurrentSessionId(remainingSessions.length > 0 ? remainingSessions[0].id : null);
    }
    
    // Delete from database
    await deleteSessionFromDb(sessionId);
  }, [currentSessionId, deleteSessionFromDb]);

  const updateSessionPersona = useCallback((sessionId: string, personaId: string) => {
    setSessions(prev => {
      const updated = prev.map(s => {
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
  }, [saveSessionToDb]);

  const updateSessionTitle = useCallback((sessionId: string, newTitle: string) => {
    setSessions(prev => {
      const updated = prev.map(s => {
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
  }, [saveSessionToDb]);

  const getSession = useCallback((id: string) => {
    return sessions.find(s => s.id === id);
  }, [sessions]);

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
  };
};


import { useState, useEffect, useCallback } from 'react';
import { ChatSession, Message, Role } from '../../types';
import { v4 as uuidv4 } from 'uuid';
import { db } from '../services/db';
import { cleanAttachmentsForDb } from './handlers/attachmentUtils';

export const useSessions = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load sessions from database on mount
  useEffect(() => {
    const loadSessions = async () => {
      try {
        setIsLoading(true);
        const loadedSessions = await db.getSessions();
        
        // Sort by createdAt descending (newest first)
        const sortedSessions = loadedSessions.sort((a, b) => b.createdAt - a.createdAt);
        
        setSessions(sortedSessions);
        
        // Restore the most recent session if available
        if (sortedSessions.length > 0) {
          setCurrentSessionId(sortedSessions[0].id);
        }
      } catch (error) {
        console.error('Failed to load sessions:', error);
        // On error, start with empty sessions (memory-only mode)
        setSessions([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadSessions();
  }, []);

  // Save session to database (with error handling for offline mode)
  const saveSessionToDb = useCallback(async (session: ChatSession) => {
    try {
      await db.saveSession(session);
    } catch (error) {
      // Silently fail - we're in memory-only mode (backend unavailable)
      // Sessions will still work in memory, just won't persist
      console.warn('Failed to save session to database (using memory-only mode):', error);
    }
  }, []);

  // Delete session from database
  const deleteSessionFromDb = useCallback(async (sessionId: string) => {
    try {
      await db.deleteSession(sessionId);
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
    isLoading
  };
};

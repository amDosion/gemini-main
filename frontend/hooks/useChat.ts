/**
 * useChat Hook - 重构版本
 * 
 * 使用策略模式替代巨大的 if-else 链
 * 修复问题1：创建全局 pollingManager 实例
 * 修复问题2：使用 PreprocessorRegistry 处理文件上传
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { Message, Role, LoadingState, ChatOptions, Attachment, AppMode, ModelConfig } from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { llmService } from '../services/llmService';
import { storageUpload } from '../services/storage/storageUpload';

// 导入新的策略模式组件
import { strategyRegistry, preprocessorRegistry } from './handlers/strategyConfig';
import { PollingManager } from './handlers/PollingManager';
import { ExecutionContext, StreamUpdate } from './handlers/types';

export const useChat = (
  currentSessionId: string | null,
  updateSessionMessages: (id: string, msgs: Message[]) => void,
  apiKey?: string
) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingState, setLoadingState] = useState<LoadingState>('idle');

  // 创建全局 pollingManager 实例（修复问题1）
  const pollingManager = useMemo(() => new PollingManager(), []);

  // 组件卸载时清理轮询任务
  useEffect(() => {
    return () => {
      pollingManager.cleanup();
    };
  }, [pollingManager]);

  const stopGeneration = useCallback(() => {
      llmService.cancelCurrentStream();
      setLoadingState('idle');
  }, []);

  const sendMessage = async (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode,
    currentModel: ModelConfig,
    protocol: 'google' | 'openai'
  ) => {
    if (!currentSessionId) return;

    try {
      // 1. Initialize Service Context
      const contextHistory = messages.filter(m => m.mode === mode || (!m.mode && mode === 'chat'));
      llmService.startNewChat(contextHistory, currentModel, options);

      // 2. Create User Message (before preprocessing)
      const userMessageId = uuidv4();
      const modelMessageId = uuidv4();

      // 3. Create ExecutionContext
      let context: ExecutionContext = {
        sessionId: currentSessionId,
        userMessageId,
        modelMessageId,
        mode,
        text,
        attachments: [...attachments],
        currentModel,
        options,
        protocol,
        apiKey,
        llmService,
        storageService: storageUpload,
        pollingManager, // 全局单例（修复问题1）
        onStreamUpdate: undefined, // 稍后设置
        onProgressUpdate: undefined // 稍后设置
      };

      // 4. Preprocess (文件上传等)（修复问题2）
      setLoadingState('uploading');
      context = await preprocessorRegistry.process(context);

      // 5. Create Optimistic User Message (使用处理后的 attachments)
      const userMessage: Message = {
        id: userMessageId,
        role: Role.USER,
        content: text,
        attachments: context.attachments,
        timestamp: Date.now(),
        mode: mode,
      };

      const updatedMessages = [...messages, userMessage];
      setMessages(updatedMessages);
      updateSessionMessages(currentSessionId, updatedMessages);
      setLoadingState(mode === 'chat' ? 'streaming' : 'loading');

      // 6. Create Model Placeholder
      const initialModelMessage: Message = {
        id: modelMessageId,
        role: Role.MODEL,
        content: '',
        attachments: [],
        timestamp: Date.now(),
        mode: mode,
      };

      setMessages(prev => [...prev, initialModelMessage]);

      // 7. Set up callbacks
      const onStreamUpdate = (update: StreamUpdate) => {
        setMessages(prev =>
          prev.map(msg =>
            msg.id === modelMessageId
              ? {
                  ...msg,
                  content: update.content || msg.content,
                  attachments: update.attachments || msg.attachments,
                  groundingMetadata: update.groundingMetadata,
                  urlContextMetadata: update.urlContextMetadata,
                  browserOperationId: update.browserOperationId
                }
              : msg
          )
        );
      };

      context.onStreamUpdate = onStreamUpdate;

      // 8. Execute Handler (策略模式，替代巨大的 if-else 链)
      const handler = strategyRegistry.getHandler(mode);
      const result = await handler.execute(context);

      // 9. Update UI with result
      const displayModelMessage: Message = {
        ...initialModelMessage,
        content: result.content,
        attachments: result.attachments as Attachment[],
        groundingMetadata: result.groundingMetadata,
        urlContextMetadata: result.urlContextMetadata,
        browserOperationId: result.browserOperationId
      };

      setMessages(prev => prev.map(msg => msg.id === modelMessageId ? displayModelMessage : msg));

      // 10. Handle upload task (if any)
      if (result.uploadTask) {
        result.uploadTask.then(({ dbAttachments, dbUserAttachments }) => {
          // 保存到数据库（使用 dbAttachments，带 uploadTaskId）
          const dbUserMessage: Message = dbUserAttachments
            ? { ...userMessage, attachments: dbUserAttachments as Attachment[] }
            : userMessage;

          const dbModelMessage: Message = {
            ...initialModelMessage,
            content: result.content,
            attachments: dbAttachments as Attachment[]
          };

          const dbMessages = [
            ...messages.filter(m => m.id !== userMessage.id),
            dbUserMessage,
            dbModelMessage
          ];

          updateSessionMessages(currentSessionId, dbMessages);
          console.log('[useChat] 上传任务已提交，已保存到数据库（pending）');
        }).catch(err => {
          console.error('[useChat] 上传任务失败:', err);
        });
      } else {
        // 没有上传任务，直接保存到数据库
        const finalMessages = [...updatedMessages, displayModelMessage];
        updateSessionMessages(currentSessionId, finalMessages);
      }

      setLoadingState('idle');

    } catch (error: any) {
      console.error('[useChat] 执行失败:', error);
      
      // 清理轮询任务
      pollingManager.cleanup();

      // 显示错误消息
      const errorMessage: Message = {
        id: uuidv4(),
        role: Role.MODEL,
        content: `错误: ${error.message || '未知错误'}`,
        attachments: [],
        timestamp: Date.now(),
        mode: mode,
      };

      setMessages(prev => [...prev.slice(0, -1), errorMessage]);
      setLoadingState('idle');
    }
  };

  return {
    messages,
    setMessages,
    loadingState,
    setLoadingState,
    sendMessage,
    stopGeneration,
  };
};

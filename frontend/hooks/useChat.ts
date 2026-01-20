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
import { getUrlType } from './handlers/attachmentUtils';

export const useChat = (
  currentSessionId: string | null,
  updateSessionMessages: (id: string, msgs: Message[]) => void,
  apiKey?: string,
  activeStorageId?: string | null
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
      // 如果启用了 Research，强制启用 Search 以提供增强的研究功能
      const enhancedOptions = options.enableResearch
        ? { ...options, enableSearch: true }
        : options;
      
      // ✅ 详细日志：记录 image-gen 模式下传递给 llmService 的参数
      if (mode === 'image-gen') {
        console.log('========== [useChat.sendMessage] image-gen 模式参数传递 ==========');
        console.log('[useChat] 接收到的 Options (原始):', {
          numberOfImages: options.numberOfImages,
          imageAspectRatio: options.imageAspectRatio,
          imageResolution: options.imageResolution,
          imageStyle: options.imageStyle,
          negativePrompt: options.negativePrompt,
          seed: options.seed,
          // guidanceScale removed - not officially documented by Google Imagen
          outputMimeType: options.outputMimeType,
          outputCompressionQuality: options.outputCompressionQuality,
          enhancePrompt: options.enhancePrompt,
        });
        console.log('[useChat] Enhanced Options (传递给 llmService):', {
          numberOfImages: enhancedOptions.numberOfImages,
          imageAspectRatio: enhancedOptions.imageAspectRatio,
          imageResolution: enhancedOptions.imageResolution,
          imageStyle: enhancedOptions.imageStyle,
          negativePrompt: enhancedOptions.negativePrompt,
          seed: enhancedOptions.seed,
          // guidanceScale removed - not officially documented by Google Imagen
          outputMimeType: enhancedOptions.outputMimeType,
          outputCompressionQuality: enhancedOptions.outputCompressionQuality,
          enhancePrompt: enhancedOptions.enhancePrompt,
        });
        console.log('[useChat] 完整 Enhanced Options:', JSON.stringify(enhancedOptions, null, 2));
        console.log('========== [useChat.sendMessage] image-gen 参数传递结束 ==========');
      }
      
      llmService.startNewChat(contextHistory, currentModel, enhancedOptions);

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
        storageId: activeStorageId ?? undefined,
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
        browserOperationId: result.browserOperationId,
        // 存储 thoughts 和 textResponse（如果存在）
        ...(result.thoughts && { thoughts: result.thoughts }),
        ...(result.textResponse && { textResponse: result.textResponse })
      };

      // ✅ 详细日志：记录附件显示使用的URL类型
      if (displayModelMessage.attachments && displayModelMessage.attachments.length > 0) {
        console.log('[useChat] ========== 附件显示URL类型分析 ==========');
        displayModelMessage.attachments.forEach((att, idx) => {
          const urlType = getUrlType(att.url, att.uploadStatus);
          
          const hasCloudUrl = att.uploadStatus === 'completed' && 
                             (att.url?.startsWith('http://') || att.url?.startsWith('https://'));
          
          console.log(`[useChat] 附件 ${idx + 1}/${displayModelMessage.attachments.length}:`, {
            attachmentId: att.id?.substring(0, 8) + '...',
            displayUrlType: urlType,
            displayUrl: att.url ? (att.url.length > 80 ? att.url.substring(0, 80) + '...' : att.url) : 'N/A',
            uploadStatus: att.uploadStatus,
            hasCloudUrl: hasCloudUrl,
            cloudUrl: hasCloudUrl ? (att.url!.length > 80 ? att.url!.substring(0, 80) + '...' : att.url!) : 'N/A',
            tempUrl: att.tempUrl ? (att.tempUrl.length > 80 ? att.tempUrl.substring(0, 80) + '...' : att.tempUrl) : 'N/A',
            source: hasCloudUrl ? '云存储URL (处理后的永久URL)' : 
                   att.url?.startsWith('data:') ? 'AI返回的Base64 (原始地址)' :
                   att.url?.startsWith('blob:') ? '处理后的Blob URL (临时本地URL)' :
                   att.url?.startsWith('http') ? 'AI返回的HTTP临时URL (原始地址)' : '未知来源'
          });
        });
        console.log('[useChat] ============================================');
      }

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
          
          // ✅ 详细日志：记录保存到数据库的附件URL类型
          console.log('[useChat] ========== 数据库保存的附件URL类型分析 ==========');
          if (dbModelMessage.attachments && dbModelMessage.attachments.length > 0) {
            dbModelMessage.attachments.forEach((att, idx) => {
              const urlType = getUrlType(att.url, att.uploadStatus);
              
              console.log(`[useChat] 数据库附件 ${idx + 1}/${dbModelMessage.attachments.length}:`, {
                attachmentId: att.id?.substring(0, 8) + '...',
                urlType: urlType,
                url: att.url ? (att.url.length > 60 ? att.url.substring(0, 60) + '...' : att.url) : '空',
                uploadStatus: att.uploadStatus,
                uploadTaskId: att.uploadTaskId ? att.uploadTaskId.substring(0, 8) + '...' : 'N/A',
                tempUrl: att.tempUrl ? (att.tempUrl.length > 60 ? att.tempUrl.substring(0, 60) + '...' : att.tempUrl) : 'N/A',
                note: att.uploadStatus === 'pending' ? '等待上传完成后，url将更新为云存储URL' : 
                     att.uploadStatus === 'completed' ? '已上传完成，url是云存储URL' : '上传状态未知'
              });
            });
          }
          console.log('[useChat] ============================================');
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

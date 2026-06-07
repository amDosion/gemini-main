/**
 * useChat Hook - 重构版本
 *
 * 使用策略模式替代巨大的 if-else 链
 * 修复问题1：创建全局 pollingManager 实例
 * 修复问题2：使用 PreprocessorRegistry 处理文件上传
 */

import { useState, useCallback, useMemo, useEffect, useRef, SetStateAction } from 'react';
import {
  Message,
  Role,
  LoadingState,
  ChatOptions,
  Attachment,
  AppMode,
  ModelConfig,
  ToolCall,
  ToolResult,
} from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { llmService } from '../services/llmService';
import { storageUpload } from '../services/storage/storageUpload';

// 导入新的策略模式组件
import { strategyRegistry, preprocessorRegistry } from './handlers/strategyConfig';
import { PollingManager } from './handlers/PollingManager';
import {
  ExecutionContext,
  StreamUpdate,
  HandlerMode,
  ResearchActionSubmitHandler,
} from './handlers/types';
import {
  AUTO_RESEARCH_CONTEXT_WINDOW,
  AUTO_RESEARCH_EVIDENCE_WINDOW,
  resolveLeadRoleByPersona,
  describeLeadRole,
  summarizeToolEvidenceForAutoResearch,
  summarizeContextForAutoResearch,
  buildAutoDeepResearchPrompt,
  combineAutoDeepResearchContent,
  STREAM_UPDATE_BATCH_INTERVAL_MS,
  composeModelMessageUpdaters,
  applyStreamUpdateToModelMessage,
  type ModelMessageUpdater,
} from './useChatHelpers';

export const useChat = (
  currentSessionId: string | null,
  updateSessionMessages: (
    id: string,
    msgs: Message[],
    options?: { strategy?: 'replace' | 'merge-by-id' }
  ) => void,
  apiKey?: string,
  activeStorageId?: string | null
) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingState, setLoadingState] = useState<LoadingState>('idle');
  const activeHandlerCancelRef = useRef<(() => void) | null>(null);
  const researchActionHandlersRef = useRef<Map<string, ResearchActionSubmitHandler>>(new Map());
  const messagesRef = useRef<Message[]>([]);
  const currentSessionIdRef = useRef<string | null>(currentSessionId);

  // 创建全局 pollingManager 实例（修复问题1）
  const pollingManager = useMemo(() => new PollingManager(), []);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  // 组件卸载时清理轮询任务
  useEffect(() => {
    return () => {
      pollingManager.cleanup();
      researchActionHandlersRef.current.clear();
    };
    // deps=[]：pollingManager 是 useMemo deps=[] 永久稳定；ref identity 永久稳定，
    // 不应在 deps（React rule）。原 [pollingManager, researchActionHandlersRef]
    // 无功能影响但属冗余 deps（修 final audit MEDIUM）。
  }, []);

  const stopGeneration = useCallback(() => {
    llmService.cancelCurrentStream();
    activeHandlerCancelRef.current?.();
    activeHandlerCancelRef.current = null;
    researchActionHandlersRef.current.clear();
    setLoadingState('idle');
  }, []);

  const submitResearchAction = useCallback(
    async (messageId: string, selectedInput: unknown) => {
      const targetMessage = messagesRef.current.find((msg) => msg.id === messageId);
      if (!targetMessage) {
        throw new Error('未找到对应的 Deep Research 消息');
      }

      if (targetMessage.responseKind !== 'deep-research' || targetMessage.role !== Role.MODEL) {
        throw new Error('仅支持对 Deep Research 模型消息提交动作');
      }

      const interactionId = targetMessage.researchInteractionId;
      if (!interactionId) {
        throw new Error('当前消息缺少 researchInteractionId，无法提交动作');
      }

      const actionHandler = researchActionHandlersRef.current.get(interactionId);
      if (!actionHandler) {
        throw new Error('当前 Deep Research 任务未处于可提交动作状态');
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                researchStatus: {
                  status: 'awaiting_action',
                  progress: '正在提交动作，准备继续研究...',
                  elapsedTime: msg.researchStatus?.elapsedTime,
                },
              }
            : msg
        )
      );

      await actionHandler(selectedInput);
    },
    [setMessages]
  );

  const sendMessage = async (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode,
    currentModel: ModelConfig,
    protocol: 'google' | 'openai',
    targetSessionId?: string
  ) => {
    const resolvedSessionId = targetSessionId || currentSessionId;
    if (!resolvedSessionId) return;

    const allowBootstrapWhileSessionSync =
      !!targetSessionId && currentSessionIdRef.current === null;

    const shouldApplyUiUpdates = () => {
      const latestSessionId = currentSessionIdRef.current;
      return (
        latestSessionId === resolvedSessionId ||
        (allowBootstrapWhileSessionSync && latestSessionId === null)
      );
    };

    const setMessagesIfCurrentSession = (updater: SetStateAction<Message[]>) => {
      if (!shouldApplyUiUpdates()) return;
      setMessages(updater);
    };

    const setLoadingStateIfCurrentSession = (state: LoadingState) => {
      if (!shouldApplyUiUpdates()) return;
      setLoadingState(state);
    };

    let userMessageId: string | null = null;
    let modelMessageId: string | null = null;
    const baseMessages = messagesRef.current;
    let streamUpdateTimer: ReturnType<typeof setTimeout> | null = null;
    let pendingModelMessageUpdater: ModelMessageUpdater | null = null;

    const flushBufferedStreamUpdates = () => {
      if (streamUpdateTimer) {
        clearTimeout(streamUpdateTimer);
        streamUpdateTimer = null;
      }
      if (!pendingModelMessageUpdater || !modelMessageId) return;
      const modelMessageUpdater = pendingModelMessageUpdater;
      pendingModelMessageUpdater = null;

      setMessagesIfCurrentSession((prev) =>
        prev.map((msg) => (msg.id === modelMessageId ? modelMessageUpdater(msg) : msg))
      );
    };

    const cancelBufferedStreamUpdates = () => {
      if (streamUpdateTimer) {
        clearTimeout(streamUpdateTimer);
        streamUpdateTimer = null;
      }
      pendingModelMessageUpdater = null;
    };

    const enqueueBufferedStreamUpdate = (update: StreamUpdate) => {
      if (!modelMessageId) return;
      const updateModelMessage: ModelMessageUpdater = (message) =>
        applyStreamUpdateToModelMessage(message, update);
      pendingModelMessageUpdater = composeModelMessageUpdaters(
        pendingModelMessageUpdater,
        updateModelMessage
      );

      if (streamUpdateTimer) return;

      streamUpdateTimer = setTimeout(() => {
        streamUpdateTimer = null;
        flushBufferedStreamUpdates();
      }, STREAM_UPDATE_BATCH_INTERVAL_MS);
    };

    try {
      // 1. Initialize Service Context
      const contextHistory = baseMessages.filter(
        (m) => m.mode === mode || (!m.mode && mode === 'chat')
      );
      // 增强检索：强制启用联网搜索
      const enhancedOptions = options.enableEnhancedRetrieval
        ? { ...options, enableSearch: true }
        : options;
      const isPrimaryDeepResearch = mode === 'chat' && !!options.enableDeepResearch;
      const isAutoDeepResearch =
        mode === 'chat' && !isPrimaryDeepResearch && !!options.enableAutoDeepResearch;
      const handlerMode: HandlerMode = isPrimaryDeepResearch ? 'deep-research' : mode;
      const previousResearchInteractionId =
        isPrimaryDeepResearch || isAutoDeepResearch
          ? [...contextHistory]
              .reverse()
              .find(
                (message) =>
                  message.role === Role.MODEL &&
                  message.responseKind === 'deep-research' &&
                  !!message.researchInteractionId
              )?.researchInteractionId
          : undefined;

      if ((isPrimaryDeepResearch || isAutoDeepResearch) && !options.deepResearchAgentId?.trim()) {
        throw new Error('请先在工具栏“自动深挖”菜单中选择 Deep Research 专用模型。');
      }

      // ✅ 详细日志：记录 image-gen 模式下传递给 llmService 的参数
      if (mode === 'image-gen') {
      }

      llmService.startNewChat(contextHistory, currentModel, enhancedOptions);

      // 2. Create User Message (before preprocessing)
      userMessageId = uuidv4();
      modelMessageId = uuidv4();

      // 3. Create ExecutionContext
      let context: ExecutionContext = {
        sessionId: resolvedSessionId,
        userMessageId,
        modelMessageId,
        mode,
        text,
        attachments: [...attachments],
        currentModel,
        options,
        protocol,
        previousResearchInteractionId,
        apiKey,
        storageId: activeStorageId ?? undefined,
        llmService,
        storageService: storageUpload,
        pollingManager, // 全局单例（修复问题1）
        onStreamUpdate: undefined, // 稍后设置
        onProgressUpdate: undefined, // 稍后设置
        registerCancel: (cancelFn) => {
          activeHandlerCancelRef.current = cancelFn;
        },
        registerResearchActionHandler: (interactionId, handler) => {
          if (!interactionId) return;
          if (handler) {
            researchActionHandlersRef.current.set(interactionId, handler);
          } else {
            researchActionHandlersRef.current.delete(interactionId);
          }
        },
      };

      // 4. Preprocess (文件上传等)（修复问题2）
      setLoadingStateIfCurrentSession('uploading');
      context = await preprocessorRegistry.process(context);

      // 5. Create Optimistic User Message (使用处理后的 attachments)
      const userMessage: Message = {
        id: userMessageId,
        role: Role.USER,
        content: text,
        attachments: context.attachments, // ✅ 保留 Blob URL 用于当前会话显示
        timestamp: Date.now(),
        mode: mode,
      };

      const updatedMessages = [...baseMessages, userMessage];
      setMessagesIfCurrentSession((prev) => [...prev, userMessage]); // ✅ 当前会话保留 Blob URL 用于显示
      // ✅ 注意：这里不调用 updateSessionMessages，等待 uploadTask 完成后再保存（会清空 Blob URL）
      // 当前会话的 messages 状态保留 Blob URL，用于立即显示
      setLoadingStateIfCurrentSession(mode === 'chat' ? 'streaming' : 'loading');

      // 6. Create Model Placeholder
      const initialModelMessage: Message = {
        id: modelMessageId,
        role: Role.MODEL,
        content: '',
        attachments: [],
        timestamp: Date.now(),
        mode: mode,
        modelId: currentModel.id,
        modelName: currentModel.name,
        responseKind: handlerMode === 'deep-research' ? 'deep-research' : 'chat',
        researchStatus:
          handlerMode === 'deep-research'
            ? { status: 'starting', progress: '正在启动 Deep Research...', elapsedTime: 0 }
            : undefined,
      };

      setMessagesIfCurrentSession((prev) => [...prev, initialModelMessage]);

      // 7. Set up callbacks
      const onStreamUpdate = (update: StreamUpdate) => {
        enqueueBufferedStreamUpdate(update);
      };

      context.onStreamUpdate = onStreamUpdate;

      // 8. Execute Handler (策略模式，替代巨大的 if-else 链)
      const handler = strategyRegistry.getHandler(handlerMode);
      const result = await handler.execute(context);
      let finalResult = result;

      if (isAutoDeepResearch && handlerMode === 'chat') {
        flushBufferedStreamUpdates();

        const chatOnlyMessage: Message = {
          ...initialModelMessage,
          content: result.content,
          attachments: result.attachments as Attachment[],
          groundingMetadata: result.groundingMetadata,
          urlContextMetadata: result.urlContextMetadata,
          browserOperationId: result.browserOperationId,
          toolCalls: result.toolCalls ? [...result.toolCalls] : undefined,
          toolResults: result.toolResults ? [...result.toolResults] : undefined,
          responseKind: 'chat',
          researchStatus: undefined,
          researchInteractionId: undefined,
          researchRequiredAction: undefined,
          ...(result.thoughts && { thoughts: result.thoughts }),
          ...(result.textResponse && { textResponse: result.textResponse }),
          ...(result.enhancedPrompt && { enhancedPrompt: result.enhancedPrompt }),
        };

        setMessagesIfCurrentSession((prev) =>
          prev.map((msg) => (msg.id === modelMessageId ? chatOnlyMessage : msg))
        );

        const autoContextSummary = summarizeContextForAutoResearch([
          ...contextHistory,
          userMessage,
          chatOnlyMessage,
        ]);
        const autoLeadRole = resolveLeadRoleByPersona(context.options.personaId);
        const toolEvidenceSummary = summarizeToolEvidenceForAutoResearch(
          result.toolCalls,
          result.toolResults
        );
        const autoPrompt = buildAutoDeepResearchPrompt(
          text,
          result.content,
          autoContextSummary,
          autoLeadRole,
          context.options.personaId,
          toolEvidenceSummary
        );
        const autoResearchBaseContent = result.content;

        onStreamUpdate({
          responseKind: 'deep-research',
          researchStatus: {
            status: 'starting',
            progress: '初稿已生成，正在启动自动深挖...',
            elapsedTime: 0,
          },
        });

        const autoDeepResearchContext: ExecutionContext = {
          ...context,
          text: autoPrompt,
          attachments: [],
          options: {
            ...context.options,
            enableDeepResearch: true,
            enableAutoDeepResearch: false,
          },
          previousResearchInteractionId,
          onStreamUpdate: (update) => {
            const mergedUpdate: StreamUpdate = {
              ...update,
              responseKind: 'deep-research',
              content:
                typeof update.content === 'string'
                  ? combineAutoDeepResearchContent(autoResearchBaseContent, update.content)
                  : undefined,
            };
            onStreamUpdate(mergedUpdate);
          },
        };

        try {
          const autoDeepResearchHandler = strategyRegistry.getHandler('deep-research');
          const autoDeepResearchResult =
            await autoDeepResearchHandler.execute(autoDeepResearchContext);
          finalResult = {
            ...result,
            content: combineAutoDeepResearchContent(result.content, autoDeepResearchResult.content),
            groundingMetadata: autoDeepResearchResult.groundingMetadata ?? result.groundingMetadata,
            toolCalls: autoDeepResearchResult.toolCalls,
            toolResults: autoDeepResearchResult.toolResults,
            responseKind: 'deep-research',
            researchStatus: autoDeepResearchResult.researchStatus,
            researchInteractionId: autoDeepResearchResult.researchInteractionId,
            researchRequiredAction: autoDeepResearchResult.researchRequiredAction,
          };
        } catch (autoResearchError) {
          const errorMessage =
            autoResearchError instanceof Error
              ? autoResearchError.message
              : String(autoResearchError);
          finalResult = {
            ...result,
            content: `${result.content}\n\n---\n\n## Deep Research 深挖补充\n\n⚠️ 自动深挖失败：${errorMessage}`,
            responseKind: 'chat',
          };
        }
      }

      activeHandlerCancelRef.current = null;
      flushBufferedStreamUpdates();

      // 9. Update UI with result
      const displayModelMessage: Message = {
        ...initialModelMessage,
        content: finalResult.content,
        attachments: finalResult.attachments as Attachment[],
        groundingMetadata: finalResult.groundingMetadata,
        urlContextMetadata: finalResult.urlContextMetadata,
        browserOperationId: finalResult.browserOperationId,
        toolCalls: finalResult.toolCalls ? [...finalResult.toolCalls] : undefined,
        toolResults: finalResult.toolResults ? [...finalResult.toolResults] : undefined,
        responseKind: finalResult.responseKind || initialModelMessage.responseKind,
        researchStatus: finalResult.researchStatus || initialModelMessage.researchStatus,
        researchInteractionId:
          finalResult.researchInteractionId || initialModelMessage.researchInteractionId,
        researchRequiredAction: finalResult.researchRequiredAction,
        // 存储 thoughts、textResponse、enhancedPrompt（如果存在）
        ...(finalResult.thoughts && { thoughts: finalResult.thoughts }),
        ...(finalResult.textResponse && { textResponse: finalResult.textResponse }),
        ...(finalResult.enhancedPrompt && { enhancedPrompt: finalResult.enhancedPrompt }),
        ...(finalResult.continuationStrategy && {
          continuationStrategy: finalResult.continuationStrategy,
        }),
        ...(typeof finalResult.videoExtensionCount === 'number' && {
          videoExtensionCount: finalResult.videoExtensionCount,
        }),
        ...(typeof finalResult.videoExtensionApplied === 'number' && {
          videoExtensionApplied: finalResult.videoExtensionApplied,
        }),
        ...(typeof finalResult.totalDurationSeconds === 'number' && {
          totalDurationSeconds: finalResult.totalDurationSeconds,
        }),
        ...(finalResult.continuedFromVideo && {
          continuedFromVideo: finalResult.continuedFromVideo,
        }),
        ...(typeof finalResult.storyboardShotSeconds === 'number' && {
          storyboardShotSeconds: finalResult.storyboardShotSeconds,
        }),
        ...(typeof finalResult.generateAudio === 'boolean' && {
          generateAudio: finalResult.generateAudio,
        }),
        ...(finalResult.subtitleMode && { subtitleMode: finalResult.subtitleMode }),
        ...(finalResult.subtitleLanguage && { subtitleLanguage: finalResult.subtitleLanguage }),
        ...(finalResult.subtitleAttachmentIds &&
          finalResult.subtitleAttachmentIds.length > 0 && {
            subtitleAttachmentIds: [...finalResult.subtitleAttachmentIds],
          }),
        ...(finalResult.trackedFeature && { trackedFeature: finalResult.trackedFeature }),
        ...(finalResult.trackingOverlayText && {
          trackingOverlayText: finalResult.trackingOverlayText,
        }),
      };

      // ✅ 调试日志：检查 thoughts/textResponse/enhancedPrompt 是否被添加到消息中


      setMessagesIfCurrentSession((prev) =>
        prev.map((msg) => (msg.id === modelMessageId ? displayModelMessage : msg))
      );

      // 10. Handle upload task (if any)
      if (finalResult.uploadTask) {
        finalResult.uploadTask
          .then(({ dbAttachments, dbUserAttachments }) => {
            // ✅ 保存到数据库（使用 dbAttachments，带 uploadTaskId）
            // 注意：dbUserAttachments 已经处理过，可能清空了 Blob URL（用于数据库持久化）
            const dbUserMessage: Message = dbUserAttachments
              ? { ...userMessage, attachments: dbUserAttachments as Attachment[] }
              : userMessage;

            const dbModelMessage: Message = {
              ...initialModelMessage,
              content: finalResult.content,
              attachments: dbAttachments as Attachment[],
              toolCalls: finalResult.toolCalls ? [...finalResult.toolCalls] : undefined,
              toolResults: finalResult.toolResults ? [...finalResult.toolResults] : undefined,
              responseKind: finalResult.responseKind || initialModelMessage.responseKind,
              researchStatus: finalResult.researchStatus || initialModelMessage.researchStatus,
              researchInteractionId:
                finalResult.researchInteractionId || initialModelMessage.researchInteractionId,
              researchRequiredAction: finalResult.researchRequiredAction,
              ...(finalResult.thoughts && { thoughts: finalResult.thoughts }),
              ...(finalResult.textResponse && { textResponse: finalResult.textResponse }),
              ...(finalResult.enhancedPrompt && { enhancedPrompt: finalResult.enhancedPrompt }),
              ...(finalResult.continuationStrategy && {
                continuationStrategy: finalResult.continuationStrategy,
              }),
              ...(typeof finalResult.videoExtensionCount === 'number' && {
                videoExtensionCount: finalResult.videoExtensionCount,
              }),
              ...(typeof finalResult.videoExtensionApplied === 'number' && {
                videoExtensionApplied: finalResult.videoExtensionApplied,
              }),
              ...(typeof finalResult.totalDurationSeconds === 'number' && {
                totalDurationSeconds: finalResult.totalDurationSeconds,
              }),
              ...(finalResult.continuedFromVideo && {
                continuedFromVideo: finalResult.continuedFromVideo,
              }),
              ...(typeof finalResult.storyboardShotSeconds === 'number' && {
                storyboardShotSeconds: finalResult.storyboardShotSeconds,
              }),
              ...(typeof finalResult.generateAudio === 'boolean' && {
                generateAudio: finalResult.generateAudio,
              }),
              ...(finalResult.subtitleMode && { subtitleMode: finalResult.subtitleMode }),
              ...(finalResult.subtitleLanguage && {
                subtitleLanguage: finalResult.subtitleLanguage,
              }),
              ...(finalResult.subtitleAttachmentIds &&
                finalResult.subtitleAttachmentIds.length > 0 && {
                  subtitleAttachmentIds: [...finalResult.subtitleAttachmentIds],
                }),
              ...(finalResult.trackedFeature && { trackedFeature: finalResult.trackedFeature }),
              ...(finalResult.trackingOverlayText && {
                trackingOverlayText: finalResult.trackingOverlayText,
              }),
            };

            // ✅ 保存到数据库的消息（会清空 Blob URL）
            const dbMessages = [
              ...baseMessages.filter((m) => m.id !== userMessage.id),
              dbUserMessage,
              dbModelMessage,
            ];

            // ✅ 保存到数据库（会清空 Blob URL，用于持久化）
            updateSessionMessages(resolvedSessionId, dbMessages, {
              strategy: 'merge-by-id',
            });

            // ✅ 重要：当前会话的 messages 状态保留 Blob URL 用于显示
            // 不需要更新 setMessages，因为 UI 显示使用的是 messages 状态，不是数据库中的

          })
          .catch((persistError) => {
            // hooks-contexts-1: never silently drop a background persistence failure
            console.error('[useChat] 上传任务后台持久化失败:', persistError);
          });
      } else {
        // 没有上传任务，直接保存到数据库（会清空 Blob URL）
        const finalMessages = [...updatedMessages, displayModelMessage];
        updateSessionMessages(resolvedSessionId, finalMessages);
      }

      setLoadingStateIfCurrentSession('idle');
    } catch (error: unknown) {
      cancelBufferedStreamUpdates();
      activeHandlerCancelRef.current = null;

      // 清理轮询任务
      pollingManager.cleanup();

      // 显示错误消息
      const errorMessage: Message = {
        id: uuidv4(),
        role: Role.MODEL,
        content: `错误: ${error instanceof Error ? error.message : '未知错误'}`,
        attachments: [],
        timestamp: Date.now(),
        mode: mode,
      };

      setMessagesIfCurrentSession((prev) => {
        const rollbackMessages = modelMessageId
          ? prev.filter((msg) => msg.id !== modelMessageId)
          : prev;
        return [...rollbackMessages, errorMessage];
      });
      setLoadingStateIfCurrentSession('idle');
    }
  };

  return {
    messages,
    setMessages,
    loadingState,
    setLoadingState,
    sendMessage,
    submitResearchAction,
    stopGeneration,
  };
};

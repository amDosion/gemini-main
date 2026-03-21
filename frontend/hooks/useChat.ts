/**
 * useChat Hook - 重构版本
 * 
 * 使用策略模式替代巨大的 if-else 链
 * 修复问题1：创建全局 pollingManager 实例
 * 修复问题2：使用 PreprocessorRegistry 处理文件上传
 */

import { useState, useCallback, useMemo, useEffect, useRef, SetStateAction } from 'react';
import { Message, Role, LoadingState, ChatOptions, Attachment, AppMode, ModelConfig, ToolCall, ToolResult } from '../types/types';
import { v4 as uuidv4 } from 'uuid';
import { llmService } from '../services/llmService';
import { storageUpload } from '../services/storage/storageUpload';

// 导入新的策略模式组件
import { strategyRegistry, preprocessorRegistry } from './handlers/strategyConfig';
import { PollingManager } from './handlers/PollingManager';
import { ExecutionContext, StreamUpdate, HandlerMode, ResearchActionSubmitHandler } from './handlers/types';
import { getUrlType } from './handlers/attachmentUtils';

const AUTO_RESEARCH_CONTEXT_WINDOW = 6;
const AUTO_RESEARCH_EVIDENCE_WINDOW = 20;

type AutoResearchLeadRole = 'selection' | 'ads' | 'listing';

const AUTO_RESEARCH_PERSONA_LEAD_BY_ID: Record<string, AutoResearchLeadRole> = {
  'amazon-selection-strategist': 'selection',
  'amazon-ads-keyword-operator': 'ads',
  'amazon-listing-cvr-optimizer': 'listing',
};

const resolvePersonaKey = (personaId?: string): string => {
  if (!personaId) return '';
  const trimmed = personaId.trim();
  if (!trimmed) return '';
  if (!trimmed.includes(':')) return trimmed;
  return trimmed.split(':').pop()?.trim() || trimmed;
};

const resolveLeadRoleByPersona = (personaId?: string): AutoResearchLeadRole => {
  const key = resolvePersonaKey(personaId);
  return AUTO_RESEARCH_PERSONA_LEAD_BY_ID[key] || 'selection';
};

const describeLeadRole = (role: AutoResearchLeadRole): string => {
  if (role === 'ads') {
    return '广告与关键词主导（B主导，A/C联动）';
  }
  if (role === 'listing') {
    return 'Listing转化主导（C主导，A/B联动）';
  }
  return '选品策略主导（A主导，B/C联动）';
};

const summarizeToolEvidenceForAutoResearch = (
  toolCalls?: ReadonlyArray<ToolCall>,
  toolResults?: ReadonlyArray<ToolResult>,
): string => {
  const calls = toolCalls || [];
  const results = toolResults || [];
  if (calls.length === 0 && results.length === 0) {
    return '无工具调用记录（可能未启用 MCP 或工具未触发）。';
  }

  const callById = new Map<string, ToolCall>();
  for (const call of calls) {
    callById.set(call.id, call);
  }

  const lines: string[] = [];
  lines.push(`工具调用数: ${calls.length}`);
  lines.push(`工具结果数: ${results.length}`);

  const recentResults = results.slice(-AUTO_RESEARCH_EVIDENCE_WINDOW);
  for (let index = 0; index < recentResults.length; index += 1) {
    const result = recentResults[index];
    const call = callById.get(result.callId);
    const toolName = call?.name || result.name || 'unknown_tool';
    const argsText = call?.arguments
      ? JSON.stringify(call.arguments, null, 0).slice(0, 280)
      : '{}';
    const rawResult =
      typeof result.result === 'string'
        ? result.result
        : JSON.stringify(result.result ?? {}, null, 0);
    const resultText = (rawResult || '').slice(0, 420);
    const status = result.error ? `失败: ${result.error}` : '成功';
    lines.push(
      [
        `- [${index + 1}] ${toolName}`,
        `  call_id=${result.callId || 'unknown'}`,
        `  参数=${argsText}`,
        `  状态=${status}`,
        `  摘要=${resultText || '(空结果)'}`,
      ].join('\n')
    );
  }

  if (results.length > recentResults.length) {
    lines.push(`（仅展示最近 ${recentResults.length} 条工具结果，共 ${results.length} 条）`);
  }

  return lines.join('\n');
};

const summarizeContextForAutoResearch = (history: Message[]): string => {
  const sliced = history.slice(-AUTO_RESEARCH_CONTEXT_WINDOW);
  if (sliced.length === 0) return '无';

  return sliced
    .map((message) => {
      const role = message.role === Role.USER ? '用户' : message.role === Role.MODEL ? '助手' : '系统';
      const content = (message.content || '').trim();
      const preview = content.length > 280 ? `${content.slice(0, 280)}...` : content;
      return `[${role}] ${preview || '(空内容)'}`;
    })
    .join('\n');
};

const buildAutoDeepResearchPrompt = (
  userQuestion: string,
  chatAnswer: string,
  contextSummary: string,
  leadRole: AutoResearchLeadRole,
  personaId: string | undefined,
  toolEvidenceSummary: string,
): string => {
  const personaKey = resolvePersonaKey(personaId) || '未指定';
  const leadRoleText = describeLeadRole(leadRole);
  return [
    '你正在执行自动深挖的第二阶段（Deep Research）。',
    '该流程是单次输入触发，你必须在一次响应内完成跨角色联动分析，不允许拆分为多轮提问。',
    '',
    '流程上下文（已完成）：',
    '1) MCP 工具采集（产品/关键词/趋势/排名等）',
    '2) Chat 阶段整理与初步判断',
    '3) 你当前接手：Deep Research 纵深分析与执行方案',
    '',
    '联动规则（强制）：',
    '1. 采用 A/B/C 三角色串联并在单次响应中融合：',
    '   A=选品与市场结构，B=广告与关键词流量，C=Listing与转化优化。',
    `2. 主导视角：${leadRoleText}（来源 persona=${personaKey}）。`,
    '3. 先做证据校验，再给策略，不得直接跳到建议。',
    '4. 必须区分：事实（工具证据）/推断（有不确定性）/执行动作（可落地）。',
    '5. 如数据不足，明确指出缺口与下一步 MCP 补采动作。',
    '',
    '输出格式（强制）：',
    '## 1. 事实核验与不确定性',
    '## 2. A/B/C 串联诊断（产品-关键词-流量-转化-竞争）',
    '## 3. 14/30/90 天执行计划（按优先级）',
    '## 4. KPI 看板（目标值/当前值/阈值/预警）',
    '## 5. 风险、假设与下一步数据补采',
    '',
    `用户原始问题：\n${userQuestion || '(空问题)'}`,
    '',
    `最近会话摘要：\n${contextSummary || '无'}`,
    '',
    `Phase1-Chat 整理结果（待深挖）：\n${chatAnswer || '(空回答)'}`,
    '',
    `Phase1-MCP 工具证据摘要：\n${toolEvidenceSummary}`,
  ].join('\n');
};

const combineAutoDeepResearchContent = (chatContent: string, deepResearchContent: string): string => {
  return [
    chatContent || '',
    '',
    '---',
    '',
    '## Deep Research 深挖补充',
    '',
    deepResearchContent || '',
  ].join('\n');
};

const STREAM_UPDATE_BATCH_INTERVAL_MS = 32;

type ModelMessageUpdater = (message: Message) => Message;

const composeModelMessageUpdaters = (
  previousUpdater: ModelMessageUpdater | null,
  nextUpdater: ModelMessageUpdater,
): ModelMessageUpdater => {
  if (!previousUpdater) return nextUpdater;
  return (message) => nextUpdater(previousUpdater(message));
};

const applyStreamUpdateToModelMessage = (message: Message, update: StreamUpdate): Message => {
  return {
    ...message,
    content: update.content || message.content,
    attachments: update.attachments || message.attachments,
    groundingMetadata: update.groundingMetadata,
    urlContextMetadata: update.urlContextMetadata,
    browserOperationId: update.browserOperationId,
    toolCalls: update.toolCalls || message.toolCalls,
    toolResults: update.toolResults || message.toolResults,
    thoughts: update.thoughts || message.thoughts,
    textResponse: Object.prototype.hasOwnProperty.call(update, 'textResponse')
      ? update.textResponse
      : message.textResponse,
    responseKind: update.responseKind || message.responseKind,
    researchStatus: update.researchStatus || message.researchStatus,
    researchInteractionId: update.researchInteractionId || message.researchInteractionId,
    researchRequiredAction: Object.prototype.hasOwnProperty.call(update, 'researchRequiredAction')
      ? update.researchRequiredAction
      : message.researchRequiredAction,
  };
};

export const useChat = (
  currentSessionId: string | null,
  updateSessionMessages: (
    id: string,
    msgs: Message[],
    options?: { strategy?: 'replace' | 'merge-by-id' },
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
  }, [pollingManager, researchActionHandlersRef]);

  const stopGeneration = useCallback(() => {
      llmService.cancelCurrentStream();
      activeHandlerCancelRef.current?.();
      activeHandlerCancelRef.current = null;
      researchActionHandlersRef.current.clear();
      setLoadingState('idle');
  }, []);

  const submitResearchAction = useCallback(async (messageId: string, selectedInput: unknown) => {
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

    setMessages(prev =>
      prev.map(msg =>
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
  }, [setMessages]);

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

      setMessagesIfCurrentSession(prev =>
        prev.map(msg => (msg.id === modelMessageId ? modelMessageUpdater(msg) : msg))
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
      const contextHistory = baseMessages.filter(m => m.mode === mode || (!m.mode && mode === 'chat'));
      // 增强检索：强制启用联网搜索
      const enhancedOptions = options.enableEnhancedRetrieval
        ? { ...options, enableSearch: true }
        : options;
      const isPrimaryDeepResearch = mode === 'chat' && !!options.enableDeepResearch;
      const isAutoDeepResearch = mode === 'chat' && !isPrimaryDeepResearch && !!options.enableAutoDeepResearch;
      const handlerMode: HandlerMode =
        isPrimaryDeepResearch
          ? 'deep-research'
          : mode;
      const previousResearchInteractionId =
        (isPrimaryDeepResearch || isAutoDeepResearch)
          ? [...contextHistory]
              .reverse()
              .find(
                (message) =>
                  message.role === Role.MODEL &&
                  message.responseKind === 'deep-research' &&
                  !!message.researchInteractionId
              )
              ?.researchInteractionId
          : undefined;

      if ((isPrimaryDeepResearch || isAutoDeepResearch) && !options.deepResearchAgentId?.trim()) {
        throw new Error('请先在工具栏“自动深挖”菜单中选择 Deep Research 专用模型。');
      }
      
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
      setMessagesIfCurrentSession(prev => [...prev, userMessage]); // ✅ 当前会话保留 Blob URL 用于显示
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
        responseKind: handlerMode === 'deep-research' ? 'deep-research' : 'chat',
        researchStatus: handlerMode === 'deep-research'
          ? { status: 'starting', progress: '正在启动 Deep Research...', elapsedTime: 0 }
          : undefined,
      };

      setMessagesIfCurrentSession(prev => [...prev, initialModelMessage]);

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
          ...(result.enhancedPrompt && { enhancedPrompt: result.enhancedPrompt })
        };

        setMessagesIfCurrentSession(prev => prev.map(msg => msg.id === modelMessageId ? chatOnlyMessage : msg));

        const autoContextSummary = summarizeContextForAutoResearch([
          ...contextHistory,
          userMessage,
          chatOnlyMessage,
        ]);
        const autoLeadRole = resolveLeadRoleByPersona(context.options.personaId);
        const toolEvidenceSummary = summarizeToolEvidenceForAutoResearch(
          result.toolCalls,
          result.toolResults,
        );
        const autoPrompt = buildAutoDeepResearchPrompt(
          text,
          result.content,
          autoContextSummary,
          autoLeadRole,
          context.options.personaId,
          toolEvidenceSummary,
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
              content: typeof update.content === 'string'
                ? combineAutoDeepResearchContent(autoResearchBaseContent, update.content)
                : undefined,
            };
            onStreamUpdate(mergedUpdate);
          },
        };

        try {
          const autoDeepResearchHandler = strategyRegistry.getHandler('deep-research');
          const autoDeepResearchResult = await autoDeepResearchHandler.execute(autoDeepResearchContext);
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
          const errorMessage = autoResearchError instanceof Error
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
        researchInteractionId: finalResult.researchInteractionId || initialModelMessage.researchInteractionId,
        researchRequiredAction: finalResult.researchRequiredAction,
        // 存储 thoughts、textResponse、enhancedPrompt（如果存在）
        ...(finalResult.thoughts && { thoughts: finalResult.thoughts }),
        ...(finalResult.textResponse && { textResponse: finalResult.textResponse }),
        ...(finalResult.enhancedPrompt && { enhancedPrompt: finalResult.enhancedPrompt }),
        ...(finalResult.continuationStrategy && { continuationStrategy: finalResult.continuationStrategy }),
        ...(typeof finalResult.videoExtensionCount === 'number' && { videoExtensionCount: finalResult.videoExtensionCount }),
        ...(typeof finalResult.videoExtensionApplied === 'number' && { videoExtensionApplied: finalResult.videoExtensionApplied }),
        ...(typeof finalResult.totalDurationSeconds === 'number' && { totalDurationSeconds: finalResult.totalDurationSeconds }),
        ...(finalResult.continuedFromVideo && { continuedFromVideo: finalResult.continuedFromVideo }),
        ...(typeof finalResult.storyboardShotSeconds === 'number' && { storyboardShotSeconds: finalResult.storyboardShotSeconds }),
        ...(typeof finalResult.generateAudio === 'boolean' && { generateAudio: finalResult.generateAudio }),
        ...(finalResult.personGeneration && { personGeneration: finalResult.personGeneration }),
        ...(finalResult.subtitleMode && { subtitleMode: finalResult.subtitleMode }),
        ...(finalResult.subtitleLanguage && { subtitleLanguage: finalResult.subtitleLanguage }),
        ...(finalResult.subtitleAttachmentIds && finalResult.subtitleAttachmentIds.length > 0 && { subtitleAttachmentIds: [...finalResult.subtitleAttachmentIds] }),
        ...(finalResult.trackedFeature && { trackedFeature: finalResult.trackedFeature }),
        ...(finalResult.trackingOverlayText && { trackingOverlayText: finalResult.trackingOverlayText }),
      };

      // ✅ 调试日志：检查 thoughts/textResponse/enhancedPrompt 是否被添加到消息中
      console.log('[useChat] 📝 displayModelMessage 元数据字段:', {
        hasThoughts: !!displayModelMessage.thoughts,
        thoughtsLength: displayModelMessage.thoughts?.length || 0,
        hasTextResponse: !!displayModelMessage.textResponse,
        hasEnhancedPrompt: !!displayModelMessage.enhancedPrompt,
        resultHasThoughts: !!finalResult.thoughts,
        resultHasTextResponse: !!finalResult.textResponse,
        resultHasEnhancedPrompt: !!finalResult.enhancedPrompt
      });

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

      setMessagesIfCurrentSession(prev => prev.map(msg => msg.id === modelMessageId ? displayModelMessage : msg));

      // 10. Handle upload task (if any)
      if (finalResult.uploadTask) {
        finalResult.uploadTask.then(({ dbAttachments, dbUserAttachments }) => {
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
              researchInteractionId: finalResult.researchInteractionId || initialModelMessage.researchInteractionId,
              researchRequiredAction: finalResult.researchRequiredAction,
              ...(finalResult.thoughts && { thoughts: finalResult.thoughts }),
              ...(finalResult.textResponse && { textResponse: finalResult.textResponse }),
              ...(finalResult.enhancedPrompt && { enhancedPrompt: finalResult.enhancedPrompt }),
              ...(finalResult.continuationStrategy && { continuationStrategy: finalResult.continuationStrategy }),
              ...(typeof finalResult.videoExtensionCount === 'number' && { videoExtensionCount: finalResult.videoExtensionCount }),
              ...(typeof finalResult.videoExtensionApplied === 'number' && { videoExtensionApplied: finalResult.videoExtensionApplied }),
              ...(typeof finalResult.totalDurationSeconds === 'number' && { totalDurationSeconds: finalResult.totalDurationSeconds }),
              ...(finalResult.continuedFromVideo && { continuedFromVideo: finalResult.continuedFromVideo }),
              ...(typeof finalResult.storyboardShotSeconds === 'number' && { storyboardShotSeconds: finalResult.storyboardShotSeconds }),
              ...(typeof finalResult.generateAudio === 'boolean' && { generateAudio: finalResult.generateAudio }),
              ...(finalResult.personGeneration && { personGeneration: finalResult.personGeneration }),
              ...(finalResult.subtitleMode && { subtitleMode: finalResult.subtitleMode }),
              ...(finalResult.subtitleLanguage && { subtitleLanguage: finalResult.subtitleLanguage }),
              ...(finalResult.subtitleAttachmentIds && finalResult.subtitleAttachmentIds.length > 0 && { subtitleAttachmentIds: [...finalResult.subtitleAttachmentIds] }),
              ...(finalResult.trackedFeature && { trackedFeature: finalResult.trackedFeature }),
              ...(finalResult.trackingOverlayText && { trackingOverlayText: finalResult.trackingOverlayText }),
            };

          // ✅ 保存到数据库的消息（会清空 Blob URL）
          const dbMessages = [
            ...baseMessages.filter(m => m.id !== userMessage.id),
            dbUserMessage,
            dbModelMessage
          ];

          // ✅ 保存到数据库（会清空 Blob URL，用于持久化）
          updateSessionMessages(resolvedSessionId, dbMessages, {
            strategy: 'merge-by-id',
          });
          
          // ✅ 重要：当前会话的 messages 状态保留 Blob URL 用于显示
          // 不需要更新 setMessages，因为 UI 显示使用的是 messages 状态，不是数据库中的
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
        // 没有上传任务，直接保存到数据库（会清空 Blob URL）
        const finalMessages = [...updatedMessages, displayModelMessage];
        updateSessionMessages(resolvedSessionId, finalMessages);
      }

      setLoadingStateIfCurrentSession('idle');

    } catch (error: any) {
      console.error('[useChat] 执行失败:', error);
      cancelBufferedStreamUpdates();
      activeHandlerCancelRef.current = null;
      
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

      setMessagesIfCurrentSession(prev => {
        const rollbackMessages = modelMessageId
          ? prev.filter(msg => msg.id !== modelMessageId)
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

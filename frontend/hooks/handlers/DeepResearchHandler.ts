import { reportError } from '../../utils/globalErrorHandler';
import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { getAuthHeaders } from '../../services/apiClient';
import {
  DEFAULT_DEEP_RESEARCH_STREAM_POLICY,
  fetchDeepResearchStreamPolicy,
} from '../../services/runtimePolicies';
import { uploadFormDataWithXhr } from '../../services/httpProgress';
import { ResearchRequiredAction, ToolCall, ToolResult } from '../../types/types';

const DELTA_TOOL_CALL_TYPES = new Set<string>([
  'function_call',
  'google_search_call',
  'code_execution_call',
  'url_context_call',
  'computer_call',
  'mcp_server_tool_call',
  'file_search_call',
]);

const DELTA_TOOL_RESULT_TYPES = new Set<string>([
  'function_result',
  'google_search_result',
  'code_execution_result',
  'url_context_result',
  'computer_result',
  'mcp_server_tool_result',
  'file_search_result',
]);

type DeepResearchStatus =
  | 'starting'
  | 'in_progress'
  | 'reconnecting'
  | 'awaiting_action'
  | 'completed'
  | 'failed'
  | 'cancelled';

const isRecord = (value: unknown): value is Record<string, any> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const extractTextFromDelta = (delta: Record<string, any>): string => {
  if (typeof delta.text === 'string') return delta.text;
  if (isRecord(delta.content) && typeof delta.content.text === 'string') {
    return delta.content.text;
  }
  if (typeof delta.thought === 'string') return delta.thought;
  return '';
};

const pickToolName = (payload: Record<string, any>, fallbackType: string): string => {
  const direct = payload.name || payload.tool || payload.label;
  if (typeof direct === 'string' && direct.trim()) {
    return direct.trim();
  }

  const nestedFields = [
    payload.functionCall,
    payload.function_call,
    payload.googleSearchCall,
    payload.google_search_call,
    payload.codeExecutionCall,
    payload.code_execution_call,
    payload.urlContextCall,
    payload.url_context_call,
    payload.computerCall,
    payload.computer_call,
    payload.mcpServerToolCall,
    payload.mcp_server_tool_call,
    payload.fileSearchCall,
    payload.file_search_call,
  ];

  for (const field of nestedFields) {
    if (isRecord(field) && typeof field.name === 'string' && field.name.trim()) {
      return field.name.trim();
    }
  }

  return fallbackType || 'unknown';
};

const pickToolArgs = (payload: Record<string, any>): Record<string, any> => {
  if (isRecord(payload.args)) return payload.args;
  if (isRecord(payload.arguments)) return payload.arguments;
  if (isRecord(payload.input)) return payload.input;

  const nested = payload.functionCall || payload.function_call;
  if (isRecord(nested)) {
    if (isRecord(nested.args)) return nested.args;
    if (isRecord(nested.arguments)) return nested.arguments;
  }

  const args: Record<string, any> = {};
  for (const [key, value] of Object.entries(payload)) {
    if (['type', 'id', 'callId', 'call_id', 'name', 'tool', 'error', 'result', 'output'].includes(key)) {
      continue;
    }
    args[key] = value;
  }
  return args;
};

const normalizeToolCall = (
  payload: Record<string, any>,
  fallbackType: string,
  fallbackId: string
): ToolCall => {
  const id =
    (typeof payload.id === 'string' && payload.id) ||
    (typeof payload.callId === 'string' && payload.callId) ||
    (typeof payload.call_id === 'string' && payload.call_id) ||
    fallbackId;

  return {
    id,
    type: fallbackType || 'function_call',
    name: pickToolName(payload, fallbackType),
    arguments: pickToolArgs(payload),
  };
};

const normalizeToolResult = (
  payload: Record<string, any>,
  fallbackType: string,
  fallbackId: string,
  calls: ToolCall[],
  results: ToolResult[]
): ToolResult => {
  const toolName = pickToolName(payload, fallbackType);

  let callId =
    (typeof payload.callId === 'string' && payload.callId) ||
    (typeof payload.call_id === 'string' && payload.call_id) ||
    (typeof payload.id === 'string' && payload.id) ||
    '';

  if (!callId) {
    const unresolved = [...calls].reverse().find((call) => {
      if (call.name !== toolName) return false;
      return !results.some((result) => result.callId === call.id);
    });
    callId = unresolved?.id || fallbackId;
  }

  const resultPayload =
    payload.result ??
    payload.output ??
    payload.functionResult ??
    payload.function_result ??
    payload;

  return {
    name: toolName,
    callId,
    result: resultPayload,
    error: typeof payload.error === 'string' ? payload.error : undefined,
    screenshot: typeof payload.screenshot === 'string' ? payload.screenshot : undefined,
    screenshotUrl:
      typeof payload.screenshotUrl === 'string'
        ? payload.screenshotUrl
        : (typeof payload.screenshot_url === 'string' ? payload.screenshot_url : undefined),
  };
};

const extractRequiredAction = (eventPayload: Record<string, any>): ResearchRequiredAction | undefined => {
  const candidates = [
    eventPayload.requiresAction,
    eventPayload.requiredAction,
    isRecord(eventPayload.interaction) ? eventPayload.interaction.requiresAction : undefined,
    isRecord(eventPayload.interaction) ? eventPayload.interaction.requiredAction : undefined,
    isRecord(eventPayload.status) ? eventPayload.status.requiresAction : undefined,
    isRecord(eventPayload.status) ? eventPayload.status.requiredAction : undefined,
  ];

  for (const candidate of candidates) {
    if (isRecord(candidate)) {
      return candidate as ResearchRequiredAction;
    }
  }

  return undefined;
};

const pickFirstString = (...values: unknown[]): string | undefined => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
};

const findUnresolvedToolCall = (toolCalls: ToolCall[], toolResults: ToolResult[]): ToolCall | undefined =>
  [...toolCalls]
    .reverse()
    .find((call) => !toolResults.some((result) => result.callId === call.id));

const extractRequiredActionCallId = (
  requiredAction: ResearchRequiredAction | undefined,
  toolCalls: ToolCall[],
  toolResults: ToolResult[]
): string | undefined => {
  if (requiredAction && isRecord(requiredAction)) {
    const directId = pickFirstString(
      requiredAction.callId,
      requiredAction.call_id,
      requiredAction.toolCallId,
      requiredAction.tool_call_id,
      requiredAction.functionCallId,
      requiredAction.function_call_id
    );
    if (directId) return directId;

    const act = isRecord(requiredAction.act) ? requiredAction.act : undefined;
    const actId = act
      ? pickFirstString(
          act.callId,
          act.call_id,
          act.toolCallId,
          act.tool_call_id,
          act.functionCallId,
          act.function_call_id
        )
      : undefined;
    if (actId) return actId;

    const candidates = [
      requiredAction.toolCall,
      requiredAction.tool_call,
      requiredAction.action,
      requiredAction.submitToolOutputs,
      requiredAction.submit_tool_outputs,
      requiredAction.requiredAction,
      requiredAction.requiresAction,
      requiredAction.required_action,
      requiredAction.requires_action,
    ];

    for (const candidate of candidates) {
      if (!isRecord(candidate)) continue;
      const candidateId = pickFirstString(
        candidate.callId,
        candidate.call_id,
        candidate.toolCallId,
        candidate.tool_call_id,
        candidate.functionCallId,
        candidate.function_call_id
      );
      if (candidateId) return candidateId;

      const toolCallsValue = candidate.toolCalls || candidate.tool_calls;
      if (Array.isArray(toolCallsValue) && toolCallsValue.length > 0) {
        for (const raw of toolCallsValue) {
          if (!isRecord(raw)) continue;
          const rawId = pickFirstString(
            raw.callId,
            raw.call_id,
            raw.id,
            raw.toolCallId,
            raw.tool_call_id
          );
          if (rawId) return rawId;
        }
      }
    }
  }

  return findUnresolvedToolCall(toolCalls, toolResults)?.id;
};

const extractRequiredActionName = (
  requiredAction: ResearchRequiredAction | undefined,
  toolCalls: ToolCall[],
  toolResults: ToolResult[],
  callId: string
): string | undefined => {
  if (requiredAction && isRecord(requiredAction.act) && typeof requiredAction.act.name === 'string') {
    return requiredAction.act.name;
  }
  const matchedCall = toolCalls.find((call) => call.id === callId);
  if (matchedCall?.name) return matchedCall.name;
  return findUnresolvedToolCall(toolCalls, toolResults)?.name;
};

const extractStatusText = (eventPayload: Record<string, any>): string | undefined => {
  const status = eventPayload.status;
  if (typeof status === 'string' && status.trim()) {
    return status.trim();
  }

  if (isRecord(status)) {
    for (const key of ['status', 'state', 'phase', 'message']) {
      const value = status[key];
      if (typeof value === 'string' && value.trim()) {
        return value.trim();
      }
    }
  }

  const interaction = eventPayload.interaction;
  if (isRecord(interaction) && typeof interaction.status === 'string' && interaction.status.trim()) {
    return interaction.status.trim();
  }

  return undefined;
};

const extractInteractionOutputs = (eventPayload: Record<string, unknown>): unknown[] => {
  const interaction = eventPayload.interaction;
  if (!isRecord(interaction)) return [];

  if (Array.isArray(interaction.outputs)) return interaction.outputs;
  if (Array.isArray(interaction.output)) return interaction.output;
  return [];
};

const collectTextsFromOutputValue = (value: unknown, texts: string[], depth = 0) => {
  if (depth > 6 || value == null) return;

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed) texts.push(trimmed);
    return;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      collectTextsFromOutputValue(item, texts, depth + 1);
    }
    return;
  }

  if (!isRecord(value)) return;

  if (typeof value.text === 'string' && value.text.trim()) {
    texts.push(value.text.trim());
  }

  for (const key of ['content', 'parts', 'result', 'output', 'outputs']) {
    if (key in value) {
      collectTextsFromOutputValue(value[key], texts, depth + 1);
    }
  }
};

const extractTextFromOutputs = (outputs: unknown[]): string => {
  if (!Array.isArray(outputs) || outputs.length === 0) return '';
  const texts: string[] = [];
  collectTextsFromOutputValue(outputs, texts, 0);
  const unique = [...new Set(texts.map((item) => item.trim()).filter(Boolean))];
  return unique.join('\n\n').trim();
};

export class DeepResearchHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const { text, attachments, onStreamUpdate, previousResearchInteractionId } = context;
    const deepResearchAgentId = context.options.deepResearchAgentId?.trim();
    if (!deepResearchAgentId) {
      throw new Error('未配置 Deep Research 专用模型，请先在工具栏选择模型。');
    }
    const startedAt = Date.now();
    const elapsedTime = () => Math.floor((Date.now() - startedAt) / 1000);
    const buildStatus = (status: DeepResearchStatus, progress: string) => ({
      status,
      progress,
      elapsedTime: elapsedTime(),
    });
    const deepResearchPolicy = await fetchDeepResearchStreamPolicy();
    const deepResearchIdleTimeoutMs = deepResearchPolicy.idleTimeoutMs || DEFAULT_DEEP_RESEARCH_STREAM_POLICY.idleTimeoutMs;
    const deepResearchWatchdogIntervalMs = deepResearchPolicy.watchdogIntervalMs || DEFAULT_DEEP_RESEARCH_STREAM_POLICY.watchdogIntervalMs;
    const deepResearchMaxRecoveryAttempts =
      deepResearchPolicy.maxRecoveryAttempts || DEFAULT_DEEP_RESEARCH_STREAM_POLICY.maxRecoveryAttempts;

    // 1. 如果有附件，先上传到 File Search Store
    let fileSearchStoreNames: string[] | undefined;

    if (attachments && attachments.length > 0) {
      onStreamUpdate?.({
        responseKind: 'deep-research',
        researchStatus: buildStatus('starting', '正在上传文档到研究存储...'),
      });

      try {
        const uploadedStores: string[] = [];

        for (const attachment of attachments) {
          let fileBlob: Blob;

          const sourceUrl = attachment.url || attachment.tempUrl;
          if (!sourceUrl) {
            throw new Error(`附件缺少可读取 URL: ${attachment.name || attachment.id}`);
          }

          const response = await fetch(sourceUrl);
          fileBlob = await response.blob();

          const formData = new FormData();
          formData.append('file', fileBlob, attachment.name || 'document');

          const uploadData = await uploadFormDataWithXhr<any>({
            url: '/api/file-search/upload',
            formData,
            headers: getAuthHeaders(),
            withCredentials: true,
            timeoutMs: 120_000,
            onUploadProgress: (progress) => {
              if (progress.percent === null) return;
              onStreamUpdate?.({
                responseKind: 'deep-research',
                researchStatus: buildStatus(
                  'starting',
                  `正在上传文档 ${attachment.name || 'unnamed'} (${progress.percent}%)`
                ),
              });
            },
          });

          uploadedStores.push(uploadData.file_search_store_name);

          onStreamUpdate?.({
            responseKind: 'deep-research',
            researchStatus: buildStatus('starting', `已上传文档: ${attachment.name || 'unnamed'}`),
          });
        }

        fileSearchStoreNames = [...new Set(uploadedStores)];

        onStreamUpdate?.({
          responseKind: 'deep-research',
          researchStatus: buildStatus('starting', '文档上传完成，开始深度研究...'),
        });
      } catch (error) {
        throw new Error(`文档上传失败: ${error instanceof Error ? error.message : String(error)}`);
      }
    }

    // 2. 启动流式研究任务
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    };

    const thinkingSummaries: 'auto' | 'none' = 'auto';

    const startResponse = await fetch('/api/research/stream/start', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        prompt: text,
        agent: deepResearchAgentId,
        background: true,
        stream: false,
        previous_interaction_id: previousResearchInteractionId,
        agent_config: {
          type: 'deep-research',
          thinkingSummaries,
        },
        file_search_store_names: fileSearchStoreNames,
      }),
    });

    if (!startResponse.ok) {
      const errorText = await startResponse.text();
      throw new Error(`Failed to start research task: ${startResponse.statusText} - ${errorText}`);
    }

    const startData = await startResponse.json();
    const initialInteractionId: string | undefined = startData.interactionId;

    if (!initialInteractionId) {
      throw new Error('Failed to start research task: No interactionId received.');
    }

    onStreamUpdate?.({
      responseKind: 'deep-research',
      researchInteractionId: initialInteractionId,
      researchStatus: buildStatus(
        'starting',
        fileSearchStoreNames && fileSearchStoreNames.length > 0
          ? 'Deep Research 已启动，正在分析文档与问题...'
          : 'Deep Research 已启动，正在分析问题...'
      ),
      toolCalls: [],
      toolResults: [],
      researchRequiredAction: undefined,
    });

    // 3. 使用 EventSource 接收 SSE 流（主动空闲检测 + 断线恢复 + Last-Event-ID 续流）
    return new Promise((resolve, reject) => {
      let currentInteractionId = initialInteractionId;
      let accumulatedText = '';
      let accumulatedThoughts = '';
      const accumulatedToolCalls: ToolCall[] = [];
      const accumulatedToolResults: ToolResult[] = [];
      let latestEventId: string | null = null;
      let isComplete = false;
      let isRecovering = false;
      let recoveryAttempts = 0;
      let lastActivityAt = Date.now();
      let watchdogTimer: ReturnType<typeof setInterval> | null = null;
      let currentEventSource: EventSource | null = null;
      let lastGroundingMetadata: unknown = undefined;
      let lastRequiredAction: ResearchRequiredAction | undefined = undefined;

      const touchActivity = () => {
        lastActivityAt = Date.now();
      };

      const closeEventSource = () => {
        currentEventSource?.close();
        currentEventSource = null;
      };

      const clearWatchdog = () => {
        if (watchdogTimer) {
          clearInterval(watchdogTimer);
          watchdogTimer = null;
        }
      };

      const buildPartialContent = (_closeThinking = true): string => {
        return accumulatedText;
      };

      const buildThoughts = () => {
        if (!accumulatedThoughts) return undefined;
        return [{ type: 'text' as const, content: accumulatedThoughts }];
      };

      const upsertToolCall = (call: ToolCall) => {
        const existingIndex = accumulatedToolCalls.findIndex((item) => item.id === call.id);
        if (existingIndex >= 0) {
          accumulatedToolCalls[existingIndex] = call;
        } else {
          accumulatedToolCalls.push(call);
        }
      };

      const upsertToolResult = (result: ToolResult) => {
        const existingIndex = accumulatedToolResults.findIndex((item) => item.callId === result.callId);
        if (existingIndex >= 0) {
          accumulatedToolResults[existingIndex] = result;
        } else {
          accumulatedToolResults.push(result);
        }
      };

      const emitProgress = (status: DeepResearchStatus, progress: string, closeThinking = true) => {
        onStreamUpdate?.({
          content: buildPartialContent(closeThinking),
          thoughts: buildThoughts(),
          textResponse: accumulatedText || undefined,
          groundingMetadata: lastGroundingMetadata,
          toolCalls: [...accumulatedToolCalls],
          toolResults: [...accumulatedToolResults],
          responseKind: 'deep-research',
          researchInteractionId: currentInteractionId,
          researchStatus: buildStatus(status, progress),
          researchRequiredAction: lastRequiredAction,
        });
      };

      const hydrateToolsFromOutputs = (outputs: unknown[]) => {
        if (!Array.isArray(outputs) || outputs.length === 0) return;

        for (const output of outputs) {
          if (!isRecord(output)) continue;
          const outputType = typeof output.type === 'string' ? output.type : '';
          if (!outputType) continue;

          if (DELTA_TOOL_CALL_TYPES.has(outputType)) {
            const call = normalizeToolCall(
              output,
              outputType,
              `tool_call_${Date.now()}_${accumulatedToolCalls.length + 1}`
            );
            upsertToolCall(call);
          } else if (DELTA_TOOL_RESULT_TYPES.has(outputType)) {
            const result = normalizeToolResult(
              output,
              outputType,
              `tool_result_${Date.now()}_${accumulatedToolResults.length + 1}`,
              accumulatedToolCalls,
              accumulatedToolResults
            );
            upsertToolResult(result);
          }
        }
      };

      const hydrateTextFromOutputs = (outputs: unknown[]) => {
        const extracted = extractTextFromOutputs(outputs);
        if (!extracted) return;
        if (!accumulatedText) {
          accumulatedText = extracted;
          return;
        }
        if (accumulatedText.includes(extracted)) {
          return;
        }
        if (extracted.includes(accumulatedText)) {
          accumulatedText = extracted;
          return;
        }
        accumulatedText = `${accumulatedText}\n\n${extracted}`;
      };

      const finalizeCompleted = (progress = 'Deep Research 已完成') => {
        if (isComplete) return;
        isComplete = true;
        clearWatchdog();
        closeEventSource();
        lastRequiredAction = undefined;

        const finalContent = accumulatedText || '研究已完成。';

        context.registerResearchActionHandler?.(currentInteractionId, null);
        resolve({
          content: finalContent,
          thoughts: buildThoughts(),
          textResponse: finalContent,
          attachments: [],
          groundingMetadata: lastGroundingMetadata,
          toolCalls: accumulatedToolCalls,
          toolResults: accumulatedToolResults,
          responseKind: 'deep-research',
          researchStatus: buildStatus('completed', progress),
          researchInteractionId: currentInteractionId,
          researchRequiredAction: undefined,
        });
      };

      const finalizeFailed = (errorMessage: string, progress: string) => {
        if (isComplete) return;
        isComplete = true;
        clearWatchdog();
        closeEventSource();
        context.registerResearchActionHandler?.(currentInteractionId, null);

        if (accumulatedText || accumulatedThoughts) {
          const baseContent = accumulatedText || '研究未返回正文内容。';
          const partialContent = `${baseContent}\n\n⚠️ ${errorMessage}`;

          resolve({
            content: partialContent,
            thoughts: buildThoughts(),
            textResponse: baseContent,
            attachments: [],
            toolCalls: accumulatedToolCalls,
            toolResults: accumulatedToolResults,
            responseKind: 'deep-research',
            researchStatus: buildStatus('failed', progress),
            researchInteractionId: currentInteractionId,
            researchRequiredAction: lastRequiredAction,
          });
          return;
        }

        reject(new Error(errorMessage || 'Unknown error during research'));
      };

      const finalizeCancelled = (progress = 'Deep Research 已停止') => {
        if (isComplete) return;
        isComplete = true;
        clearWatchdog();
        closeEventSource();
        context.registerResearchActionHandler?.(currentInteractionId, null);
        resolve({
          content: buildPartialContent(),
          thoughts: buildThoughts(),
          textResponse: accumulatedText || undefined,
          attachments: [],
          groundingMetadata: lastGroundingMetadata,
          toolCalls: accumulatedToolCalls,
          toolResults: accumulatedToolResults,
          responseKind: 'deep-research',
          researchStatus: buildStatus('cancelled', progress),
          researchInteractionId: currentInteractionId,
          researchRequiredAction: lastRequiredAction,
        });
      };

      const fetchInteractionStatus = async () => {
        const response = await fetch(
          `/api/research/stream/status/${encodeURIComponent(currentInteractionId)}`,
          {
            method: 'GET',
            headers: {
              ...getAuthHeaders(),
            },
          }
        );
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`获取研究状态失败: ${response.status} ${response.statusText} - ${errorText}`);
        }
        return response.json();
      };

      let connectSSE: () => void = () => {};
      const reconnectWithStatusCheck = async (reason: string) => {
        if (isComplete || isRecovering) return;

        isRecovering = true;
        recoveryAttempts += 1;
        emitProgress(
          'reconnecting',
          `连接异常（${reason}），正在恢复（${recoveryAttempts}/${deepResearchMaxRecoveryAttempts}）...`
        );

        closeEventSource();

        try {
          const statusSnapshot = await fetchInteractionStatus();
          const statusText =
            (typeof statusSnapshot?.status === 'string' ? statusSnapshot.status : '') || 'in_progress';
          const outputs = Array.isArray(statusSnapshot?.outputs) ? statusSnapshot.outputs : [];
          const snapshotRequiredAction = extractRequiredAction(
            isRecord(statusSnapshot) ? statusSnapshot : {}
          );

          if (snapshotRequiredAction) {
            lastRequiredAction = snapshotRequiredAction;
          }

          if (outputs.length > 0) {
            hydrateToolsFromOutputs(outputs);
            hydrateTextFromOutputs(outputs);
          }

          if (statusText === 'completed') {
            finalizeCompleted('Deep Research 已完成（状态恢复）');
            return;
          }

          if (statusText === 'cancelled') {
            finalizeCancelled('研究任务已取消（状态恢复）');
            return;
          }

          if (statusText === 'failed') {
            const errorPayload = statusSnapshot?.error;
            const statusErrorMessage =
              typeof errorPayload === 'string'
                ? errorPayload
                : (errorPayload?.message || `研究任务状态: ${statusText}`);
            finalizeFailed(statusErrorMessage, `研究失败（状态恢复）: ${statusText}`);
            return;
          }

          if ((statusText === 'requires_action' || snapshotRequiredAction) && snapshotRequiredAction) {
            const actionName =
              (isRecord(snapshotRequiredAction.act) && typeof snapshotRequiredAction.act.name === 'string')
                ? snapshotRequiredAction.act.name
                : '需要外部动作';
            emitProgress('awaiting_action', `等待动作: ${actionName}`);
            return;
          }

          if (recoveryAttempts > deepResearchMaxRecoveryAttempts) {
            finalizeFailed(
              `连接恢复次数过多（最后事件: ${latestEventId || 'unknown'}）`,
              '连接恢复失败，返回部分结果'
            );
            return;
          }

          emitProgress('reconnecting', '状态检查完成，正在重新连接研究流...');
          connectSSE();
        } catch (error) {
          if (recoveryAttempts > deepResearchMaxRecoveryAttempts) {
            const msg = error instanceof Error ? error.message : String(error);
            finalizeFailed(`自动恢复失败: ${msg}`, '连接恢复失败，返回部分结果');
            return;
          }
          emitProgress('reconnecting', '状态检查失败，正在重连研究流...');
          connectSSE();
        } finally {
          isRecovering = false;
        }
      };

      const startWatchdog = () => {
        clearWatchdog();
        watchdogTimer = setInterval(() => {
          if (isComplete || isRecovering) return;
          const idleMs = Date.now() - lastActivityAt;
          if (idleMs < deepResearchIdleTimeoutMs) return;
          void reconnectWithStatusCheck(`空闲超时 ${Math.floor(idleMs / 1000)}s`);
        }, deepResearchWatchdogIntervalMs);
      };

      const finalizeByCancel = async () => {
        if (isComplete) return;
        await fetch(`/api/research/stream/cancel/${currentInteractionId}`, {
          method: 'POST',
          headers,
        });
        finalizeCancelled('Deep Research 已停止');
      };

      context.registerCancel?.(() => {
        void finalizeByCancel();
      });

      const registerResearchActionHandler = (interactionId: string) => {
        context.registerResearchActionHandler?.(interactionId, async (selectedInput: unknown) => {
          if (isComplete) {
            throw new Error('研究任务已结束，无法提交动作');
          }

          if (!lastRequiredAction) {
            throw new Error('当前没有待提交的动作');
          }

          const callId = extractRequiredActionCallId(
            lastRequiredAction,
            accumulatedToolCalls,
            accumulatedToolResults
          );
          if (!callId) {
            throw new Error('无法确定 requires_action 对应的 call_id');
          }

          const actionName = extractRequiredActionName(
            lastRequiredAction,
            accumulatedToolCalls,
            accumulatedToolResults,
            callId
          );

          const actionResponse = await fetch('/api/research/stream/action', {
            method: 'POST',
            headers,
            body: JSON.stringify({
              agent: deepResearchAgentId,
              previous_interaction_id: currentInteractionId,
              call_id: callId,
              result: selectedInput,
              name: actionName,
            }),
          });

          if (!actionResponse.ok) {
            const errorText = await actionResponse.text();
            throw new Error(
              `提交 Deep Research 动作失败: ${actionResponse.statusText} - ${errorText}`
            );
          }

          const actionData = await actionResponse.json();
          const nextInteractionId: string | undefined = actionData.interactionId;
          if (!nextInteractionId) {
            throw new Error('提交动作后未收到新的 interactionId');
          }

          const previousInteractionId = currentInteractionId;
          closeEventSource();
          touchActivity();

          currentInteractionId = nextInteractionId;
          latestEventId = null;
          lastRequiredAction = undefined;
          recoveryAttempts = 0;

          context.registerResearchActionHandler?.(previousInteractionId, null);
          registerResearchActionHandler(currentInteractionId);

          onStreamUpdate?.({
            content: buildPartialContent(),
            thoughts: buildThoughts(),
            textResponse: accumulatedText || undefined,
            groundingMetadata: lastGroundingMetadata,
            toolCalls: [...accumulatedToolCalls],
            toolResults: [...accumulatedToolResults],
            responseKind: 'deep-research',
            researchInteractionId: currentInteractionId,
            researchStatus: buildStatus('in_progress', '动作已提交，继续研究...'),
            researchRequiredAction: undefined,
          });

          connectSSE();
        });
      };

      connectSSE = () => {
        if (isComplete) return;
        const query = latestEventId ? `?last_event_id=${encodeURIComponent(latestEventId)}` : '';
        const sseUrl = `/api/research/stream/${currentInteractionId}${query}`;

        const eventSource = new EventSource(sseUrl);
        currentEventSource = eventSource;
        touchActivity();


        eventSource.onopen = () => {
          touchActivity();
          recoveryAttempts = 0;
          onStreamUpdate?.({
            responseKind: 'deep-research',
            researchStatus: buildStatus('in_progress', '已连接研究流，正在执行...'),
          });
        };

        eventSource.onmessage = (event) => {
          touchActivity();
          recoveryAttempts = 0;
          try {
            const data = JSON.parse(event.data);
            const eventType = data.eventType;

            const receivedEventId =
              (typeof event.lastEventId === 'string' && event.lastEventId) ||
              (typeof data.eventId === 'string' ? data.eventId : undefined);
            if (receivedEventId) {
              latestEventId = receivedEventId;
            }

            if (eventType === 'content.delta') {
              const delta = isRecord(data.delta) ? data.delta : {};
              const deltaType = typeof delta.type === 'string' ? delta.type : '';

              if (deltaType === 'text') {
                const textDelta = extractTextFromDelta(delta);
                if (textDelta) {
                  accumulatedText += textDelta;
                }
                lastRequiredAction = undefined;
                emitProgress('in_progress', '正在生成研究结论...');
                return;
              }

              if (deltaType === 'thought_summary' || deltaType === 'thought') {
                const thoughtText = extractTextFromDelta(delta);
                if (thoughtText) {
                  accumulatedThoughts += (accumulatedThoughts ? '\n\n' : '') + thoughtText;
                }
                lastRequiredAction = undefined;
                emitProgress('in_progress', '正在思考与分析...', false);
                return;
              }

              if (DELTA_TOOL_CALL_TYPES.has(deltaType)) {
                const call = normalizeToolCall(
                  delta,
                  deltaType,
                  data.eventId || `tool_call_${Date.now()}_${accumulatedToolCalls.length + 1}`
                );
                upsertToolCall(call);
                lastRequiredAction = undefined;
                emitProgress('in_progress', `正在调用工具: ${call.name}`);
                return;
              }

              if (DELTA_TOOL_RESULT_TYPES.has(deltaType)) {
                const result = normalizeToolResult(
                  delta,
                  deltaType,
                  data.eventId || `tool_result_${Date.now()}_${accumulatedToolResults.length + 1}`,
                  accumulatedToolCalls,
                  accumulatedToolResults
                );
                upsertToolResult(result);
                lastRequiredAction = undefined;
                emitProgress('in_progress', `工具返回结果: ${result.name}`);
                return;
              }

              // 兜底：部分 SDK 版本可能在未知 delta 类型里仍返回 text/content.text
              const genericText = extractTextFromDelta(delta);
              if (genericText) {
                accumulatedText += genericText;
                lastRequiredAction = undefined;
                emitProgress('in_progress', '正在生成研究结论...');
              }
              return;
            }

            if (eventType === 'interaction.status_update') {
              const statusText = extractStatusText(data) || '处理中';
              const requiredAction = extractRequiredAction(data);
              lastRequiredAction = requiredAction;

              if (requiredAction) {
                const actionName =
                  (isRecord(requiredAction.act) && typeof requiredAction.act.name === 'string')
                    ? requiredAction.act.name
                    : '需要外部动作';
                emitProgress('awaiting_action', `等待动作: ${actionName}`);
              } else {
                emitProgress('in_progress', `状态更新: ${statusText}`);
              }
              return;
            }

            if (eventType === 'tool.call') {
              const rawToolCall = isRecord(data.toolCall) ? data.toolCall : {};
              const call = normalizeToolCall(
                rawToolCall,
                typeof rawToolCall.type === 'string' ? rawToolCall.type : 'function_call',
                data.eventId || `tool_call_${Date.now()}_${accumulatedToolCalls.length + 1}`
              );
              upsertToolCall(call);
              lastRequiredAction = undefined;
              emitProgress('in_progress', `正在调用工具: ${call.name}`);
              return;
            }

            if (eventType === 'tool.result') {
              const rawToolResult = isRecord(data.toolResult) ? data.toolResult : {};
              const result = normalizeToolResult(
                rawToolResult,
                typeof rawToolResult.type === 'string' ? rawToolResult.type : 'function_result',
                data.eventId || `tool_result_${Date.now()}_${accumulatedToolResults.length + 1}`,
                accumulatedToolCalls,
                accumulatedToolResults
              );
              upsertToolResult(result);
              lastRequiredAction = undefined;
              emitProgress('in_progress', `工具返回结果: ${result.name}`);
              return;
            }

            if (eventType === 'interaction.complete') {

              if (data.groundingMetadata) {
                lastGroundingMetadata = data.groundingMetadata;
              }

              const outputs = extractInteractionOutputs(data);
              hydrateToolsFromOutputs(outputs);
              hydrateTextFromOutputs(outputs);
              finalizeCompleted('Deep Research 已完成');
              return;
            }

            if (eventType === 'error') {
              const errorMessage =
                typeof data.error === 'string'
                  ? data.error
                  : (data.error?.message || JSON.stringify(data.error));
              finalizeFailed(`研究过程中出现错误: ${errorMessage}`, `研究失败: ${errorMessage}`);
            }
          } catch (err) {
            reportError('研究数据解析错误', err);
          }
        };

        eventSource.onerror = (error) => {

          if (isComplete) {
            return;
          }

          if (eventSource.readyState === EventSource.CONNECTING) {
            emitProgress('reconnecting', '连接中断，正在自动重连...');
            return;
          }

          currentEventSource = null;
          void reconnectWithStatusCheck(
            eventSource.readyState === EventSource.CLOSED ? 'SSE 已关闭' : 'SSE 发生错误'
          );
        };
      };

      registerResearchActionHandler(currentInteractionId);
      startWatchdog();
      connectSSE();
    });
  }
}

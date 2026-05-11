/**
 * DeepResearch 流式事件解析辅助函数。
 *
 * 1:1 抽离自 `DeepResearchHandler.ts` L13-372
 * （< 800 行合规拆分）。
 */

import { ResearchRequiredAction, ToolCall, ToolResult } from '../../types/types';

export const DELTA_TOOL_CALL_TYPES = new Set<string>([
  'function_call',
  'google_search_call',
  'code_execution_call',
  'url_context_call',
  'computer_call',
  'mcp_server_tool_call',
  'file_search_call',
]);

export const DELTA_TOOL_RESULT_TYPES = new Set<string>([
  'function_result',
  'google_search_result',
  'code_execution_result',
  'url_context_result',
  'computer_result',
  'mcp_server_tool_result',
  'file_search_result',
]);

export type DeepResearchStatus =
  | 'starting'
  | 'in_progress'
  | 'reconnecting'
  | 'awaiting_action'
  | 'completed'
  | 'failed'
  | 'cancelled';

export const isRecord = (value: unknown): value is Record<string, any> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

export const extractTextFromDelta = (delta: Record<string, any>): string => {
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
    if (
      ['type', 'id', 'callId', 'call_id', 'name', 'tool', 'error', 'result', 'output'].includes(key)
    ) {
      continue;
    }
    args[key] = value;
  }
  return args;
};

export const normalizeToolCall = (
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

export const normalizeToolResult = (
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
        : typeof payload.screenshot_url === 'string'
          ? payload.screenshot_url
          : undefined,
  };
};

export const extractRequiredAction = (
  eventPayload: Record<string, any>
): ResearchRequiredAction | undefined => {
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

const findUnresolvedToolCall = (
  toolCalls: ToolCall[],
  toolResults: ToolResult[]
): ToolCall | undefined =>
  [...toolCalls].reverse().find((call) => !toolResults.some((result) => result.callId === call.id));

export const extractRequiredActionCallId = (
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

export const extractRequiredActionName = (
  requiredAction: ResearchRequiredAction | undefined,
  toolCalls: ToolCall[],
  toolResults: ToolResult[],
  callId: string
): string | undefined => {
  if (
    requiredAction &&
    isRecord(requiredAction.act) &&
    typeof requiredAction.act.name === 'string'
  ) {
    return requiredAction.act.name;
  }
  const matchedCall = toolCalls.find((call) => call.id === callId);
  if (matchedCall?.name) return matchedCall.name;
  return findUnresolvedToolCall(toolCalls, toolResults)?.name;
};

export const extractStatusText = (eventPayload: Record<string, any>): string | undefined => {
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
  if (
    isRecord(interaction) &&
    typeof interaction.status === 'string' &&
    interaction.status.trim()
  ) {
    return interaction.status.trim();
  }

  return undefined;
};

export const extractInteractionOutputs = (eventPayload: Record<string, unknown>): unknown[] => {
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

export const extractTextFromOutputs = (outputs: unknown[]): string => {
  if (!Array.isArray(outputs) || outputs.length === 0) return '';
  const texts: string[] = [];
  collectTextsFromOutputValue(outputs, texts, 0);
  const unique = [...new Set(texts.map((item) => item.trim()).filter(Boolean))];
  return unique.join('\n\n').trim();
};


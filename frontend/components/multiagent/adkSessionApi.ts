/**
 * ADK Session API 调用 + 运行时错误格式化。
 *
 * 1:1 抽离自 `adkSessionService.ts` L1244-1639
 * （JIRA-frontend-deep-architecture-split.md #2 — adkSessionService 拆分 Step 1）。
 *
 * 包括：
 * - buildAdkRuntimeErrorPayload / parseAdkRuntimeErrorPayload / mapAdkRuntimeErrorMessage
 *   解析后端结构化 runtime 错误负载
 * - format{Runtime,Confirm,Precheck}ErrorMessage 用户可读消息映射
 * - remapRequestFailedError / normalizeSessionId / buildAgentRuntimeRoute 内部 helper
 * - 4 个 API 函数（list/get/confirm/rewind）+ 4 个 agent-runtime alias
 */

import { requestJson } from '../../services/http';
import type {
  AdkSessionItem,
  AdkSessionSnapshot,
  ConfirmToolRequest,
  AdkApprovalTicket,
  AdkRuntimeErrorCode,
  AdkRuntimeErrorPayload,
} from './adkSessionTypes';
import {
  toSafeString,
  isRecord,
  pickFirstString,
  pickFirstValue,
  toBoolean,
  toPositiveInteger,
  parseAdkTimestampMs,
  REQUEST_FAILED_STATUS_RE,
  DEFAULT_RUNTIME_STRATEGY,
  ADK_RUNTIME_ERROR_CODES,
  ADK_RUNTIME_ERROR_CODE_SET,
  RUNTIME_STRATEGY_KEYS,
  STRICT_MODE_KEYS,
  buildApprovalTicketPayload,
  resolveTicketTimestampAndTtl,
} from './adkSessionService';

const buildAdkRuntimeErrorPayload = (value: unknown): AdkRuntimeErrorPayload | null => {
  if (!isRecord(value)) return null;
  const rawErrorCode = pickFirstString(value, ['error_code', 'errorCode']);
  if (!rawErrorCode || !ADK_RUNTIME_ERROR_CODE_SET.has(rawErrorCode)) return null;

  return {
    errorCode: rawErrorCode as AdkRuntimeErrorCode,
    message: pickFirstString(value, ['message', 'detail', 'error']) || rawErrorCode,
    runtimeStrategy: pickFirstString(value, RUNTIME_STRATEGY_KEYS) || DEFAULT_RUNTIME_STRATEGY,
    strictMode: toBoolean(pickFirstValue(value, STRICT_MODE_KEYS)),
  };
};

const parseAdkRuntimeErrorPayload = (message: string): AdkRuntimeErrorPayload | null => {
  const rawMessage = toSafeString(message);
  if (!rawMessage) return null;

  const tryParse = (candidate: string): AdkRuntimeErrorPayload | null => {
    try {
      return buildAdkRuntimeErrorPayload(JSON.parse(candidate));
    } catch {
      return null;
    }
  };

  const direct = tryParse(rawMessage);
  if (direct) return direct;

  const begin = rawMessage.indexOf('{');
  const end = rawMessage.lastIndexOf('}');
  if (begin >= 0 && end > begin) {
    const embedded = tryParse(rawMessage.slice(begin, end + 1));
    if (embedded) return embedded;
  }

  for (const code of ADK_RUNTIME_ERROR_CODES) {
    if (rawMessage.includes(code)) {
      return {
        errorCode: code,
        message: rawMessage,
        runtimeStrategy: DEFAULT_RUNTIME_STRATEGY,
        strictMode: false,
      };
    }
  }

  return null;
};

const mapAdkRuntimeErrorMessage = (message: string): string | null => {
  const payload = parseAdkRuntimeErrorPayload(message);
  if (!payload) return null;

  if (payload.errorCode === 'ADK_RUNTIME_UNAVAILABLE') {
    return `官方 ADK runtime 当前不可用（runtime_strategy=${payload.runtimeStrategy}，strict_mode=${payload.strictMode ? 'true' : 'false'}），请稍后重试。`;
  }

  if (payload.errorCode === 'ADK_FALLBACK_FORBIDDEN') {
    if (payload.strictMode) {
      return `strict_mode=true，禁止 fallback（runtime_strategy=${payload.runtimeStrategy}）。请切换策略或关闭 strict_mode 后重试。`;
    }
    return `当前入口禁止返回 fallback 内容（runtime_strategy=${payload.runtimeStrategy}）。`;
  }

  return `运行策略冲突（runtime_strategy=${payload.runtimeStrategy}，strict_mode=${payload.strictMode ? 'true' : 'false'}），请在 Runtime Policy 面板检查配置。`;
};

export const formatAdkRuntimeContractErrorMessage = (
  error: unknown,
  fallbackMessage: string
): string => {
  if (error instanceof Error) {
    const mapped = mapAdkRuntimeErrorMessage(error.message);
    if (mapped) return mapped;
    return error.message || fallbackMessage;
  }
  return fallbackMessage;
};

const mapConfirmToolErrorMessage = (message: string): string | null => {
  const runtimeMapped = mapAdkRuntimeErrorMessage(message);
  if (runtimeMapped) return runtimeMapped;

  const normalized = String(message || '').toLowerCase();
  if (!normalized) return null;

  const hasNonce = normalized.includes('nonce');
  const hasTicket = normalized.includes('ticket');
  const isExpired = normalized.includes('expire') || normalized.includes('过期');
  const isInvalid =
    normalized.includes('invalid') ||
    normalized.includes('mismatch') ||
    normalized.includes('replay') ||
    normalized.includes('consumed') ||
    normalized.includes('used') ||
    normalized.includes('绑定');

  if ((hasNonce || hasTicket) && isExpired) {
    return '审批票据已过期，请刷新会话后重新选择候选确认项。';
  }

  if ((hasNonce || hasTicket) && isInvalid) {
    return '审批票据无效或已被消费，请刷新会话后重新提交。';
  }

  if (
    normalized.includes('tenant') &&
    (normalized.includes('mismatch') || normalized.includes('invalid'))
  ) {
    return '审批票据与当前租户不匹配，请确认租户上下文后重试。';
  }

  if (
    normalized.includes('default deny') ||
    normalized.includes('explicit approve') ||
    normalized.includes('explicit confirmed=true')
  ) {
    return '当前策略默认拒绝，请先显式选择“批准”并使用有效票据。';
  }

  return null;
};

export const formatAdkConfirmToolErrorMessage = (
  error: unknown,
  fallbackMessage: string
): string => {
  if (error instanceof Error) {
    const runtimeMapped = mapAdkRuntimeErrorMessage(error.message);
    if (runtimeMapped) return runtimeMapped;

    const mapped = mapConfirmToolErrorMessage(error.message);
    if (mapped) return mapped;

    const matched = REQUEST_FAILED_STATUS_RE.exec(String(error.message || '').trim());
    if (matched) {
      return `${fallbackMessage} (HTTP ${matched[1]})`;
    }

    return error.message || fallbackMessage;
  }
  return fallbackMessage;
};

export const formatAdkExportPrecheckErrorMessage = (
  error: unknown,
  fallbackMessage: string = '导出前校验失败'
): string => {
  if (!(error instanceof Error)) return fallbackMessage;

  const normalized = String(error.message || '').toLowerCase();
  if (!normalized) return fallbackMessage;

  if (normalized.includes('tenant') && normalized.includes('mismatch')) {
    return '导出被拒绝：资源租户与当前会话租户不匹配。';
  }

  if (
    normalized.includes('sensitive') ||
    normalized.includes('pii') ||
    normalized.includes('secret') ||
    normalized.includes('敏感')
  ) {
    return '导出被拒绝：检测到敏感字段，请先脱敏后再导出。';
  }

  return error.message || fallbackMessage;
};

const remapRequestFailedError = (error: unknown, fallbackMessage: string): Error => {
  if (error instanceof Error) {
    const runtimeMapped = mapAdkRuntimeErrorMessage(error.message);
    if (runtimeMapped) {
      return new Error(runtimeMapped);
    }
    const matched = REQUEST_FAILED_STATUS_RE.exec(String(error.message || '').trim());
    if (matched) {
      return new Error(`${fallbackMessage} (HTTP ${matched[1]})`);
    }
    return error;
  }
  return new Error(fallbackMessage);
};

const normalizeSessionId = (payload: Record<string, unknown>): string =>
  toSafeString(payload?.sessionId || payload?.id);
const buildAgentRuntimeRoute = (agentId: string, suffix: string): string =>
  `/api/multi-agent/agents/${encodeURIComponent(agentId)}/runtime${suffix}`;

export const listAdkAgentSessions = async (
  agentId: string,
  signal?: AbortSignal
): Promise<AdkSessionItem[]> => {
  const normalizedAgentId = toSafeString(agentId);
  if (!normalizedAgentId) return [];

  let payload: unknown;
  try {
    payload = await requestJson<unknown>(buildAgentRuntimeRoute(normalizedAgentId, '/sessions'), {
      signal,
      timeoutMs: 0,
      withAuth: true,
    });
  } catch (error) {
    throw remapRequestFailedError(error, '加载运行时会话失败');
  }
  const payloadObj = (payload && typeof payload === 'object' ? payload : {}) as Record<
    string,
    unknown
  >;
  const sessions = Array.isArray(payloadObj.sessions) ? (payloadObj.sessions as unknown[]) : [];

  return sessions
    .map((session) => {
      const sessObj = (session && typeof session === 'object' ? session : {}) as Record<
        string,
        unknown
      >;
      return {
        id: normalizeSessionId(sessObj),
        raw: sessObj,
      };
    })
    .filter((item: AdkSessionItem) => Boolean(item.id));
};

export const getAdkAgentSession = async (
  agentId: string,
  sessionId: string,
  signal?: AbortSignal
): Promise<AdkSessionSnapshot> => {
  const normalizedAgentId = toSafeString(agentId);
  const normalizedSessionId = toSafeString(sessionId);
  if (!normalizedAgentId || !normalizedSessionId) {
    throw new Error('agentId/sessionId 不能为空');
  }

  let payload: unknown;
  try {
    payload = await requestJson<unknown>(
      buildAgentRuntimeRoute(
        normalizedAgentId,
        `/sessions/${encodeURIComponent(normalizedSessionId)}`
      ),
      {
        signal,
        timeoutMs: 0,
        withAuth: true,
      }
    );
  } catch (error) {
    throw remapRequestFailedError(error, '加载运行时会话详情失败');
  }
  const payloadObj = (payload && typeof payload === 'object' ? payload : {}) as Record<
    string,
    unknown
  >;
  const session = payloadObj.session;
  const sessObj = (session && typeof session === 'object' ? session : {}) as Record<
    string,
    unknown
  >;
  const resolvedId = normalizeSessionId(sessObj) || normalizedSessionId;

  return {
    id: resolvedId,
    raw: sessObj,
  };
};

export const confirmAdkToolCall = async (
  agentId: string,
  sessionId: string,
  request: ConfirmToolRequest,
  signal?: AbortSignal
): Promise<unknown> => {
  const normalizedAgentId = toSafeString(agentId);
  const normalizedSessionId = toSafeString(sessionId);
  if (!normalizedAgentId || !normalizedSessionId) {
    throw new Error('agentId/sessionId 不能为空');
  }
  const functionCallId = toSafeString(request.functionCallId);
  if (!functionCallId) {
    throw new Error('functionCallId 不能为空');
  }

  const invocationId = toSafeString(request.invocationId);
  const rawTicket = request.ticket;
  const legacyTicketField: unknown = isRecord(rawTicket)
    ? rawTicket
    : toSafeString(rawTicket) || undefined;
  const nonce = toSafeString(request.nonce);
  const nonceExpiresAt = toSafeString(request.nonceExpiresAt);
  const tenantId = toSafeString(request.tenantId);
  const candidateId = toSafeString(request.candidateId);
  const approvalTicket = buildApprovalTicketPayload({
    sessionId: normalizedSessionId,
    functionCallId,
    invocationId,
    ticket: rawTicket,
    approvalTicket: request.approvalTicket || null,
    nonce,
    nonceExpiresAt,
    ticketTimestampMs: request.ticketTimestampMs,
    ticketTtlSeconds: request.ticketTtlSeconds,
    tenantId,
  });
  const ticketTiming = resolveTicketTimestampAndTtl({
    approvalTicket,
    nonceExpiresAt,
    ticketTimestampMs: request.ticketTimestampMs,
    ticketTtlSeconds: request.ticketTtlSeconds,
  });

  try {
    return await requestJson<unknown>(
      buildAgentRuntimeRoute(
        normalizedAgentId,
        `/sessions/${encodeURIComponent(normalizedSessionId)}/confirm-tool`
      ),
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal,
        timeoutMs: 0,
        withAuth: true,
        body: JSON.stringify({
          function_call_id: functionCallId,
          confirmed: request.confirmed === true,
          hint: toSafeString(request.hint) || undefined,
          payload: request.payload,
          invocation_id: invocationId || undefined,
          approval_ticket: approvalTicket || undefined,
          confirmation_ticket: legacyTicketField,
          ticket: legacyTicketField,
          nonce: nonce || undefined,
          nonce_expires_at: nonceExpiresAt || undefined,
          nonce_expiry: nonceExpiresAt || undefined,
          ticket_timestamp_ms: ticketTiming?.timestampMs || undefined,
          ticket_ttl_seconds: ticketTiming?.ttlSeconds || undefined,
          tenant_id: tenantId || undefined,
          confirm_candidate_id: candidateId || undefined,
        }),
      }
    );
  } catch (error) {
    throw new Error(formatAdkConfirmToolErrorMessage(error, '提交工具确认失败'));
  }
};

export const rewindAdkSession = async (
  agentId: string,
  sessionId: string,
  rewindBeforeInvocationId: string,
  signal?: AbortSignal
): Promise<unknown> => {
  const normalizedAgentId = toSafeString(agentId);
  const normalizedSessionId = toSafeString(sessionId);
  const normalizedInvocation = toSafeString(rewindBeforeInvocationId);
  if (!normalizedAgentId || !normalizedSessionId) {
    throw new Error('agentId/sessionId 不能为空');
  }
  if (!normalizedInvocation) {
    throw new Error('rewindBeforeInvocationId 不能为空');
  }

  try {
    return await requestJson<unknown>(
      buildAgentRuntimeRoute(
        normalizedAgentId,
        `/sessions/${encodeURIComponent(normalizedSessionId)}/rewind`
      ),
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal,
        timeoutMs: 0,
        withAuth: true,
        body: JSON.stringify({
          rewind_before_invocation_id: normalizedInvocation,
        }),
      }
    );
  } catch (error) {
    throw remapRequestFailedError(error, '会话回滚失败');
  }
};

export const listAgentRuntimeSessions = listAdkAgentSessions;
export const getAgentRuntimeSession = getAdkAgentSession;
export const confirmAgentRuntimeToolCall = confirmAdkToolCall;
export const rewindAgentRuntimeSession = rewindAdkSession;

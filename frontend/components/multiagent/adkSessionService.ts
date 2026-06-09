import { requestJson } from '../../services/http';
import { safeJsonParse } from '../../utils/safeOps';
import type {
  AdkSessionItem,
  AdkSessionSnapshot,
  ConfirmToolRequest,
  AdkApprovalTicket,
  AdkConfirmCandidate,
  AdkExportPrecheckIssueCode,
  AdkExportPrecheckIssue,
  AdkRuntimeErrorCode,
  AdkRuntimeErrorPayload,
  AdkRuntimePolicyOption,
  AdkRuntimePolicyState,
  AdkConfirmActionSupport,
} from './adkSessionTypes';

// Re-export types for backwards compat（8 个 importer 用 ./adkSessionService）
export type {
  AdkSessionItem,
  AdkSessionSnapshot,
  ConfirmToolRequest,
  AdkApprovalTicket,
  AdkConfirmCandidate,
  AdkExportPrecheckIssueCode,
  AdkExportPrecheckIssue,
  AdkRuntimeErrorCode,
  AdkRuntimePolicyOption,
  AdkRuntimePolicyState,
  AdkConfirmActionSupport,
} from './adkSessionTypes';

export const toSafeString = (value: unknown): string => String(value ?? '').trim();

type UnknownRecord = Record<string, unknown>;

type CandidateSource = 'requested_confirmation' | 'function_call';

interface CandidateDraft extends AdkConfirmCandidate {
  score: number;
}

export const CONFIRMATION_CONTAINER_KEYS = new Set([
  'requested_tool_confirmations',
  'requestedToolConfirmations',
  'pending_tool_confirmations',
  'pendingToolConfirmations',
  'tool_confirmations',
  'toolConfirmations',
]);

export const FUNCTION_CALL_CONTAINER_KEYS = new Set(['function_calls', 'functionCalls']);

export const CANDIDATE_ID_KEYS = [
  'id',
  'function_call_id',
  'functionCallId',
  'call_id',
  'callId',
  'tool_call_id',
  'toolCallId',
];

export const CANDIDATE_NAME_KEYS = [
  'name',
  'function_name',
  'functionName',
  'tool_name',
  'toolName',
];

export const CANDIDATE_HINT_KEYS = [
  'hint',
  'message',
  'description',
  'reason',
  'title',
  'approval_prompt',
  'approvalPrompt',
];

export const INVOCATION_ID_KEYS = [
  'invocation_id',
  'invocationId',
  'last_invocation_id',
  'lastInvocationId',
];

export const CANDIDATE_TICKET_KEYS = [
  'ticket',
  'confirmation_ticket',
  'confirmationTicket',
  'approval_ticket',
  'approvalTicket',
  'ticket_id',
  'ticketId',
  'token',
  'approval_token',
  'approvalToken',
];

export const CANDIDATE_NONCE_KEYS = [
  'nonce',
  'confirmation_nonce',
  'confirmationNonce',
  'approval_nonce',
  'approvalNonce',
];

export const CANDIDATE_NONCE_EXPIRES_KEYS = [
  'nonce_expires_at',
  'nonceExpiresAt',
  'expires_at',
  'expiresAt',
  'nonce_expiry',
  'nonceExpiry',
  'deadline',
];

export const CANDIDATE_TENANT_KEYS = [
  'tenant_id',
  'tenantId',
  'tenant',
  'tenant_scope',
  'tenantScope',
];

export const CANDIDATE_CONTEXT_KEYS = [
  'ticket',
  'security',
  'binding',
  'context',
  'request',
  'details',
  'meta',
  'metadata',
  'policy',
  'verification',
];

export const EXPORT_PRECHECK_CONTAINER_KEYS = new Set([
  'export_precheck',
  'exportPrecheck',
  'export_prechecks',
  'exportPrechecks',
  'export_precheck_result',
  'exportPrecheckResult',
  'precheck',
  'pre_check',
]);

export const EXPORT_PRECHECK_ISSUES_KEYS = [
  'issues',
  'errors',
  'reasons',
  'violations',
  'findings',
];

export const EXPORT_PRECHECK_CODE_KEYS = [
  'code',
  'reason_code',
  'reasonCode',
  'type',
  'kind',
  'error_code',
  'errorCode',
];

export const EXPORT_PRECHECK_MESSAGE_KEYS = [
  'message',
  'detail',
  'reason',
  'hint',
  'description',
  'error',
  'status',
];

export const EXPORT_PRECHECK_FIELDS_KEYS = [
  'sensitive_fields',
  'sensitiveFields',
  'fields',
  'column_names',
  'columnNames',
  'columns',
];

export const EXPORT_PRECHECK_TENANT_KEYS = [
  'tenant_id',
  'tenantId',
  'tenant',
  'actual_tenant_id',
  'actualTenantId',
];

export const EXPORT_PRECHECK_EXPECTED_TENANT_KEYS = [
  'expected_tenant_id',
  'expectedTenantId',
  'resource_tenant_id',
  'resourceTenantId',
];

export const REQUEST_FAILED_STATUS_RE = /^Request failed:\s*(\d+)$/;
export const DEFAULT_RUNTIME_STRATEGY = 'official_or_legacy';
export const MAX_APPROVAL_TICKET_TTL_SECONDS = 30 * 60;
export const ADK_RUNTIME_ERROR_CODES: AdkRuntimeErrorCode[] = [
  'ADK_RUNTIME_UNAVAILABLE',
  'ADK_FALLBACK_FORBIDDEN',
  'ADK_STRATEGY_VIOLATION',
];
export const ADK_RUNTIME_ERROR_CODE_SET = new Set<string>(ADK_RUNTIME_ERROR_CODES);
export const RUNTIME_STRATEGY_KEYS = ['runtime_strategy', 'runtimeStrategy'];
export const STRICT_MODE_KEYS = ['strict_mode', 'strictMode'];
export const BACKEND_RUNTIME_STRATEGY_OPTIONS = [
  'official_only',
  'official_or_legacy',
  'allow_legacy',
];
export const RUNTIME_STRATEGY_OPTIONS_KEYS = [
  'runtime_strategy_values',
  'runtimeStrategyValues',
  'runtime_strategies',
  'runtimeStrategies',
  'strategy_options',
  'strategyOptions',
  'allowed_runtime_strategies',
  'allowedRuntimeStrategies',
  'allowed_strategies',
  'allowedStrategies',
];
export const RUNTIME_STRATEGY_LABELS: Record<string, string> = {
  official_only: '仅官方 ADK',
  official_or_legacy: '官方优先（默认禁止 fallback）',
  allow_legacy: '显式允许 legacy fallback',
};
export const EXPLICIT_REJECT_SUPPORT_KEYS = [
  'supports_reject',
  'supportsReject',
  'reject_supported',
  'rejectSupported',
  'allow_reject',
  'allowReject',
  'can_reject',
  'canReject',
];
export const EXPLICIT_REJECT_CONTAINER_KEYS = new Set([
  'confirm_tool_contract',
  'confirmToolContract',
  'tool_confirmation_contract',
  'toolConfirmationContract',
  'confirm_contract',
  'confirmContract',
]);

export const isRecord = (value: unknown): value is UnknownRecord =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

export const pickFirstString = (record: UnknownRecord, keys: string[]): string => {
  for (const key of keys) {
    if (!(key in record)) continue;
    const text = toSafeString(record[key]);
    if (text) return text;
  }
  return '';
};

export const pickFirstValue = (record: UnknownRecord, keys: string[]): unknown => {
  for (const key of keys) {
    if (!(key in record)) continue;
    const value = record[key];
    if (value !== undefined) return value;
  }
  return undefined;
};

export const trimPreview = (text: string, maxLen: number = 220): string => {
  const compact = String(text || '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!compact) return '';
  if (compact.length <= maxLen) return compact;
  return `${compact.slice(0, maxLen)}...`;
};

export const buildPayloadPreview = (value: unknown): string => {
  if (value === undefined || value === null) return '';
  if (typeof value === 'string') return trimPreview(value);
  try {
    return trimPreview(JSON.stringify(value));
  } catch {
    return '';
  }
};

export const parseAdkTimestampMs = (value: unknown): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 1e12 ? value : value * 1000;
  }
  const raw = toSafeString(value);
  if (!raw) return 0;

  if (/^\d+(\.\d+)?$/.test(raw)) {
    const numeric = Number(raw);
    if (Number.isFinite(numeric)) {
      return numeric > 1e12 ? numeric : numeric * 1000;
    }
  }

  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const isAdkNonceExpired = (value: unknown): boolean => {
  const expiresAt = parseAdkTimestampMs(value);
  if (!expiresAt) return false;
  return expiresAt <= Date.now();
};

export const toPositiveInteger = (value: unknown): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 0 ? Math.floor(value) : 0;
  }
  const raw = toSafeString(value);
  if (!raw) return 0;
  const numeric = Number(raw);
  if (!Number.isFinite(numeric)) return 0;
  return numeric > 0 ? Math.floor(numeric) : 0;
};

export const isApprovalTicketLike = (record: UnknownRecord): boolean => {
  const keys = [
    'session_id',
    'sessionId',
    'function_call_id',
    'functionCallId',
    'invocation_id',
    'invocationId',
    'tenant_id',
    'tenantId',
    'timestamp_ms',
    'timestampMs',
    'ttl_seconds',
    'ttlSeconds',
    'nonce',
    'ticket',
    'confirmation_ticket',
    'confirmationTicket',
  ];
  return keys.some((key) => key in record);
};

export const parseJsonObject = (value: string): UnknownRecord | null => {
  const raw = String(value || '').trim();
  if (!raw) return null;
  return safeJsonParse<UnknownRecord | null>(raw, null, isRecord);
};

export const toApprovalTicketObject = (value: unknown): AdkApprovalTicket | null => {
  if (isRecord(value) && isApprovalTicketLike(value)) {
    return { ...value };
  }
  if (typeof value === 'string') {
    const parsed = parseJsonObject(value);
    if (parsed && isApprovalTicketLike(parsed)) {
      return { ...parsed };
    }
  }
  return null;
};

export const resolveTicketTimestampAndTtl = ({
  approvalTicket,
  nonceExpiresAt,
  ticketTimestampMs,
  ticketTtlSeconds,
}: {
  approvalTicket: AdkApprovalTicket | null;
  nonceExpiresAt: string;
  ticketTimestampMs: unknown;
  ticketTtlSeconds: unknown;
}): { timestampMs: number; ttlSeconds: number } | null => {
  const ticketRecord = isRecord(approvalTicket) ? approvalTicket : null;
  const existingTimestamp = ticketRecord
    ? parseAdkTimestampMs(
        pickFirstValue(ticketRecord, [
          'timestamp_ms',
          'timestampMs',
          'issued_at_ms',
          'issuedAtMs',
          'timestamp',
          'issued_at',
        ])
      )
    : 0;
  const existingTtl = ticketRecord
    ? toPositiveInteger(pickFirstValue(ticketRecord, ['ttl_seconds', 'ttlSeconds', 'ttl']))
    : 0;
  if (existingTimestamp > 0 && existingTtl > 0) {
    return {
      timestampMs: existingTimestamp,
      ttlSeconds: Math.min(existingTtl, MAX_APPROVAL_TICKET_TTL_SECONDS),
    };
  }

  const explicitTimestamp = parseAdkTimestampMs(ticketTimestampMs);
  const explicitTtl = toPositiveInteger(ticketTtlSeconds);
  if (explicitTimestamp > 0 && explicitTtl > 0) {
    return {
      timestampMs: explicitTimestamp,
      ttlSeconds: Math.min(explicitTtl, MAX_APPROVAL_TICKET_TTL_SECONDS),
    };
  }

  const expiresAtMs = parseAdkTimestampMs(nonceExpiresAt);
  if (!expiresAtMs) return null;

  const nowMs = Date.now();
  let ttlSeconds = Math.floor((expiresAtMs - nowMs + 999) / 1000);
  if (ttlSeconds > MAX_APPROVAL_TICKET_TTL_SECONDS) {
    ttlSeconds = MAX_APPROVAL_TICKET_TTL_SECONDS;
  }
  if (ttlSeconds > 0) {
    return {
      timestampMs: nowMs,
      ttlSeconds,
    };
  }
  return {
    timestampMs: expiresAtMs - 1000,
    ttlSeconds: 1,
  };
};

export const buildApprovalTicketPayload = ({
  sessionId,
  functionCallId,
  invocationId,
  ticket,
  approvalTicket,
  nonce,
  nonceExpiresAt,
  ticketTimestampMs,
  ticketTtlSeconds,
  tenantId,
}: {
  sessionId: string;
  functionCallId: string;
  invocationId: string;
  ticket: unknown;
  approvalTicket: AdkApprovalTicket | null;
  nonce: string;
  nonceExpiresAt: string;
  ticketTimestampMs: unknown;
  ticketTtlSeconds: unknown;
  tenantId: string;
}): AdkApprovalTicket | null => {
  const ticketObject = toApprovalTicketObject(ticket);
  const payload: AdkApprovalTicket = {
    ...(ticketObject || {}),
    ...(approvalTicket || {}),
  };

  if (sessionId) payload.session_id = sessionId;
  if (functionCallId) payload.function_call_id = functionCallId;
  if (invocationId) payload.invocation_id = invocationId;
  if (tenantId) payload.tenant_id = tenantId;
  if (nonce) payload.nonce = nonce;

  const ticketText = toSafeString(ticket);
  if (ticketText && !isRecord(ticket)) {
    payload.ticket = ticketText;
  }

  const timing = resolveTicketTimestampAndTtl({
    approvalTicket: payload,
    nonceExpiresAt,
    ticketTimestampMs,
    ticketTtlSeconds,
  });
  if (timing) {
    payload.timestamp_ms = timing.timestampMs;
    payload.ttl_seconds = timing.ttlSeconds;
  }

  return Object.keys(payload).length > 0 ? payload : null;
};

export const collectStringList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => toSafeString(item)).filter(Boolean);
  }

  if (typeof value === 'string') {
    return value
      .split(',')
      .map((item) => toSafeString(item))
      .filter(Boolean);
  }

  return [];
};

export const toBoolean = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value;
  const text = toSafeString(value).toLowerCase();
  return text === '1' || text === 'true' || text === 'yes';
};

// API + error formatters 抽离至 ./adkSessionApi（JIRA #2 Step 1）
export {
  formatAdkRuntimeContractErrorMessage,
  formatAdkConfirmToolErrorMessage,
  formatAdkExportPrecheckErrorMessage,
  listAdkAgentSessions,
  getAdkAgentSession,
  confirmAdkToolCall,
  rewindAdkSession,
  listAgentRuntimeSessions,
  getAgentRuntimeSession,
  confirmAgentRuntimeToolCall,
  rewindAgentRuntimeSession,
} from './adkSessionApi';

// Runtime policy / Confirm action support 抽离至 ./adkRuntimePolicy（JIRA #2 Step 2）
export { extractAdkRuntimePolicyState, extractAdkConfirmActionSupport } from './adkRuntimePolicy';

// Export precheck issues 抽离至 ./adkExportPrecheck（JIRA #2 Step 3）
export { extractAdkExportPrecheckIssues } from './adkExportPrecheck';

// Confirm candidates extractor 抽离至 ./adkConfirmCandidates（JIRA #2 Step 4）
export { extractAdkConfirmCandidates } from './adkConfirmCandidates';

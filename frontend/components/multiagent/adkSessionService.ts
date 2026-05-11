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

const CONFIRMATION_CONTAINER_KEYS = new Set([
  'requested_tool_confirmations',
  'requestedToolConfirmations',
  'pending_tool_confirmations',
  'pendingToolConfirmations',
  'tool_confirmations',
  'toolConfirmations',
]);

const FUNCTION_CALL_CONTAINER_KEYS = new Set(['function_calls', 'functionCalls']);

const CANDIDATE_ID_KEYS = [
  'id',
  'function_call_id',
  'functionCallId',
  'call_id',
  'callId',
  'tool_call_id',
  'toolCallId',
];

const CANDIDATE_NAME_KEYS = ['name', 'function_name', 'functionName', 'tool_name', 'toolName'];

const CANDIDATE_HINT_KEYS = [
  'hint',
  'message',
  'description',
  'reason',
  'title',
  'approval_prompt',
  'approvalPrompt',
];

const INVOCATION_ID_KEYS = [
  'invocation_id',
  'invocationId',
  'last_invocation_id',
  'lastInvocationId',
];

const CANDIDATE_TICKET_KEYS = [
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

const CANDIDATE_NONCE_KEYS = [
  'nonce',
  'confirmation_nonce',
  'confirmationNonce',
  'approval_nonce',
  'approvalNonce',
];

const CANDIDATE_NONCE_EXPIRES_KEYS = [
  'nonce_expires_at',
  'nonceExpiresAt',
  'expires_at',
  'expiresAt',
  'nonce_expiry',
  'nonceExpiry',
  'deadline',
];

const CANDIDATE_TENANT_KEYS = ['tenant_id', 'tenantId', 'tenant', 'tenant_scope', 'tenantScope'];

const CANDIDATE_CONTEXT_KEYS = [
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

export const EXPORT_PRECHECK_ISSUES_KEYS = ['issues', 'errors', 'reasons', 'violations', 'findings'];

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
export const BACKEND_RUNTIME_STRATEGY_OPTIONS = ['official_only', 'official_or_legacy', 'allow_legacy'];
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

const trimPreview = (text: string, maxLen: number = 220): string => {
  const compact = String(text || '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!compact) return '';
  if (compact.length <= maxLen) return compact;
  return `${compact.slice(0, maxLen)}...`;
};

const buildPayloadPreview = (value: unknown): string => {
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

const isApprovalTicketLike = (record: UnknownRecord): boolean => {
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

const parseJsonObject = (value: string): UnknownRecord | null => {
  const raw = String(value || '').trim();
  if (!raw) return null;
  return safeJsonParse<UnknownRecord | null>(raw, null, isRecord);
};

const toApprovalTicketObject = (value: unknown): AdkApprovalTicket | null => {
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

const resolveInvocationId = (record: UnknownRecord, contextInvocationId: string): string => {
  const direct = pickFirstString(record, INVOCATION_ID_KEYS);
  if (direct) return direct;

  const nested = pickFirstValue(record, ['function_call', 'functionCall']);
  if (isRecord(nested)) {
    const nestedInvocation = pickFirstString(nested, INVOCATION_ID_KEYS);
    if (nestedInvocation) return nestedInvocation;
  }
  return contextInvocationId;
};

const resolveCandidateId = (record: UnknownRecord): string => {
  const direct = pickFirstString(record, CANDIDATE_ID_KEYS);
  if (direct) return direct;

  const nestedCall = pickFirstValue(record, ['function_call', 'functionCall']);
  if (isRecord(nestedCall)) {
    const nestedId = pickFirstString(nestedCall, CANDIDATE_ID_KEYS);
    if (nestedId) return nestedId;
  }
  return '';
};

const resolveCandidateName = (record: UnknownRecord): string => {
  const direct = pickFirstString(record, CANDIDATE_NAME_KEYS);
  if (direct) return direct;

  const nestedCall = pickFirstValue(record, ['function_call', 'functionCall']);
  if (isRecord(nestedCall)) {
    const nestedName = pickFirstString(nestedCall, CANDIDATE_NAME_KEYS);
    if (nestedName) return nestedName;
  }
  return '';
};

const resolveCandidateHint = (record: UnknownRecord): string => {
  const direct = pickFirstString(record, CANDIDATE_HINT_KEYS);
  if (direct) return direct;

  const nestedContext = pickFirstValue(record, ['context', 'request', 'details']);
  if (isRecord(nestedContext)) {
    const nestedHint = pickFirstString(nestedContext, CANDIDATE_HINT_KEYS);
    if (nestedHint) return nestedHint;
  }
  return '';
};

const resolveCandidatePayload = (record: UnknownRecord): unknown => {
  const directPayload = pickFirstValue(record, [
    'payload',
    'args',
    'arguments',
    'response',
    'tool_input',
    'toolInput',
    'input',
    'data',
  ]);
  if (directPayload !== undefined) return directPayload;

  const nestedCall = pickFirstValue(record, ['function_call', 'functionCall']);
  if (isRecord(nestedCall)) {
    const nestedPayload = pickFirstValue(nestedCall, ['args', 'arguments', 'payload']);
    if (nestedPayload !== undefined) return nestedPayload;
  }
  return undefined;
};

const resolveNestedSecurityString = (
  value: unknown,
  keys: string[],
  allowIdValueFallback: boolean = false
): string => {
  if (isRecord(value)) {
    const direct = pickFirstString(value, keys);
    if (direct) return direct;

    if (allowIdValueFallback) {
      const byId = pickFirstString(value, ['id', 'value']);
      if (byId) return byId;
    }
  }

  if (typeof value === 'string') {
    const raw = toSafeString(value);
    if (raw) return raw;
  }
  return '';
};

const resolveCandidateSecurityField = (
  record: UnknownRecord,
  keys: string[],
  options: { allowIdValueFallback?: boolean } = {}
): string => {
  const direct = pickFirstString(record, keys);
  if (direct) return direct;

  for (const contextKey of CANDIDATE_CONTEXT_KEYS) {
    const nested = pickFirstValue(record, [contextKey]);
    const nestedText = resolveNestedSecurityString(
      nested,
      keys,
      options.allowIdValueFallback === true
    );
    if (nestedText) return nestedText;
  }

  const nestedCall = pickFirstValue(record, ['function_call', 'functionCall']);
  if (isRecord(nestedCall)) {
    const nestedCallDirect = pickFirstString(nestedCall, keys);
    if (nestedCallDirect) return nestedCallDirect;

    for (const contextKey of CANDIDATE_CONTEXT_KEYS) {
      const nested = pickFirstValue(nestedCall, [contextKey]);
      const nestedText = resolveNestedSecurityString(
        nested,
        keys,
        options.allowIdValueFallback === true
      );
      if (nestedText) return nestedText;
    }
  }

  return '';
};

const resolveCandidateTicket = (record: UnknownRecord): string =>
  resolveCandidateSecurityField(record, CANDIDATE_TICKET_KEYS, { allowIdValueFallback: true });

const resolveCandidateNonce = (record: UnknownRecord): string =>
  resolveCandidateSecurityField(record, CANDIDATE_NONCE_KEYS);

const resolveCandidateNonceExpiresAt = (record: UnknownRecord): string =>
  resolveCandidateSecurityField(record, CANDIDATE_NONCE_EXPIRES_KEYS);

const resolveCandidateTenantId = (record: UnknownRecord): string =>
  resolveCandidateSecurityField(record, CANDIDATE_TENANT_KEYS);

const resolveCandidateApprovalTicket = (record: UnknownRecord): AdkApprovalTicket | null => {
  const tryPickFromRecord = (target: UnknownRecord): AdkApprovalTicket | null => {
    for (const key of CANDIDATE_TICKET_KEYS) {
      if (!(key in target)) continue;
      const nested = toApprovalTicketObject(target[key]);
      if (nested) return nested;
    }
    return isApprovalTicketLike(target) ? { ...target } : null;
  };

  const direct = tryPickFromRecord(record);
  if (direct) return direct;

  for (const contextKey of CANDIDATE_CONTEXT_KEYS) {
    const nested = pickFirstValue(record, [contextKey]);
    if (!isRecord(nested)) continue;
    const nestedTicket = tryPickFromRecord(nested);
    if (nestedTicket) return nestedTicket;
  }

  const nestedCall = pickFirstValue(record, ['function_call', 'functionCall']);
  if (isRecord(nestedCall)) {
    const callTicket = tryPickFromRecord(nestedCall);
    if (callTicket) return callTicket;

    for (const contextKey of CANDIDATE_CONTEXT_KEYS) {
      const nested = pickFirstValue(nestedCall, [contextKey]);
      if (!isRecord(nested)) continue;
      const nestedTicket = tryPickFromRecord(nested);
      if (nestedTicket) return nestedTicket;
    }
  }

  return null;
};

const buildCandidateDraft = ({
  record,
  sourcePath,
  contextInvocationId,
  source,
}: {
  record: UnknownRecord;
  sourcePath: string;
  contextInvocationId: string;
  source: CandidateSource;
}): CandidateDraft | null => {
  const id = resolveCandidateId(record);
  if (!id) return null;

  const name = resolveCandidateName(record);
  const hint = resolveCandidateHint(record);
  const payload = resolveCandidatePayload(record);
  const invocationId = resolveInvocationId(record, contextInvocationId);
  const payloadPreview = buildPayloadPreview(payload);
  const ticket = resolveCandidateTicket(record);
  const approvalTicket = resolveCandidateApprovalTicket(record);
  const nonce = resolveCandidateNonce(record);
  const nonceExpiresAt = resolveCandidateNonceExpiresAt(record);
  const tenantId = resolveCandidateTenantId(record);

  let score = source === 'requested_confirmation' ? 4 : 2;
  if (name) score += 1;
  if (hint) score += 1;
  if (invocationId) score += 1;
  if (payload !== undefined && payloadPreview) score += 1;
  if (ticket) score += 1;
  if (approvalTicket) score += 1;
  if (nonce) score += 1;
  if (nonceExpiresAt) score += 1;
  if (tenantId) score += 1;

  return {
    id,
    name,
    hint,
    invocationId,
    payload,
    payloadPreview,
    ticket,
    approvalTicket,
    nonce,
    nonceExpiresAt,
    tenantId,
    sourcePath,
    score,
  };
};

const mergeCandidateDraft = (
  existing: CandidateDraft | undefined,
  next: CandidateDraft
): CandidateDraft => {
  if (!existing) return next;
  if (next.score > existing.score) {
    return {
      ...next,
      name: next.name || existing.name,
      hint: next.hint || existing.hint,
      invocationId: next.invocationId || existing.invocationId,
      payload: next.payload !== undefined ? next.payload : existing.payload,
      payloadPreview: next.payloadPreview || existing.payloadPreview,
      ticket: next.ticket || existing.ticket,
      approvalTicket: next.approvalTicket || existing.approvalTicket,
      nonce: next.nonce || existing.nonce,
      nonceExpiresAt: next.nonceExpiresAt || existing.nonceExpiresAt,
      tenantId: next.tenantId || existing.tenantId,
    };
  }

  return {
    ...existing,
    name: existing.name || next.name,
    hint: existing.hint || next.hint,
    invocationId: existing.invocationId || next.invocationId,
    payload: existing.payload !== undefined ? existing.payload : next.payload,
    payloadPreview: existing.payloadPreview || next.payloadPreview,
    ticket: existing.ticket || next.ticket,
    approvalTicket: existing.approvalTicket || next.approvalTicket,
    nonce: existing.nonce || next.nonce,
    nonceExpiresAt: existing.nonceExpiresAt || next.nonceExpiresAt,
    tenantId: existing.tenantId || next.tenantId,
    sourcePath: existing.sourcePath || next.sourcePath,
    score: Math.max(existing.score, next.score),
  };
};

const collectCandidatesFromContainer = ({
  container,
  sourcePath,
  contextInvocationId,
  source,
  collector,
}: {
  container: unknown;
  sourcePath: string;
  contextInvocationId: string;
  source: CandidateSource;
  collector: Map<string, CandidateDraft>;
}): void => {
  if (Array.isArray(container)) {
    container.forEach((item, index) => {
      if (!isRecord(item)) return;
      const candidate = buildCandidateDraft({
        record: item,
        sourcePath: `${sourcePath}[${index}]`,
        contextInvocationId,
        source,
      });
      if (!candidate) return;
      collector.set(candidate.id, mergeCandidateDraft(collector.get(candidate.id), candidate));
    });
    return;
  }

  if (!isRecord(container)) return;
  const directCandidate = buildCandidateDraft({
    record: container,
    sourcePath,
    contextInvocationId,
    source,
  });
  if (directCandidate) {
    collector.set(
      directCandidate.id,
      mergeCandidateDraft(collector.get(directCandidate.id), directCandidate)
    );
  }

  for (const [entryKey, entryValue] of Object.entries(container)) {
    if (!isRecord(entryValue)) continue;
    const candidate = buildCandidateDraft({
      record: entryValue,
      sourcePath: `${sourcePath}.${entryKey}`,
      contextInvocationId,
      source,
    });
    if (!candidate) continue;
    collector.set(candidate.id, mergeCandidateDraft(collector.get(candidate.id), candidate));
  }
};

export const extractAdkConfirmCandidates = (sessionSnapshot: unknown): AdkConfirmCandidate[] => {
  if (!sessionSnapshot) return [];

  const collector = new Map<string, CandidateDraft>();
  const visited = new WeakSet<object>();

  const visit = (value: unknown, path: string, contextInvocationId: string): void => {
    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        visit(item, `${path}[${index}]`, contextInvocationId);
      });
      return;
    }
    if (!isRecord(value)) return;
    if (visited.has(value)) return;
    visited.add(value);

    const currentInvocationId = pickFirstString(value, INVOCATION_ID_KEYS) || contextInvocationId;
    for (const [key, nestedValue] of Object.entries(value)) {
      const nextPath = `${path}.${key}`;
      if (CONFIRMATION_CONTAINER_KEYS.has(key)) {
        collectCandidatesFromContainer({
          container: nestedValue,
          sourcePath: nextPath,
          contextInvocationId: currentInvocationId,
          source: 'requested_confirmation',
          collector,
        });
      }
      if (FUNCTION_CALL_CONTAINER_KEYS.has(key)) {
        collectCandidatesFromContainer({
          container: nestedValue,
          sourcePath: nextPath,
          contextInvocationId: currentInvocationId,
          source: 'function_call',
          collector,
        });
      }
    }

    for (const [key, nestedValue] of Object.entries(value)) {
      visit(nestedValue, `${path}.${key}`, currentInvocationId);
    }
  };

  visit(sessionSnapshot, 'snapshot', '');

  return Array.from(collector.values())
    .sort((left, right) => right.score - left.score || left.id.localeCompare(right.id))
    .map(({ score: _score, ...candidate }) => candidate);
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
export {
  extractAdkRuntimePolicyState,
  extractAdkConfirmActionSupport,
} from './adkRuntimePolicy';

// Export precheck issues 抽离至 ./adkExportPrecheck（JIRA #2 Step 3）
export { extractAdkExportPrecheckIssues } from './adkExportPrecheck';

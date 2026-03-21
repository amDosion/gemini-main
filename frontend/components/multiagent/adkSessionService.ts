import {
  requestJson,
} from '../../services/http';

export interface AdkSessionItem {
  id: string;
  raw: Record<string, unknown>;
}

export interface AdkSessionSnapshot {
  id: string;
  raw: Record<string, unknown>;
}

export interface ConfirmToolRequest {
  functionCallId: string;
  confirmed?: boolean;
  hint?: string;
  payload?: unknown;
  invocationId?: string;
  ticket?: unknown;
  approvalTicket?: AdkApprovalTicket | null;
  nonce?: string;
  nonceExpiresAt?: string;
  ticketTimestampMs?: unknown;
  ticketTtlSeconds?: unknown;
  tenantId?: string;
  candidateId?: string;
}

export interface AdkApprovalTicket {
  [key: string]: unknown;
}

export interface AdkConfirmCandidate {
  id: string;
  name: string;
  hint: string;
  invocationId: string;
  payload: unknown;
  payloadPreview: string;
  ticket: string;
  approvalTicket: AdkApprovalTicket | null;
  nonce: string;
  nonceExpiresAt: string;
  tenantId: string;
  sourcePath: string;
}

export type AdkExportPrecheckIssueCode = 'sensitive_fields' | 'tenant_mismatch' | 'unknown';

export interface AdkExportPrecheckIssue {
  id: string;
  code: AdkExportPrecheckIssueCode;
  title: string;
  detail: string;
  fields: string[];
  tenantId: string;
  expectedTenantId: string;
  sourcePath: string;
  raw: Record<string, unknown>;
}

export type AdkRuntimeErrorCode =
  | 'ADK_RUNTIME_UNAVAILABLE'
  | 'ADK_FALLBACK_FORBIDDEN'
  | 'ADK_STRATEGY_VIOLATION';

interface AdkRuntimeErrorPayload {
  errorCode: AdkRuntimeErrorCode;
  message: string;
  runtimeStrategy: string;
  strictMode: boolean;
}

export interface AdkRuntimePolicyOption {
  value: string;
  label: string;
}

export interface AdkRuntimePolicyState {
  effectiveStrategy: string;
  effectiveStrictMode: boolean;
  selectedStrategy: string;
  selectedStrictMode: boolean;
  sourcePath: string;
  options: AdkRuntimePolicyOption[];
}

export interface AdkConfirmActionSupport {
  supportsExplicitReject: boolean;
  sourcePath: string;
}

const toSafeString = (value: unknown): string => String(value ?? '').trim();

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

const FUNCTION_CALL_CONTAINER_KEYS = new Set([
  'function_calls',
  'functionCalls',
]);

const CANDIDATE_ID_KEYS = [
  'id',
  'function_call_id',
  'functionCallId',
  'call_id',
  'callId',
  'tool_call_id',
  'toolCallId',
];

const CANDIDATE_NAME_KEYS = [
  'name',
  'function_name',
  'functionName',
  'tool_name',
  'toolName',
];

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

const CANDIDATE_TENANT_KEYS = [
  'tenant_id',
  'tenantId',
  'tenant',
  'tenant_scope',
  'tenantScope',
];

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

const EXPORT_PRECHECK_CONTAINER_KEYS = new Set([
  'export_precheck',
  'exportPrecheck',
  'export_prechecks',
  'exportPrechecks',
  'export_precheck_result',
  'exportPrecheckResult',
  'precheck',
  'pre_check',
]);

const EXPORT_PRECHECK_ISSUES_KEYS = [
  'issues',
  'errors',
  'reasons',
  'violations',
  'findings',
];

const EXPORT_PRECHECK_CODE_KEYS = [
  'code',
  'reason_code',
  'reasonCode',
  'type',
  'kind',
  'error_code',
  'errorCode',
];

const EXPORT_PRECHECK_MESSAGE_KEYS = [
  'message',
  'detail',
  'reason',
  'hint',
  'description',
  'error',
  'status',
];

const EXPORT_PRECHECK_FIELDS_KEYS = [
  'sensitive_fields',
  'sensitiveFields',
  'fields',
  'column_names',
  'columnNames',
  'columns',
];

const EXPORT_PRECHECK_TENANT_KEYS = [
  'tenant_id',
  'tenantId',
  'tenant',
  'actual_tenant_id',
  'actualTenantId',
];

const EXPORT_PRECHECK_EXPECTED_TENANT_KEYS = [
  'expected_tenant_id',
  'expectedTenantId',
  'resource_tenant_id',
  'resourceTenantId',
];

const REQUEST_FAILED_STATUS_RE = /^Request failed:\s*(\d+)$/;
const DEFAULT_RUNTIME_STRATEGY = 'official_or_legacy';
const MAX_APPROVAL_TICKET_TTL_SECONDS = 30 * 60;
const ADK_RUNTIME_ERROR_CODES: AdkRuntimeErrorCode[] = [
  'ADK_RUNTIME_UNAVAILABLE',
  'ADK_FALLBACK_FORBIDDEN',
  'ADK_STRATEGY_VIOLATION',
];
const ADK_RUNTIME_ERROR_CODE_SET = new Set<string>(ADK_RUNTIME_ERROR_CODES);
const RUNTIME_STRATEGY_KEYS = ['runtime_strategy', 'runtimeStrategy'];
const STRICT_MODE_KEYS = ['strict_mode', 'strictMode'];
const BACKEND_RUNTIME_STRATEGY_OPTIONS = ['official_only', 'official_or_legacy', 'allow_legacy'];
const RUNTIME_STRATEGY_OPTIONS_KEYS = [
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
const RUNTIME_STRATEGY_LABELS: Record<string, string> = {
  official_only: '仅官方 ADK',
  official_or_legacy: '官方优先（默认禁止 fallback）',
  allow_legacy: '显式允许 legacy fallback',
};
const EXPLICIT_REJECT_SUPPORT_KEYS = [
  'supports_reject',
  'supportsReject',
  'reject_supported',
  'rejectSupported',
  'allow_reject',
  'allowReject',
  'can_reject',
  'canReject',
];
const EXPLICIT_REJECT_CONTAINER_KEYS = new Set([
  'confirm_tool_contract',
  'confirmToolContract',
  'tool_confirmation_contract',
  'toolConfirmationContract',
  'confirm_contract',
  'confirmContract',
]);

const isRecord = (value: unknown): value is UnknownRecord =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const pickFirstString = (record: UnknownRecord, keys: string[]): string => {
  for (const key of keys) {
    if (!(key in record)) continue;
    const text = toSafeString(record[key]);
    if (text) return text;
  }
  return '';
};

const pickFirstValue = (record: UnknownRecord, keys: string[]): unknown => {
  for (const key of keys) {
    if (!(key in record)) continue;
    const value = record[key];
    if (value !== undefined) return value;
  }
  return undefined;
};

const trimPreview = (text: string, maxLen: number = 220): string => {
  const compact = String(text || '').replace(/\s+/g, ' ').trim();
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

const toPositiveInteger = (value: unknown): number => {
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
  if (!raw || (!raw.startsWith('{') || !raw.endsWith('}'))) return null;
  try {
    const parsed = JSON.parse(raw);
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
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

const resolveTicketTimestampAndTtl = ({
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
    ? toPositiveInteger(
        pickFirstValue(ticketRecord, ['ttl_seconds', 'ttlSeconds', 'ttl'])
      )
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

const buildApprovalTicketPayload = ({
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
    const nestedText = resolveNestedSecurityString(nested, keys, options.allowIdValueFallback === true);
    if (nestedText) return nestedText;
  }

  const nestedCall = pickFirstValue(record, ['function_call', 'functionCall']);
  if (isRecord(nestedCall)) {
    const nestedCallDirect = pickFirstString(nestedCall, keys);
    if (nestedCallDirect) return nestedCallDirect;

    for (const contextKey of CANDIDATE_CONTEXT_KEYS) {
      const nested = pickFirstValue(nestedCall, [contextKey]);
      const nestedText = resolveNestedSecurityString(nested, keys, options.allowIdValueFallback === true);
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

const collectStringList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value
      .map((item) => toSafeString(item))
      .filter(Boolean);
  }

  if (typeof value === 'string') {
    return value
      .split(',')
      .map((item) => toSafeString(item))
      .filter(Boolean);
  }

  return [];
};

const normalizeExportPrecheckCode = (
  rawCode: string,
  detail: string,
  fields: string[],
  record: UnknownRecord
): AdkExportPrecheckIssueCode => {
  const text = `${rawCode} ${detail}`.toLowerCase();
  const hasTenantFlag = Boolean(record.tenant_mismatch || record.tenantMismatch);
  if (hasTenantFlag || /tenant|租户/.test(text)) {
    return 'tenant_mismatch';
  }

  if (
    fields.length > 0
    || Boolean(record.sensitive_fields)
    || Boolean(record.sensitiveFields)
    || /sensitive|pii|secret|隐私|敏感/.test(text)
  ) {
    return 'sensitive_fields';
  }

  return 'unknown';
};

const buildExportPrecheckIssue = (
  record: UnknownRecord,
  sourcePath: string,
  fallbackIndex: number
): AdkExportPrecheckIssue | null => {
  const fields = EXPORT_PRECHECK_FIELDS_KEYS.flatMap((key) => collectStringList(record[key]));
  const detail = pickFirstString(record, EXPORT_PRECHECK_MESSAGE_KEYS);
  const rawCode = pickFirstString(record, EXPORT_PRECHECK_CODE_KEYS);
  const tenantId = pickFirstString(record, EXPORT_PRECHECK_TENANT_KEYS);
  const expectedTenantId = pickFirstString(record, EXPORT_PRECHECK_EXPECTED_TENANT_KEYS);
  const code = normalizeExportPrecheckCode(rawCode, detail, fields, record);

  if (code === 'unknown' && !detail && fields.length === 0 && !tenantId && !expectedTenantId) {
    return null;
  }

  const title = (
    code === 'sensitive_fields'
      ? '导出前校验失败：命中敏感字段'
      : code === 'tenant_mismatch'
        ? '导出前校验失败：租户不匹配'
        : '导出前校验失败'
  );

  const resolvedDetail = (
    detail
    || (code === 'sensitive_fields'
      ? '检测到敏感字段，导出被后端安全策略拒绝。'
      : code === 'tenant_mismatch'
        ? '检测到导出租户与会话租户不一致，导出被拒绝。'
        : '导出 precheck 未通过。')
  );

  return {
    id: `${sourcePath}:${rawCode || code || fallbackIndex}`,
    code,
    title,
    detail: resolvedDetail,
    fields: Array.from(new Set(fields)),
    tenantId,
    expectedTenantId,
    sourcePath,
    raw: record,
  };
};

const collectExportPrecheckIssuesFromContainer = (
  container: unknown,
  sourcePath: string,
  collector: Map<string, AdkExportPrecheckIssue>
): void => {
  if (Array.isArray(container)) {
    container.forEach((item, index) => {
      if (!isRecord(item)) return;
      const issue = buildExportPrecheckIssue(item, `${sourcePath}[${index}]`, index);
      if (!issue) return;
      collector.set(issue.id, issue);
    });
    return;
  }

  if (!isRecord(container)) return;
  const directIssue = buildExportPrecheckIssue(container, sourcePath, 0);
  if (directIssue) {
    collector.set(directIssue.id, directIssue);
  }

  for (const key of EXPORT_PRECHECK_ISSUES_KEYS) {
    const nested = pickFirstValue(container, [key]);
    if (Array.isArray(nested)) {
      nested.forEach((item, index) => {
        if (!isRecord(item)) return;
        const issue = buildExportPrecheckIssue(item, `${sourcePath}.${key}[${index}]`, index);
        if (!issue) return;
        collector.set(issue.id, issue);
      });
      continue;
    }

    if (isRecord(nested)) {
      const issue = buildExportPrecheckIssue(nested, `${sourcePath}.${key}`, 0);
      if (issue) {
        collector.set(issue.id, issue);
      }
    }
  }
};

export const extractAdkExportPrecheckIssues = (sessionSnapshot: unknown): AdkExportPrecheckIssue[] => {
  if (!sessionSnapshot) return [];

  const collector = new Map<string, AdkExportPrecheckIssue>();
  const visited = new WeakSet<object>();

  const visit = (value: unknown, path: string): void => {
    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        visit(item, `${path}[${index}]`);
      });
      return;
    }

    if (!isRecord(value)) return;
    if (visited.has(value)) return;
    visited.add(value);

    for (const [key, nestedValue] of Object.entries(value)) {
      const nextPath = `${path}.${key}`;
      if (EXPORT_PRECHECK_CONTAINER_KEYS.has(key)) {
        collectExportPrecheckIssuesFromContainer(nestedValue, nextPath, collector);
      }
      visit(nestedValue, nextPath);
    }
  };

  visit(sessionSnapshot, 'snapshot');

  return Array.from(collector.values()).sort((left, right) => left.id.localeCompare(right.id));
};

const toBoolean = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value;
  const text = toSafeString(value).toLowerCase();
  return text === '1' || text === 'true' || text === 'yes';
};

const resolveRuntimeStrategyLabel = (strategy: string): string =>
  RUNTIME_STRATEGY_LABELS[strategy] || `自定义策略（${strategy}）`;

const normalizeRuntimeStrategyValue = (value: unknown): string => toSafeString(value).toLowerCase();

const collectRuntimeStrategyValues = (sessionSnapshot: unknown): string[] => {
  const collector = new Set<string>();
  const visited = new WeakSet<object>();

  const addStrategy = (rawValue: Record<string, unknown>): void => {
    if (Array.isArray(rawValue)) {
      rawValue.forEach((item) => addStrategy(item));
      return;
    }
    const text = normalizeRuntimeStrategyValue(rawValue);
    if (!text) return;
    collector.add(text);
  };

  const visit = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach((item) => visit(item));
      return;
    }
    if (!isRecord(value)) return;
    if (visited.has(value)) return;
    visited.add(value);

    const runtimeStrategy = pickFirstString(value, RUNTIME_STRATEGY_KEYS);
    if (runtimeStrategy) {
      addStrategy(runtimeStrategy);
    }

    for (const key of RUNTIME_STRATEGY_OPTIONS_KEYS) {
      if (!(key in value)) continue;
      addStrategy(value[key]);
    }

    Object.values(value).forEach((nested) => visit(nested));
  };

  visit(sessionSnapshot);

  return Array.from(collector);
};

const buildRuntimePolicyOptions = ({
  sessionSnapshot,
  effectiveStrategy,
  selectedStrategy,
}: {
  sessionSnapshot: unknown;
  effectiveStrategy: string;
  selectedStrategy: string;
}): AdkRuntimePolicyOption[] => {
  const discoveredValues = collectRuntimeStrategyValues(sessionSnapshot);
  const ordered = [
    ...(discoveredValues.length > 0 ? discoveredValues : BACKEND_RUNTIME_STRATEGY_OPTIONS),
    effectiveStrategy,
    selectedStrategy,
  ].filter(Boolean);

  const seen = new Set<string>();
  const deduped: string[] = [];
  ordered.forEach((item) => {
    const normalized = normalizeRuntimeStrategyValue(item);
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    deduped.push(normalized);
  });

  return deduped.map((value) => ({
    value,
    label: resolveRuntimeStrategyLabel(value),
  }));
};

interface RuntimePolicyProbe {
  runtimeStrategy: string;
  strictMode: boolean;
  score: number;
  sourcePath: string;
}

const probeRuntimePolicy = (value: unknown, path: string, visited: WeakSet<object>): RuntimePolicyProbe | null => {
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      const nested = probeRuntimePolicy(value[index], `${path}[${index}]`, visited);
      if (nested) return nested;
    }
    return null;
  }

  if (!isRecord(value)) return null;
  if (visited.has(value)) return null;
  visited.add(value);

  const runtimeStrategy = pickFirstString(value, RUNTIME_STRATEGY_KEYS);
  const strictModeRaw = pickFirstValue(value, STRICT_MODE_KEYS);
  const hasStrategy = Boolean(runtimeStrategy);
  const hasStrictMode = strictModeRaw !== undefined;
  if (hasStrategy || hasStrictMode) {
    return {
      runtimeStrategy: runtimeStrategy || DEFAULT_RUNTIME_STRATEGY,
      strictMode: hasStrictMode ? toBoolean(strictModeRaw) : false,
      score: (hasStrategy ? 2 : 0) + (hasStrictMode ? 1 : 0),
      sourcePath: path,
    };
  }

  let best: RuntimePolicyProbe | null = null;
  for (const [key, nestedValue] of Object.entries(value)) {
    const nested = probeRuntimePolicy(nestedValue, `${path}.${key}`, visited);
    if (!nested) continue;
    if (!best || nested.score > best.score) {
      best = nested;
    }
  }
  return best;
};

export const extractAdkRuntimePolicyState = (
  sessionSnapshot: unknown,
  draft: Partial<Pick<AdkRuntimePolicyState, 'selectedStrategy' | 'selectedStrictMode'>> = {}
): AdkRuntimePolicyState => {
  const probe = probeRuntimePolicy(sessionSnapshot, 'snapshot', new WeakSet<object>());
  const effectiveStrategy = normalizeRuntimeStrategyValue(probe?.runtimeStrategy || DEFAULT_RUNTIME_STRATEGY);
  const effectiveStrictMode = probe?.strictMode ?? false;
  const selectedStrategy = normalizeRuntimeStrategyValue(draft.selectedStrategy) || effectiveStrategy;
  const selectedStrictMode = (
    typeof draft.selectedStrictMode === 'boolean'
      ? draft.selectedStrictMode
      : effectiveStrictMode
  );

  return {
    effectiveStrategy,
    effectiveStrictMode,
    selectedStrategy,
    selectedStrictMode,
    sourcePath: probe?.sourcePath || 'snapshot(default)',
    options: buildRuntimePolicyOptions({
      sessionSnapshot,
      effectiveStrategy,
      selectedStrategy,
    }),
  };
};

const detectExplicitRejectSupport = (record: UnknownRecord): boolean | null => {
  const direct = pickFirstValue(record, EXPLICIT_REJECT_SUPPORT_KEYS);
  if (direct !== undefined) {
    return toBoolean(direct);
  }

  const supportedActions = pickFirstValue(record, ['supported_actions', 'supportedActions', 'actions']);
  if (Array.isArray(supportedActions)) {
    const normalized = supportedActions.map((item) => toSafeString(item).toLowerCase()).filter(Boolean);
    if (normalized.includes('reject') || normalized.includes('deny')) {
      return true;
    }
  }

  const confirmedValues = pickFirstValue(record, ['confirmed_values', 'confirmedValues']);
  if (Array.isArray(confirmedValues)) {
    const hasTrue = confirmedValues.some((item) => item === true || toSafeString(item) === 'true');
    const hasFalse = confirmedValues.some((item) => item === false || toSafeString(item) === 'false');
    if (hasTrue && hasFalse) {
      return true;
    }
  }

  return null;
};

export const extractAdkConfirmActionSupport = (sessionSnapshot: unknown): AdkConfirmActionSupport => {
  const visited = new WeakSet<object>();
  const fallback: AdkConfirmActionSupport = {
    supportsExplicitReject: false,
    sourcePath: 'snapshot(default)',
  };

  const visit = (value: unknown, path: string): AdkConfirmActionSupport | null => {
    if (Array.isArray(value)) {
      for (let index = 0; index < value.length; index += 1) {
        const nested = visit(value[index], `${path}[${index}]`);
        if (nested) return nested;
      }
      return null;
    }

    if (!isRecord(value)) return null;
    if (visited.has(value)) return null;
    visited.add(value);

    const direct = detectExplicitRejectSupport(value);
    if (direct !== null) {
      return {
        supportsExplicitReject: direct,
        sourcePath: path,
      };
    }

    for (const [key, nestedValue] of Object.entries(value)) {
      const nestedPath = `${path}.${key}`;
      if (EXPLICIT_REJECT_CONTAINER_KEYS.has(key) && isRecord(nestedValue)) {
        const container = detectExplicitRejectSupport(nestedValue);
        if (container !== null) {
          return {
            supportsExplicitReject: container,
            sourcePath: nestedPath,
          };
        }
      }
      const nested = visit(nestedValue, nestedPath);
      if (nested) return nested;
    }

    return null;
  };

  return visit(sessionSnapshot, 'snapshot') || fallback;
};

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

export const formatAdkRuntimeContractErrorMessage = (error: unknown, fallbackMessage: string): string => {
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
  const isInvalid = (
    normalized.includes('invalid')
    || normalized.includes('mismatch')
    || normalized.includes('replay')
    || normalized.includes('consumed')
    || normalized.includes('used')
    || normalized.includes('绑定')
  );

  if ((hasNonce || hasTicket) && isExpired) {
    return '审批票据已过期，请刷新会话后重新选择候选确认项。';
  }

  if ((hasNonce || hasTicket) && isInvalid) {
    return '审批票据无效或已被消费，请刷新会话后重新提交。';
  }

  if (normalized.includes('tenant') && (normalized.includes('mismatch') || normalized.includes('invalid'))) {
    return '审批票据与当前租户不匹配，请确认租户上下文后重试。';
  }

  if (
    normalized.includes('default deny')
    || normalized.includes('explicit approve')
    || normalized.includes('explicit confirmed=true')
  ) {
    return '当前策略默认拒绝，请先显式选择“批准”并使用有效票据。';
  }

  return null;
};

export const formatAdkConfirmToolErrorMessage = (error: unknown, fallbackMessage: string): string => {
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
    normalized.includes('sensitive')
    || normalized.includes('pii')
    || normalized.includes('secret')
    || normalized.includes('敏感')
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

const normalizeSessionId = (payload: Record<string, unknown>): string => toSafeString(payload?.sessionId || payload?.session_id || payload?.id);
const buildAgentRuntimeRoute = (agentId: string, suffix: string): string => (
  `/api/multi-agent/agents/${encodeURIComponent(agentId)}/runtime${suffix}`
);

export const listAdkAgentSessions = async (
  agentId: string,
  signal?: AbortSignal
): Promise<AdkSessionItem[]> => {
  const normalizedAgentId = toSafeString(agentId);
  if (!normalizedAgentId) return [];

  let payload: unknown;
  try {
    payload = await requestJson<unknown>(
      buildAgentRuntimeRoute(normalizedAgentId, '/sessions'),
      {
        signal,
        timeoutMs: 0,
        withAuth: true,
      }
    );
  } catch (error) {
    throw remapRequestFailedError(error, '加载运行时会话失败');
  }
  const sessions = Array.isArray(payload?.sessions) ? payload.sessions : [];

  return sessions
    .map((session: Record<string, unknown>) => ({
      id: normalizeSessionId(session),
      raw: session,
    }))
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
  const session = payload?.session;
  const resolvedId = normalizeSessionId(session) || normalizedSessionId;

  return {
    id: resolvedId,
    raw: session,
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
  const legacyTicketField: unknown = (
    isRecord(rawTicket)
      ? rawTicket
      : (toSafeString(rawTicket) || undefined)
  );
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

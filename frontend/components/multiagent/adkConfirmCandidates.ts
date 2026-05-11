/**
 * ADK Confirm Candidates 提取器（最大单一 extractor）。
 *
 * 1:1 抽离自 `adkSessionService.ts` L466-839
 * （JIRA-frontend-deep-architecture-split.md #2 Step 4 — 最终步骤）。
 *
 * 包括：
 * - 15 个 resolveCandidate* 字段解析 helper
 * - buildCandidateDraft / mergeCandidateDraft / collectCandidatesFromContainer
 * - extractAdkConfirmCandidates 主入口
 */

import type {
  AdkConfirmCandidate,
  AdkApprovalTicket,
} from './adkSessionTypes';
import {
  toSafeString,
  isRecord,
  pickFirstString,
  pickFirstValue,
  trimPreview,
  buildPayloadPreview,
  isApprovalTicketLike,
  parseJsonObject,
  toApprovalTicketObject,
  CONFIRMATION_CONTAINER_KEYS,
  FUNCTION_CALL_CONTAINER_KEYS,
  CANDIDATE_ID_KEYS,
  CANDIDATE_NAME_KEYS,
  CANDIDATE_HINT_KEYS,
  INVOCATION_ID_KEYS,
  CANDIDATE_TICKET_KEYS,
  CANDIDATE_NONCE_KEYS,
  CANDIDATE_NONCE_EXPIRES_KEYS,
  CANDIDATE_TENANT_KEYS,
  CANDIDATE_CONTEXT_KEYS,
} from './adkSessionService';

type UnknownRecord = Record<string, unknown>;
type CandidateSource = 'requested_confirmation' | 'function_call';

interface CandidateDraft extends AdkConfirmCandidate {
  score: number;
}


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

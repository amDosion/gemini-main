/**
 * ADK Session 协议类型定义（外部 + 内部）。
 *
 * 1:1 抽离自 `adkSessionService.ts` L4-92
 * （< 800 行合规拆分）。
 */

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

export interface AdkRuntimeErrorPayload {
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

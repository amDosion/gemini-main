import { requestJson } from './http';

export interface DeepResearchStreamPolicy {
  idleTimeoutMs: number;
  watchdogIntervalMs: number;
  maxRecoveryAttempts: number;
}

export interface WorkflowExecutionPolicy {
  sseIdleThresholdMs: number;
  pollingIntervalMs: number;
  hardTimeoutMs: number;
}

export const DEFAULT_DEEP_RESEARCH_STREAM_POLICY: DeepResearchStreamPolicy = {
  idleTimeoutMs: 180_000,
  watchdogIntervalMs: 5_000,
  maxRecoveryAttempts: 8,
};

export const DEFAULT_WORKFLOW_EXECUTION_POLICY: WorkflowExecutionPolicy = {
  sseIdleThresholdMs: 15_000,
  pollingIntervalMs: 8_000,
  hardTimeoutMs: 30 * 60 * 1000,
};

let deepResearchPolicyCache: DeepResearchStreamPolicy | null = null;
let workflowExecutionPolicyCache: WorkflowExecutionPolicy | null = null;

const clampInteger = (
  value: unknown,
  fallback: number,
  minimum: number,
  maximum: number
): number => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, Math.min(maximum, Math.round(parsed)));
};

const normalizeDeepResearchPolicy = (payload: Record<string, unknown>): DeepResearchStreamPolicy => ({
  idleTimeoutMs: clampInteger(
    payload?.idleTimeoutMs ?? payload?.idle_timeout_ms,
    DEFAULT_DEEP_RESEARCH_STREAM_POLICY.idleTimeoutMs,
    30_000,
    30 * 60 * 1000
  ),
  watchdogIntervalMs: clampInteger(
    payload?.watchdogIntervalMs ?? payload?.watchdog_interval_ms,
    DEFAULT_DEEP_RESEARCH_STREAM_POLICY.watchdogIntervalMs,
    1_000,
    60_000
  ),
  maxRecoveryAttempts: clampInteger(
    payload?.maxRecoveryAttempts ?? payload?.max_recovery_attempts,
    DEFAULT_DEEP_RESEARCH_STREAM_POLICY.maxRecoveryAttempts,
    1,
    20
  ),
});

const normalizeWorkflowExecutionPolicy = (payload: Record<string, unknown>): WorkflowExecutionPolicy => ({
  sseIdleThresholdMs: clampInteger(
    payload?.sseIdleThresholdMs ?? payload?.sse_idle_threshold_ms,
    DEFAULT_WORKFLOW_EXECUTION_POLICY.sseIdleThresholdMs,
    5_000,
    2 * 60 * 1000
  ),
  pollingIntervalMs: clampInteger(
    payload?.pollingIntervalMs ?? payload?.polling_interval_ms,
    DEFAULT_WORKFLOW_EXECUTION_POLICY.pollingIntervalMs,
    1_000,
    2 * 60 * 1000
  ),
  hardTimeoutMs: clampInteger(
    payload?.hardTimeoutMs ?? payload?.hard_timeout_ms,
    DEFAULT_WORKFLOW_EXECUTION_POLICY.hardTimeoutMs,
    60_000,
    6 * 60 * 60 * 1000
  ),
});

export const fetchDeepResearchStreamPolicy = async (): Promise<DeepResearchStreamPolicy> => {
  if (deepResearchPolicyCache) {
    return deepResearchPolicyCache;
  }
  try {
    const payload = await requestJson<Record<string, unknown>>('/api/research/stream/policy', {
      withAuth: true,
      errorMessage: '加载 Deep Research 策略失败',
    });
    deepResearchPolicyCache = normalizeDeepResearchPolicy(payload);
    return deepResearchPolicyCache;
  } catch {
    return deepResearchPolicyCache || DEFAULT_DEEP_RESEARCH_STREAM_POLICY;
  }
};

export const fetchWorkflowExecutionPolicy = async (): Promise<WorkflowExecutionPolicy> => {
  if (workflowExecutionPolicyCache) {
    return workflowExecutionPolicyCache;
  }
  try {
    const payload = await requestJson<Record<string, unknown>>('/api/workflows/execution-policy', {
      withAuth: true,
      errorMessage: '加载工作流执行策略失败',
    });
    workflowExecutionPolicyCache = normalizeWorkflowExecutionPolicy(payload);
    return workflowExecutionPolicyCache;
  } catch {
    return workflowExecutionPolicyCache || DEFAULT_WORKFLOW_EXECUTION_POLICY;
  }
};


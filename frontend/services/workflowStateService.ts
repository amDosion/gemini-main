import { requestJson } from './http';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value);

const WORKFLOW_STATE_MARKER_KEYS = [
  'status',
  'finalStatus',
  'executionId',
  'isTerminal',
  'stateVersion',
  'clientPolicy',
  'nodeStatuses',
  'nodeExecutions',
  'nodeResults',
  'nodeErrors',
  'nodeProgress',
  'resultSummary',
  'finalResult',
  'result',
  'error',
] as const;

const hasWorkflowStateMarker = (payload: Record<string, unknown>): boolean =>
  WORKFLOW_STATE_MARKER_KEYS.some((key) => Object.prototype.hasOwnProperty.call(payload, key));

export const resolveWorkflowExecutionStatePayload = (payload: unknown): Record<string, unknown> => {
  if (!isRecord(payload)) {
    throw new Error('工作流状态格式错误：缺少 execution_state');
  }
  if (isRecord(payload.execution_state)) {
    return payload.execution_state;
  }
  if (isRecord(payload.executionState)) {
    return payload.executionState;
  }
  if (hasWorkflowStateMarker(payload)) {
    return payload;
  }
  throw new Error('工作流状态格式错误：缺少 execution_state');
};

export const fetchWorkflowExecutionState = async (
  executionId: string,
  signal?: AbortSignal
): Promise<{ execution_state: Record<string, unknown> }> => {
  const safeExecutionId = String(executionId || '').trim();
  if (!safeExecutionId) {
    throw new Error('缺少 executionId');
  }

  const payload = await requestJson<Record<string, unknown>>(
    `/api/workflows/${encodeURIComponent(safeExecutionId)}/state`,
    {
      withAuth: true,
      signal,
      timeoutMs: 0,
      errorMessage: '加载工作流状态失败',
    }
  );

  return {
    execution_state: resolveWorkflowExecutionStatePayload(payload),
  };
};

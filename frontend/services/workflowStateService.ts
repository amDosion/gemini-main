import { requestJson } from './http';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value);

export const resolveWorkflowExecutionStatePayload = (payload: unknown): Record<string, unknown> => {
  if (!isRecord(payload) || !isRecord(payload.execution_state)) {
    throw new Error('工作流状态格式错误：缺少 execution_state');
  }
  return payload.execution_state;
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
      credentials: 'include',
      signal,
      timeoutMs: 0,
      errorMessage: '加载工作流状态失败',
    }
  );

  return {
    execution_state: resolveWorkflowExecutionStatePayload(payload),
  };
};

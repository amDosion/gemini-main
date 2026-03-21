import { requestJson } from './http';

const isRecord = (value: unknown): value is Record<string, any> =>
  !!value && typeof value === 'object' && !Array.isArray(value);

export const resolveWorkflowExecutionStatePayload = (payload: any): any => {
  if (!isRecord(payload) || !isRecord(payload.execution_state)) {
    throw new Error('工作流状态格式错误：缺少 execution_state');
  }
  return payload.execution_state;
};

export const fetchWorkflowExecutionState = async (
  executionId: string,
  signal?: AbortSignal
): Promise<any> => {
  const safeExecutionId = String(executionId || '').trim();
  if (!safeExecutionId) {
    throw new Error('缺少 executionId');
  }

  const payload = await requestJson<any>(
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

import type { ExecutionStatus } from '../../multiagent/types';
import { PREVIEW_IMAGE_MAX_ENTRIES } from '../../multiagent/workflowResultUtils';
import { resolveWorkflowExecutionStatePayload } from '../../../services/workflowStateService';
import { normalizeSnapshotForApply, normalizeWorkflowFinalStatus } from './executionStatusUtils';
import {
  extractRuntimeHints,
  mergeRuntimeHints,
  normalizeRuntimeHint,
  pickPrimaryRuntime,
} from './runtimeHints';

export type UnknownRecord = Record<string, unknown>;
export type WorkflowFinalStatus = NonNullable<ExecutionStatus['finalStatus']>;
export type NormalizedWorkflowSnapshot = ReturnType<typeof normalizeSnapshotForApply>;
type WorkflowNormalizedStatus = ReturnType<typeof normalizeWorkflowFinalStatus>;
type ExecutionLogLevel = ExecutionStatus['logs'][number]['level'];

export interface ConsumedExecutionState {
  consumed: boolean;
  normalizedPayload: NormalizedWorkflowSnapshot | null;
  status: WorkflowNormalizedStatus;
}

export interface TerminalPayloadOptions {
  failedError?: string;
  pausedError?: string;
}

export interface TerminalStateResolution {
  normalizedPayload: NormalizedWorkflowSnapshot;
  terminalStatus: WorkflowFinalStatus;
  terminalError: string;
  terminalLogLevel: ExecutionLogLevel;
  terminalLogMessage: string;
}

export type ConsumedStateFinalizePlan =
  | { kind: 'none' }
  | { kind: 'completed'; payload: NormalizedWorkflowSnapshot }
  | { kind: 'terminal'; payload: NormalizedWorkflowSnapshot };

export type ExecutionStreamAction =
  | { type: 'apply_snapshot'; snapshot: unknown }
  | { type: 'apply_completed'; payload: unknown; now: number }
  | { type: 'apply_terminal'; resolution: TerminalStateResolution; now: number }
  | { type: 'append_log'; entry: ExecutionStatus['logs'][number] };

const isRecord = (value: unknown): value is UnknownRecord =>
  !!value && typeof value === 'object' && !Array.isArray(value);

const normalizeSnapshot = (payload: unknown): NormalizedWorkflowSnapshot =>
  normalizeSnapshotForApply(payload) as NormalizedWorkflowSnapshot;

const normalizePreviewUrls = (value: unknown): string[] =>
  Array.isArray(value)
    ? value
        .map((item) => String(item || '').trim())
        .filter(Boolean)
    : [];

const normalizeBoundedPreviewUrls = (value: unknown, limit: number): string[] =>
  normalizePreviewUrls(value).slice(0, Math.max(0, limit));

const appendLog = (
  prev: ExecutionStatus,
  entry: ExecutionStatus['logs'][number]
): ExecutionStatus => ({
  ...prev,
  logs: [...(prev.logs || []), entry],
});

export const consumeExecutionStatePayload = (payload: unknown): ConsumedExecutionState => {
  let resolvedPayload: unknown = null;
  try {
    resolvedPayload = resolveWorkflowExecutionStatePayload(payload) as unknown;
  } catch {
    return { consumed: false, normalizedPayload: null, status: 'pending' };
  }
  if (!isRecord(resolvedPayload)) {
    return { consumed: false, normalizedPayload: null, status: 'pending' };
  }
  const normalizedPayload = normalizeSnapshot(resolvedPayload);
  return {
    consumed: true,
    normalizedPayload,
    status: normalizeWorkflowFinalStatus(normalizedPayload?.status),
  };
};

export const buildTerminalPayload = (
  normalizedPayload: NormalizedWorkflowSnapshot,
  status: WorkflowFinalStatus,
  now: number,
  options: TerminalPayloadOptions = {}
): NormalizedWorkflowSnapshot => ({
  ...normalizedPayload,
  status,
  error:
    normalizedPayload?.error ||
    (status === 'failed'
      ? options.failedError || `工作流状态异常: ${status}`
      : status === 'workflow_paused'
        ? options.pausedError
        : undefined),
  completedAt: normalizedPayload?.completedAt || now,
});

export const resolveConsumedStateFinalizePlan = (
  consumedState: ConsumedExecutionState,
  now: number,
  options: TerminalPayloadOptions = {}
): ConsumedStateFinalizePlan => {
  if (!consumedState.consumed || !consumedState.normalizedPayload) {
    return { kind: 'none' };
  }
  if (consumedState.status === 'completed') {
    return { kind: 'completed', payload: consumedState.normalizedPayload };
  }
  if (
    consumedState.status === 'failed' ||
    consumedState.status === 'cancelled' ||
    consumedState.status === 'workflow_paused'
  ) {
    return {
      kind: 'terminal',
      payload: buildTerminalPayload(consumedState.normalizedPayload, consumedState.status, now, options),
    };
  }
  return { kind: 'none' };
};

export const resolveTerminalState = (payload: unknown): TerminalStateResolution => {
  const normalizedPayload = normalizeSnapshot(payload);
  const normalizedStatus = normalizeWorkflowFinalStatus(normalizedPayload?.status);
  const terminalStatus: WorkflowFinalStatus =
    normalizedStatus === 'cancelled' || normalizedStatus === 'workflow_paused'
      ? normalizedStatus
      : 'failed';
  const terminalDefaultError =
    terminalStatus === 'cancelled'
      ? '工作流执行已取消'
      : terminalStatus === 'workflow_paused'
        ? '工作流已暂停，可稍后在历史记录中继续查看。'
        : '工作流执行失败';
  const terminalError = String(normalizedPayload?.error || terminalDefaultError);
  const terminalLogLevel: ExecutionLogLevel = terminalStatus === 'failed' ? 'error' : 'warn';
  const terminalLogMessage =
    terminalStatus === 'failed'
      ? `工作流执行失败: ${terminalError}`
      : terminalStatus === 'workflow_paused'
        ? `工作流执行已暂停: ${terminalError}`
        : `工作流执行已取消${normalizedPayload?.error ? `: ${terminalError}` : ''}`;

  return {
    normalizedPayload,
    terminalStatus,
    terminalError,
    terminalLogLevel,
    terminalLogMessage,
  };
};

export const executionStreamReducer = (
  prev: ExecutionStatus | undefined,
  action: ExecutionStreamAction
): ExecutionStatus | undefined => {
  if (!prev) return prev;

  switch (action.type) {
    case 'apply_snapshot': {
      const normalizedSnapshot = normalizeSnapshot(action.snapshot);
      const snapshotNodeRuntimes: Record<string, string> = {};
      const nodeResults = isRecord(normalizedSnapshot?.nodeResults) ? normalizedSnapshot.nodeResults : {};
      Object.entries(nodeResults).forEach(([nodeId, nodeOutput]) => {
        const runtime = pickPrimaryRuntime(extractRuntimeHints(nodeOutput));
        if (runtime) {
          snapshotNodeRuntimes[nodeId] = runtime;
        }
      });
      const snapshotRuntimeHints = mergeRuntimeHints(
        mergeRuntimeHints(
          extractRuntimeHints(normalizedSnapshot?.result),
          extractRuntimeHints(normalizedSnapshot?.resultSummary)
        ),
        Array.isArray(normalizedSnapshot?.runtimeHints) ? normalizedSnapshot.runtimeHints : []
      );
      const snapshotPrimaryRuntime =
        normalizeRuntimeHint(
          normalizedSnapshot?.primaryRuntime || normalizedSnapshot?.resultSummary?.primaryRuntime || ''
        ) || pickPrimaryRuntime(snapshotRuntimeHints);
      const mergedHints = mergeRuntimeHints(prev.runtimeHints || [], snapshotRuntimeHints);

      return {
        ...prev,
        nodeStatuses: { ...prev.nodeStatuses, ...(normalizedSnapshot?.nodeStatuses || {}) },
        nodeProgress: { ...prev.nodeProgress, ...(normalizedSnapshot?.nodeProgress || {}) },
        nodeResults: { ...prev.nodeResults, ...(normalizedSnapshot?.nodeResults || {}) },
        nodeErrors: { ...prev.nodeErrors, ...(normalizedSnapshot?.nodeErrors || {}) },
        nodeRuntimes: {
          ...(prev.nodeRuntimes || {}),
          ...snapshotNodeRuntimes,
          ...(normalizedSnapshot?.nodeRuntimes || {}),
        },
        runtimeHints: mergedHints,
        finalRuntime: snapshotPrimaryRuntime || prev.finalRuntime || pickPrimaryRuntime(mergedHints),
        resultPreviewImageUrls: normalizeBoundedPreviewUrls(
          normalizedSnapshot?.resultPreviewImageUrls,
          PREVIEW_IMAGE_MAX_ENTRIES
        ).length > 0
          ? normalizeBoundedPreviewUrls(normalizedSnapshot?.resultPreviewImageUrls, PREVIEW_IMAGE_MAX_ENTRIES)
          : prev.resultPreviewImageUrls,
        resultPreviewAudioUrls: normalizeBoundedPreviewUrls(normalizedSnapshot?.resultPreviewAudioUrls, 12).length > 0
          ? normalizeBoundedPreviewUrls(normalizedSnapshot?.resultPreviewAudioUrls, 12)
          : prev.resultPreviewAudioUrls,
        resultPreviewVideoUrls: normalizeBoundedPreviewUrls(normalizedSnapshot?.resultPreviewVideoUrls, 12).length > 0
          ? normalizeBoundedPreviewUrls(normalizedSnapshot?.resultPreviewVideoUrls, 12)
          : prev.resultPreviewVideoUrls,
      };
    }
    case 'apply_completed': {
      const normalizedPayload = normalizeSnapshot(action.payload);
      const runtimeHints = mergeRuntimeHints(
        extractRuntimeHints(normalizedPayload?.result),
        Array.isArray(normalizedPayload?.runtimeHints) ? normalizedPayload.runtimeHints : []
      );
      const primaryRuntime =
        normalizeRuntimeHint(
          normalizedPayload?.primaryRuntime || normalizedPayload?.resultSummary?.primaryRuntime || ''
        ) || pickPrimaryRuntime(runtimeHints);
      const previewImageUrls = normalizeBoundedPreviewUrls(
        normalizedPayload?.resultPreviewImageUrls,
        PREVIEW_IMAGE_MAX_ENTRIES
      );
      const previewAudioUrls = normalizeBoundedPreviewUrls(normalizedPayload?.resultPreviewAudioUrls, 12);
      const previewVideoUrls = normalizeBoundedPreviewUrls(normalizedPayload?.resultPreviewVideoUrls, 12);

      return {
        ...prev,
        finalStatus: 'completed',
        finalResult: normalizedPayload?.result,
        finalRuntime: primaryRuntime || prev.finalRuntime,
        runtimeHints: mergeRuntimeHints(prev.runtimeHints || [], runtimeHints),
        resultPreviewImageUrls: previewImageUrls.length > 0 ? previewImageUrls : prev.resultPreviewImageUrls,
        resultPreviewAudioUrls: previewAudioUrls.length > 0 ? previewAudioUrls : prev.resultPreviewAudioUrls,
        resultPreviewVideoUrls: previewVideoUrls.length > 0 ? previewVideoUrls : prev.resultPreviewVideoUrls,
        finalError: undefined,
        completedAt: normalizedPayload?.completedAt || action.now,
        logs: [
          ...(prev.logs || []),
          {
            timestamp: action.now,
            nodeId: 'system',
            message: primaryRuntime ? `工作流执行完成（runtime: ${primaryRuntime}）` : '工作流执行完成',
            level: 'info',
          },
        ],
      };
    }
    case 'apply_terminal': {
      const { resolution, now } = action;
      return {
        ...prev,
        finalStatus: resolution.terminalStatus,
        finalResult: undefined,
        finalError: resolution.terminalError,
        completedAt: resolution.normalizedPayload?.completedAt || now,
        logs: [
          ...(prev.logs || []),
          {
            timestamp: now,
            nodeId: 'system',
            message: resolution.terminalLogMessage,
            level: resolution.terminalLogLevel,
          },
        ],
      };
    }
    case 'append_log':
      return appendLog(prev, action.entry);
    default:
      return prev;
  }
};

import type { ExecutionStatus, NodeStatus } from '../../multiagent/types';
import { PREVIEW_IMAGE_MAX_ENTRIES } from '../../multiagent/workflowResultUtils';
import {
  extractRuntimeHints,
  mergeRuntimeHints,
  normalizeRuntimeHint,
  pickPrimaryRuntime,
} from './runtimeHints';

type WorkflowFinalStatus = NonNullable<ExecutionStatus['finalStatus']>;
const MEDIA_PREVIEW_URL_MAX_ENTRIES = 12;

interface HistoryDetailPreviewState {
  imageUrls?: string[];
  audioUrls?: string[];
  videoUrls?: string[];
}

const normalizeStatusToken = (status: unknown): string =>
  String(status || '').trim().toLowerCase();

export const normalizeNodeStatus = (status: unknown): NodeStatus => {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'running') return 'running';
  if (normalized === 'failed') return 'failed';
  if (normalized === 'skipped') return 'skipped';
  if (normalized === 'completed') return 'completed';
  return 'pending';
};

export const normalizeWorkflowFinalStatus = (status: unknown): WorkflowFinalStatus => {
  const normalized = normalizeStatusToken(status);
  if (normalized === 'completed') return 'completed';
  if (normalized === 'failed') return 'failed';
  if (normalized === 'cancelled' || normalized === 'canceled') return 'cancelled';
  if (normalized === 'workflow_paused' || normalized === 'paused' || normalized === 'pause') {
    return 'workflow_paused';
  }
  if (normalized === 'running' || normalized === 'in_progress') return 'running';
  return 'pending';
};

export const normalizeNodeProgress = (
  rawProgress: unknown,
  fallbackStatus: NodeStatus
): number => {
  const numericProgress = Number(rawProgress);
  if (Number.isFinite(numericProgress)) {
    return Math.max(0, Math.min(100, Math.round(numericProgress)));
  }
  if (fallbackStatus === 'pending') return 0;
  if (fallbackStatus === 'running') return 30;
  return 100;
};

export const createInitialExecutionStatus = (
  nodes: Array<{ id: string }>
): ExecutionStatus => {
  const initialStatus: ExecutionStatus = {
    nodeStatuses: {},
    nodeProgress: {},
    nodeResults: {},
    nodeErrors: {},
    nodeRuntimes: {},
    executionId: undefined,
    finalStatus: 'running',
    finalResult: undefined,
    finalRuntime: undefined,
    runtimeHints: [],
    finalError: undefined,
    completedAt: undefined,
    logs: [],
  };

  nodes.forEach((node) => {
    initialStatus.nodeStatuses[node.id] = 'pending';
    initialStatus.nodeProgress[node.id] = 0;
  });

  return initialStatus;
};

export const buildFailedExecutionStatus = (
  prev: ExecutionStatus,
  errorMessage: string,
  timestamp: number = Date.now()
): ExecutionStatus => {
  const failedStatuses: Record<string, NodeStatus> = {};
  Object.keys(prev.nodeStatuses).forEach((nodeId) => {
    failedStatuses[nodeId] = 'failed';
  });

  return {
    ...prev,
    nodeStatuses: failedStatuses,
    finalStatus: 'failed',
    finalResult: undefined,
    finalError: errorMessage,
    completedAt: timestamp,
    logs: [
      ...prev.logs,
      {
        timestamp,
        nodeId: 'system',
        message: `工作流执行失败: ${errorMessage}`,
        level: 'error',
      },
    ],
  };
};

export const normalizeSnapshotForApply = (snapshot: any) => {
  const payload =
    snapshot && typeof snapshot === 'object' && !Array.isArray(snapshot)
      ? snapshot
      : {};
  const nodeStatuses: Record<string, NodeStatus> = {};
  const nodeProgress: Record<string, number> = {};
  const nodeResults: Record<string, any> = {};
  const nodeErrors: Record<string, string> = {};
  const nodeRuntimes: Record<string, string> = {};
  const nodeExecutions = Array.isArray(payload?.nodeExecutions) ? payload.nodeExecutions : [];

  nodeExecutions.forEach((nodeExecution: any) => {
    const nodeId = String(nodeExecution?.nodeId || '').trim();
    if (!nodeId) return;
    const normalizedStatus = normalizeNodeStatus(nodeExecution?.status);
    nodeStatuses[nodeId] = normalizedStatus;
    nodeProgress[nodeId] = normalizeNodeProgress(nodeExecution?.progress, normalizedStatus);
    if (nodeExecution?.output !== undefined && nodeExecution?.output !== null) {
      nodeResults[nodeId] = nodeExecution.output;
    }
    if (nodeExecution?.error) {
      nodeErrors[nodeId] = String(nodeExecution.error);
    }
    const runtimeHints = extractRuntimeHints(nodeExecution?.output);
    const nodeRuntime =
      normalizeRuntimeHint(nodeExecution?.runtime || '') || pickPrimaryRuntime(runtimeHints);
    if (nodeRuntime) {
      nodeRuntimes[nodeId] = nodeRuntime;
    }
  });

  const rawNodeStatuses = payload?.nodeStatuses;
  if (rawNodeStatuses && typeof rawNodeStatuses === 'object' && !Array.isArray(rawNodeStatuses)) {
    Object.entries(rawNodeStatuses).forEach(([rawNodeId, rawStatus]) => {
      const nodeId = String(rawNodeId || '').trim();
      if (!nodeId) return;
      const normalizedStatus = normalizeNodeStatus(rawStatus);
      nodeStatuses[nodeId] = normalizedStatus;
      if (!(nodeId in nodeProgress)) {
        nodeProgress[nodeId] = normalizeNodeProgress(undefined, normalizedStatus);
      }
    });
  }

  const rawNodeProgress = payload?.nodeProgress;
  if (rawNodeProgress && typeof rawNodeProgress === 'object' && !Array.isArray(rawNodeProgress)) {
    Object.entries(rawNodeProgress).forEach(([rawNodeId, rawProgress]) => {
      const nodeId = String(rawNodeId || '').trim();
      if (!nodeId) return;
      nodeProgress[nodeId] = normalizeNodeProgress(rawProgress, nodeStatuses[nodeId] || 'running');
    });
  }

  const rawNodeResults = payload?.nodeResults;
  if (rawNodeResults && typeof rawNodeResults === 'object' && !Array.isArray(rawNodeResults)) {
    Object.entries(rawNodeResults).forEach(([rawNodeId, rawResult]) => {
      const nodeId = String(rawNodeId || '').trim();
      if (!nodeId) return;
      nodeResults[nodeId] = rawResult;
    });
  }

  const rawNodeErrors = payload?.nodeErrors;
  if (rawNodeErrors && typeof rawNodeErrors === 'object' && !Array.isArray(rawNodeErrors)) {
    Object.entries(rawNodeErrors).forEach(([rawNodeId, rawError]) => {
      const nodeId = String(rawNodeId || '').trim();
      if (!nodeId) return;
      if (rawError) {
        nodeErrors[nodeId] = String(rawError);
      }
    });
  }

  const rawNodeRuntimes = payload?.nodeRuntimes;
  if (rawNodeRuntimes && typeof rawNodeRuntimes === 'object' && !Array.isArray(rawNodeRuntimes)) {
    Object.entries(rawNodeRuntimes).forEach(([rawNodeId, rawRuntime]) => {
      const nodeId = String(rawNodeId || '').trim();
      if (!nodeId) return;
      const normalizedRuntime = normalizeRuntimeHint(rawRuntime || '');
      if (normalizedRuntime) {
        nodeRuntimes[nodeId] = normalizedRuntime;
      }
    });
  }

  Object.entries(nodeStatuses).forEach(([nodeId, status]) => {
    if (!(nodeId in nodeProgress)) {
      nodeProgress[nodeId] = normalizeNodeProgress(undefined, status);
    }
  });

  const resultSummary =
    payload?.resultSummary &&
    typeof payload.resultSummary === 'object' &&
    !Array.isArray(payload.resultSummary)
      ? payload.resultSummary
      : {};
  const runtimeHints = mergeRuntimeHints(
    Array.isArray(payload?.runtimeHints) ? payload.runtimeHints : [],
    Array.isArray(resultSummary?.runtimeHints) ? resultSummary.runtimeHints : []
  );
  const primaryRuntime =
    normalizeRuntimeHint(payload?.primaryRuntime || resultSummary?.primaryRuntime || '') ||
    pickPrimaryRuntime(runtimeHints);

  return {
    ...payload,
    status: normalizeWorkflowFinalStatus(payload?.status),
    nodeStatuses,
    nodeProgress,
    nodeResults,
    nodeErrors,
    nodeRuntimes,
    runtimeHints,
    primaryRuntime,
    resultSummary,
  };
};

export const buildExecutionStatusFromHistoryDetail = (
  detail: any,
  previewState: HistoryDetailPreviewState = {}
): ExecutionStatus => {
  const normalizedDetail = normalizeSnapshotForApply(detail);
  const finalStatus = normalizeWorkflowFinalStatus(normalizedDetail?.status);
  const runtimeFromNodes = Object.values(normalizedDetail?.nodeRuntimes || {})
    .map((runtime) => String(runtime || '').trim())
    .filter((runtime) => runtime.length > 0);
  const detailResultSummary = normalizedDetail?.resultSummary || {};
  const runtimeHintsFromSummary = Array.isArray(detailResultSummary?.runtimeHints)
    ? detailResultSummary.runtimeHints
    : [];
  const runtimeHints = mergeRuntimeHints(
    mergeRuntimeHints([], runtimeHintsFromSummary),
    mergeRuntimeHints(runtimeFromNodes, extractRuntimeHints(normalizedDetail?.result))
  );
  const finalRuntime =
    normalizeRuntimeHint(normalizedDetail?.primaryRuntime || detailResultSummary?.primaryRuntime || '') ||
    pickPrimaryRuntime(runtimeHints);
  const restoredLog =
    finalStatus === 'workflow_paused'
      ? '已恢复历史执行结果（状态：已暂停）'
      : finalRuntime
        ? `已恢复历史执行结果（runtime: ${finalRuntime}）`
        : '已恢复历史执行结果';

  return {
    nodeStatuses: normalizedDetail?.nodeStatuses || {},
    nodeProgress: normalizedDetail?.nodeProgress || {},
    nodeResults: normalizedDetail?.nodeResults || {},
    nodeErrors: normalizedDetail?.nodeErrors || {},
    nodeRuntimes: normalizedDetail?.nodeRuntimes || {},
    executionId: normalizedDetail?.id || '',
    finalStatus,
    finalResult: normalizedDetail?.result,
    finalRuntime,
    runtimeHints,
    resultPreviewImageUrls: Array.isArray(previewState.imageUrls)
      ? previewState.imageUrls
        .filter((url) => typeof url === 'string' && url.trim().length > 0)
        .slice(0, PREVIEW_IMAGE_MAX_ENTRIES)
      : [],
    resultPreviewAudioUrls: Array.isArray(previewState.audioUrls)
      ? previewState.audioUrls
        .filter((url) => typeof url === 'string' && url.trim().length > 0)
        .slice(0, MEDIA_PREVIEW_URL_MAX_ENTRIES)
      : [],
    resultPreviewVideoUrls: Array.isArray(previewState.videoUrls)
      ? previewState.videoUrls
        .filter((url) => typeof url === 'string' && url.trim().length > 0)
        .slice(0, MEDIA_PREVIEW_URL_MAX_ENTRIES)
      : [],
    finalError:
      normalizedDetail?.error ||
      (finalStatus === 'workflow_paused' ? '工作流已暂停，可在历史记录中查看后续状态。' : undefined),
    completedAt: normalizedDetail?.completedAt || Date.now(),
    logs: [
      {
        timestamp: Date.now(),
        nodeId: 'system',
        message: restoredLog,
        level: finalStatus === 'workflow_paused' ? 'warn' : 'info',
      },
    ],
  };
};

export const getHistoryStatusLabel = (status: string): string => {
  const normalized = normalizeStatusToken(status);
  if (normalized === 'completed') return '完成';
  if (normalized === 'failed') return '失败';
  if (normalized === 'cancelled' || normalized === 'canceled') return '已取消';
  if (normalized === 'workflow_paused' || normalized === 'paused' || normalized === 'pause') {
    return '已暂停';
  }
  if (normalized === 'running' || normalized === 'in_progress') return '运行中';
  if (normalized === 'pending') return '排队中';
  return status;
};

export const getHistoryStatusClass = (status: string): string => {
  const normalized = normalizeStatusToken(status);
  if (normalized === 'completed') return 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10';
  if (normalized === 'failed') return 'text-rose-300 border-rose-500/30 bg-rose-500/10';
  if (normalized === 'cancelled' || normalized === 'canceled') {
    return 'text-slate-300 border-slate-500/40 bg-slate-600/30';
  }
  if (normalized === 'workflow_paused' || normalized === 'paused' || normalized === 'pause') {
    return 'text-amber-300 border-amber-500/30 bg-amber-500/10';
  }
  if (normalized === 'running' || normalized === 'in_progress') {
    return 'text-sky-300 border-sky-500/30 bg-sky-500/10';
  }
  return 'text-slate-300 border-slate-600 bg-slate-700/40';
};

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import { getAuthHeaders } from '../../../services/apiClient';
import {
  downloadBlobInBrowser,
  inferFileNameFromContentDisposition,
} from '../../../services/downloadService';
import { downloadBlobWithXhr } from '../../../services/httpProgress';
import { requestJson } from '../../../services/http';
import { removeRecordKey } from '../../../services/boundedRecordCache';
import type { ExecutionStatus } from '../../multiagent/types';
import { buildExecutionStatusFromHistoryDetail } from './executionStatusUtils';
import { mergeRuntimeHints, normalizeRuntimeHint, pickPrimaryRuntime } from './runtimeHints';
import type { WorkflowHistoryItem, WorkflowLoadRequest } from './types';
import { useWorkflowHistoryPreviewState } from './useWorkflowHistoryPreviewState';
import { isWorkflowExecutionAbortError } from './workflowExecutionErrors';
import type { WorkflowHistoryMediaPreviewItem } from '../../../services/workflowHistoryService';

interface UseWorkflowHistoryControllerParams {
  setExecutionStatus: Dispatch<SetStateAction<ExecutionStatus | undefined>>;
  showError: (message: string) => void;
}

interface UseWorkflowHistoryControllerResult {
  historySearchQuery: string;
  historyLoading: boolean;
  historyError: string | null;
  displayedWorkflowHistory: WorkflowHistoryItem[];
  historyPreviewImages: Record<string, string[]>;
  historyPreviewMedia: Record<string, {
    audioItems: WorkflowHistoryMediaPreviewItem[];
    videoItems: WorkflowHistoryMediaPreviewItem[];
  }>;
  expandedPreviewHistoryId: string | null;
  selectedHistoryId: string | null;
  loadingHistoryId: string | null;
  deletingHistoryId: string | null;
  downloadingHistoryId: string | null;
  downloadingAnalysisId: string | null;
  downloadMediaProgress: Record<string, number>;
  downloadAnalysisProgress: Record<string, number>;
  previewingHistoryId: string | null;
  workflowLoadRequest: WorkflowLoadRequest | null;
  isMountedRef: MutableRefObject<boolean>;
  activeExecutionControllerRef: MutableRefObject<AbortController | null>;
  activeExecutionCleanupRef: MutableRefObject<(() => void) | null>;
  setHistorySearchQuery: Dispatch<SetStateAction<string>>;
  createRequestController: () => AbortController;
  releaseRequestController: (controller: AbortController) => void;
  fetchWorkflowHistory: () => Promise<void>;
  handleLoadWorkflowFromHistory: (executionId: string) => Promise<void>;
  handleDeleteWorkflowHistory: (executionId: string) => Promise<void>;
  handleDownloadWorkflowMedia: (item: WorkflowHistoryItem) => Promise<void>;
  handleDownloadWorkflowAnalysis: (item: WorkflowHistoryItem) => Promise<void>;
  handleToggleWorkflowMediaPreview: (item: WorkflowHistoryItem) => Promise<void>;
}

export const useWorkflowHistoryController = ({
  setExecutionStatus,
  showError,
}: UseWorkflowHistoryControllerParams): UseWorkflowHistoryControllerResult => {
  const [workflowHistory, setWorkflowHistory] = useState<WorkflowHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [loadingHistoryId, setLoadingHistoryId] = useState<string | null>(null);
  const [deletingHistoryId, setDeletingHistoryId] = useState<string | null>(null);
  const [downloadingHistoryId, setDownloadingHistoryId] = useState<string | null>(null);
  const [downloadingAnalysisId, setDownloadingAnalysisId] = useState<string | null>(null);
  const [downloadMediaProgress, setDownloadMediaProgress] = useState<Record<string, number>>({});
  const [downloadAnalysisProgress, setDownloadAnalysisProgress] = useState<Record<string, number>>({});
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [workflowLoadRequest, setWorkflowLoadRequest] = useState<WorkflowLoadRequest | null>(null);
  const [historySearchQuery, setHistorySearchQuery] = useState('');

  const isMountedRef = useRef(true);
  const inFlightControllersRef = useRef<Set<AbortController>>(new Set());
  const activeExecutionControllerRef = useRef<AbortController | null>(null);
  const activeExecutionCleanupRef = useRef<(() => void) | null>(null);
  const historyListRequestSeqRef = useRef(0);
  const historyListControllerRef = useRef<AbortController | null>(null);
  const historyDetailRequestSeqRef = useRef(0);
  const historyDetailControllerRef = useRef<AbortController | null>(null);

  const createRequestController = useCallback(() => {
    const controller = new AbortController();
    inFlightControllersRef.current.add(controller);
    return controller;
  }, []);

  const releaseRequestController = useCallback((controller: AbortController) => {
    inFlightControllersRef.current.delete(controller);
  }, []);

  const {
    historyPreviewImages,
    historyPreviewMedia,
    expandedPreviewHistoryId,
    previewingHistoryId,
    setExpandedPreviewHistoryId,
    removeHistoryPreviewImageCache,
    removeHistoryPreviewMediaCache,
    resolveHistoryDetailPreviewImages,
    resolveHistoryDetailPreviewMedia,
    handleToggleWorkflowMediaPreview,
  } = useWorkflowHistoryPreviewState({
    isMountedRef,
    createRequestController,
    releaseRequestController,
    showError,
  });

  const stopActiveExecutionFlow = useCallback(() => {
    const activeExecutionController = activeExecutionControllerRef.current;
    if (activeExecutionController) {
      activeExecutionController.abort();
      releaseRequestController(activeExecutionController);
      activeExecutionControllerRef.current = null;
    }

    const activeExecutionCleanup = activeExecutionCleanupRef.current;
    if (activeExecutionCleanup) {
      activeExecutionCleanup();
      activeExecutionCleanupRef.current = null;
    }
  }, [releaseRequestController]);

  const mapHistoryItem = useCallback((item: Record<string, unknown>): WorkflowHistoryItem => {
    const workflowSummary = (item?.workflowSummary || {}) as Record<string, unknown>;
    const resultSummary = (item?.resultSummary || {}) as Record<string, unknown>;
    const title = String(item?.title || item?.task || '未命名工作流');
    const resultPreviewRaw = resultSummary?.textPreview || '';
    const resultPreview = typeof resultPreviewRaw === 'string' ? resultPreviewRaw : '';
    const resultImageCount = Number(resultSummary?.imageCount || 0) || 0;
    const resultAudioCount = Number(resultSummary?.audioCount || 0) || 0;
    const resultVideoCount = Number(resultSummary?.videoCount || 0) || 0;
    const continuationStrategy = String(
      resultSummary?.continuationStrategy ?? resultSummary?.continuation_strategy ?? ''
    ).trim();
    const videoExtensionCount = Number(
      resultSummary?.videoExtensionCount ?? resultSummary?.video_extension_count ?? 0
    ) || 0;
    const videoExtensionApplied = Number(
      resultSummary?.videoExtensionApplied ?? resultSummary?.video_extension_applied ?? 0
    ) || 0;
    const totalDurationSeconds = Number(
      resultSummary?.totalDurationSeconds ?? resultSummary?.total_duration_seconds ?? 0
    ) || 0;
    const continuedFromVideo = Boolean(
      resultSummary?.continuedFromVideo ?? resultSummary?.continued_from_video ?? false
    );
    const subtitleMode = String(
      resultSummary?.subtitleMode ?? resultSummary?.subtitle_mode ?? ''
    ).trim();
    const subtitleFileCount = Number(
      resultSummary?.subtitleFileCount ?? resultSummary?.subtitle_file_count ?? 0
    ) || 0;
    const runtimeHintsRaw = Array.isArray(resultSummary?.runtimeHints)
      ? resultSummary.runtimeHints
      : [];
    const runtimeHints = mergeRuntimeHints([], runtimeHintsRaw);
    const primaryRuntime =
      normalizeRuntimeHint(resultSummary?.primaryRuntime || '') || pickPrimaryRuntime(runtimeHints);
    const resultImageUrls = Array.isArray(resultSummary?.imageUrls) ? resultSummary.imageUrls : [];
    const resultAudioUrls = Array.isArray(resultSummary?.audioUrls) ? resultSummary.audioUrls : [];
    const resultVideoUrls = Array.isArray(resultSummary?.videoUrls) ? resultSummary.videoUrls : [];
    return {
      id: String(item?.id || ''),
      status: String(item?.status || 'unknown'),
      title,
      source: String(item?.source || ''),
      task: String(item?.task || ''),
      resultPreview,
      resultImageCount,
      resultImageUrls: resultImageUrls.filter((url: unknown) => typeof url === 'string'),
      resultAudioCount,
      resultAudioUrls: resultAudioUrls.filter((url: unknown) => typeof url === 'string'),
      resultVideoCount,
      resultVideoUrls: resultVideoUrls.filter((url: unknown) => typeof url === 'string'),
      continuationStrategy: continuationStrategy || undefined,
      videoExtensionCount: videoExtensionCount > 0 ? videoExtensionCount : undefined,
      videoExtensionApplied: videoExtensionApplied > 0 ? videoExtensionApplied : undefined,
      totalDurationSeconds: totalDurationSeconds > 0 ? totalDurationSeconds : undefined,
      continuedFromVideo,
      subtitleMode: subtitleMode || undefined,
      subtitleFileCount: subtitleFileCount > 0 ? subtitleFileCount : undefined,
      primaryRuntime,
      runtimeHints,
      startedAt: Number(item?.startedAt || Date.now()),
      completedAt: typeof item?.completedAt === 'number' ? item.completedAt : undefined,
      durationMs: typeof item?.durationMs === 'number' ? item.durationMs : undefined,
      error: typeof item?.error === 'string' ? item.error : undefined,
      nodeCount: Number(workflowSummary?.nodeCount || 0),
      edgeCount: Number(workflowSummary?.edgeCount || 0),
    };
  }, []);

  const fetchWorkflowHistory = useCallback(async () => {
    historyListRequestSeqRef.current += 1;
    const requestSeq = historyListRequestSeqRef.current;

    const previousController = historyListControllerRef.current;
    if (previousController) {
      previousController.abort();
      releaseRequestController(previousController);
      historyListControllerRef.current = null;
    }

    const controller = createRequestController();
    historyListControllerRef.current = controller;
    const isStaleRequest = () =>
      requestSeq !== historyListRequestSeqRef.current || historyListControllerRef.current !== controller;
    if (isMountedRef.current) {
      setHistoryLoading(true);
      setHistoryError(null);
    }
    try {
      const payload = await requestJson<any>('/api/workflows/history?limit=100', {
        withAuth: true,
        credentials: 'include',
        signal: controller.signal,
        timeoutMs: 0,
        errorMessage: '加载工作流历史失败',
      });
      if (!isMountedRef.current || controller.signal.aborted || isStaleRequest()) return;
      const items = Array.isArray(payload?.executions) ? payload.executions.map(mapHistoryItem) : [];
      setWorkflowHistory(items);
    } catch (error) {
      if (
        isWorkflowExecutionAbortError(error) ||
        !isMountedRef.current ||
        controller.signal.aborted ||
        isStaleRequest()
      ) {
        return;
      }
      const message = error instanceof Error ? error.message : '加载工作流历史失败';
      setHistoryError(message);
    } finally {
      releaseRequestController(controller);
      if (historyListControllerRef.current === controller) {
        historyListControllerRef.current = null;
      }
      if (isMountedRef.current && requestSeq === historyListRequestSeqRef.current) {
        setHistoryLoading(false);
      }
    }
  }, [createRequestController, mapHistoryItem, releaseRequestController]);

  const handleLoadWorkflowFromHistory = useCallback(async (executionId: string) => {
    stopActiveExecutionFlow();
    historyDetailRequestSeqRef.current += 1;
    const requestSeq = historyDetailRequestSeqRef.current;

    const previousController = historyDetailControllerRef.current;
    if (previousController) {
      previousController.abort();
      releaseRequestController(previousController);
      historyDetailControllerRef.current = null;
    }

    const controller = createRequestController();
    historyDetailControllerRef.current = controller;
    const isStaleRequest = () =>
      requestSeq !== historyDetailRequestSeqRef.current ||
      historyDetailControllerRef.current !== controller;
    if (isMountedRef.current) {
      setLoadingHistoryId(executionId);
    }
    try {
      const payload = await requestJson<any>(`/api/workflows/history/${executionId}`, {
        withAuth: true,
        credentials: 'include',
        signal: controller.signal,
        timeoutMs: 0,
        errorMessage: '加载历史详情失败',
      });
      if (!isMountedRef.current || controller.signal.aborted || isStaleRequest()) return;

      const workflow = payload?.workflow || {};
      const input = payload?.input || {};
      const nodes = Array.isArray(workflow?.nodes) ? workflow.nodes : [];
      const edges = Array.isArray(workflow?.edges) ? workflow.edges : [];
      const promptFromInput = input?.task || input?.prompt || '';
      const workflowName = payload?.title || payload?.task || `执行记录 ${executionId.slice(0, 8)}`;

      const summaryImageCount = Number(payload?.resultSummary?.imageCount || 0);
      const summaryAudioCount = Number(payload?.resultSummary?.audioCount || 0);
      const summaryVideoCount = Number(payload?.resultSummary?.videoCount || 0);
      const [previewImagesForResult, previewMediaForResult] = await Promise.all([
        resolveHistoryDetailPreviewImages({
          executionId,
          summaryImageCount,
          signal: controller.signal,
          isStaleRequest,
        }),
        resolveHistoryDetailPreviewMedia({
          executionId,
          summaryAudioCount,
          summaryVideoCount,
          signal: controller.signal,
          isStaleRequest,
        }),
      ]);
      if (previewImagesForResult === null || previewMediaForResult === null) {
        return;
      }

      setExecutionStatus(buildExecutionStatusFromHistoryDetail(payload, {
        imageUrls: previewImagesForResult,
        audioUrls: previewMediaForResult.audioUrls,
        videoUrls: previewMediaForResult.videoUrls,
      }));
      setWorkflowLoadRequest({
        token: `${executionId}-${Date.now()}`,
        name: workflowName,
        prompt: promptFromInput,
        input: input && typeof input === 'object' && !Array.isArray(input) ? input : {},
        nodes,
        edges,
      });
      setSelectedHistoryId(executionId);
    } catch (error) {
      if (
        isWorkflowExecutionAbortError(error) ||
        !isMountedRef.current ||
        controller.signal.aborted ||
        isStaleRequest()
      ) {
        return;
      }
      const message = error instanceof Error ? error.message : '加载历史详情失败';
      showError(message);
    } finally {
      releaseRequestController(controller);
      if (historyDetailControllerRef.current === controller) {
        historyDetailControllerRef.current = null;
      }
      if (isMountedRef.current && requestSeq === historyDetailRequestSeqRef.current) {
        setLoadingHistoryId(null);
      }
    }
  }, [
    createRequestController,
    releaseRequestController,
    resolveHistoryDetailPreviewImages,
    resolveHistoryDetailPreviewMedia,
    setExecutionStatus,
    stopActiveExecutionFlow,
    showError,
  ]);

  const handleDeleteWorkflowHistory = useCallback(async (executionId: string) => {
    const controller = createRequestController();
    if (isMountedRef.current) {
      setDeletingHistoryId(executionId);
    }
    try {
      await requestJson(`/api/workflows/history/${executionId}`, {
        method: 'DELETE',
        withAuth: true,
        credentials: 'include',
        signal: controller.signal,
        timeoutMs: 0,
        errorMessage: '删除工作流历史失败',
      });
      if (!isMountedRef.current || controller.signal.aborted) return;

      setWorkflowHistory((prev) => prev.filter((item) => item.id !== executionId));
      setSelectedHistoryId((prev) => (prev === executionId ? null : prev));
      setExpandedPreviewHistoryId((prev) => (prev === executionId ? null : prev));
      removeHistoryPreviewImageCache(executionId);
      removeHistoryPreviewMediaCache(executionId);
      setDownloadMediaProgress((prev) => removeRecordKey(prev, executionId));
      setDownloadAnalysisProgress((prev) => removeRecordKey(prev, executionId));
    } catch (error) {
      if (isWorkflowExecutionAbortError(error) || !isMountedRef.current || controller.signal.aborted) return;
      const message = error instanceof Error ? error.message : '删除工作流历史失败';
      showError(message);
    } finally {
      releaseRequestController(controller);
      if (isMountedRef.current) {
        setDeletingHistoryId(null);
      }
    }
  }, [
    createRequestController,
    releaseRequestController,
    removeHistoryPreviewImageCache,
    removeHistoryPreviewMediaCache,
    showError,
  ]);

  const handleDownloadWorkflowMedia = useCallback(async (item: WorkflowHistoryItem) => {
    if (!item?.id) return;
    const mediaKind = item.resultImageCount > 0
      ? 'images'
      : item.resultVideoCount > 0
        ? 'video'
        : item.resultAudioCount > 0
          ? 'audio'
          : null;
    if (!mediaKind) return;
    if (isMountedRef.current) {
      setDownloadingHistoryId(item.id);
      setDownloadMediaProgress((prev) => ({ ...prev, [item.id]: 0 }));
    }
    try {
      const { blob, headers } = await downloadBlobWithXhr({
        url: `/api/workflows/history/${item.id}/${mediaKind}/download`,
        headers: getAuthHeaders(),
        withCredentials: true,
        timeoutMs: 180000,
        onDownloadProgress: (progress) => {
          if (!isMountedRef.current) return;
          if (progress.percent === null) return;
          setDownloadMediaProgress((prev) => ({ ...prev, [item.id]: progress.percent || 0 }));
        },
      });
      if (!isMountedRef.current) return;
      const contentDisposition = headers['content-disposition'] || '';
      const fallbackName = `workflow-${item.id.slice(0, 8)}-${mediaKind}.zip`;
      const fileName = inferFileNameFromContentDisposition(contentDisposition, fallbackName);
      downloadBlobInBrowser({ blob, fileName });
    } catch (error) {
      if (!isMountedRef.current) return;
      const message = error instanceof Error ? error.message : '下载结果媒体失败';
      showError(message);
    } finally {
      if (!isMountedRef.current) return;
      setDownloadingHistoryId(null);
      setDownloadMediaProgress((prev) => removeRecordKey(prev, item.id));
    }
  }, [showError]);

  const handleDownloadWorkflowAnalysis = useCallback(async (item: WorkflowHistoryItem) => {
    if (!item?.id) return;
    if (isMountedRef.current) {
      setDownloadingAnalysisId(item.id);
      setDownloadAnalysisProgress((prev) => ({ ...prev, [item.id]: 0 }));
    }
    try {
      const { blob, headers } = await downloadBlobWithXhr({
        url: `/api/workflows/history/${item.id}/analysis/download`,
        headers: getAuthHeaders(),
        withCredentials: true,
        timeoutMs: 180000,
        onDownloadProgress: (progress) => {
          if (!isMountedRef.current) return;
          if (progress.percent === null) return;
          setDownloadAnalysisProgress((prev) => ({ ...prev, [item.id]: progress.percent || 0 }));
        },
      });
      if (!isMountedRef.current) return;
      const contentDisposition = headers['content-disposition'] || '';
      const fallbackName = `workflow-${item.id.slice(0, 8)}-analysis.xlsx`;
      const fileName = inferFileNameFromContentDisposition(contentDisposition, fallbackName);
      downloadBlobInBrowser({ blob, fileName });
    } catch (error) {
      if (!isMountedRef.current) return;
      const message = error instanceof Error ? error.message : '下载分析结果失败';
      showError(message);
    } finally {
      if (!isMountedRef.current) return;
      setDownloadingAnalysisId(null);
      setDownloadAnalysisProgress((prev) => removeRecordKey(prev, item.id));
    }
  }, [showError]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (activeExecutionCleanupRef.current) {
        activeExecutionCleanupRef.current();
        activeExecutionCleanupRef.current = null;
      }
      if (activeExecutionControllerRef.current) {
        activeExecutionControllerRef.current.abort();
        activeExecutionControllerRef.current = null;
      }
      historyListControllerRef.current = null;
      historyDetailControllerRef.current = null;
      inFlightControllersRef.current.forEach((controller) => {
        controller.abort();
      });
      inFlightControllersRef.current.clear();
    };
  }, []);

  useEffect(() => {
    void fetchWorkflowHistory();
  }, [fetchWorkflowHistory]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void fetchWorkflowHistory();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [fetchWorkflowHistory]);

  const displayedWorkflowHistory = useMemo(() => {
    const keyword = historySearchQuery.trim().toLowerCase();
    if (!keyword) {
      return workflowHistory;
    }
    return workflowHistory.filter((item) => {
      const haystack = `${item.title} ${item.task} ${item.id}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [historySearchQuery, workflowHistory]);

  return {
    historySearchQuery,
    historyLoading,
    historyError,
    displayedWorkflowHistory,
    historyPreviewImages,
    historyPreviewMedia,
    expandedPreviewHistoryId,
    selectedHistoryId,
    loadingHistoryId,
    deletingHistoryId,
    downloadingHistoryId,
    downloadingAnalysisId,
    downloadMediaProgress,
    downloadAnalysisProgress,
    previewingHistoryId,
    workflowLoadRequest,
    isMountedRef,
    activeExecutionControllerRef,
    activeExecutionCleanupRef,
    setHistorySearchQuery,
    createRequestController,
    releaseRequestController,
    fetchWorkflowHistory,
    handleLoadWorkflowFromHistory,
    handleDeleteWorkflowHistory,
    handleDownloadWorkflowMedia,
    handleDownloadWorkflowAnalysis,
    handleToggleWorkflowMediaPreview,
  };
};

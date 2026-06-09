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
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from '../../../services/privateCacheInvalidation';
import { usePrivateCacheLifecycleRevision } from '../../../hooks/usePrivateCacheScopeRevision';
import { removeRecordKey } from '../../../services/boundedRecordCache';
import type { ExecutionStatus, WorkflowEdge, WorkflowNode } from '../../multiagent/types';
import {
  extractAudioUrls,
  extractImageUrls,
  extractVideoUrls,
  filterPersistedWorkflowResultUrls,
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
} from '../../multiagent/workflowResultUtils';
import { buildExecutionStatusFromHistoryDetail } from './executionStatusUtils';
import { mergeRuntimeHints, normalizeRuntimeHint, pickPrimaryRuntime } from './runtimeHints';
import type { WorkflowHistoryItem, WorkflowLoadRequest } from './types';
import { useWorkflowHistoryPreviewState } from './useWorkflowHistoryPreviewState';
import { isWorkflowExecutionAbortError } from './workflowExecutionErrors';
import type { WorkflowHistoryMediaPreviewItem } from '../../../services/workflowHistoryService';

/** Shape of the /api/workflows/history list response. */
interface WorkflowHistoryListResponse {
  executions: Record<string, unknown>[];
}

/** Shape of the /api/workflows/history/:id detail response. */
interface WorkflowHistoryDetailResponse {
  workflow?: {
    nodes?: WorkflowNode[];
    edges?: WorkflowEdge[];
  };
  input?: Record<string, unknown>;
  title?: string;
  task?: string;
  resultSummary?: {
    imageCount?: number;
    audioCount?: number;
    videoCount?: number;
    [key: string]: unknown;
  };
  result?: unknown;
  [key: string]: unknown;
}

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
  historyPreviewMedia: Record<
    string,
    {
      audioItems: WorkflowHistoryMediaPreviewItem[];
      videoItems: WorkflowHistoryMediaPreviewItem[];
    }
  >;
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
  const [downloadAnalysisProgress, setDownloadAnalysisProgress] = useState<Record<string, number>>(
    {}
  );
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

  const resetPrivateWorkflowHistoryState = useCallback(() => {
    if (!isMountedRef.current) return;
    historyListRequestSeqRef.current += 1;
    historyDetailRequestSeqRef.current += 1;
    historyListControllerRef.current = null;
    historyDetailControllerRef.current = null;
    setWorkflowHistory([]);
    setHistoryLoading(false);
    setHistoryError(null);
    setLoadingHistoryId(null);
    setDeletingHistoryId(null);
    setDownloadingHistoryId(null);
    setDownloadingAnalysisId(null);
    setDownloadMediaProgress({});
    setDownloadAnalysisProgress({});
    setSelectedHistoryId(null);
    setWorkflowLoadRequest(null);
    setExecutionStatus(undefined);
  }, [setExecutionStatus]);

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
    const videoExtensionCount =
      Number(resultSummary?.videoExtensionCount ?? resultSummary?.video_extension_count ?? 0) || 0;
    const videoExtensionApplied =
      Number(resultSummary?.videoExtensionApplied ?? resultSummary?.video_extension_applied ?? 0) ||
      0;
    const totalDurationSeconds =
      Number(resultSummary?.totalDurationSeconds ?? resultSummary?.total_duration_seconds ?? 0) ||
      0;
    const continuedFromVideo = Boolean(
      resultSummary?.continuedFromVideo ?? resultSummary?.continued_from_video ?? false
    );
    const subtitleMode = String(
      resultSummary?.subtitleMode ?? resultSummary?.subtitle_mode ?? ''
    ).trim();
    const subtitleFileCount =
      Number(resultSummary?.subtitleFileCount ?? resultSummary?.subtitle_file_count ?? 0) || 0;
    const runtimeHintsRaw = Array.isArray(resultSummary?.runtimeHints)
      ? resultSummary.runtimeHints
      : [];
    const runtimeHints = mergeRuntimeHints([], runtimeHintsRaw);
    const primaryRuntime =
      normalizeRuntimeHint(resultSummary?.primaryRuntime || '') || pickPrimaryRuntime(runtimeHints);
    const resultImageUrls = filterPersistedWorkflowResultUrls(resultSummary?.imageUrls);
    const resultAudioUrls = filterPersistedWorkflowResultUrls(resultSummary?.audioUrls);
    const resultVideoUrls = filterPersistedWorkflowResultUrls(resultSummary?.videoUrls);
    return {
      id: String(item?.id || ''),
      status: String(item?.status || 'unknown'),
      title,
      source: String(item?.source || ''),
      task: String(item?.task || ''),
      resultPreview,
      resultImageCount,
      resultImageUrls,
      resultAudioCount,
      resultAudioUrls,
      resultVideoCount,
      resultVideoUrls,
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
    const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();

    const previousController = historyListControllerRef.current;
    if (previousController) {
      previousController.abort();
      releaseRequestController(previousController);
      historyListControllerRef.current = null;
    }

    const controller = createRequestController();
    historyListControllerRef.current = controller;
    const isStaleRequest = () =>
      requestSeq !== historyListRequestSeqRef.current ||
      historyListControllerRef.current !== controller ||
      !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot);
    if (isMountedRef.current) {
      setHistoryLoading(true);
      setHistoryError(null);
    }
    try {
      const payload = await requestJson<WorkflowHistoryListResponse>(
        '/api/workflows/history?limit=100',
        {
          withAuth: true,
          signal: controller.signal,
          timeoutMs: 0,
          errorMessage: '加载工作流历史失败',
        }
      );
      if (!isMountedRef.current || controller.signal.aborted || isStaleRequest()) return;
      const items = Array.isArray(payload?.executions)
        ? payload.executions.map(mapHistoryItem)
        : [];
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

  const handleLoadWorkflowFromHistory = useCallback(
    async (executionId: string) => {
      stopActiveExecutionFlow();
      historyDetailRequestSeqRef.current += 1;
      const requestSeq = historyDetailRequestSeqRef.current;
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();

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
        historyDetailControllerRef.current !== controller ||
        !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot);
      let previewHydrationStarted = false;
      if (isMountedRef.current) {
        setLoadingHistoryId(executionId);
      }
      try {
        const payload = await requestJson<WorkflowHistoryDetailResponse>(
          `/api/workflows/history/${executionId}`,
          {
            withAuth: true,
            signal: controller.signal,
            timeoutMs: 0,
            errorMessage: '加载历史详情失败',
          }
        );
        if (!isMountedRef.current || controller.signal.aborted || isStaleRequest()) return;

        const workflow = payload?.workflow || {};
        const input = payload?.input || {};
        const nodes = Array.isArray(workflow?.nodes) ? workflow.nodes : [];
        const edges = Array.isArray(workflow?.edges) ? workflow.edges : [];
        const promptFromInput = String(input?.task || input?.prompt || '');
        const workflowName =
          payload?.title || payload?.task || `执行记录 ${executionId.slice(0, 8)}`;

        const summaryImageCount = Number(payload?.resultSummary?.imageCount || 0);
        const summaryAudioCount = Number(payload?.resultSummary?.audioCount || 0);
        const summaryVideoCount = Number(payload?.resultSummary?.videoCount || 0);
        const resultPayload = payload?.result;
        const hasDirectResultImage = extractImageUrls(resultPayload).some((url) =>
          isDirectlyRenderableImageUrl(url)
        );
        const hasDirectResultAudio = extractAudioUrls(resultPayload).some((url) =>
          isDirectlyRenderableAudioUrl(url)
        );
        const hasDirectResultVideo = extractVideoUrls(resultPayload).some((url) =>
          isDirectlyRenderableVideoUrl(url)
        );
        const restoredExecutionStatus = buildExecutionStatusFromHistoryDetail(payload, {
          imageUrls: [],
          audioUrls: [],
          videoUrls: [],
        });
        setExecutionStatus(restoredExecutionStatus);
        setWorkflowLoadRequest({
          token: `${executionId}-${Date.now()}`,
          name: workflowName,
          prompt: promptFromInput,
          input: input && typeof input === 'object' && !Array.isArray(input) ? input : {},
          nodes,
          edges,
          executionStatus: restoredExecutionStatus,
        });
        setSelectedHistoryId(executionId);

        const needsImagePreview = !hasDirectResultImage && summaryImageCount > 0;
        const needsAudioPreview = !hasDirectResultAudio && summaryAudioCount > 0;
        const needsVideoPreview = !hasDirectResultVideo && summaryVideoCount > 0;
        if (!needsImagePreview && !needsAudioPreview && !needsVideoPreview) {
          return;
        }

        previewHydrationStarted = true;
        void (async () => {
          try {
            const [previewImagesForResult, previewMediaForResult] = await Promise.all([
              needsImagePreview
                ? resolveHistoryDetailPreviewImages({
                    executionId,
                    summaryImageCount,
                    signal: controller.signal,
                    isStaleRequest,
                  })
                : Promise.resolve([]),
              needsAudioPreview || needsVideoPreview
                ? resolveHistoryDetailPreviewMedia({
                    executionId,
                    summaryAudioCount: needsAudioPreview ? summaryAudioCount : 0,
                    summaryVideoCount: needsVideoPreview ? summaryVideoCount : 0,
                    signal: controller.signal,
                    isStaleRequest,
                  })
                : Promise.resolve({ audioUrls: [], videoUrls: [] }),
            ]);
            if (
              previewImagesForResult === null ||
              previewMediaForResult === null ||
              !isMountedRef.current ||
              controller.signal.aborted ||
              isStaleRequest()
            ) {
              return;
            }

            const hydratedExecutionStatus = buildExecutionStatusFromHistoryDetail(payload, {
              imageUrls: previewImagesForResult,
              audioUrls: previewMediaForResult.audioUrls,
              videoUrls: previewMediaForResult.videoUrls,
            });
            setExecutionStatus((current) => {
              if (!current || current.executionId === executionId) {
                return hydratedExecutionStatus;
              }
              return current;
            });
          } catch (previewError) {
            if (
              isWorkflowExecutionAbortError(previewError) ||
              !isMountedRef.current ||
              controller.signal.aborted ||
              isStaleRequest()
            ) {
              return;
            }
            const message =
              previewError instanceof Error ? previewError.message : '加载历史媒体预览失败';
            showError(message);
          } finally {
            releaseRequestController(controller);
            if (historyDetailControllerRef.current === controller) {
              historyDetailControllerRef.current = null;
            }
          }
        })();
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
        if (!previewHydrationStarted) {
          releaseRequestController(controller);
          if (historyDetailControllerRef.current === controller) {
            historyDetailControllerRef.current = null;
          }
        }
        if (isMountedRef.current && requestSeq === historyDetailRequestSeqRef.current) {
          setLoadingHistoryId(null);
        }
      }
    },
    [
      createRequestController,
      releaseRequestController,
      resolveHistoryDetailPreviewImages,
      resolveHistoryDetailPreviewMedia,
      setExecutionStatus,
      stopActiveExecutionFlow,
      showError,
    ]
  );

  const handleDeleteWorkflowHistory = useCallback(
    async (executionId: string) => {
      const controller = createRequestController();
      if (isMountedRef.current) {
        setDeletingHistoryId(executionId);
      }
      try {
        await requestJson(`/api/workflows/history/${executionId}`, {
          method: 'DELETE',
          withAuth: true,
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
        if (
          isWorkflowExecutionAbortError(error) ||
          !isMountedRef.current ||
          controller.signal.aborted
        )
          return;
        const message = error instanceof Error ? error.message : '删除工作流历史失败';
        showError(message);
      } finally {
        releaseRequestController(controller);
        if (isMountedRef.current) {
          setDeletingHistoryId(null);
        }
      }
    },
    [
      createRequestController,
      releaseRequestController,
      removeHistoryPreviewImageCache,
      removeHistoryPreviewMediaCache,
      showError,
    ]
  );

  // 媒体下载与分析下载结构一致（下载 blob → 推断文件名 → 触发浏览器下载），
  // 仅 URL 后缀、回退文件名、错误文案与状态 setter 不同，统一到该泛型助手。
  const handleDownloadWorkflowFile = useCallback(
    async (
      item: WorkflowHistoryItem,
      config: {
        urlSegment: string;
        fallbackName: string;
        errorMessage: string;
        setDownloadingId: Dispatch<SetStateAction<string | null>>;
        setProgress: Dispatch<SetStateAction<Record<string, number>>>;
      }
    ) => {
      const { urlSegment, fallbackName, errorMessage, setDownloadingId, setProgress } = config;
      if (isMountedRef.current) {
        setDownloadingId(item.id);
        setProgress((prev) => ({ ...prev, [item.id]: 0 }));
      }
      try {
        const { blob, headers } = await downloadBlobWithXhr({
          url: `/api/workflows/history/${item.id}/${urlSegment}/download`,
          headers: getAuthHeaders(),
          withCredentials: true,
          timeoutMs: 180000,
          onDownloadProgress: (progress) => {
            if (!isMountedRef.current) return;
            if (progress.percent === null) return;
            setProgress((prev) => ({ ...prev, [item.id]: progress.percent || 0 }));
          },
        });
        if (!isMountedRef.current) return;
        const contentDisposition = headers['content-disposition'] || '';
        const fileName = inferFileNameFromContentDisposition(contentDisposition, fallbackName);
        downloadBlobInBrowser({ blob, fileName });
      } catch (error) {
        if (!isMountedRef.current) return;
        const message = error instanceof Error ? error.message : errorMessage;
        showError(message);
      } finally {
        if (!isMountedRef.current) return;
        setDownloadingId(null);
        setProgress((prev) => removeRecordKey(prev, item.id));
      }
    },
    [showError]
  );

  const handleDownloadWorkflowMedia = useCallback(
    async (item: WorkflowHistoryItem) => {
      if (!item?.id) return;
      const mediaKind =
        item.resultImageCount > 0
          ? 'images'
          : item.resultVideoCount > 0
            ? 'video'
            : item.resultAudioCount > 0
              ? 'audio'
              : null;
      if (!mediaKind) return;
      await handleDownloadWorkflowFile(item, {
        urlSegment: mediaKind,
        fallbackName: `workflow-${item.id.slice(0, 8)}-${mediaKind}.zip`,
        errorMessage: '下载结果媒体失败',
        setDownloadingId: setDownloadingHistoryId,
        setProgress: setDownloadMediaProgress,
      });
    },
    [handleDownloadWorkflowFile]
  );

  const handleDownloadWorkflowAnalysis = useCallback(
    async (item: WorkflowHistoryItem) => {
      if (!item?.id) return;
      await handleDownloadWorkflowFile(item, {
        urlSegment: 'analysis',
        fallbackName: `workflow-${item.id.slice(0, 8)}-analysis.xlsx`,
        errorMessage: '下载分析结果失败',
        setDownloadingId: setDownloadingAnalysisId,
        setProgress: setDownloadAnalysisProgress,
      });
    },
    [handleDownloadWorkflowFile]
  );

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      // 仅清理 user-initiated workflow execution（真用户操作产生的请求需要 abort）
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
      // 修用户反馈：history?limit=100 + agents (canceled) — React StrictMode 双 mount
      // 触发 unmount cleanup abort all in-flight fetch → re-mount 重新发起请求，
      // 在 Network tab 看到 (canceled) 状态。改为不 abort 自动 fetch（list/detail/
      // 下载等 background fetch），让请求自然完成；fetch 内部已有 isMountedRef +
      // sequence guard 防止 setState-after-unmount。
      inFlightControllersRef.current.clear();
    };
  }, []);

  usePrivateCacheLifecycleRevision(resetPrivateWorkflowHistoryState, { includeCacheReset: true });

  // ref-mirror fetchWorkflowHistory：让 mount useEffect 与 interval useEffect 不响应
  // fetch 引用变化，避免父组件 re-render 导致 useCallback 重建 → useEffect 重 fire →
  // 重复 fetch。useEffect deps=[] 后仅 mount 时 fire 一次，cleanup 不 abort 网络层
  // controller（fetchWorkflowHistory 内部 sequence-based dedupe 已经 handle stale）
  const fetchWorkflowHistoryRef = useRef(fetchWorkflowHistory);
  fetchWorkflowHistoryRef.current = fetchWorkflowHistory;

  useEffect(() => {
    void fetchWorkflowHistoryRef.current();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void fetchWorkflowHistoryRef.current();
    }, 15000);
    return () => window.clearInterval(timer);
  }, []);

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

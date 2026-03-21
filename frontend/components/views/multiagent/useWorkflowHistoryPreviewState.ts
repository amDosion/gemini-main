import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import { removeRecordKey, upsertBoundedRecord } from '../../../services/boundedRecordCache';
import {
  fetchWorkflowPreviewImagesWithMeta,
  fetchWorkflowPreviewMediaWithMeta,
  type WorkflowHistoryMediaKind,
  type WorkflowHistoryMediaPreviewItem,
} from '../../../services/workflowHistoryService';
import { PREVIEW_IMAGE_MAX_ENTRIES } from '../../multiagent/workflowResultUtils';
import type { WorkflowHistoryItem } from './types';
import { isWorkflowExecutionAbortError } from './workflowExecutionErrors';

const HISTORY_PREVIEW_CACHE_MAX_ENTRIES = PREVIEW_IMAGE_MAX_ENTRIES;
const HISTORY_PREVIEW_IMAGE_FETCH_LIMIT = PREVIEW_IMAGE_MAX_ENTRIES;
const HISTORY_PREVIEW_MEDIA_FETCH_LIMIT = 12;

type WorkflowHistoryPreviewMediaState = {
  audioItems: WorkflowHistoryMediaPreviewItem[];
  videoItems: WorkflowHistoryMediaPreviewItem[];
};

const createEmptyWorkflowHistoryPreviewMediaState = (): WorkflowHistoryPreviewMediaState => ({
  audioItems: [],
  videoItems: [],
});

const hasPreviewCacheEntry = (record: Record<string, unknown>, executionId: string): boolean =>
  Object.prototype.hasOwnProperty.call(record, executionId);

const warnSkippedHistoryPreviewImages = (
  executionId: string,
  count: number,
  skippedCount: number
) => {
  if (skippedCount <= 0) {
    return;
  }
};

const warnSkippedHistoryPreviewMedia = (
  executionId: string,
  mediaKind: WorkflowHistoryMediaKind,
  count: number,
  skippedCount: number
) => {
  if (skippedCount <= 0) {
    return;
  }
};

interface UseWorkflowHistoryPreviewStateParams {
  isMountedRef: MutableRefObject<boolean>;
  createRequestController: () => AbortController;
  releaseRequestController: (controller: AbortController) => void;
  showError: (message: string) => void;
}

interface ResolveHistoryDetailPreviewImagesParams {
  executionId: string;
  summaryImageCount: number;
  signal: AbortSignal;
  isStaleRequest: () => boolean;
}

interface ResolveHistoryDetailPreviewMediaParams {
  executionId: string;
  summaryAudioCount: number;
  summaryVideoCount: number;
  signal: AbortSignal;
  isStaleRequest: () => boolean;
}

interface HistoryDetailPreviewMediaUrls {
  audioUrls: string[];
  videoUrls: string[];
}

interface UseWorkflowHistoryPreviewStateResult {
  historyPreviewImages: Record<string, string[]>;
  historyPreviewMedia: Record<string, WorkflowHistoryPreviewMediaState>;
  expandedPreviewHistoryId: string | null;
  previewingHistoryId: string | null;
  setExpandedPreviewHistoryId: Dispatch<SetStateAction<string | null>>;
  removeHistoryPreviewImageCache: (executionId: string) => void;
  removeHistoryPreviewMediaCache: (executionId: string) => void;
  resolveHistoryDetailPreviewImages: (
    params: ResolveHistoryDetailPreviewImagesParams
  ) => Promise<string[] | null>;
  resolveHistoryDetailPreviewMedia: (
    params: ResolveHistoryDetailPreviewMediaParams
  ) => Promise<HistoryDetailPreviewMediaUrls | null>;
  handleToggleWorkflowMediaPreview: (item: WorkflowHistoryItem) => Promise<void>;
}

const toBoundedPreviewMediaUrls = (items: WorkflowHistoryMediaPreviewItem[]): string[] =>
  (Array.isArray(items) ? items : [])
    .map((item) => String(item?.previewUrl || '').trim())
    .filter((url) => url.length > 0)
    .slice(0, HISTORY_PREVIEW_MEDIA_FETCH_LIMIT);

export const useWorkflowHistoryPreviewState = ({
  isMountedRef,
  createRequestController,
  releaseRequestController,
  showError,
}: UseWorkflowHistoryPreviewStateParams): UseWorkflowHistoryPreviewStateResult => {
  const [previewingHistoryId, setPreviewingHistoryId] = useState<string | null>(null);
  const [expandedPreviewHistoryId, setExpandedPreviewHistoryId] = useState<string | null>(null);
  const [historyPreviewImages, setHistoryPreviewImages] = useState<Record<string, string[]>>({});
  const [historyPreviewMedia, setHistoryPreviewMedia] = useState<Record<string, WorkflowHistoryPreviewMediaState>>({});
  const historyPreviewRequestSeqRef = useRef(0);
  const historyPreviewControllerRef = useRef<AbortController | null>(null);

  const removeHistoryPreviewImageCache = useCallback((executionId: string) => {
    setHistoryPreviewImages((prev) => removeRecordKey(prev, executionId));
  }, []);

  const removeHistoryPreviewMediaCache = useCallback((executionId: string) => {
    setHistoryPreviewMedia((prev) => removeRecordKey(prev, executionId));
  }, []);

  const resolveHistoryDetailPreviewImages = useCallback(async ({
    executionId,
    summaryImageCount,
    signal,
    isStaleRequest,
  }: ResolveHistoryDetailPreviewImagesParams): Promise<string[] | null> => {
    const cachedImages = historyPreviewImages[executionId];
    if (hasPreviewCacheEntry(historyPreviewImages, executionId)) {
      return Array.isArray(cachedImages) ? cachedImages : [];
    }
    if (summaryImageCount <= 0) {
      return [];
    }
    try {
      const { imageUrls, skippedCount, count } = await fetchWorkflowPreviewImagesWithMeta(
        executionId,
        HISTORY_PREVIEW_IMAGE_FETCH_LIMIT,
        signal
      );
      if (!isMountedRef.current || signal.aborted || isStaleRequest()) {
        return null;
      }
      warnSkippedHistoryPreviewImages(executionId, count, skippedCount);
      setHistoryPreviewImages((prev) => upsertBoundedRecord({
        record: prev,
        key: executionId,
        value: imageUrls,
        maxEntries: HISTORY_PREVIEW_CACHE_MAX_ENTRIES,
        protectedKeys: [expandedPreviewHistoryId, executionId],
      }));
      return imageUrls;
    } catch (error) {
      if (isWorkflowExecutionAbortError(error) || signal.aborted || isStaleRequest()) {
        return null;
      }
      const message = error instanceof Error ? error.message : '加载图片预览失败';
      showError(message);
      return null;
    }
  }, [expandedPreviewHistoryId, historyPreviewImages, isMountedRef, showError]);

  const resolveHistoryDetailPreviewMedia = useCallback(async ({
    executionId,
    summaryAudioCount,
    summaryVideoCount,
    signal,
    isStaleRequest,
  }: ResolveHistoryDetailPreviewMediaParams): Promise<HistoryDetailPreviewMediaUrls | null> => {
    const cachedMedia = historyPreviewMedia[executionId];
    const cachedAudioUrls = toBoundedPreviewMediaUrls(cachedMedia?.audioItems || []);
    const cachedVideoUrls = toBoundedPreviewMediaUrls(cachedMedia?.videoItems || []);
    if (hasPreviewCacheEntry(historyPreviewMedia, executionId)) {
      return {
        audioUrls: cachedAudioUrls,
        videoUrls: cachedVideoUrls,
      };
    }
    if (summaryAudioCount <= 0 && summaryVideoCount <= 0) {
      return {
        audioUrls: [],
        videoUrls: [],
      };
    }
    try {
      const [audioResult, videoResult] = await Promise.all([
        summaryAudioCount > 0
          ? fetchWorkflowPreviewMediaWithMeta(
            executionId,
            'audio',
            HISTORY_PREVIEW_MEDIA_FETCH_LIMIT,
            signal
          )
          : Promise.resolve({ mediaType: 'audio' as const, items: [], skippedCount: 0, count: 0 }),
        summaryVideoCount > 0
          ? fetchWorkflowPreviewMediaWithMeta(
            executionId,
            'video',
            HISTORY_PREVIEW_MEDIA_FETCH_LIMIT,
            signal
          )
          : Promise.resolve({ mediaType: 'video' as const, items: [], skippedCount: 0, count: 0 }),
      ]);
      if (!isMountedRef.current || signal.aborted || isStaleRequest()) {
        return null;
      }
      warnSkippedHistoryPreviewMedia(executionId, 'audio', audioResult.count, audioResult.skippedCount);
      warnSkippedHistoryPreviewMedia(executionId, 'video', videoResult.count, videoResult.skippedCount);
      const nextMediaState = {
        audioItems: audioResult.items,
        videoItems: videoResult.items,
      };
      setHistoryPreviewMedia((prev) => upsertBoundedRecord({
        record: prev,
        key: executionId,
        value: nextMediaState,
        maxEntries: HISTORY_PREVIEW_CACHE_MAX_ENTRIES,
        protectedKeys: [expandedPreviewHistoryId, executionId],
      }));
      return {
        audioUrls: toBoundedPreviewMediaUrls(audioResult.items),
        videoUrls: toBoundedPreviewMediaUrls(videoResult.items),
      };
    } catch (error) {
      if (isWorkflowExecutionAbortError(error) || signal.aborted || isStaleRequest()) {
        return null;
      }
      const message = error instanceof Error ? error.message : '加载媒体预览失败';
      showError(message);
      return null;
    }
  }, [expandedPreviewHistoryId, historyPreviewMedia, isMountedRef, showError]);

  const handleToggleWorkflowMediaPreview = useCallback(async (item: WorkflowHistoryItem) => {
    if (!item?.id) return;
    historyPreviewRequestSeqRef.current += 1;
    const requestSeq = historyPreviewRequestSeqRef.current;

    const previousController = historyPreviewControllerRef.current;
    if (previousController) {
      previousController.abort();
      releaseRequestController(previousController);
      historyPreviewControllerRef.current = null;
    }

    if (isMountedRef.current && requestSeq === historyPreviewRequestSeqRef.current) {
      setPreviewingHistoryId(null);
    }

    if (expandedPreviewHistoryId === item.id) {
      setExpandedPreviewHistoryId(null);
      return;
    }

    const cachedImages = historyPreviewImages[item.id];
    const cachedMedia = historyPreviewMedia[item.id];
    const hasCachedPreview = (
      hasPreviewCacheEntry(historyPreviewImages, item.id) ||
      hasPreviewCacheEntry(historyPreviewMedia, item.id)
    );
    if (hasCachedPreview) {
      setExpandedPreviewHistoryId(item.id);
      return;
    }

    const controller = createRequestController();
    historyPreviewControllerRef.current = controller;
    const isStaleRequest = () =>
      requestSeq !== historyPreviewRequestSeqRef.current ||
      historyPreviewControllerRef.current !== controller;

    if (isMountedRef.current) {
      setPreviewingHistoryId(item.id);
    }
    try {
      const shouldLoadImages = item.resultImageCount > 0;
      const shouldLoadAudio = item.resultAudioCount > 0;
      const shouldLoadVideo = item.resultVideoCount > 0;
      const [imageResult, audioResult, videoResult] = await Promise.all([
        shouldLoadImages
          ? fetchWorkflowPreviewImagesWithMeta(
            item.id,
            HISTORY_PREVIEW_IMAGE_FETCH_LIMIT,
            controller.signal
          )
          : Promise.resolve({ imageUrls: [], skippedCount: 0, count: 0 }),
        shouldLoadAudio
          ? fetchWorkflowPreviewMediaWithMeta(
            item.id,
            'audio',
            HISTORY_PREVIEW_MEDIA_FETCH_LIMIT,
            controller.signal
          )
          : Promise.resolve({ mediaType: 'audio' as const, items: [], skippedCount: 0, count: 0 }),
        shouldLoadVideo
          ? fetchWorkflowPreviewMediaWithMeta(
            item.id,
            'video',
            HISTORY_PREVIEW_MEDIA_FETCH_LIMIT,
            controller.signal
          )
          : Promise.resolve({ mediaType: 'video' as const, items: [], skippedCount: 0, count: 0 }),
      ]);
      if (!isMountedRef.current || controller.signal.aborted || isStaleRequest()) return;

      warnSkippedHistoryPreviewImages(item.id, imageResult.count, imageResult.skippedCount);
      warnSkippedHistoryPreviewMedia(item.id, 'audio', audioResult.count, audioResult.skippedCount);
      warnSkippedHistoryPreviewMedia(item.id, 'video', videoResult.count, videoResult.skippedCount);

      setHistoryPreviewImages((prev) => upsertBoundedRecord({
        record: prev,
        key: item.id,
        value: imageResult.imageUrls,
        maxEntries: HISTORY_PREVIEW_CACHE_MAX_ENTRIES,
        protectedKeys: [expandedPreviewHistoryId, item.id],
      }));
      setHistoryPreviewMedia((prev) => upsertBoundedRecord({
        record: prev,
        key: item.id,
        value: audioResult.items.length > 0 || videoResult.items.length > 0
          ? {
            audioItems: audioResult.items,
            videoItems: videoResult.items,
          }
          : createEmptyWorkflowHistoryPreviewMediaState(),
        maxEntries: HISTORY_PREVIEW_CACHE_MAX_ENTRIES,
        protectedKeys: [expandedPreviewHistoryId, item.id],
      }));
      setExpandedPreviewHistoryId(item.id);
    } catch (error) {
      if (
        isWorkflowExecutionAbortError(error) ||
        !isMountedRef.current ||
        controller.signal.aborted ||
        isStaleRequest()
      ) {
        return;
      }
      const message = error instanceof Error ? error.message : '加载媒体预览失败';
      showError(message);
    } finally {
      releaseRequestController(controller);
      if (historyPreviewControllerRef.current === controller) {
        historyPreviewControllerRef.current = null;
      }
      if (isMountedRef.current && requestSeq === historyPreviewRequestSeqRef.current) {
        setPreviewingHistoryId(null);
      }
    }
  }, [
    createRequestController,
    expandedPreviewHistoryId,
    historyPreviewImages,
    historyPreviewMedia,
    isMountedRef,
    releaseRequestController,
    showError,
  ]);

  useEffect(() => () => {
    historyPreviewRequestSeqRef.current += 1;
    const historyPreviewController = historyPreviewControllerRef.current;
    if (!historyPreviewController) {
      return;
    }
    historyPreviewController.abort();
    releaseRequestController(historyPreviewController);
    historyPreviewControllerRef.current = null;
  }, [releaseRequestController]);

  return {
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
  };
};

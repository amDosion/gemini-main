import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { Node } from 'reactflow';
import {
  fetchWorkflowPreviewImagesWithMeta,
  fetchWorkflowPreviewMediaWithMeta,
} from '../../services/workflowHistoryService';
import { removeRecordKey, upsertBoundedRecord } from '../../services/boundedRecordCache';
import type { ExecutionStatus, WorkflowNodeData } from './types';
import { isTerminalExecutionStatus } from './workflowEditorUtils';
import {
  extractAudioUrls,
  extractImageUrls,
  extractVideoUrls,
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
  mergePreviewImagesIntoResult,
  mergePreviewMediaIntoResult,
  PREVIEW_IMAGE_MAX_ENTRIES,
} from './workflowResultUtils';

const RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES = PREVIEW_IMAGE_MAX_ENTRIES;
const RESULT_PANEL_PREVIEW_MEDIA_FETCH_LIMIT = 12;

type ResultPanelPreviewFetchOutcome = 'succeeded' | 'failed';

interface ResultPanelPreviewMediaState {
  audioUrls: string[];
  videoUrls: string[];
}

interface UseResultPanelPreviewStateParams {
  executionStatus?: ExecutionStatus;
  finalResult: any;
  setFinalResult: Dispatch<SetStateAction<any>>;
  setNodes: Dispatch<SetStateAction<Node<WorkflowNodeData>[]>>;
  addLog: (
    nodeId: string,
    nodeName: string,
    level: 'info' | 'warn' | 'error',
    message: string,
    timestamp?: number
  ) => void;
}

interface UseResultPanelPreviewStateResult {
  executionId: string;
  executionFinalStatus: string;
  executionStatusPreviewImageUrls: string[];
  executionStatusPreviewAudioUrls: string[];
  executionStatusPreviewVideoUrls: string[];
  resultPanelPreviewImageUrls: string[];
  mergedResultPanelPreviewImageUrls: string[];
  resultPanelPreviewAudioUrls: string[];
  resultPanelPreviewVideoUrls: string[];
  resultPanelPreviewLoadingExecutionId: string | null;
  handleRetryResultPreview: () => void;
}

export const useResultPanelPreviewState = ({
  executionStatus,
  finalResult,
  setFinalResult,
  setNodes,
  addLog,
}: UseResultPanelPreviewStateParams): UseResultPanelPreviewStateResult => {
  const [resultPanelPreviewCache, setResultPanelPreviewCache] = useState<Record<string, string[]>>({});
  const [resultPanelPreviewFetchOutcomeByExecutionId, setResultPanelPreviewFetchOutcomeByExecutionId] = useState<Record<string, ResultPanelPreviewFetchOutcome>>({});
  const [resultPanelPreviewMediaCache, setResultPanelPreviewMediaCache] = useState<Record<string, ResultPanelPreviewMediaState>>({});
  const [resultPanelPreviewMediaFetchOutcomeByExecutionId, setResultPanelPreviewMediaFetchOutcomeByExecutionId] = useState<Record<string, ResultPanelPreviewFetchOutcome>>({});
  const [resultPanelPreviewLoadingExecutionId, setResultPanelPreviewLoadingExecutionId] = useState<string | null>(null);
  const previewLoadCountRef = useRef<Record<string, number>>({});

  const executionId = useMemo(
    () => String(executionStatus?.executionId || '').trim(),
    [executionStatus?.executionId]
  );
  const executionFinalStatus = useMemo(
    () => String(executionStatus?.finalStatus || '').trim().toLowerCase(),
    [executionStatus?.finalStatus]
  );
  const executionStatusPreviewImageUrls = useMemo(() => {
    const source = executionStatus?.resultPreviewImageUrls;
    if (!Array.isArray(source)) {
      return [] as string[];
    }
    return source
      .map((item) => String(item || '').trim())
      .filter((item) => item.length > 0)
      .slice(0, RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES);
  }, [executionStatus?.resultPreviewImageUrls]);
  const executionStatusPreviewAudioUrls = useMemo(() => {
    const source = executionStatus?.resultPreviewAudioUrls;
    if (!Array.isArray(source)) {
      return [] as string[];
    }
    return source
      .map((item) => String(item || '').trim())
      .filter((item) => item.length > 0)
      .slice(0, RESULT_PANEL_PREVIEW_MEDIA_FETCH_LIMIT);
  }, [executionStatus?.resultPreviewAudioUrls]);
  const executionStatusPreviewVideoUrls = useMemo(() => {
    const source = executionStatus?.resultPreviewVideoUrls;
    if (!Array.isArray(source)) {
      return [] as string[];
    }
    return source
      .map((item) => String(item || '').trim())
      .filter((item) => item.length > 0)
      .slice(0, RESULT_PANEL_PREVIEW_MEDIA_FETCH_LIMIT);
  }, [executionStatus?.resultPreviewVideoUrls]);

  const toBoundedImageUrls = useCallback((urls: unknown): string[] => {
    if (!Array.isArray(urls)) {
      return [];
    }
    return urls
      .map((item) => String(item || '').trim())
      .filter((item) => item.length > 0)
      .slice(0, RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES);
  }, []);

  const toBoundedMediaUrls = useCallback((urls: unknown): string[] => {
    if (!Array.isArray(urls)) {
      return [];
    }
    return urls
      .map((item) => String(item || '').trim())
      .filter((item) => item.length > 0)
      .slice(0, RESULT_PANEL_PREVIEW_MEDIA_FETCH_LIMIT);
  }, []);

  const startPreviewLoad = useCallback((targetExecutionId: string) => {
    previewLoadCountRef.current[targetExecutionId] = (previewLoadCountRef.current[targetExecutionId] || 0) + 1;
    setResultPanelPreviewLoadingExecutionId(targetExecutionId);
  }, []);

  const finishPreviewLoad = useCallback((targetExecutionId: string) => {
    const nextCount = Math.max(0, (previewLoadCountRef.current[targetExecutionId] || 0) - 1);
    if (nextCount <= 0) {
      delete previewLoadCountRef.current[targetExecutionId];
      setResultPanelPreviewLoadingExecutionId((current) => (current === targetExecutionId ? null : current));
      return;
    }
    previewLoadCountRef.current[targetExecutionId] = nextCount;
  }, []);

  useEffect(() => {
    if (!executionId) {
      return;
    }
    if (!isTerminalExecutionStatus(executionFinalStatus)) {
      return;
    }
    if (resultPanelPreviewLoadingExecutionId === executionId) {
      return;
    }
    if ((resultPanelPreviewCache[executionId] || []).length > 0) {
      return;
    }
    if (executionStatusPreviewImageUrls.length > 0) {
      return;
    }
    const hasPreviewCacheEntry = Object.prototype.hasOwnProperty.call(resultPanelPreviewCache, executionId);
    const previewFetchOutcome = resultPanelPreviewFetchOutcomeByExecutionId[executionId];
    if (previewFetchOutcome === 'failed') {
      return;
    }
    if (previewFetchOutcome === 'succeeded' && hasPreviewCacheEntry) {
      return;
    }
    const existingResultImageUrls = extractImageUrls(executionStatus?.finalResult);
    const hasRenderableResultImage = existingResultImageUrls.some((item) => isDirectlyRenderableImageUrl(item));
    if (hasRenderableResultImage) {
      return;
    }
    let cancelled = false;
    startPreviewLoad(executionId);

    void (async () => {
      try {
        const { imageUrls, skippedCount, count } = await fetchWorkflowPreviewImagesWithMeta(
          executionId,
          RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES
        );
        if (!cancelled) {
          const boundedImageUrls = toBoundedImageUrls(imageUrls);
          setResultPanelPreviewCache((prev) => upsertBoundedRecord({
            record: prev,
            key: executionId,
            value: boundedImageUrls,
            maxEntries: RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES,
            protectedKeys: [executionId],
          }));
          setResultPanelPreviewFetchOutcomeByExecutionId((prev) => upsertBoundedRecord({
            record: prev,
            key: executionId,
            value: 'succeeded',
            maxEntries: RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES,
            protectedKeys: [executionId],
          }));
          if (skippedCount > 0) {
            addLog(
              'system',
              '系统',
              'warn',
              `最终结果图片预览存在跳过项：成功 ${count} 张，跳过 ${skippedCount} 张（仅提示，不自动重试）`
            );
          }
        }
      } catch (error) {
        if (!cancelled) {
          setResultPanelPreviewCache((prev) => upsertBoundedRecord({
            record: prev,
            key: executionId,
            value: [],
            maxEntries: RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES,
            protectedKeys: [executionId],
          }));
          setResultPanelPreviewFetchOutcomeByExecutionId((prev) => upsertBoundedRecord({
            record: prev,
            key: executionId,
            value: 'failed',
            maxEntries: RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES,
            protectedKeys: [executionId],
          }));
          addLog('system', '系统', 'warn', `加载最终结果图片预览失败: ${error}`);
        }
      } finally {
        if (!cancelled) {
          finishPreviewLoad(executionId);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    addLog,
    executionFinalStatus,
    executionId,
    executionStatus?.finalResult,
    executionStatusPreviewImageUrls,
    resultPanelPreviewCache,
    resultPanelPreviewFetchOutcomeByExecutionId,
    finishPreviewLoad,
    startPreviewLoad,
    toBoundedImageUrls,
  ]);

  useEffect(() => {
    if (!executionId) {
      return;
    }
    if (!isTerminalExecutionStatus(executionFinalStatus)) {
      return;
    }
    const cachedMedia = resultPanelPreviewMediaCache[executionId];
    const hasCachedPreviewMedia = Boolean(cachedMedia?.audioUrls?.length || cachedMedia?.videoUrls?.length);
    const hasPreviewCacheEntry = Object.prototype.hasOwnProperty.call(resultPanelPreviewMediaCache, executionId);
    const previewFetchOutcome = resultPanelPreviewMediaFetchOutcomeByExecutionId[executionId];
    if (previewFetchOutcome === 'failed') {
      return;
    }
    if (previewFetchOutcome === 'succeeded' && hasPreviewCacheEntry) {
      return;
    }

    const existingResultAudioUrls = extractAudioUrls(executionStatus?.finalResult);
    const existingResultVideoUrls = extractVideoUrls(executionStatus?.finalResult);
    const hasExecutionStatusPreviewAudio = executionStatusPreviewAudioUrls.some((item) => isDirectlyRenderableAudioUrl(item));
    const hasExecutionStatusPreviewVideo = executionStatusPreviewVideoUrls.some((item) => isDirectlyRenderableVideoUrl(item));
    const needsAudioPreview = !existingResultAudioUrls.some((item) => isDirectlyRenderableAudioUrl(item)) && !hasExecutionStatusPreviewAudio;
    const needsVideoPreview = !existingResultVideoUrls.some((item) => isDirectlyRenderableVideoUrl(item)) && !hasExecutionStatusPreviewVideo;
    if (!needsAudioPreview && !needsVideoPreview) {
      return;
    }
    if (hasCachedPreviewMedia) {
      return;
    }

    let cancelled = false;
    startPreviewLoad(executionId);

    void (async () => {
      try {
        const [audioResult, videoResult] = await Promise.all([
          needsAudioPreview
            ? fetchWorkflowPreviewMediaWithMeta(executionId, 'audio', RESULT_PANEL_PREVIEW_MEDIA_FETCH_LIMIT)
            : Promise.resolve({ mediaType: 'audio' as const, items: [], skippedCount: 0, count: 0 }),
          needsVideoPreview
            ? fetchWorkflowPreviewMediaWithMeta(executionId, 'video', RESULT_PANEL_PREVIEW_MEDIA_FETCH_LIMIT)
            : Promise.resolve({ mediaType: 'video' as const, items: [], skippedCount: 0, count: 0 }),
        ]);

        if (cancelled) {
          return;
        }

        const nextMediaState: ResultPanelPreviewMediaState = {
          audioUrls: toBoundedMediaUrls(audioResult.items.map((item) => item.previewUrl)),
          videoUrls: toBoundedMediaUrls(videoResult.items.map((item) => item.previewUrl)),
        };
        setResultPanelPreviewMediaCache((prev) => upsertBoundedRecord({
          record: prev,
          key: executionId,
          value: nextMediaState,
          maxEntries: RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES,
          protectedKeys: [executionId],
        }));
        setResultPanelPreviewMediaFetchOutcomeByExecutionId((prev) => upsertBoundedRecord({
          record: prev,
          key: executionId,
          value: 'succeeded',
          maxEntries: RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES,
          protectedKeys: [executionId],
        }));

        if (audioResult.skippedCount > 0) {
          addLog(
            'system',
            '系统',
            'warn',
            `最终结果音频预览存在跳过项：成功 ${audioResult.count} 条，跳过 ${audioResult.skippedCount} 条（仅提示，不自动重试）`
          );
        }
        if (videoResult.skippedCount > 0) {
          addLog(
            'system',
            '系统',
            'warn',
            `最终结果视频预览存在跳过项：成功 ${videoResult.count} 条，跳过 ${videoResult.skippedCount} 条（仅提示，不自动重试）`
          );
        }
      } catch (error) {
        if (!cancelled) {
          setResultPanelPreviewMediaCache((prev) => upsertBoundedRecord({
            record: prev,
            key: executionId,
            value: {
              audioUrls: [],
              videoUrls: [],
            },
            maxEntries: RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES,
            protectedKeys: [executionId],
          }));
          setResultPanelPreviewMediaFetchOutcomeByExecutionId((prev) => upsertBoundedRecord({
            record: prev,
            key: executionId,
            value: 'failed',
            maxEntries: RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES,
            protectedKeys: [executionId],
          }));
          addLog('system', '系统', 'warn', `加载最终结果媒体预览失败: ${error}`);
        }
      } finally {
        if (!cancelled) {
          finishPreviewLoad(executionId);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    addLog,
    executionFinalStatus,
    executionId,
    executionStatus?.finalResult,
    executionStatusPreviewAudioUrls,
    executionStatusPreviewVideoUrls,
    finishPreviewLoad,
    resultPanelPreviewMediaCache,
    resultPanelPreviewMediaFetchOutcomeByExecutionId,
    startPreviewLoad,
    toBoundedMediaUrls,
  ]);

  const resultPanelPreviewImageUrls = useMemo(() => {
    if (!executionId) {
      return [] as string[];
    }
    return resultPanelPreviewCache[executionId] || [];
  }, [executionId, resultPanelPreviewCache]);

  const mergedResultPanelPreviewImageUrls = useMemo(() => {
    const dedup = new Set<string>();
    const merged: string[] = [];
    [executionStatusPreviewImageUrls, resultPanelPreviewImageUrls].forEach((source) => {
      source.forEach((imageUrl) => {
        if (!dedup.has(imageUrl)) {
          dedup.add(imageUrl);
          merged.push(imageUrl);
        }
      });
    });
    return merged.slice(0, RESULT_PANEL_PREVIEW_CACHE_MAX_ENTRIES);
  }, [executionStatusPreviewImageUrls, resultPanelPreviewImageUrls]);

  const resultPanelPreviewMedia = useMemo<ResultPanelPreviewMediaState>(() => {
    const dedup = (urls: string[]) => Array.from(new Set(urls)).slice(0, RESULT_PANEL_PREVIEW_MEDIA_FETCH_LIMIT);
    const cachedMedia = executionId
      ? (resultPanelPreviewMediaCache[executionId] || { audioUrls: [], videoUrls: [] })
      : { audioUrls: [], videoUrls: [] };
    return {
      audioUrls: dedup([...executionStatusPreviewAudioUrls, ...cachedMedia.audioUrls]),
      videoUrls: dedup([...executionStatusPreviewVideoUrls, ...cachedMedia.videoUrls]),
    };
  }, [
    executionId,
    executionStatusPreviewAudioUrls,
    executionStatusPreviewVideoUrls,
    resultPanelPreviewMediaCache,
  ]);

  useEffect(() => {
    if (resultPanelPreviewImageUrls.length === 0) {
      return;
    }

    const mergeIfMissing = (payload: any) => {
      const existingUrls = extractImageUrls(payload)
        .map((item) => String(item || '').trim())
        .filter(Boolean);
      const hasAllPreviewImages = resultPanelPreviewImageUrls.every((previewUrl) => existingUrls.includes(previewUrl));
      if (hasAllPreviewImages) {
        return payload;
      }
      return mergePreviewImagesIntoResult(payload, resultPanelPreviewImageUrls);
    };

    setFinalResult((prev: any) => {
      const merged = mergeIfMissing(prev);
      return merged === prev ? prev : merged;
    });

    setNodes((nds) => nds.map((node) => {
      const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
      if (nodeType !== 'end') {
        return node;
      }
      const baseResult = node.data?.result ?? finalResult;
      const mergedResult = mergeIfMissing(baseResult);
      if (mergedResult === baseResult) {
        return node;
      }
      return {
        ...node,
        data: {
          ...node.data,
          result: mergedResult,
        },
      };
    }));
  }, [finalResult, resultPanelPreviewImageUrls, setFinalResult, setNodes]);

  useEffect(() => {
    if (resultPanelPreviewMedia.audioUrls.length === 0 && resultPanelPreviewMedia.videoUrls.length === 0) {
      return;
    }

    const mergeIfMissing = (payload: any) => {
      let merged = payload;
      if (resultPanelPreviewMedia.audioUrls.length > 0) {
        const existingAudioUrls = extractAudioUrls(merged)
          .map((item) => String(item || '').trim())
          .filter(Boolean);
        const hasAllPreviewAudio = resultPanelPreviewMedia.audioUrls.every((previewUrl) => existingAudioUrls.includes(previewUrl));
        if (!hasAllPreviewAudio) {
          merged = mergePreviewMediaIntoResult(merged, 'audio', resultPanelPreviewMedia.audioUrls);
        }
      }
      if (resultPanelPreviewMedia.videoUrls.length > 0) {
        const existingVideoUrls = extractVideoUrls(merged)
          .map((item) => String(item || '').trim())
          .filter(Boolean);
        const hasAllPreviewVideo = resultPanelPreviewMedia.videoUrls.every((previewUrl) => existingVideoUrls.includes(previewUrl));
        if (!hasAllPreviewVideo) {
          merged = mergePreviewMediaIntoResult(merged, 'video', resultPanelPreviewMedia.videoUrls);
        }
      }
      return merged;
    };

    setFinalResult((prev: any) => {
      const merged = mergeIfMissing(prev);
      return merged === prev ? prev : merged;
    });

    setNodes((nds) => nds.map((node) => {
      const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
      if (nodeType !== 'end') {
        return node;
      }
      const baseResult = node.data?.result ?? finalResult;
      const mergedResult = mergeIfMissing(baseResult);
      if (mergedResult === baseResult) {
        return node;
      }
      return {
        ...node,
        data: {
          ...node.data,
          result: mergedResult,
        },
      };
    }));
  }, [finalResult, resultPanelPreviewMedia, setFinalResult, setNodes]);

  const handleRetryResultPreview = useCallback(() => {
    if (!executionId) return;
    delete previewLoadCountRef.current[executionId];
    setResultPanelPreviewLoadingExecutionId((current) => (current === executionId ? null : current));
    setResultPanelPreviewCache((prev) => removeRecordKey(prev, executionId));
    setResultPanelPreviewFetchOutcomeByExecutionId((prev) => removeRecordKey(prev, executionId));
    setResultPanelPreviewMediaCache((prev) => removeRecordKey(prev, executionId));
    setResultPanelPreviewMediaFetchOutcomeByExecutionId((prev) => removeRecordKey(prev, executionId));
    addLog('system', '系统', 'info', '已触发结果媒体重新加载');
  }, [addLog, executionId]);

  return {
    executionId,
    executionFinalStatus,
    executionStatusPreviewImageUrls,
    executionStatusPreviewAudioUrls,
    executionStatusPreviewVideoUrls,
    resultPanelPreviewImageUrls,
    mergedResultPanelPreviewImageUrls,
    resultPanelPreviewAudioUrls: resultPanelPreviewMedia.audioUrls,
    resultPanelPreviewVideoUrls: resultPanelPreviewMedia.videoUrls,
    resultPanelPreviewLoadingExecutionId,
    handleRetryResultPreview,
  };
};

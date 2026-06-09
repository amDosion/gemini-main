import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { upsertBoundedRecord } from '../../../services/boundedRecordCache';
import {
  getWorkflowPreviewImagesWithCache,
  readWorkflowPreviewImagesCacheEntry,
  writeWorkflowPreviewImagesCacheEntry,
} from '../../../services/workflowPreviewCache';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from '../../../services/privateCacheInvalidation';
import { usePrivateCacheLifecycleRevision } from '../../../hooks/usePrivateCacheScopeRevision';
import {
  PREVIEW_IMAGE_MAX_ENTRIES,
  isDirectlyRenderableImageUrl,
} from '../../multiagent/workflowResultUtils';
import type { WorkflowResultImageCard } from '../../multiagent/WorkflowResultImageCanvas';
import type { WorkflowHistoryItem } from './types';
import { isWorkflowExecutionAbortError } from './workflowExecutionErrors';

const HISTORY_IMAGE_BROWSER_PAGE_SIZE = 24;
const HISTORY_IMAGE_BROWSER_CACHE_MAX_ENTRIES = PREVIEW_IMAGE_MAX_ENTRIES * 2;

type WorkflowHistoryImagePreviewCacheEntry = {
  imageUrls: string[];
  loading: boolean;
  requestedLimit?: number;
  error?: string;
};

type MissingPreviewRequest = {
  executionId: string;
  requiredLimit: number;
};

interface UseWorkflowHistoryImageBrowserParams {
  items: WorkflowHistoryItem[];
  seedPreviewImages: Record<string, string[]>;
  enabled: boolean;
  showError: (message: string) => void;
  pageSize?: number;
}

interface UseWorkflowHistoryImageBrowserResult {
  cards: WorkflowResultImageCard[];
  currentPageCards: WorkflowResultImageCard[];
  hasImages: boolean;
  page: number;
  pageSize: number;
  totalCount: number;
  totalPages: number;
  setPage: (page: number) => void;
  resetPage: () => void;
}

const normalizePageSize = (value?: number): number => {
  if (!Number.isFinite(value)) {
    return HISTORY_IMAGE_BROWSER_PAGE_SIZE;
  }
  return Math.max(1, Math.floor(value || HISTORY_IMAGE_BROWSER_PAGE_SIZE));
};

const toRenderableImageUrls = (imageUrls: unknown): string[] => {
  if (!Array.isArray(imageUrls)) {
    return [];
  }
  const seen = new Set<string>();
  const urls: string[] = [];
  imageUrls.forEach((imageUrl) => {
    if (!isDirectlyRenderableImageUrl(imageUrl)) {
      return;
    }
    const normalized = String(imageUrl).trim();
    if (normalized.toLowerCase().startsWith('blob:')) {
      return;
    }
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    urls.push(normalized);
  });
  return urls;
};

const createHistoryItemsSignature = (items: WorkflowHistoryItem[]): string =>
  items
    .map((item) => `${item.id}:${item.resultImageCount}:${(item.resultImageUrls || []).join('|')}`)
    .join('||');

const warnSkippedHistoryBrowserPreviewImages = (
  executionId: string,
  count: number,
  skippedCount: number
) => {
  if (skippedCount <= 0) {
    return;
  }
  console.warn(
    `[WorkflowHistoryImageBrowser] Preview images skipped: execution=${executionId}, count=${count}, skipped=${skippedCount}`
  );
};

export const useWorkflowHistoryImageBrowser = ({
  items,
  seedPreviewImages,
  enabled,
  showError,
  pageSize,
}: UseWorkflowHistoryImageBrowserParams): UseWorkflowHistoryImageBrowserResult => {
  const [page, setRawPage] = useState(1);
  const [localPreviewCache, setLocalPreviewCache] = useState<
    Record<string, WorkflowHistoryImagePreviewCacheEntry>
  >({});
  const mountedRef = useRef(true);
  const blockedItemsSignatureRef = useRef('');
  const itemsSignatureRef = useRef('');
  const normalizedPageSize = normalizePageSize(pageSize);
  const itemsSignature = useMemo(() => createHistoryItemsSignature(items), [items]);

  const resetLocalBrowserCache = useCallback(() => {
    blockedItemsSignatureRef.current = itemsSignatureRef.current;
    setLocalPreviewCache({});
    setRawPage(1);
  }, []);

  const cards = useMemo<WorkflowResultImageCard[]>(() => {
    const nextCards: WorkflowResultImageCard[] = [];

    items.forEach((item) => {
      const executionId = String(item.id || '').trim();
      if (!executionId) {
        return;
      }

      const directImageUrls = toRenderableImageUrls(item.resultImageUrls);
      const seededImageUrls = toRenderableImageUrls(seedPreviewImages[executionId]);
      const sharedEntry = readWorkflowPreviewImagesCacheEntry(executionId);
      const localEntry =
        localPreviewCache[executionId] ||
        (sharedEntry
          ? {
              imageUrls: sharedEntry.imageUrls,
              loading: false,
              requestedLimit: sharedEntry.requestedLimit,
              error: sharedEntry.error,
            }
          : undefined);
      const localImageUrls = toRenderableImageUrls(localEntry?.imageUrls);
      const previewImageUrls = seededImageUrls.length > 0 ? seededImageUrls : localImageUrls;
      const imageCount = Math.max(
        Number(item.resultImageCount || 0),
        directImageUrls.length,
        previewImageUrls.length
      );

      for (let imageIndex = 0; imageIndex < imageCount; imageIndex += 1) {
        const imageUrl = directImageUrls[imageIndex] || previewImageUrls[imageIndex] || undefined;
        const hasRequestedMissingPreview = Boolean(
          localEntry?.requestedLimit && localEntry.requestedLimit > imageIndex
        );
        nextCards.push({
          id: `workflow-history-image-${executionId}-${imageIndex}`,
          title: item.title || `工作流 ${executionId.slice(0, 8)}`,
          subtitle: item.task || item.resultPreview || executionId,
          executionId,
          imageIndex,
          imageUrl,
          loadState: imageUrl
            ? 'loaded'
            : localEntry?.loading
              ? 'loading'
              : localEntry?.error || hasRequestedMissingPreview
                ? 'error'
                : 'idle',
        });
      }
    });

    return nextCards.map((card, index) => ({
      ...card,
      indexLabel: `${index + 1}/${nextCards.length}`,
    }));
  }, [items, localPreviewCache, seedPreviewImages]);

  const totalCount = cards.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / normalizedPageSize));
  const normalizedPage = Math.max(1, Math.min(page, totalPages));
  const currentPageCards = useMemo(() => {
    const startIndex = (normalizedPage - 1) * normalizedPageSize;
    return cards.slice(startIndex, startIndex + normalizedPageSize);
  }, [cards, normalizedPage, normalizedPageSize]);
  const missingPreviewRequests = useMemo<MissingPreviewRequest[]>(() => {
    const requestByExecutionId = new Map<string, number>();
    currentPageCards.forEach((card) => {
      if (card.imageUrl || card.loadState === 'loading' || card.loadState === 'error') {
        return;
      }
      if (card.executionId && typeof card.imageIndex === 'number') {
        requestByExecutionId.set(
          card.executionId,
          Math.max(requestByExecutionId.get(card.executionId) || 0, card.imageIndex + 1)
        );
      }
    });
    return Array.from(requestByExecutionId.entries()).map(([executionId, requiredLimit]) => ({
      executionId,
      requiredLimit,
    }));
  }, [currentPageCards]);
  const missingPreviewRequestsKey = missingPreviewRequests
    .map((request) => `${request.executionId}:${request.requiredLimit}`)
    .join('|');

  const setPage = useCallback(
    (nextPage: number) => {
      const normalized = Math.max(1, Math.min(totalPages, Math.floor(Number(nextPage) || 1)));
      setRawPage(normalized);
    },
    [totalPages]
  );

  const resetPage = useCallback(() => {
    setRawPage(1);
  }, []);

  useEffect(() => {
    itemsSignatureRef.current = itemsSignature;
    if (blockedItemsSignatureRef.current && blockedItemsSignatureRef.current !== itemsSignature) {
      blockedItemsSignatureRef.current = '';
    }
    setRawPage(1);
  }, [itemsSignature]);

  useEffect(() => {
    if (normalizedPage !== page) {
      setRawPage(normalizedPage);
    }
  }, [normalizedPage, page]);

  useEffect(() => {
    if (
      !enabled ||
      missingPreviewRequests.length === 0 ||
      blockedItemsSignatureRef.current === itemsSignature
    ) {
      return;
    }

    missingPreviewRequests.forEach(({ executionId, requiredLimit }) => {
      const requestLimit = Math.max(PREVIEW_IMAGE_MAX_ENTRIES, requiredLimit);
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      setLocalPreviewCache((prev) =>
        upsertBoundedRecord({
          record: prev,
          key: executionId,
          value: {
            imageUrls:
              prev[executionId]?.imageUrls ||
              readWorkflowPreviewImagesCacheEntry(executionId)?.imageUrls ||
              [],
            loading: true,
            requestedLimit: Math.max(prev[executionId]?.requestedLimit || 0, requestLimit),
          },
          maxEntries: HISTORY_IMAGE_BROWSER_CACHE_MAX_ENTRIES,
          protectedKeys: [executionId],
        })
      );

      void getWorkflowPreviewImagesWithCache(executionId, requestLimit)
        .then(({ imageUrls, skippedCount, count }) => {
          if (!mountedRef.current || !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)) {
            return;
          }
          warnSkippedHistoryBrowserPreviewImages(executionId, count, skippedCount);
          setLocalPreviewCache((prev) =>
            upsertBoundedRecord({
              record: prev,
              key: executionId,
              value: {
                imageUrls,
                loading: false,
                requestedLimit: Math.max(prev[executionId]?.requestedLimit || 0, requestLimit),
              },
              maxEntries: HISTORY_IMAGE_BROWSER_CACHE_MAX_ENTRIES,
              protectedKeys: [executionId],
            })
          );
        })
        .catch((error) => {
          if (
            isWorkflowExecutionAbortError(error) ||
            !mountedRef.current ||
            !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
          ) {
            return;
          }
          const message = error instanceof Error ? error.message : '加载图片预览失败';
          showError(message);
          // 从共享模块级缓存读取,而非 effect 闭包里捕获的 localPreviewCache:后者是该次
          // effect 运行时的旧值,promise reject 时可能已过期,会用陈旧 URL 覆盖共享缓存。
          const cachedImageUrls = readWorkflowPreviewImagesCacheEntry(executionId)?.imageUrls || [];
          writeWorkflowPreviewImagesCacheEntry(executionId, {
            imageUrls: cachedImageUrls,
            requestedLimit: requestLimit,
            skippedCount: 0,
            count: cachedImageUrls.length,
            error: message,
          });
          setLocalPreviewCache((prev) =>
            upsertBoundedRecord({
              record: prev,
              key: executionId,
              value: {
                imageUrls: prev[executionId]?.imageUrls || [],
                loading: false,
                requestedLimit: Math.max(prev[executionId]?.requestedLimit || 0, requestLimit),
                error: message,
              },
              maxEntries: HISTORY_IMAGE_BROWSER_CACHE_MAX_ENTRIES,
              protectedKeys: [executionId],
            })
          );
        });
    });
  }, [
    enabled,
    itemsSignature,
    localPreviewCache,
    missingPreviewRequests,
    missingPreviewRequestsKey,
    showError,
  ]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  usePrivateCacheLifecycleRevision(
    () => {
      if (!mountedRef.current) return;
      resetLocalBrowserCache();
    },
    { includeCacheReset: true }
  );

  return {
    cards,
    currentPageCards,
    hasImages: totalCount > 0,
    page: normalizedPage,
    pageSize: normalizedPageSize,
    totalCount,
    totalPages,
    setPage,
    resetPage,
  };
};

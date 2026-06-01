import { cacheManager } from './CacheManager';
import {
  fetchWorkflowPreviewImagesWithMeta,
  fetchWorkflowPreviewMediaWithMeta,
  type WorkflowHistoryMediaKind,
  type WorkflowHistoryMediaPreviewItem,
  type WorkflowHistoryMediaPreviewMeta,
  type WorkflowPreviewImagesMeta,
} from './workflowHistoryService';
import {
  getPrivateCacheUserScope,
  scopedPrivateCacheKey,
  scopedPrivateCachePrefix,
} from './privateCacheScope';
import {
  isSafeWorkflowPreviewMediaUrl,
  normalizeWorkflowPreviewImageUrls,
  normalizeWorkflowPreviewUrlField,
} from './workflowPreviewUrlPolicy';

export const WORKFLOW_PREVIEW_IMAGES_PREFIX = 'workflowPreviewImages:';
export const WORKFLOW_PREVIEW_MEDIA_PREFIX = 'workflowPreviewMedia:';

const WORKFLOW_PREVIEW_CACHE_TTL_MS = 30 * 60 * 1000;
const WORKFLOW_PREVIEW_IMAGE_MAX_ENTRIES = 80;
const WORKFLOW_PREVIEW_MEDIA_MAX_ENTRIES = 80;

cacheManager.setTTL(WORKFLOW_PREVIEW_IMAGES_PREFIX, WORKFLOW_PREVIEW_CACHE_TTL_MS);
cacheManager.setTTL(WORKFLOW_PREVIEW_MEDIA_PREFIX, WORKFLOW_PREVIEW_CACHE_TTL_MS);

export interface WorkflowPreviewImageCacheEntry {
  imageUrls: string[];
  requestedLimit: number;
  skippedCount: number;
  count: number;
  updatedAt: number;
  error?: string;
}

export interface WorkflowPreviewMediaCacheEntry {
  mediaType: WorkflowHistoryMediaKind;
  items: WorkflowHistoryMediaPreviewItem[];
  requestedLimit: number;
  skippedCount: number;
  count: number;
  updatedAt: number;
  error?: string;
}

const normalizeId = (value: string | null | undefined): string => String(value || '').trim();

const normalizeLimit = (limit: number | null | undefined): number => {
  if (!Number.isFinite(limit)) return 0;
  return Math.max(0, Math.floor(Number(limit)));
};

const imageCacheKey = (executionId: string, userScope?: string | null): string =>
  scopedPrivateCacheKey(WORKFLOW_PREVIEW_IMAGES_PREFIX, normalizeId(executionId), userScope);

const mediaCacheKey = (
  executionId: string,
  mediaKind: WorkflowHistoryMediaKind,
  userScope?: string | null
): string =>
  scopedPrivateCacheKey(
    WORKFLOW_PREVIEW_MEDIA_PREFIX,
    `${normalizeId(executionId)}:${mediaKind}`,
    userScope
  );

const prunePrefix = (
  prefix: string,
  maxEntries: number,
  protectedKeys: string[] = []
): void => {
  const protectedSet = new Set(protectedKeys.filter(Boolean));
  const entries = cacheManager.getEntriesByPrefix<{ updatedAt?: number }>(prefix);
  if (entries.length <= maxEntries) return;

  const staleEntries = entries
    .filter(([key]) => !protectedSet.has(key))
    .sort((left, right) => Number(left[1]?.updatedAt || 0) - Number(right[1]?.updatedAt || 0))
    .slice(0, entries.length - maxEntries);

  staleEntries.forEach(([key]) => cacheManager.remove(key));
};

const imageInFlight = new Map<string, Promise<WorkflowPreviewImagesMeta>>();
const mediaInFlight = new Map<string, Promise<WorkflowHistoryMediaPreviewMeta>>();
let cacheClearGeneration = 0;

const isWorkflowPreviewRequestCurrent = (
  generationAtStart: number,
  requestScope: string
): boolean =>
  generationAtStart === cacheClearGeneration &&
  getPrivateCacheUserScope() === requestScope;

const emptyWorkflowPreviewImagesMeta = (): WorkflowPreviewImagesMeta => ({
  imageUrls: [],
  skippedCount: 0,
  count: 0,
});

const emptyWorkflowPreviewMediaMeta = (
  mediaKind: WorkflowHistoryMediaKind
): WorkflowHistoryMediaPreviewMeta => ({
  mediaType: mediaKind,
  items: [],
  skippedCount: 0,
  count: 0,
});

const normalizeWorkflowPreviewMediaItems = (
  items: unknown
): WorkflowHistoryMediaPreviewItem[] => {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      const previewUrl = isSafeWorkflowPreviewMediaUrl(item?.previewUrl)
        ? item.previewUrl.trim()
        : '';
      if (!previewUrl) return null;
      return {
        ...item,
        sourceUrl: normalizeWorkflowPreviewUrlField(item?.sourceUrl),
        resolvedUrl: normalizeWorkflowPreviewUrlField(item?.resolvedUrl),
        previewUrl,
      } satisfies WorkflowHistoryMediaPreviewItem;
    })
    .filter((item): item is WorkflowHistoryMediaPreviewItem => Boolean(item));
};

const clearWorkflowPreviewMemoryCache = (): void => {
  imageInFlight.clear();
  mediaInFlight.clear();
  cacheManager.clearDomain(WORKFLOW_PREVIEW_IMAGES_PREFIX);
  cacheManager.clearDomain(WORKFLOW_PREVIEW_MEDIA_PREFIX);
};

export const clearWorkflowPreviewCacheForLogout = (): void => {
  cacheClearGeneration += 1;
  clearWorkflowPreviewMemoryCache();
};

export const readWorkflowPreviewImagesCacheEntry = (
  executionId: string
): WorkflowPreviewImageCacheEntry | null => {
  const safeExecutionId = normalizeId(executionId);
  if (!safeExecutionId) return null;
  return cacheManager.get<WorkflowPreviewImageCacheEntry>(imageCacheKey(safeExecutionId));
};

export const writeWorkflowPreviewImagesCacheEntry = (
  executionId: string,
  entry: Omit<WorkflowPreviewImageCacheEntry, 'updatedAt'> & { updatedAt?: number },
  userScope?: string | null
): void => {
  const safeExecutionId = normalizeId(executionId);
  if (!safeExecutionId) return;
  const key = imageCacheKey(safeExecutionId, userScope);
  cacheManager.set<WorkflowPreviewImageCacheEntry>(key, {
    ...entry,
    imageUrls: normalizeWorkflowPreviewImageUrls(entry.imageUrls),
    requestedLimit: normalizeLimit(entry.requestedLimit),
    skippedCount: normalizeLimit(entry.skippedCount),
    count: normalizeLimit(entry.count),
    updatedAt: entry.updatedAt || Date.now(),
  });
  prunePrefix(
    scopedPrivateCachePrefix(WORKFLOW_PREVIEW_IMAGES_PREFIX, userScope),
    WORKFLOW_PREVIEW_IMAGE_MAX_ENTRIES,
    [key]
  );
};

export const removeWorkflowPreviewImagesCacheEntry = (executionId: string): void => {
  const safeExecutionId = normalizeId(executionId);
  if (!safeExecutionId) return;
  cacheManager.remove(imageCacheKey(safeExecutionId));
};

export const getWorkflowPreviewImagesWithCache = async (
  executionId: string,
  limit: number
): Promise<WorkflowPreviewImagesMeta> => {
  const safeExecutionId = normalizeId(executionId);
  const safeLimit = normalizeLimit(limit);
  if (!safeExecutionId) {
    return { imageUrls: [], skippedCount: 0, count: 0 };
  }
  const requestScope = getPrivateCacheUserScope();

  const cached = readWorkflowPreviewImagesCacheEntry(safeExecutionId);
  if (cached && cached.requestedLimit >= safeLimit) {
    return {
      imageUrls: cached.imageUrls,
      skippedCount: cached.skippedCount,
      count: cached.count,
    };
  }

  const key = `${imageCacheKey(safeExecutionId, requestScope)}:${safeLimit}`;
  const existing = imageInFlight.get(key);
  if (existing) return existing;

  const generationAtStart = cacheClearGeneration;
  let promise: Promise<WorkflowPreviewImagesMeta>;
  promise = fetchWorkflowPreviewImagesWithMeta(safeExecutionId, safeLimit)
    .then((result) => {
      if (!isWorkflowPreviewRequestCurrent(generationAtStart, requestScope)) {
        return emptyWorkflowPreviewImagesMeta();
      }
      writeWorkflowPreviewImagesCacheEntry(
        safeExecutionId,
        {
          imageUrls: result.imageUrls,
          requestedLimit: safeLimit,
          skippedCount: result.skippedCount,
          count: result.count,
        },
        requestScope
      );
      return result;
    })
    .finally(() => {
      if (imageInFlight.get(key) === promise) {
        imageInFlight.delete(key);
      }
    });
  imageInFlight.set(key, promise);
  return promise;
};

export const readWorkflowPreviewMediaCacheEntry = (
  executionId: string,
  mediaKind: WorkflowHistoryMediaKind
): WorkflowPreviewMediaCacheEntry | null => {
  const safeExecutionId = normalizeId(executionId);
  if (!safeExecutionId) return null;
  return cacheManager.get<WorkflowPreviewMediaCacheEntry>(mediaCacheKey(safeExecutionId, mediaKind));
};

export const writeWorkflowPreviewMediaCacheEntry = (
  executionId: string,
  mediaKind: WorkflowHistoryMediaKind,
  entry: Omit<WorkflowPreviewMediaCacheEntry, 'mediaType' | 'updatedAt'> & { updatedAt?: number },
  userScope?: string | null
): void => {
  const safeExecutionId = normalizeId(executionId);
  if (!safeExecutionId) return;
  const key = mediaCacheKey(safeExecutionId, mediaKind, userScope);
  cacheManager.set<WorkflowPreviewMediaCacheEntry>(key, {
    ...entry,
    mediaType: mediaKind,
    items: normalizeWorkflowPreviewMediaItems(entry.items),
    requestedLimit: normalizeLimit(entry.requestedLimit),
    skippedCount: normalizeLimit(entry.skippedCount),
    count: normalizeLimit(entry.count),
    updatedAt: entry.updatedAt || Date.now(),
  });
  prunePrefix(
    scopedPrivateCachePrefix(WORKFLOW_PREVIEW_MEDIA_PREFIX, userScope),
    WORKFLOW_PREVIEW_MEDIA_MAX_ENTRIES,
    [key]
  );
};

export const removeWorkflowPreviewMediaCacheEntry = (
  executionId: string,
  mediaKind?: WorkflowHistoryMediaKind
): void => {
  const safeExecutionId = normalizeId(executionId);
  if (!safeExecutionId) return;
  if (mediaKind) {
    cacheManager.remove(mediaCacheKey(safeExecutionId, mediaKind));
    return;
  }
  cacheManager.remove(mediaCacheKey(safeExecutionId, 'audio'));
  cacheManager.remove(mediaCacheKey(safeExecutionId, 'video'));
};

export const getWorkflowPreviewMediaWithCache = async (
  executionId: string,
  mediaKind: WorkflowHistoryMediaKind,
  limit: number
): Promise<WorkflowHistoryMediaPreviewMeta> => {
  const safeExecutionId = normalizeId(executionId);
  const safeLimit = normalizeLimit(limit);
  if (!safeExecutionId) {
    return { mediaType: mediaKind, items: [], skippedCount: 0, count: 0 };
  }
  const requestScope = getPrivateCacheUserScope();

  const cached = readWorkflowPreviewMediaCacheEntry(safeExecutionId, mediaKind);
  if (cached && cached.requestedLimit >= safeLimit) {
    return {
      mediaType: cached.mediaType,
      items: cached.items,
      skippedCount: cached.skippedCount,
      count: cached.count,
    };
  }

  const key = `${mediaCacheKey(safeExecutionId, mediaKind, requestScope)}:${safeLimit}`;
  const existing = mediaInFlight.get(key);
  if (existing) return existing;

  const generationAtStart = cacheClearGeneration;
  let promise: Promise<WorkflowHistoryMediaPreviewMeta>;
  promise = fetchWorkflowPreviewMediaWithMeta(safeExecutionId, mediaKind, safeLimit)
    .then((result) => {
      if (!isWorkflowPreviewRequestCurrent(generationAtStart, requestScope)) {
        return emptyWorkflowPreviewMediaMeta(mediaKind);
      }
      writeWorkflowPreviewMediaCacheEntry(
        safeExecutionId,
        mediaKind,
        {
          items: result.items,
          requestedLimit: safeLimit,
          skippedCount: result.skippedCount,
          count: result.count,
        },
        requestScope
      );
      return result;
    })
    .finally(() => {
      if (mediaInFlight.get(key) === promise) {
        mediaInFlight.delete(key);
      }
    });
  mediaInFlight.set(key, promise);
  return promise;
};

export const __resetWorkflowPreviewCacheForTest = (): void => {
  cacheClearGeneration = 0;
  clearWorkflowPreviewMemoryCache();
};

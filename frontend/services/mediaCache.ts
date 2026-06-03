import { cacheManager } from './CacheManager';
import { requestJson } from './http';
import { isSafeStoragePreviewCandidateUrl, isStoragePreviewProxyUrl } from './storagePreviewService';
import {
  deleteMediaCacheMetadata,
  listMediaCacheMetadata,
  readMediaCacheMetadata,
  writeMediaCacheMetadata,
  type MediaCacheMetadata,
} from './mediaCacheIndexedDb';
import {
  getPrivateCacheScopeSegment,
  getPrivateCacheUserScope,
  setPrivateCacheUserScope,
} from './privateCacheScope';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from './privateCacheInvalidation';

export interface MediaCacheSource {
  id?: string | null;
  attachmentId?: string | null;
  url?: string | null;
  tempUrl?: string | null;
  temp_url?: string | null;
  cloudUrl?: string | null;
  cloud_url?: string | null;
  previewUrl?: string | null;
  mimeType?: string | null;
  mime_type?: string | null;
  name?: string | null;
  file?: Blob | null;
  uploadStatus?: string | null;
  upload_status?: string | null;
  uploadTaskId?: string | null;
  upload_task_id?: string | null;
  storageRevision?: number | string | null;
  updatedAt?: number | string | null;
  createdAt?: number | string | null;
  userScope?: string | null;
  fileUri?: string | null;
  file_uri?: string | null;
}

export interface MediaCacheIdentity {
  cacheKey: string;
  attachmentId?: string | null;
  sourceUrl: string;
  canonicalUrl: string;
  versionSignature: string;
  storageRevision?: string | null;
  userScope: string;
  persistable: boolean;
  sourceBlob?: Blob | null;
  seedUrl?: string | null;
  temporary?: boolean;
}

export type MediaCacheStatus =
  | 'idle'
  | 'memory-hit'
  | 'persistent-hit'
  | 'loading'
  | 'fresh'
  | 'fresh-memory-only'
  | 'stale'
  | 'stale-error'
  | 'raw-fallback'
  | 'error';

export interface CachedMedia {
  objectUrl: string;
  status: 'fresh' | 'fresh-memory-only' | 'persistent-hit' | 'stale' | 'not-modified';
  metadata?: MediaCacheMetadata | null;
}

export type MediaCacheDiagnosticEventType =
  | 'memory-hit'
  | 'persistent-hit'
  | 'persistent-miss'
  | 'network-fetch'
  | 'network-dedupe'
  | 'network-304'
  | 'cache-write'
  | 'cache-write-memory-only'
  | 'prune-entry'
  | 'clear-entry';

export interface MediaCacheDiagnosticEvent {
  type: MediaCacheDiagnosticEventType;
  cacheKey?: string;
  sourceUrl?: string;
  userScope?: string;
  size?: number | null;
  reason?: string;
  timestamp: number;
}

export interface MediaCacheDiagnosticsSnapshot {
  enabled: boolean;
  counters: Partial<Record<MediaCacheDiagnosticEventType, number>>;
  recentEvents: MediaCacheDiagnosticEvent[];
}

interface MemoryEntry {
  objectUrl: string;
  versionSignature: string;
  updatedAt: number;
  lastAccessedAt: number;
}

interface FetchAndStoreOptions {
  allowRevalidate?: boolean;
  replaceObjectUrl?: boolean;
}

interface SaveMediaBlobOptions {
  contentType?: string | null;
  etag?: string | null;
  lastModified?: string | null;
}

interface GetCachedOptions {
  allowStale?: boolean;
  allowMemory?: boolean;
  replaceObjectUrl?: boolean;
}

interface AttachmentCloudUrlResponse {
  url?: string | null;
  cloudUrl?: string | null;
  cloud_url?: string | null;
  uploadStatus?: string | null;
  upload_status?: string | null;
}

const MEDIA_CACHE_NAME = 'gemini-ai-media-cache-v1';
const MEDIA_CACHE_REQUEST_PREFIX = '/__gemini_media_cache__/';
const MEDIA_OBJECT_URL_PREFIX = 'mediaObjectUrl:';
const MEDIA_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const MEDIA_MAX_ENTRIES = 400;
const DEFAULT_PERSISTENT_MAX_ENTRIES = 500;
const DEFAULT_PERSISTENT_MAX_BYTES = 250 * 1024 * 1024;
const PERSISTENT_CACHE_MIN_BYTES = 50 * 1024 * 1024;
const PERSISTENT_CACHE_QUOTA_FRACTION = 0.2;
const PRUNE_INTERVAL_MS = 30_000;
const DIAGNOSTIC_EVENT_LIMIT = 200;
const RETAINED_OBJECT_URL_REVOKE_DELAY_MS = 1_500;

cacheManager.setTTL(MEDIA_OBJECT_URL_PREFIX, MEDIA_MAX_AGE_MS);

const inFlightFetches = new Map<string, Promise<CachedMedia>>();
const volatileObjectUrls = new Set<string>();
const selfOwnedObjectUrls = new Set<string>();
const retainedObjectUrls = new Map<string, number>();
const retiredObjectUrls = new Set<string>();
const failedObjectUrls = new Set<string>();
const revokedObjectUrls = new Set<string>();
const pendingRevokeObjectUrls = new Map<string, ReturnType<typeof setTimeout>>();
const scheduledFailedObjectUrls = new Set<string>();
let lastPruneAt = 0;
let cacheClearGeneration = 0;
let persistentMaxEntries = DEFAULT_PERSISTENT_MAX_ENTRIES;
let persistentMaxBytes = DEFAULT_PERSISTENT_MAX_BYTES;
let diagnosticsEnabledOverride: boolean | null = null;
let diagnosticCounters: Partial<Record<MediaCacheDiagnosticEventType, number>> = {};
// Bounded ring buffer for dev-only diagnostics. We mutate `diagnosticEventRing`
// in place (writing at `diagnosticEventHead` and advancing modulo the capacity)
// so recording never allocates a new array, and the buffer can never grow past
// DIAGNOSTIC_EVENT_LIMIT entries regardless of how many events are recorded.
const diagnosticEventRing: MediaCacheDiagnosticEvent[] = [];
let diagnosticEventHead = 0;
let diagnosticEventCount = 0;

const OBJECT_URL_RECORD_LIMIT = 1000;

const addBoundedObjectUrlRecord = (records: Set<string>, objectUrl: string): void => {
  records.delete(objectUrl);
  records.add(objectUrl);
  while (records.size > OBJECT_URL_RECORD_LIMIT) {
    const oldest = records.values().next().value;
    if (!oldest) break;
    records.delete(oldest);
  }
};

const isDevelopmentEnvironment = (): boolean => {
  try {
    return Boolean(import.meta.env?.DEV);
  } catch {
    return false;
  }
};

const isDiagnosticsEnabled = (): boolean =>
  diagnosticsEnabledOverride ?? isDevelopmentEnvironment();

const recordDiagnostic = (
  type: MediaCacheDiagnosticEventType,
  detail: Omit<MediaCacheDiagnosticEvent, 'type' | 'timestamp'> = {}
): void => {
  if (!isDiagnosticsEnabled()) return;

  diagnosticCounters = {
    ...diagnosticCounters,
    [type]: (diagnosticCounters[type] || 0) + 1,
  };

  const event: MediaCacheDiagnosticEvent = {
    type,
    ...detail,
    timestamp: Date.now(),
  };

  // Write into the ring in place; once full, overwrite the oldest slot.
  diagnosticEventRing[diagnosticEventHead] = event;
  diagnosticEventHead = (diagnosticEventHead + 1) % DIAGNOSTIC_EVENT_LIMIT;
  if (diagnosticEventCount < DIAGNOSTIC_EVENT_LIMIT) {
    diagnosticEventCount += 1;
  }
};

const readDiagnosticEventsInOrder = (): MediaCacheDiagnosticEvent[] => {
  // Materialize the ring oldest-first so consumers see chronological order.
  const ordered: MediaCacheDiagnosticEvent[] = new Array(diagnosticEventCount);
  const start =
    diagnosticEventCount < DIAGNOSTIC_EVENT_LIMIT
      ? 0
      : diagnosticEventHead;
  for (let offset = 0; offset < diagnosticEventCount; offset += 1) {
    ordered[offset] = diagnosticEventRing[(start + offset) % DIAGNOSTIC_EVENT_LIMIT];
  }
  return ordered;
};

export const getMediaCacheDiagnosticsSnapshot = (): MediaCacheDiagnosticsSnapshot => ({
  enabled: isDiagnosticsEnabled(),
  counters: { ...diagnosticCounters },
  recentEvents: readDiagnosticEventsInOrder(),
});

export const resetMediaCacheDiagnostics = (): void => {
  diagnosticCounters = {};
  diagnosticEventRing.length = 0;
  diagnosticEventHead = 0;
  diagnosticEventCount = 0;
};

const canUseCacheStorage = (): boolean =>
  typeof window !== 'undefined' && typeof window.caches !== 'undefined';

const canUseObjectUrl = (): boolean =>
  typeof window !== 'undefined' &&
  typeof URL !== 'undefined' &&
  typeof URL.createObjectURL === 'function';

const revokeVolatileObjectUrls = (): void => {
  if (!canUseObjectUrl()) {
    volatileObjectUrls.clear();
    selfOwnedObjectUrls.clear();
    return;
  }
  const objectUrls = Array.from(volatileObjectUrls);
  volatileObjectUrls.clear();
  selfOwnedObjectUrls.clear();
  objectUrls.forEach((objectUrl) => revokeTrackedObjectUrl(objectUrl));
};

const invalidatePendingMediaCacheWrites = (): void => {
  cacheClearGeneration += 1;
  inFlightFetches.clear();
  revokeVolatileObjectUrls();
};

const normalizeString = (value: unknown): string => String(value || '').trim();

const isTemporaryUrl = (url: string): boolean => {
  const lowered = url.toLowerCase();
  return lowered.startsWith('blob:') || lowered.startsWith('data:') || lowered.startsWith('local-blob:');
};

const isBlobObjectUrl = (url: string | null | undefined): boolean =>
  normalizeString(url).toLowerCase().startsWith('blob:');

const markFailedObjectUrl = (objectUrl: string | null | undefined): void => {
  const normalized = normalizeString(objectUrl);
  if (!isBlobObjectUrl(normalized)) return;
  addBoundedObjectUrlRecord(failedObjectUrls, normalized);
};

const clearPendingObjectUrlRevoke = (objectUrl: string): void => {
  const pendingTimer = pendingRevokeObjectUrls.get(objectUrl);
  if (!pendingTimer) return;
  clearTimeout(pendingTimer);
  pendingRevokeObjectUrls.delete(objectUrl);
  if (scheduledFailedObjectUrls.delete(objectUrl)) {
    failedObjectUrls.delete(objectUrl);
  }
};

const revokeObjectUrlNow = (objectUrl: string): void => {
  clearPendingObjectUrlRevoke(objectUrl);
  markFailedObjectUrl(objectUrl);
  volatileObjectUrls.delete(objectUrl);
  selfOwnedObjectUrls.delete(objectUrl);
  retiredObjectUrls.delete(objectUrl);
  retainedObjectUrls.delete(objectUrl);
  if (revokedObjectUrls.has(objectUrl)) {
    return;
  }
  addBoundedObjectUrlRecord(revokedObjectUrls, objectUrl);
  if (!canUseObjectUrl()) return;
  try {
    URL.revokeObjectURL(objectUrl);
  } catch {
    // ignore revoke errors
  }
};

const scheduleObjectUrlRevoke = (objectUrl: string): void => {
  if (revokedObjectUrls.has(objectUrl) || pendingRevokeObjectUrls.has(objectUrl)) return;
  markFailedObjectUrl(objectUrl);
  scheduledFailedObjectUrls.add(objectUrl);
  const timer = setTimeout(() => {
    pendingRevokeObjectUrls.delete(objectUrl);
    scheduledFailedObjectUrls.delete(objectUrl);
    revokeObjectUrlNow(objectUrl);
  }, RETAINED_OBJECT_URL_REVOKE_DELAY_MS);
  pendingRevokeObjectUrls.set(objectUrl, timer);
};

const revokeTrackedObjectUrl = (
  objectUrl: string,
  options: { force?: boolean; defer?: boolean } = {}
): void => {
  if (!objectUrl) return;
  const retainCount = retainedObjectUrls.get(objectUrl) || 0;
  if (!options.force && retainCount > 0) {
    retiredObjectUrls.add(objectUrl);
    return;
  }

  retiredObjectUrls.delete(objectUrl);
  retainedObjectUrls.delete(objectUrl);
  if (options.defer) {
    scheduleObjectUrlRevoke(objectUrl);
    return;
  }

  revokeObjectUrlNow(objectUrl);
};

export const retainMediaObjectUrl = (objectUrl: string | null | undefined): void => {
  if (!isBlobObjectUrl(objectUrl)) return;
  clearPendingObjectUrlRevoke(objectUrl!);
  if (revokedObjectUrls.has(objectUrl!) || failedObjectUrls.has(objectUrl!)) return;
  const current = retainedObjectUrls.get(objectUrl!) || 0;
  retainedObjectUrls.set(objectUrl!, current + 1);
};

export const releaseMediaObjectUrl = (objectUrl: string | null | undefined): void => {
  if (!isBlobObjectUrl(objectUrl)) return;
  const current = retainedObjectUrls.get(objectUrl!) || 0;
  if (current <= 1) {
    retainedObjectUrls.delete(objectUrl!);
    if (retiredObjectUrls.has(objectUrl!)) {
      revokeTrackedObjectUrl(objectUrl!, { force: true, defer: true });
    } else if (selfOwnedObjectUrls.has(objectUrl!)) {
      volatileObjectUrls.delete(objectUrl!);
      selfOwnedObjectUrls.delete(objectUrl!);
      revokeTrackedObjectUrl(objectUrl!, { force: true, defer: true });
    }
    return;
  }
  retainedObjectUrls.set(objectUrl!, current - 1);
};

const getSourceBlob = (source: MediaCacheSource): Blob | null => {
  if (typeof Blob === 'undefined') return null;
  return source.file instanceof Blob ? source.file : null;
};

const isPathRelativeUrl = (url: string): boolean => url.startsWith('/') && !url.startsWith('//');

const isSameOriginUrl = (url: string): boolean => {
  if (isPathRelativeUrl(url)) return true;
  if (typeof window === 'undefined') return false;
  try {
    return new URL(url, window.location.origin).origin === window.location.origin;
  } catch {
    return false;
  }
};

const looksLikeImageUrl = (url: string): boolean => {
  const pathname = (() => {
    try {
      return new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://local')
        .pathname;
    } catch {
      return url;
    }
  })();
  return /\.(png|jpe?g|webp|gif|avif|bmp|svg)$/i.test(pathname);
};

const isImageSource = (source: MediaCacheSource, url: string): boolean => {
  const mimeType = normalizeString(source.mimeType ?? source.mime_type).toLowerCase();
  if (mimeType) return mimeType.startsWith('image/');
  const sourceBlob = getSourceBlob(source);
  if (sourceBlob?.type) return sourceBlob.type.toLowerCase().startsWith('image/');
  return looksLikeImageUrl(url) || url.includes('/api/storage/');
};

const hashString = (value: string): string => {
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index);
  }
  return (hash >>> 0).toString(36);
};

const getMediaUserScope = (source: Pick<MediaCacheSource, 'userScope'> | null | undefined): string =>
  normalizeString(source?.userScope) || getPrivateCacheUserScope();

const getScopeCacheSegment = (userScope: string): string => getPrivateCacheScopeSegment(userScope);

const buildScopedMediaCacheKey = (
  userScope: string,
  type: 'attachment' | 'path' | 'url',
  stableId: string
): string => `media:${getScopeCacheSegment(userScope)}:${type}:${stableId}`;

export const setDefaultMediaCacheUserScope = (userScope: string | null | undefined): void => {
  setPrivateCacheUserScope(userScope);
};

export const getDefaultMediaCacheUserScope = (): string => getPrivateCacheUserScope();

const cacheMemoryKey = (cacheKey: string): string => `${MEDIA_OBJECT_URL_PREFIX}${cacheKey}`;
const cacheMemoryScopePrefix = (userScope: string): string =>
  `${MEDIA_OBJECT_URL_PREFIX}media:${getScopeCacheSegment(userScope)}:`;

const storageCacheRequest = (cacheKey: string): Request =>
  new Request(getMediaCacheStorageRequestUrl(cacheKey));

export const getMediaCacheStorageRequestUrl = (cacheKey: string): string => {
  const encoded = encodeURIComponent(cacheKey);
  if (typeof window === 'undefined') return `${MEDIA_CACHE_REQUEST_PREFIX}${encoded}`;
  return new URL(`${MEDIA_CACHE_REQUEST_PREFIX}${encoded}`, window.location.origin).toString();
};

const getSourceUrl = (source: MediaCacheSource): string => {
  const candidates = [
    normalizeString(source.previewUrl),
    normalizeString(source.cloudUrl ?? source.cloud_url),
    normalizeString(source.fileUri ?? source.file_uri),
    normalizeString(source.url),
    normalizeString(source.tempUrl ?? source.temp_url),
  ].filter(Boolean);
  return (
    candidates.find((url) => isPersistentlyCacheableUrl(url)) ||
    candidates.find((url) => !isTemporaryUrl(url)) ||
    candidates[0] ||
    ''
  );
};

const getSeedUrl = (source: MediaCacheSource, selectedSourceUrl: string): string | null => {
  const candidates = [
    normalizeString(source.url),
    normalizeString(source.tempUrl ?? source.temp_url),
  ].filter(Boolean);
  return (
    candidates.find(
      (url) => url !== selectedSourceUrl && url.toLowerCase().startsWith('data:')
    ) || null
  );
};

const getPreviewNestedUrl = (url: string): string | null => {
  if (!isStoragePreviewProxyUrl(url)) return null;
  try {
    const parsed = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://local');
    return parsed.searchParams.get('url');
  } catch {
    return null;
  }
};

const getStorageRevision = (source: MediaCacheSource, url: string): string => {
  const explicit = normalizeString(source.storageRevision);
  if (explicit) return explicit;
  try {
    const parsed = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://local');
    return normalizeString(parsed.searchParams.get('rev'));
  } catch {
    return '';
  }
};

const getCanonicalUrl = (sourceUrl: string, userScope: string): string => {
  const nestedPreviewUrl = getPreviewNestedUrl(sourceUrl);
  if (nestedPreviewUrl) {
    return `preview:${userScope}:${nestedPreviewUrl}`;
  }
  if (!isPathRelativeUrl(sourceUrl)) {
    try {
      const parsed = new URL(sourceUrl);
      return parsed.toString();
    } catch {
      return sourceUrl;
    }
  }
  return sourceUrl;
};

const getVersionSignature = (
  source: MediaCacheSource,
  sourceUrl: string,
  canonicalUrl: string
): string => {
  const storageRevision = getStorageRevision(source, sourceUrl);
  if (storageRevision) return `rev:${storageRevision}`;

  const updatedAt = normalizeString(source.updatedAt);
  if (updatedAt) return `updated:${updatedAt}`;

  const uploadTaskId = normalizeString(source.uploadTaskId);
  const uploadStatus = normalizeString(source.uploadStatus ?? source.upload_status);
  if (uploadTaskId || uploadStatus) return `upload:${uploadTaskId}:${uploadStatus}`;

  const createdAt = normalizeString(source.createdAt);
  if (createdAt) return `created:${createdAt}`;

  return `url:${canonicalUrl}`;
};

const isPersistentlyCacheableUrl = (url: string): boolean => {
  if (!url || isTemporaryUrl(url)) return false;
  if (!isSafeStoragePreviewCandidateUrl(url)) return false;
  if (!isSameOriginUrl(url)) return false;
  return isPathRelativeUrl(url) || url.includes('/api/storage/');
};

const getCacheableDurableUrl = (url: string): string | null => {
  const normalized = normalizeString(url);
  if (!normalized || isTemporaryUrl(normalized)) return null;
  if (!isSafeStoragePreviewCandidateUrl(normalized)) return null;
  if (isPersistentlyCacheableUrl(normalized)) return normalized;
  if (!isSameOriginUrl(normalized)) {
    return `/api/storage/preview?url=${encodeURIComponent(normalized)}`;
  }
  return null;
};

const getBlobVersionSignature = (source: MediaCacheSource, sourceBlob: Blob | null): string => {
  const storageRevision = normalizeString(source.storageRevision);
  if (storageRevision) return `rev:${storageRevision}`;

  const updatedAt = normalizeString(source.updatedAt);
  if (updatedAt) return `updated:${updatedAt}`;

  const uploadTaskId = normalizeString(source.uploadTaskId ?? source.upload_task_id);
  const uploadStatus = normalizeString(source.uploadStatus ?? source.upload_status);
  if (uploadTaskId || uploadStatus) return `upload:${uploadTaskId}:${uploadStatus}`;

  if (sourceBlob) {
    const file = sourceBlob as File;
    const fileName = normalizeString(file.name) || normalizeString(source.name);
    const lastModified = normalizeString(file.lastModified);
    return `blob:${fileName}:${sourceBlob.type}:${sourceBlob.size}:${lastModified}`;
  }

  const createdAt = normalizeString(source.createdAt);
  if (createdAt) return `created:${createdAt}`;

  return `temp:${hashString(getSourceUrl(source))}`;
};

export const resolveMediaCacheIdentity = (
  source: MediaCacheSource | null | undefined
): MediaCacheIdentity | null => {
  if (!source) return null;
  const sourceUrl = getSourceUrl(source);
  const sourceBlob = getSourceBlob(source);
  if (!sourceUrl && !sourceBlob) return null;
  if (!isImageSource(source, sourceUrl)) return null;

  const userScope = getMediaUserScope(source);
  const attachmentId = normalizeString(source.attachmentId) || normalizeString(source.id);

  if (sourceUrl && isPersistentlyCacheableUrl(sourceUrl)) {
    const canonicalUrl = getCanonicalUrl(sourceUrl, userScope);
    const cacheKey = canonicalUrl.startsWith('/api/storage/local-files/')
      ? buildScopedMediaCacheKey(userScope, 'path', hashString(canonicalUrl))
      : buildScopedMediaCacheKey(userScope, 'url', hashString(canonicalUrl));
    const storageRevision = getStorageRevision(source, sourceUrl) || null;
    const versionSignature = getVersionSignature(source, sourceUrl, canonicalUrl);

    return {
      cacheKey,
      attachmentId: attachmentId || null,
      sourceUrl,
      canonicalUrl,
      versionSignature,
      storageRevision,
      userScope,
      persistable: true,
      sourceBlob,
      seedUrl: getSeedUrl(source, sourceUrl),
    };
  }

  if (!attachmentId || (!sourceBlob && (!sourceUrl || !isTemporaryUrl(sourceUrl)))) {
    return null;
  }

  const temporarySourceUrl = sourceUrl || `local-blob:${attachmentId}`;
  return {
    cacheKey: buildScopedMediaCacheKey(userScope, 'attachment', attachmentId),
    attachmentId,
    sourceUrl: temporarySourceUrl,
    canonicalUrl: `temporary:${userScope}:${attachmentId}`,
    versionSignature: getBlobVersionSignature(source, sourceBlob),
    storageRevision: getStorageRevision(source, temporarySourceUrl) || null,
    userScope,
    persistable: true,
    sourceBlob,
    temporary: true,
  };
};

const deleteObjectUrlMemory = (cacheKey: string): void => {
  const key = cacheMemoryKey(cacheKey);
  const entry = cacheManager.get<MemoryEntry>(key);
  if (!entry) return;
  cacheManager.remove(key);
  revokeTrackedObjectUrl(entry.objectUrl, { defer: true });
};

export const evictCachedMediaObjectUrl = (
  identity: MediaCacheIdentity | null | undefined,
  objectUrl?: string | null
): boolean => {
  markFailedObjectUrl(objectUrl);
  if (!identity) return false;
  const key = cacheMemoryKey(identity.cacheKey);
  const entry = cacheManager.get<MemoryEntry>(key);
  if (!entry) return false;
  const failedObjectUrl = normalizeString(objectUrl);
  if (failedObjectUrl && entry.objectUrl !== failedObjectUrl) return false;

  cacheManager.remove(key);
  revokeTrackedObjectUrl(entry.objectUrl);
  recordDiagnostic('clear-entry', {
    cacheKey: identity.cacheKey,
    sourceUrl: identity.sourceUrl,
    userScope: identity.userScope,
    reason: 'object-url-error',
  });
  return true;
};

const clearObjectUrlMemoryByPrefix = (memoryPrefix: string): void => {
  const entries = cacheManager.getEntriesByPrefix<MemoryEntry>(memoryPrefix);
  entries.forEach(([key]) => {
    deleteObjectUrlMemory(key.slice(MEDIA_OBJECT_URL_PREFIX.length));
  });
};

const pruneObjectUrlMemory = (userScope: string): void => {
  if (!canUseObjectUrl()) return;
  const now = Date.now();
  const memoryPrefix = cacheMemoryScopePrefix(userScope);
  const entries = cacheManager.getEntriesByPrefix<MemoryEntry>(memoryPrefix);

  entries.forEach(([key, entry]) => {
    if (!Number.isFinite(entry.lastAccessedAt) || now - entry.lastAccessedAt > MEDIA_MAX_AGE_MS) {
      deleteObjectUrlMemory(key.slice(MEDIA_OBJECT_URL_PREFIX.length));
    }
  });

  const remaining = cacheManager.getEntriesByPrefix<MemoryEntry>(memoryPrefix);
  if (remaining.length <= MEDIA_MAX_ENTRIES) return;

  remaining
    .sort((left, right) => left[1].lastAccessedAt - right[1].lastAccessedAt)
    .slice(0, remaining.length - MEDIA_MAX_ENTRIES)
    .forEach(([key]) => deleteObjectUrlMemory(key.slice(MEDIA_OBJECT_URL_PREFIX.length)));
};

export const getCachedMediaObjectUrlSync = (
  identity: MediaCacheIdentity | null | undefined,
  options: GetCachedOptions = {}
): string | null => {
  if (!identity || !canUseObjectUrl()) return null;
  if (!isMediaIdentityCurrentScope(identity)) return null;
  const now = Date.now();
  if (now - lastPruneAt > PRUNE_INTERVAL_MS) {
    lastPruneAt = now;
    pruneObjectUrlMemory(identity.userScope);
  }

  const entry = cacheManager.get<MemoryEntry>(cacheMemoryKey(identity.cacheKey));
  if (!entry) return null;
  if (failedObjectUrls.has(entry.objectUrl)) {
    cacheManager.remove(cacheMemoryKey(identity.cacheKey));
    if (!pendingRevokeObjectUrls.has(entry.objectUrl)) {
      revokeTrackedObjectUrl(entry.objectUrl);
    }
    recordDiagnostic('clear-entry', {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      userScope: identity.userScope,
      reason: 'failed-object-url',
    });
    return null;
  }
  if (!options.allowStale && entry.versionSignature !== identity.versionSignature) return null;

  entry.lastAccessedAt = now;
  cacheManager.set(cacheMemoryKey(identity.cacheKey), entry);
  recordDiagnostic('memory-hit', {
    cacheKey: identity.cacheKey,
    sourceUrl: identity.sourceUrl,
    userScope: identity.userScope,
  });
  return entry.objectUrl;
};

const cacheObjectUrl = (
  identity: MediaCacheIdentity,
  blob: Blob,
  versionSignature = identity.versionSignature,
  options: { replace?: boolean } = {}
): string | null => {
  if (!canUseObjectUrl()) return null;

  const existing = getCachedMediaObjectUrlSync(identity, { allowStale: true });
  const existingEntry = cacheManager.get<MemoryEntry>(cacheMemoryKey(identity.cacheKey));
  if (existing && existingEntry?.versionSignature === versionSignature && !options.replace) {
    return existing;
  }
  if (existing) {
    deleteObjectUrlMemory(identity.cacheKey);
  }

  const objectUrl = URL.createObjectURL(blob);
  failedObjectUrls.delete(objectUrl);
  revokedObjectUrls.delete(objectUrl);
  cacheManager.set(cacheMemoryKey(identity.cacheKey), {
    objectUrl,
    versionSignature,
    updatedAt: Date.now(),
    lastAccessedAt: Date.now(),
  } satisfies MemoryEntry);
  pruneObjectUrlMemory(identity.userScope);
  return objectUrl;
};

const createVolatileObjectUrl = (
  blob: Blob,
  options: { selfOwned?: boolean } = {}
): string | null => {
  if (!canUseObjectUrl()) return null;
  const objectUrl = URL.createObjectURL(blob);
  failedObjectUrls.delete(objectUrl);
  revokedObjectUrls.delete(objectUrl);
  volatileObjectUrls.add(objectUrl);
  if (options.selfOwned) {
    selfOwnedObjectUrls.add(objectUrl);
  }
  return objectUrl;
};

export const createManagedMediaObjectUrl = (blob: Blob): string | null =>
  createVolatileObjectUrl(blob);

export const revokeManagedMediaObjectUrl = (objectUrl: string | null | undefined): void => {
  if (!isBlobObjectUrl(objectUrl)) return;
  volatileObjectUrls.delete(objectUrl!);
  selfOwnedObjectUrls.delete(objectUrl!);
  revokeTrackedObjectUrl(objectUrl!);
};

const createUncachedMediaResult = (
  identity: MediaCacheIdentity,
  blob: Blob,
  reason: string
): CachedMedia => {
  recordDiagnostic('cache-write-memory-only', {
    cacheKey: identity.cacheKey,
    sourceUrl: identity.sourceUrl,
    userScope: identity.userScope,
    size: blob.size,
    reason,
  });

  return {
    objectUrl: createVolatileObjectUrl(blob, { selfOwned: true }) || identity.sourceUrl,
    status: 'fresh-memory-only',
    metadata: null,
  };
};

const isMediaIdentityCurrentScope = (identity: MediaCacheIdentity): boolean =>
  normalizeString(identity.userScope) === getPrivateCacheUserScope();

const isMediaIdentityLifecycleCurrent = (
  identity: MediaCacheIdentity,
  generationAtStart: number,
  lifecycleSnapshot: ReturnType<typeof capturePrivateCacheLifecycleSnapshot>
): boolean =>
  generationAtStart === cacheClearGeneration &&
  isMediaIdentityCurrentScope(identity) &&
  isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot);

const isMediaIdentityPrivateLifecycleCurrent = (
  identity: MediaCacheIdentity,
  lifecycleSnapshot: ReturnType<typeof capturePrivateCacheLifecycleSnapshot>
): boolean =>
  isMediaIdentityCurrentScope(identity) &&
  isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot);

const createPrivateLifecycleChangedError = (operation: string): Error =>
  new Error(`Media cache private lifecycle changed during ${operation}`);

const openMediaCache = async (): Promise<Cache | null> => {
  if (!canUseCacheStorage()) return null;
  try {
    return await window.caches.open(MEDIA_CACHE_NAME);
  } catch {
    return null;
  }
};

const deleteMediaCacheStorage = async (): Promise<void> => {
  if (!canUseCacheStorage()) return;
  try {
    await window.caches.delete(MEDIA_CACHE_NAME);
  } catch {
    // ignore cache deletion errors
  }
};

const deletePersistentMediaEntry = async (cacheKey: string): Promise<void> => {
  deleteObjectUrlMemory(cacheKey);
  const cache = await openMediaCache();
  await cache?.delete(storageCacheRequest(cacheKey));
  await deleteMediaCacheMetadata(cacheKey);
};

const createCacheBlobResponse = async (
  blob: Blob,
  contentType: string
): Promise<Response> => {
  const headers = { 'Content-Type': contentType };
  try {
    return new Response(blob, {
      status: 200,
      headers,
    });
  } catch {
    return new Response(await blob.arrayBuffer(), {
      status: 200,
      headers,
    });
  }
};

const getPersistentByteLimit = async (): Promise<number> => {
  if (typeof navigator === 'undefined' || !navigator.storage?.estimate) {
    return persistentMaxBytes;
  }

  try {
    const estimate = await navigator.storage.estimate();
    const quota = Number(estimate.quota || 0);
    if (!Number.isFinite(quota) || quota <= 0) return persistentMaxBytes;
    return Math.max(
      PERSISTENT_CACHE_MIN_BYTES,
      Math.min(persistentMaxBytes, Math.floor(quota * PERSISTENT_CACHE_QUOTA_FRACTION))
    );
  } catch {
    return persistentMaxBytes;
  }
};

const prunePersistentMediaCache = async (
  cache: Cache,
  reservedCacheKey?: string
): Promise<void> => {
  const entries = await listMediaCacheMetadata();
  if (entries.length === 0) return;

  const byteLimit = await getPersistentByteLimit();
  let totalBytes = entries.reduce((sum, entry) => {
    const size = Number(entry.size || 0);
    return sum + (Number.isFinite(size) && size > 0 ? size : 0);
  }, 0);
  let totalEntries = entries.length;

  if (totalEntries <= persistentMaxEntries && totalBytes <= byteLimit) return;

  const candidates = [...entries]
    .filter((entry) => entry.cacheKey !== reservedCacheKey)
    .sort((left, right) => left.lastAccessedAt - right.lastAccessedAt);

  for (const entry of candidates) {
    if (totalEntries <= persistentMaxEntries && totalBytes <= byteLimit) break;
    deleteObjectUrlMemory(entry.cacheKey);
    await cache.delete(storageCacheRequest(entry.cacheKey));
    await deleteMediaCacheMetadata(entry.cacheKey);
    recordDiagnostic('prune-entry', {
      cacheKey: entry.cacheKey,
      sourceUrl: entry.sourceUrl,
      userScope: entry.userScope,
      size: entry.size,
      reason: 'persistent-limit',
    });
    totalEntries -= 1;
    const size = Number(entry.size || 0);
    if (Number.isFinite(size) && size > 0) {
      totalBytes = Math.max(0, totalBytes - size);
    }
  }
};

export const getCachedMediaObjectUrl = async (
  identity: MediaCacheIdentity,
  options: GetCachedOptions = {}
): Promise<string | null> => {
  const generationAtStart = cacheClearGeneration;
  const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
  const isCurrentLifecycle = () =>
    isMediaIdentityLifecycleCurrent(identity, generationAtStart, lifecycleSnapshot);
  if (!isCurrentLifecycle()) return null;

  const memoryHit =
    options.allowMemory === false ? null : getCachedMediaObjectUrlSync(identity, options);
  if (memoryHit) return memoryHit;

  const metadata = await readMediaCacheMetadata(identity.cacheKey);
  if (!isCurrentLifecycle()) return null;
  if (!metadata) {
    recordDiagnostic('persistent-miss', {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      userScope: identity.userScope,
      reason: 'metadata-miss',
    });
    return null;
  }
  if (normalizeString(metadata.userScope) !== identity.userScope) {
    const cache = await openMediaCache();
    deleteObjectUrlMemory(identity.cacheKey);
    await cache?.delete(storageCacheRequest(identity.cacheKey));
    await deleteMediaCacheMetadata(identity.cacheKey);
    recordDiagnostic('persistent-miss', {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      userScope: identity.userScope,
      reason: 'user-scope-mismatch',
    });
    return null;
  }
  if (!options.allowStale && metadata.versionSignature !== identity.versionSignature) {
    recordDiagnostic('persistent-miss', {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      userScope: identity.userScope,
      reason: 'version-mismatch',
    });
    return null;
  }

  const cache = await openMediaCache();
  if (!isCurrentLifecycle()) return null;
  if (!cache) {
    recordDiagnostic('persistent-miss', {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      userScope: identity.userScope,
      reason: 'cache-storage-unavailable',
    });
    return null;
  }
  const response = await cache.match(storageCacheRequest(identity.cacheKey));
  if (!isCurrentLifecycle()) return null;
  if (!response) {
    await deleteMediaCacheMetadata(identity.cacheKey);
    recordDiagnostic('persistent-miss', {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      userScope: identity.userScope,
      reason: 'blob-miss',
    });
    return null;
  }

  const blob = await response.blob();
  if (!isCurrentLifecycle()) return null;
  const objectUrl = cacheObjectUrl(identity, blob, metadata.versionSignature, {
    replace: options.replaceObjectUrl,
  });
  if (!objectUrl) return null;
  if (!isCurrentLifecycle()) {
    deleteObjectUrlMemory(identity.cacheKey);
    return null;
  }

  await writeMediaCacheMetadata({
    ...metadata,
    lastAccessedAt: Date.now(),
  });
  if (!isCurrentLifecycle()) {
    deleteObjectUrlMemory(identity.cacheKey);
    if (generationAtStart !== cacheClearGeneration) {
      await deletePersistentMediaEntry(identity.cacheKey);
    }
    return null;
  }
  recordDiagnostic('persistent-hit', {
    cacheKey: identity.cacheKey,
    sourceUrl: identity.sourceUrl,
    userScope: identity.userScope,
    size: metadata.size,
  });
  return objectUrl;
};

const persistCachedMedia = async (
  identity: MediaCacheIdentity,
  blob: Blob,
  response: Response
): Promise<MediaCacheMetadata | null> => {
  const cache = await openMediaCache();
  if (!cache) return null;

  const now = Date.now();
  const metadata: MediaCacheMetadata = {
    cacheKey: identity.cacheKey,
    sourceUrl: identity.sourceUrl,
    canonicalUrl: identity.canonicalUrl,
    versionSignature: identity.versionSignature,
    etag: response.headers.get('etag'),
    lastModified: response.headers.get('last-modified'),
    storageRevision: identity.storageRevision || null,
    contentType: response.headers.get('content-type') || blob.type || null,
    size: blob.size,
    cachedAt: now,
    lastAccessedAt: now,
    userScope: identity.userScope,
  };

  await cache.put(
    storageCacheRequest(identity.cacheKey),
    await createCacheBlobResponse(blob, metadata.contentType || 'application/octet-stream')
  );
  await writeMediaCacheMetadata(metadata);
  await prunePersistentMediaCache(cache, identity.cacheKey);
  recordDiagnostic('cache-write', {
    cacheKey: identity.cacheKey,
    sourceUrl: identity.sourceUrl,
    userScope: identity.userScope,
    size: blob.size,
  });
  return metadata;
};

const decodeDataUrlToBlob = (dataUrl: string): Blob | null => {
  const match = dataUrl.match(/^data:([^;,]+)?((?:;[^,]*)?),(.*)$/i);
  if (!match) return null;

  const contentType = match[1] || 'application/octet-stream';
  const metadata = match[2] || '';
  const payload = match[3] || '';
  try {
    if (metadata.toLowerCase().includes(';base64')) {
      const binary = atob(payload);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      return new Blob([bytes], { type: contentType });
    }
    return new Blob([decodeURIComponent(payload)], { type: contentType });
  } catch {
    return null;
  }
};

const readSeedMediaBlob = async (
  identity: MediaCacheIdentity
): Promise<{ blob: Blob; response: Response } | null> => {
  if (identity.sourceBlob) {
    const contentType = identity.sourceBlob.type || 'application/octet-stream';
    return {
      blob: identity.sourceBlob,
      response: new Response(null, {
        status: 200,
        headers: { 'Content-Type': contentType },
      }),
    };
  }

  const seedUrl = normalizeString(identity.seedUrl);
  if (!seedUrl || !isTemporaryUrl(seedUrl)) return null;

  if (seedUrl.toLowerCase().startsWith('data:')) {
    const blob = decodeDataUrlToBlob(seedUrl);
    if (!blob) return null;
    return {
      blob,
      response: new Response(null, {
        status: 200,
        headers: { 'Content-Type': blob.type || 'application/octet-stream' },
      }),
    };
  }

  return null;
};

const fetchAttachmentDurableUrl = async (
  identity: MediaCacheIdentity
): Promise<string | null> => {
  const attachmentId = normalizeString(identity.attachmentId);
  if (!identity.temporary || !attachmentId || identity.sourceBlob) return null;

  try {
    const payload = await requestJson<AttachmentCloudUrlResponse>(
      `/api/attachments/${encodeURIComponent(attachmentId)}/cloud-url`,
      {
        method: 'GET',
        withAuth: true,
        timeoutMs: 10000,
        errorMessage: '附件状态查询失败',
      }
    );
    const rawUrl =
      normalizeString(payload.url) ||
      normalizeString(payload.cloudUrl) ||
      normalizeString(payload.cloud_url);
    return getCacheableDurableUrl(rawUrl);
  } catch {
    return null;
  }
};

const resolveDownloadIdentity = async (
  identity: MediaCacheIdentity
): Promise<MediaCacheIdentity> => {
  const durableUrl = await fetchAttachmentDurableUrl(identity);
  if (!durableUrl) return identity;

  const source: MediaCacheSource = {
    attachmentId: identity.attachmentId,
    url: durableUrl,
    userScope: identity.userScope,
    storageRevision: identity.storageRevision,
  };
  return resolveMediaCacheIdentity(source) || identity;
};

const fetchMediaBlob = async (
  identity: MediaCacheIdentity,
  metadata: MediaCacheMetadata | null,
  options: FetchAndStoreOptions
): Promise<{ blob: Blob | null; response: Response; notModified: boolean }> => {
  const seedMedia = await readSeedMediaBlob(identity);
  if (seedMedia) {
    return {
      blob: seedMedia.blob,
      response: seedMedia.response,
      notModified: false,
    };
  }

  if (identity.temporary && isBlobObjectUrl(identity.sourceUrl)) {
    throw new Error('Temporary blob media source is no longer available');
  }

  const headers = new Headers();
  if (!identity.temporary && options.allowRevalidate !== false) {
    if (metadata?.etag) headers.set('If-None-Match', metadata.etag);
    if (metadata?.lastModified) headers.set('If-Modified-Since', metadata.lastModified);
  }

  recordDiagnostic('network-fetch', {
    cacheKey: identity.cacheKey,
    sourceUrl: identity.sourceUrl,
    userScope: identity.userScope,
  });
  const response = await fetch(
    identity.sourceUrl,
    identity.temporary
      ? { method: 'GET' }
      : {
          method: 'GET',
          credentials: isSameOriginUrl(identity.sourceUrl) ? 'include' : 'same-origin',
          headers,
        }
  );

  if (response.status === 304) {
    return { blob: null, response, notModified: true };
  }
  if (!response.ok) {
    throw new Error(`Media cache fetch failed: HTTP ${response.status}`);
  }
  return { blob: await response.blob(), response, notModified: false };
};

export const fetchAndStoreMedia = async (
  identity: MediaCacheIdentity,
  options: FetchAndStoreOptions = {}
): Promise<CachedMedia> => {
  const inFlightKey = `${identity.cacheKey}:${identity.versionSignature}`;
  const existing = inFlightFetches.get(inFlightKey);
  if (existing) {
    recordDiagnostic('network-dedupe', {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      userScope: identity.userScope,
    });
    return existing;
  }

  const generationAtStart = cacheClearGeneration;
  const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
  const isPrivateLifecycleCurrent = (currentIdentity = identity) =>
    isMediaIdentityPrivateLifecycleCurrent(currentIdentity, lifecycleSnapshot);
  const isPersistentLifecycleCurrent = (currentIdentity = identity) =>
    isMediaIdentityLifecycleCurrent(currentIdentity, generationAtStart, lifecycleSnapshot);
  let promise: Promise<CachedMedia>;
  promise = (async (): Promise<CachedMedia> => {
    const downloadIdentity = await resolveDownloadIdentity(identity);
    if (!isPrivateLifecycleCurrent(downloadIdentity)) {
      throw createPrivateLifecycleChangedError('media fetch');
    }

    if (downloadIdentity.cacheKey !== identity.cacheKey) {
      const cachedObjectUrl = await getCachedMediaObjectUrl(downloadIdentity, {
        allowStale: false,
      });
      if (cachedObjectUrl) {
        return {
          objectUrl: cachedObjectUrl,
          status: 'persistent-hit',
          metadata: await readMediaCacheMetadata(downloadIdentity.cacheKey),
        };
      }
    }

    const previousMetadata = await readMediaCacheMetadata(downloadIdentity.cacheKey);
    const { blob, response, notModified } = await fetchMediaBlob(
      downloadIdentity,
      previousMetadata,
      options
    );

    if (notModified) {
      const objectUrl = await getCachedMediaObjectUrl(
        downloadIdentity,
        options.replaceObjectUrl
          ? { allowMemory: false, allowStale: true, replaceObjectUrl: true }
          : { allowStale: true }
      );
      if (!objectUrl) {
        throw new Error('Media cache returned 304 without a cached Blob');
      }
      if (!isPrivateLifecycleCurrent(downloadIdentity)) {
        await deletePersistentMediaEntry(downloadIdentity.cacheKey);
        throw createPrivateLifecycleChangedError('304 revalidation');
      }
      if (!isPersistentLifecycleCurrent(downloadIdentity)) {
        await deletePersistentMediaEntry(downloadIdentity.cacheKey);
        throw new Error('Media cache lifecycle changed during 304 revalidation');
      }
      if (previousMetadata) {
        await writeMediaCacheMetadata({
          ...previousMetadata,
          versionSignature: downloadIdentity.versionSignature,
          lastAccessedAt: Date.now(),
        });
        if (!isPrivateLifecycleCurrent(downloadIdentity)) {
          await deletePersistentMediaEntry(downloadIdentity.cacheKey);
          throw createPrivateLifecycleChangedError('304 metadata update');
        }
        if (!isPersistentLifecycleCurrent(downloadIdentity)) {
          await deletePersistentMediaEntry(downloadIdentity.cacheKey);
          throw new Error('Media cache lifecycle changed during 304 metadata update');
        }
      }
      recordDiagnostic('network-304', {
        cacheKey: downloadIdentity.cacheKey,
        sourceUrl: downloadIdentity.sourceUrl,
        userScope: downloadIdentity.userScope,
        size: previousMetadata?.size,
      });
      return { objectUrl, status: 'not-modified', metadata: previousMetadata };
    }

    if (!blob) {
      throw new Error('Media cache fetch returned no Blob');
    }

    let metadata: MediaCacheMetadata | null = null;
    if (isPersistentLifecycleCurrent(downloadIdentity)) {
      try {
        metadata = await persistCachedMedia(downloadIdentity, blob, response);
      } catch {
        metadata = null;
      }
    }
    if (!isPrivateLifecycleCurrent(downloadIdentity)) {
      if (metadata) {
        await deletePersistentMediaEntry(downloadIdentity.cacheKey);
      }
      throw createPrivateLifecycleChangedError('media fetch');
    }
    if (!isPersistentLifecycleCurrent(downloadIdentity)) {
      if (metadata) {
        await deletePersistentMediaEntry(downloadIdentity.cacheKey);
      }
      return createUncachedMediaResult(
        downloadIdentity,
        blob,
        'cache-generation-changed-during-fetch'
      );
    }
    if (!metadata) {
      recordDiagnostic('cache-write-memory-only', {
        cacheKey: downloadIdentity.cacheKey,
        sourceUrl: downloadIdentity.sourceUrl,
        userScope: downloadIdentity.userScope,
        size: blob.size,
      });
    }
    const objectUrl = cacheObjectUrl(downloadIdentity, blob, downloadIdentity.versionSignature, {
      replace: options.replaceObjectUrl,
    });
    if (!objectUrl) {
      return {
        objectUrl: downloadIdentity.sourceUrl,
        status: metadata ? 'fresh' : 'fresh-memory-only',
        metadata,
      };
    }

    return {
      objectUrl,
      status: metadata ? 'fresh' : 'fresh-memory-only',
      metadata,
    };
  })().finally(() => {
    if (inFlightFetches.get(inFlightKey) === promise) {
      inFlightFetches.delete(inFlightKey);
    }
  });

  inFlightFetches.set(inFlightKey, promise);
  return promise;
};

export const saveMediaBlobToCache = async (
  identity: MediaCacheIdentity,
  blob: Blob,
  options: SaveMediaBlobOptions = {}
): Promise<CachedMedia> => {
  const headers = new Headers();
  headers.set('Content-Type', options.contentType || blob.type || 'application/octet-stream');
  if (options.etag) headers.set('ETag', options.etag);
  if (options.lastModified) headers.set('Last-Modified', options.lastModified);

  const response = new Response(null, {
    status: 200,
    headers,
  });
  const generationAtStart = cacheClearGeneration;
  const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
  const isPrivateLifecycleCurrent = () =>
    isMediaIdentityPrivateLifecycleCurrent(identity, lifecycleSnapshot);
  const isPersistentLifecycleCurrent = () =>
    isMediaIdentityLifecycleCurrent(identity, generationAtStart, lifecycleSnapshot);
  if (!isPrivateLifecycleCurrent()) {
    throw createPrivateLifecycleChangedError('media save');
  }
  let metadata: MediaCacheMetadata | null = null;
  if (isPersistentLifecycleCurrent()) {
    try {
      metadata = await persistCachedMedia(identity, blob, response);
    } catch {
      metadata = null;
    }
  }
  if (!isPrivateLifecycleCurrent()) {
    if (metadata) {
      await deletePersistentMediaEntry(identity.cacheKey);
    }
    throw createPrivateLifecycleChangedError('media save');
  }
  if (!isPersistentLifecycleCurrent()) {
    if (metadata) {
      await deletePersistentMediaEntry(identity.cacheKey);
    }
    return createUncachedMediaResult(identity, blob, 'cache-generation-changed-during-save');
  }
  if (!metadata) {
    recordDiagnostic('cache-write-memory-only', {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      userScope: identity.userScope,
      size: blob.size,
    });
  }
  const objectUrl = cacheObjectUrl(identity, blob);

  return {
    objectUrl: objectUrl || identity.sourceUrl,
    status: metadata ? 'fresh' : 'fresh-memory-only',
    metadata,
  };
};

export const clearUserMediaCache = async (userScope: string): Promise<void> => {
  const scope = normalizeString(userScope);
  if (!scope) return;
  invalidatePendingMediaCacheWrites();
  clearObjectUrlMemoryByPrefix(cacheMemoryScopePrefix(scope));
  const cache = await openMediaCache();
  const metadata = await listMediaCacheMetadata();
  const scopedEntries = metadata.filter((entry) => entry.userScope === scope);
  await Promise.all(
    scopedEntries.map(async (entry) => {
      deleteObjectUrlMemory(entry.cacheKey);
      await cache?.delete(storageCacheRequest(entry.cacheKey));
      await deleteMediaCacheMetadata(entry.cacheKey);
      recordDiagnostic('clear-entry', {
        cacheKey: entry.cacheKey,
        sourceUrl: entry.sourceUrl,
        userScope: entry.userScope,
        size: entry.size,
        reason: 'user-scope',
      });
    })
  );
};

export const clearAllMediaCache = async (): Promise<void> => {
  invalidatePendingMediaCacheWrites();
  const metadata = await listMediaCacheMetadata();
  clearObjectUrlMemoryByPrefix(MEDIA_OBJECT_URL_PREFIX);
  await deleteMediaCacheStorage();
  await Promise.all(
    metadata.map(async (entry) => {
      await deleteMediaCacheMetadata(entry.cacheKey);
      recordDiagnostic('clear-entry', {
        cacheKey: entry.cacheKey,
        sourceUrl: entry.sourceUrl,
        userScope: entry.userScope,
        size: entry.size,
        reason: 'all',
      });
    })
  );
};

export const clearMediaCacheForLogout = async (): Promise<void> => {
  await clearAllMediaCache();
};

export const requestMediaCachePersistence = async (): Promise<boolean> => {
  if (typeof navigator === 'undefined' || !navigator.storage?.persist) return false;
  try {
    if (await navigator.storage.persisted?.()) return true;
    return await navigator.storage.persist();
  } catch {
    return false;
  }
};

export const __resetMediaCacheForTest = (): void => {
  inFlightFetches.clear();
  volatileObjectUrls.clear();
  selfOwnedObjectUrls.clear();
  retainedObjectUrls.clear();
  retiredObjectUrls.clear();
  failedObjectUrls.clear();
  revokedObjectUrls.clear();
  pendingRevokeObjectUrls.forEach((timer) => clearTimeout(timer));
  pendingRevokeObjectUrls.clear();
  scheduledFailedObjectUrls.clear();
  cacheManager.clearDomain(MEDIA_OBJECT_URL_PREFIX);
  lastPruneAt = 0;
  cacheClearGeneration = 0;
  persistentMaxEntries = DEFAULT_PERSISTENT_MAX_ENTRIES;
  persistentMaxBytes = DEFAULT_PERSISTENT_MAX_BYTES;
  setPrivateCacheUserScope(null);
  resetMediaCacheDiagnostics();
};

export const __setMediaCacheLimitsForTest = (limits: {
  maxEntries?: number;
  maxBytes?: number;
}): void => {
  if (Number.isFinite(limits.maxEntries)) {
    persistentMaxEntries = Math.max(1, Number(limits.maxEntries));
  }
  if (Number.isFinite(limits.maxBytes)) {
    persistentMaxBytes = Math.max(1, Number(limits.maxBytes));
  }
};

export const __setMediaCacheDiagnosticsEnabledForTest = (enabled: boolean | null): void => {
  diagnosticsEnabledOverride = enabled;
};

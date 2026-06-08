import { cacheManager } from './CacheManager';
import { requestJson } from './http';
import {
  deleteMediaCacheMetadata,
  listMediaCacheMetadata,
  readMediaCacheMetadata,
  writeMediaCacheMetadata,
  type MediaCacheMetadata,
} from './mediaCacheIndexedDb';
import { getPrivateCacheUserScope, setPrivateCacheUserScope } from './privateCacheScope';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from './privateCacheInvalidation';
import {
  type AttachmentCloudUrlResponse,
  type CachedMedia,
  type FetchAndStoreOptions,
  type GetCachedOptions,
  type MediaCacheIdentity,
  type MediaCacheSource,
  type MemoryEntry,
  type SaveMediaBlobOptions,
} from './mediaCacheTypes';
import {
  canUseObjectUrl,
  clearFailedObjectUrl,
  clearRevokedObjectUrl,
  createVolatileObjectUrl,
  hasPendingObjectUrlRevoke,
  isBlobObjectUrl,
  isFailedObjectUrl,
  markFailedObjectUrl,
  normalizeString,
  revokeTrackedObjectUrl,
  revokeVolatileObjectUrls,
  __resetObjectUrlRegistriesForTest,
} from './mediaCacheObjectUrls';
import {
  getCacheableDurableUrl,
  getScopeCacheSegment,
  isSameOriginUrl,
  resolveMediaCacheIdentity,
} from './mediaCacheIdentity';
import {
  deletePersistentMediaEntry,
  getMediaCacheStorageRequestUrl,
  openMediaCache,
  persistCachedMedia,
  readSeedMediaBlob,
  resetMediaCacheLimits,
  setMediaCacheLimits,
  setMediaCacheMemoryEvictionHook,
  storageCacheRequest,
  deleteMediaCacheStorage,
} from './mediaCachePersistence';
import { recordDiagnostic, resetMediaCacheDiagnostics } from './mediaCacheDiagnostics';

export { resolveMediaCacheIdentity } from './mediaCacheIdentity';
export { getMediaCacheStorageRequestUrl } from './mediaCachePersistence';
export {
  createManagedMediaObjectUrl,
  releaseMediaObjectUrl,
  retainMediaObjectUrl,
  revokeManagedMediaObjectUrl,
} from './mediaCacheObjectUrls';
export {
  getMediaCacheDiagnosticsSnapshot,
  resetMediaCacheDiagnostics,
  __getMediaCacheDiagnosticCountersRefForTest,
  __setMediaCacheDiagnosticsEnabledForTest,
} from './mediaCacheDiagnostics';
export type {
  CachedMedia,
  MediaCacheDiagnosticEvent,
  MediaCacheDiagnosticEventType,
  MediaCacheDiagnosticsSnapshot,
  MediaCacheIdentity,
  MediaCacheSource,
  MediaCacheStatus,
} from './mediaCacheTypes';

const MEDIA_OBJECT_URL_PREFIX = 'mediaObjectUrl:';
const MEDIA_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const MEDIA_MAX_ENTRIES = 400;
const PRUNE_INTERVAL_MS = 30_000;

cacheManager.setTTL(MEDIA_OBJECT_URL_PREFIX, MEDIA_MAX_AGE_MS);

const inFlightFetches = new Map<string, Promise<CachedMedia>>();
let lastPruneAt = 0;
let cacheClearGeneration = 0;

const invalidatePendingMediaCacheWrites = (): void => {
  cacheClearGeneration += 1;
  inFlightFetches.clear();
  revokeVolatileObjectUrls();
};

export const setDefaultMediaCacheUserScope = (userScope: string | null | undefined): void => {
  setPrivateCacheUserScope(userScope);
};

export const getDefaultMediaCacheUserScope = (): string => getPrivateCacheUserScope();

const cacheMemoryKey = (cacheKey: string): string => `${MEDIA_OBJECT_URL_PREFIX}${cacheKey}`;
const cacheMemoryScopePrefix = (userScope: string): string =>
  `${MEDIA_OBJECT_URL_PREFIX}media:${getScopeCacheSegment(userScope)}:`;

// Diagnostics consistently key off the same identity triple; build it once so the
// repeated `{ cacheKey, sourceUrl, userScope }` literal does not drift across sites.
const diagnosticIdentity = (
  source: Pick<MediaCacheIdentity, 'cacheKey' | 'sourceUrl' | 'userScope'>
): Pick<MediaCacheIdentity, 'cacheKey' | 'sourceUrl' | 'userScope'> => ({
  cacheKey: source.cacheKey,
  sourceUrl: source.sourceUrl,
  userScope: source.userScope,
});

const deleteObjectUrlMemory = (cacheKey: string): void => {
  const key = cacheMemoryKey(cacheKey);
  const entry = cacheManager.get<MemoryEntry>(key);
  if (!entry) return;
  cacheManager.remove(key);
  revokeTrackedObjectUrl(entry.objectUrl, { defer: true });
};

// The persistence layer evicts the matching in-memory object URL whenever it
// removes a persisted blob; wire that callback to this module's memory map.
setMediaCacheMemoryEvictionHook(deleteObjectUrlMemory);

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
    ...diagnosticIdentity(identity),
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
  if (isFailedObjectUrl(entry.objectUrl)) {
    cacheManager.remove(cacheMemoryKey(identity.cacheKey));
    if (!hasPendingObjectUrlRevoke(entry.objectUrl)) {
      revokeTrackedObjectUrl(entry.objectUrl);
    }
    recordDiagnostic('clear-entry', {
      ...diagnosticIdentity(identity),
      reason: 'failed-object-url',
    });
    return null;
  }
  if (!options.allowStale && entry.versionSignature !== identity.versionSignature) return null;

  entry.lastAccessedAt = now;
  cacheManager.set(cacheMemoryKey(identity.cacheKey), entry);
  recordDiagnostic('memory-hit', diagnosticIdentity(identity));
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
  clearFailedObjectUrl(objectUrl);
  clearRevokedObjectUrl(objectUrl);
  cacheManager.set(cacheMemoryKey(identity.cacheKey), {
    objectUrl,
    versionSignature,
    updatedAt: Date.now(),
    lastAccessedAt: Date.now(),
  } satisfies MemoryEntry);
  pruneObjectUrlMemory(identity.userScope);
  return objectUrl;
};

const createUncachedMediaResult = (
  identity: MediaCacheIdentity,
  blob: Blob,
  reason: string
): CachedMedia => {
  recordDiagnostic('cache-write-memory-only', {
    ...diagnosticIdentity(identity),
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
      ...diagnosticIdentity(identity),
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
      ...diagnosticIdentity(identity),
      reason: 'user-scope-mismatch',
    });
    return null;
  }
  if (!options.allowStale && metadata.versionSignature !== identity.versionSignature) {
    recordDiagnostic('persistent-miss', {
      ...diagnosticIdentity(identity),
      reason: 'version-mismatch',
    });
    return null;
  }

  const cache = await openMediaCache();
  if (!isCurrentLifecycle()) return null;
  if (!cache) {
    recordDiagnostic('persistent-miss', {
      ...diagnosticIdentity(identity),
      reason: 'cache-storage-unavailable',
    });
    return null;
  }
  const response = await cache.match(storageCacheRequest(identity.cacheKey));
  if (!isCurrentLifecycle()) return null;
  if (!response) {
    await deleteMediaCacheMetadata(identity.cacheKey);
    recordDiagnostic('persistent-miss', {
      ...diagnosticIdentity(identity),
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
    ...diagnosticIdentity(identity),
    size: metadata.size,
  });
  return objectUrl;
};

const fetchAttachmentDurableUrl = async (identity: MediaCacheIdentity): Promise<string | null> => {
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
    // The /cloud-url endpoint returns { url, uploadStatus } (middleware-camelCased);
    // there is no cloud_url field — the frontend must not read snake_case.
    const rawUrl = normalizeString(payload.url) || normalizeString(payload.cloudUrl);
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

  recordDiagnostic('network-fetch', diagnosticIdentity(identity));
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
    recordDiagnostic('network-dedupe', diagnosticIdentity(identity));
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
        ...diagnosticIdentity(downloadIdentity),
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
        // persistCachedMedia writes the Cache API blob (cache.put) before later steps
        // (writeMetadata/prune) that can throw — leaving the blob orphaned with no
        // metadata. Best-effort clear so it isn't stranded (logout sweep is the backstop).
        try {
          await deletePersistentMediaEntry(downloadIdentity.cacheKey);
        } catch {
          /* orphan cleanup is best-effort */
        }
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
        ...diagnosticIdentity(downloadIdentity),
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
      // See fetchAndStoreMedia: cache.put may have landed before a later persist step
      // threw; best-effort clear so the blob isn't orphaned without metadata.
      try {
        await deletePersistentMediaEntry(identity.cacheKey);
      } catch {
        /* orphan cleanup is best-effort */
      }
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
      ...diagnosticIdentity(identity),
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
        ...diagnosticIdentity(entry),
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
        ...diagnosticIdentity(entry),
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
  __resetObjectUrlRegistriesForTest();
  cacheManager.clearDomain(MEDIA_OBJECT_URL_PREFIX);
  lastPruneAt = 0;
  cacheClearGeneration = 0;
  resetMediaCacheLimits();
  setPrivateCacheUserScope(null);
  resetMediaCacheDiagnostics();
};

export const __setMediaCacheLimitsForTest = (limits: {
  maxEntries?: number;
  maxBytes?: number;
}): void => {
  setMediaCacheLimits(limits);
};

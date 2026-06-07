import {
  deleteMediaCacheMetadata,
  listMediaCacheMetadata,
  writeMediaCacheMetadata,
  type MediaCacheMetadata,
} from './mediaCacheIndexedDb';
import { type MediaCacheIdentity } from './mediaCacheTypes';
import { canUseCacheStorage, isTemporaryUrl, normalizeString } from './mediaCacheObjectUrls';
import { recordDiagnostic } from './mediaCacheDiagnostics';

const MEDIA_CACHE_NAME = 'gemini-ai-media-cache-v1';
const MEDIA_CACHE_REQUEST_PREFIX = '/__gemini_media_cache__/';
const DEFAULT_PERSISTENT_MAX_ENTRIES = 500;
const DEFAULT_PERSISTENT_MAX_BYTES = 250 * 1024 * 1024;
const PERSISTENT_CACHE_MIN_BYTES = 50 * 1024 * 1024;
const PERSISTENT_CACHE_QUOTA_FRACTION = 0.2;

let persistentMaxEntries = DEFAULT_PERSISTENT_MAX_ENTRIES;
let persistentMaxBytes = DEFAULT_PERSISTENT_MAX_BYTES;

// The in-memory object-URL layer lives in the entry module (it owns the
// cacheManager-backed memory map). Persistence needs to evict the matching
// memory entry whenever it removes a persisted blob, so the entry registers
// the eviction callback once at module load. Defaults to a no-op so the
// persistence module is safe to import in isolation (e.g. unit tests).
let evictMemoryEntry: (cacheKey: string) => void = () => {};

export const setMediaCacheMemoryEvictionHook = (hook: (cacheKey: string) => void): void => {
  evictMemoryEntry = hook;
};

export const getMediaCacheStorageRequestUrl = (cacheKey: string): string => {
  const encoded = encodeURIComponent(cacheKey);
  if (typeof window === 'undefined') return `${MEDIA_CACHE_REQUEST_PREFIX}${encoded}`;
  return new URL(`${MEDIA_CACHE_REQUEST_PREFIX}${encoded}`, window.location.origin).toString();
};

export const storageCacheRequest = (cacheKey: string): Request =>
  new Request(getMediaCacheStorageRequestUrl(cacheKey));

export const openMediaCache = async (): Promise<Cache | null> => {
  if (!canUseCacheStorage()) return null;
  try {
    return await window.caches.open(MEDIA_CACHE_NAME);
  } catch {
    return null;
  }
};

export const deleteMediaCacheStorage = async (): Promise<void> => {
  if (!canUseCacheStorage()) return;
  try {
    await window.caches.delete(MEDIA_CACHE_NAME);
  } catch {
    // ignore cache deletion errors
  }
};

export const deletePersistentMediaEntry = async (cacheKey: string): Promise<void> => {
  evictMemoryEntry(cacheKey);
  const cache = await openMediaCache();
  await cache?.delete(storageCacheRequest(cacheKey));
  await deleteMediaCacheMetadata(cacheKey);
};

const createCacheBlobResponse = async (blob: Blob, contentType: string): Promise<Response> => {
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
    evictMemoryEntry(entry.cacheKey);
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

export const persistCachedMedia = async (
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

export const readSeedMediaBlob = async (
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

export const setMediaCacheLimits = (limits: { maxEntries?: number; maxBytes?: number }): void => {
  if (Number.isFinite(limits.maxEntries)) {
    persistentMaxEntries = Math.max(1, Number(limits.maxEntries));
  }
  if (Number.isFinite(limits.maxBytes)) {
    persistentMaxBytes = Math.max(1, Number(limits.maxBytes));
  }
};

export const resetMediaCacheLimits = (): void => {
  persistentMaxEntries = DEFAULT_PERSISTENT_MAX_ENTRIES;
  persistentMaxBytes = DEFAULT_PERSISTENT_MAX_BYTES;
};

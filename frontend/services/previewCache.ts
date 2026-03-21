import { isStoragePreviewProxyUrl } from './storagePreviewService';

const PREVIEW_CACHE_NAME = 'cloud-storage-preview-v1';
const PREVIEW_META_KEY = 'cloud-storage-preview-meta-v1';
const PREVIEW_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const PREVIEW_MAX_ENTRIES = 400;

type PreviewMetaMap = Record<string, number>;
type PreviewMemoryEntry = {
  objectUrl: string;
  updatedAt: number;
};

const previewObjectUrlMemory = new Map<string, PreviewMemoryEntry>();

const canUsePersistentCache = (): boolean => {
  return typeof window !== 'undefined' && typeof window.caches !== 'undefined';
};

const canUseObjectUrlMemoryCache = (): boolean => {
  return typeof window !== 'undefined' && typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function';
};

const deletePreviewObjectUrlMemory = (url: string) => {
  const entry = previewObjectUrlMemory.get(url);
  if (!entry) return;
  previewObjectUrlMemory.delete(url);
  try {
    URL.revokeObjectURL(entry.objectUrl);
  } catch {
    // ignore revoke errors
  }
};

const prunePreviewObjectUrlMemory = () => {
  if (!canUseObjectUrlMemoryCache()) return;

  const now = Date.now();
  for (const [url, entry] of previewObjectUrlMemory.entries()) {
    if (!Number.isFinite(entry.updatedAt) || now - entry.updatedAt > PREVIEW_MAX_AGE_MS) {
      deletePreviewObjectUrlMemory(url);
    }
  }

  if (previewObjectUrlMemory.size <= PREVIEW_MAX_ENTRIES) {
    return;
  }

  const staleByCapacity = [...previewObjectUrlMemory.entries()]
    .sort((left, right) => left[1].updatedAt - right[1].updatedAt)
    .slice(0, previewObjectUrlMemory.size - PREVIEW_MAX_ENTRIES);

  staleByCapacity.forEach(([url]) => {
    deletePreviewObjectUrlMemory(url);
  });
};

const readMetaMap = (): PreviewMetaMap => {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(PREVIEW_META_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as PreviewMetaMap;
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed;
  } catch {
    return {};
  }
};

const writeMetaMap = (meta: PreviewMetaMap) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(PREVIEW_META_KEY, JSON.stringify(meta));
  } catch {
    // ignore storage quota and serialization errors
  }
};

const pruneMetaMap = async (cache: Cache, meta: PreviewMetaMap): Promise<PreviewMetaMap> => {
  const now = Date.now();
  const next: PreviewMetaMap = { ...meta };

  for (const [url, ts] of Object.entries(next)) {
    if (!Number.isFinite(ts) || now - ts > PREVIEW_MAX_AGE_MS) {
      await cache.delete(url);
      delete next[url];
    }
  }

  const entries = Object.entries(next);
  if (entries.length <= PREVIEW_MAX_ENTRIES) {
    return next;
  }

  const staleByCapacity = entries
    .sort((a, b) => a[1] - b[1])
    .slice(0, entries.length - PREVIEW_MAX_ENTRIES);

  for (const [url] of staleByCapacity) {
    await cache.delete(url);
    delete next[url];
  }

  return next;
};

export const getCachedPreviewBlob = async (url: string): Promise<Blob | null> => {
  if (!canUsePersistentCache() || !isStoragePreviewProxyUrl(url)) {
    return null;
  }

  try {
    const cache = await window.caches.open(PREVIEW_CACHE_NAME);
    const meta = await pruneMetaMap(cache, readMetaMap());
    writeMetaMap(meta);

    const lastWriteTs = meta[url];
    if (!lastWriteTs || Date.now() - lastWriteTs > PREVIEW_MAX_AGE_MS) {
      await cache.delete(url);
      delete meta[url];
      writeMetaMap(meta);
      return null;
    }

    const response = await cache.match(url);
    if (!response) {
      delete meta[url];
      writeMetaMap(meta);
      return null;
    }

    return await response.blob();
  } catch {
    return null;
  }
};

export const getCachedPreviewObjectUrlSync = (url: string): string | null => {
  const normalizedUrl = String(url || '').trim();
  if (!canUseObjectUrlMemoryCache() || !normalizedUrl) {
    return null;
  }

  prunePreviewObjectUrlMemory();
  const entry = previewObjectUrlMemory.get(normalizedUrl);
  if (!entry) {
    return null;
  }

  entry.updatedAt = Date.now();
  previewObjectUrlMemory.set(normalizedUrl, entry);
  return entry.objectUrl;
};

export const cachePreviewBlobObjectUrl = (url: string, blob: Blob): string | null => {
  const normalizedUrl = String(url || '').trim();
  if (!canUseObjectUrlMemoryCache() || !normalizedUrl) {
    return null;
  }

  const existing = getCachedPreviewObjectUrlSync(normalizedUrl);
  if (existing) {
    return existing;
  }

  const objectUrl = URL.createObjectURL(blob);
  previewObjectUrlMemory.set(normalizedUrl, {
    objectUrl,
    updatedAt: Date.now()
  });
  prunePreviewObjectUrlMemory();
  return objectUrl;
};

export const getCachedPreviewObjectUrl = async (url: string): Promise<string | null> => {
  const inMemoryObjectUrl = getCachedPreviewObjectUrlSync(url);
  if (inMemoryObjectUrl) {
    return inMemoryObjectUrl;
  }

  const cachedBlob = await getCachedPreviewBlob(url);
  if (!cachedBlob) {
    return null;
  }

  return cachePreviewBlobObjectUrl(url, cachedBlob);
};

export const savePreviewBlobToCache = async (
  url: string,
  blob: Blob,
  contentType?: string | null
): Promise<void> => {
  cachePreviewBlobObjectUrl(url, blob);

  if (!canUsePersistentCache() || !isStoragePreviewProxyUrl(url)) {
    return;
  }

  try {
    const cache = await window.caches.open(PREVIEW_CACHE_NAME);
    const response = new Response(blob, {
      status: 200,
      headers: {
        'Content-Type': String(contentType || blob.type || 'application/octet-stream')
      }
    });

    await cache.put(url, response);
    const meta = await pruneMetaMap(cache, readMetaMap());
    meta[url] = Date.now();
    writeMetaMap(meta);
  } catch {
    // ignore cache put errors
  }
};

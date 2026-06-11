import {
  isSafeStoragePreviewCandidateUrl,
  isStoragePreviewProxyUrl,
} from './storagePreviewService';
import {
  getCachedMediaObjectUrl,
  getCachedMediaObjectUrlSync,
  getDefaultMediaCacheUserScope,
  evictCachedMediaObjectUrl,
  resolveMediaCacheIdentity,
  saveMediaBlobToCache,
  type MediaCacheIdentity,
} from './mediaCache';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
  type PrivateCacheLifecycleSnapshot,
} from './privateCacheInvalidation';

const PREVIEW_CACHE_NAME = 'cloud-storage-preview-v1';
const PREVIEW_META_KEY = 'cloud-storage-preview-meta-v1';

interface GetCachedPreviewOptions {
  allowMemory?: boolean;
}

const canUsePersistentCache = (): boolean => {
  return typeof window !== 'undefined' && typeof window.caches !== 'undefined';
};

const getPreviewUserScope = (): string => getDefaultMediaCacheUserScope();

const splitPreviewCacheKey = (
  url: string
): { sourceUrl: string; versionFingerprint?: string } | null => {
  const normalizedUrl = String(url || '').trim();
  if (!normalizedUrl) return null;
  const separatorIndex = normalizedUrl.indexOf('::');
  if (separatorIndex < 0) {
    return { sourceUrl: normalizedUrl };
  }

  const sourceUrl = normalizedUrl.slice(0, separatorIndex).trim();
  if (!sourceUrl) return null;
  return {
    sourceUrl,
    versionFingerprint: normalizedUrl,
  };
};

const isPathRelativeUrl = (url: string): boolean => url.startsWith('/') && !url.startsWith('//');

const getSharedPreviewIdentityUrl = (sourceUrl: string): string => {
  if (isPathRelativeUrl(sourceUrl) || isStoragePreviewProxyUrl(sourceUrl)) {
    return sourceUrl;
  }

  const lowered = sourceUrl.toLowerCase();
  if (lowered.startsWith('http://') || lowered.startsWith('https://')) {
    return `/api/storage/preview?url=${encodeURIComponent(sourceUrl)}`;
  }

  return sourceUrl;
};

const getPreviewMediaIdentity = (
  url: string,
  contentType?: string | null,
  userScope = getPreviewUserScope()
): MediaCacheIdentity | null => {
  const previewSource = splitPreviewCacheKey(url);
  if (!previewSource || !isSafeStoragePreviewCandidateUrl(previewSource.sourceUrl)) return null;
  const identityUrl = getSharedPreviewIdentityUrl(previewSource.sourceUrl);
  return resolveMediaCacheIdentity({
    url: identityUrl,
    mimeType: contentType || 'image/png',
    userScope,
    updatedAt: previewSource.versionFingerprint,
  });
};

const isPreviewCacheLifecycleCurrent = (
  snapshot: PrivateCacheLifecycleSnapshot,
  userScope: string
): boolean =>
  getPreviewUserScope() === userScope && isPrivateCacheLifecycleSnapshotCurrent(snapshot);

const getCachedPreviewObjectUrlSync = (url: string): string | null => {
  const normalizedUrl = String(url || '').trim();
  if (!normalizedUrl) return null;

  const mediaIdentity = getPreviewMediaIdentity(normalizedUrl);
  if (!mediaIdentity) return null;
  return getCachedMediaObjectUrlSync(mediaIdentity, { allowStale: false });
};

export const getCachedPreviewObjectUrl = async (
  url: string,
  options: GetCachedPreviewOptions = {}
): Promise<string | null> => {
  const requestScope = getPreviewUserScope();
  const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
  const allowMemory = options.allowMemory !== false;
  const inMemoryObjectUrl = allowMemory ? getCachedPreviewObjectUrlSync(url) : null;
  if (inMemoryObjectUrl) {
    return inMemoryObjectUrl;
  }

  const mediaIdentity = getPreviewMediaIdentity(url, undefined, requestScope);
  if (!mediaIdentity) return null;

  const readOptions = allowMemory
    ? { allowStale: false }
    : { allowStale: false, allowMemory: false };
  const mediaObjectUrl = await getCachedMediaObjectUrl(mediaIdentity, readOptions);
  if (!isPreviewCacheLifecycleCurrent(lifecycleSnapshot, requestScope)) return null;
  return mediaObjectUrl || null;
};

export const evictCachedPreviewObjectUrl = (url: string, objectUrl?: string | null): boolean => {
  const requestScope = getPreviewUserScope();
  const mediaIdentity = getPreviewMediaIdentity(url, undefined, requestScope);
  if (!mediaIdentity) return false;
  return evictCachedMediaObjectUrl(mediaIdentity, objectUrl);
};

export const savePreviewBlobToCache = async (
  url: string,
  blob: Blob,
  contentType?: string | null
): Promise<string | null> => {
  const requestScope = getPreviewUserScope();
  const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
  const mediaIdentity = getPreviewMediaIdentity(url, contentType || blob.type, requestScope);
  if (!mediaIdentity) return null;

  try {
    const cached = await saveMediaBlobToCache(mediaIdentity, blob, { contentType });
    if (!isPreviewCacheLifecycleCurrent(lifecycleSnapshot, requestScope)) return null;
    return cached.objectUrl;
  } catch {
    return null;
  }
};

export const clearPreviewCacheForLogout = async (): Promise<void> => {
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.removeItem(PREVIEW_META_KEY);
      const scopedKeys: string[] = [];
      for (let index = 0; index < window.localStorage.length; index += 1) {
        const key = window.localStorage.key(index);
        if (key?.startsWith(`${PREVIEW_META_KEY}:`)) {
          scopedKeys.push(key);
        }
      }
      scopedKeys.forEach((key) => window.localStorage.removeItem(key));
    } catch {
      // ignore storage errors
    }
  }

  if (!canUsePersistentCache()) return;
  try {
    await window.caches.delete(PREVIEW_CACHE_NAME);
  } catch {
    // ignore cache deletion errors
  }
};

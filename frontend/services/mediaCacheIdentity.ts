import {
  isSafeStoragePreviewCandidateUrl,
  isStoragePreviewProxyUrl,
} from './storagePreviewService';
import { getPrivateCacheScopeSegment, getPrivateCacheUserScope } from './privateCacheScope';
import { type MediaCacheIdentity, type MediaCacheSource } from './mediaCacheTypes';
import { hashString, isTemporaryUrl, normalizeString } from './mediaCacheObjectUrls';

const getSourceBlob = (source: MediaCacheSource): Blob | null => {
  if (typeof Blob === 'undefined') return null;
  return source.file instanceof Blob ? source.file : null;
};

const isPathRelativeUrl = (url: string): boolean => url.startsWith('/') && !url.startsWith('//');

export const isSameOriginUrl = (url: string): boolean => {
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

const getMediaUserScope = (
  source: Pick<MediaCacheSource, 'userScope'> | null | undefined
): string => normalizeString(source?.userScope) || getPrivateCacheUserScope();

export const getScopeCacheSegment = (userScope: string): string =>
  getPrivateCacheScopeSegment(userScope);

const buildScopedMediaCacheKey = (
  userScope: string,
  type: 'attachment' | 'path' | 'url',
  stableId: string
): string => `media:${getScopeCacheSegment(userScope)}:${type}:${stableId}`;

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
    candidates.find((url) => url !== selectedSourceUrl && url.toLowerCase().startsWith('data:')) ||
    null
  );
};

const getPreviewNestedUrl = (url: string): string | null => {
  if (!isStoragePreviewProxyUrl(url)) return null;
  try {
    const parsed = new URL(
      url,
      typeof window !== 'undefined' ? window.location.origin : 'http://local'
    );
    return parsed.searchParams.get('url');
  } catch {
    return null;
  }
};

const getStorageRevision = (source: MediaCacheSource, url: string): string => {
  const explicit = normalizeString(source.storageRevision);
  if (explicit) return explicit;
  try {
    const parsed = new URL(
      url,
      typeof window !== 'undefined' ? window.location.origin : 'http://local'
    );
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

export const getCacheableDurableUrl = (url: string): string | null => {
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

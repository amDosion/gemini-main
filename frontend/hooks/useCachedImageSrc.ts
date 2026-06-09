import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  evictCachedMediaObjectUrl,
  fetchAndStoreMedia,
  getCachedMediaObjectUrl,
  getCachedMediaObjectUrlSync,
  resolveMediaCacheIdentity,
  type MediaCacheSource,
  type MediaCacheStatus,
} from '../services/mediaCache';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from '../services/privateCacheInvalidation';
import { usePrivateCacheLifecycleRevision } from './usePrivateCacheScopeRevision';
import { useRetainedBlobObjectUrlState } from './useRetainedBlobObjectUrlState';

interface UseCachedImageSrcOptions {
  enabled?: boolean;
  fallbackSrc?: string | null;
  preferStale?: boolean;
  preferMemoryCache?: boolean;
  replaceCachedObjectUrl?: boolean;
}

interface UseCachedImageSrcResult {
  src: string | null;
  status: MediaCacheStatus;
  error: Error | null;
  refresh: () => Promise<void>;
  recoverFromImageError: (failedSrc?: string | null) => boolean;
}

const getBlobSourceSignature = (blob: Blob | null | undefined): string => {
  if (!blob) return '';
  const file = typeof File !== 'undefined' && blob instanceof File ? blob : null;
  return [blob.type || '', blob.size || 0, file?.name || '', file?.lastModified || ''].join(':');
};

const getSourceSignature = (
  source: MediaCacheSource | null | undefined,
  fallbackSrc: string | null
): string =>
  [
    source?.id || '',
    source?.attachmentId || '',
    source?.url || '',
    source?.tempUrl || '',
    source?.temp_url || '',
    source?.cloudUrl || '',
    source?.cloud_url || '',
    source?.fileUri || '',
    source?.file_uri || '',
    source?.previewUrl || '',
    source?.mimeType || '',
    source?.mime_type || '',
    source?.name || '',
    source?.uploadStatus || '',
    source?.upload_status || '',
    source?.uploadTaskId || '',
    source?.upload_task_id || '',
    source?.storageRevision || '',
    source?.updatedAt || '',
    source?.createdAt || '',
    source?.userScope || '',
    getBlobSourceSignature(source?.file),
    fallbackSrc || '',
  ]
    .map((value) => String(value))
    .join('\u001f');

const isBlobObjectUrl = (value: string | null | undefined): boolean =>
  String(value || '')
    .trim()
    .toLowerCase()
    .startsWith('blob:');

const isUnrenderableTemporarySrc = (value: string | null | undefined): boolean => {
  const src = String(value || '')
    .trim()
    .toLowerCase();
  return src.startsWith('blob:') || src.startsWith('local-blob:');
};

const isAuthenticatedStorageSrc = (value: string | null | undefined): boolean => {
  const src = String(value || '').trim();
  if (!src) return false;

  try {
    const origin = typeof window !== 'undefined' ? window.location.origin : 'http://local';
    const parsed = new URL(src, origin);
    return parsed.origin === origin && parsed.pathname.startsWith('/api/storage/');
  } catch {
    return src.startsWith('/api/storage/');
  }
};

const isTemporaryImageSrc = (value: string | null | undefined): boolean => {
  const src = String(value || '')
    .trim()
    .toLowerCase();
  return src.startsWith('blob:') || src.startsWith('data:') || src.startsWith('local-blob:');
};

export const useCachedImageSrc = (
  source: MediaCacheSource | null | undefined,
  options: UseCachedImageSrcOptions = {}
): UseCachedImageSrcResult => {
  const {
    enabled = true,
    fallbackSrc = null,
    preferStale = true,
    preferMemoryCache = true,
    replaceCachedObjectUrl = false,
  } = options;
  const resetLocalStateRef = useRef<() => void>(() => undefined);
  const scopeVersion = usePrivateCacheLifecycleRevision(
    () => {
      resetLocalStateRef.current();
    },
    { includeCacheReset: true }
  );
  const sourceSignature = getSourceSignature(source, fallbackSrc);
  const normalizedSource = useMemo<MediaCacheSource | null>(() => {
    if (!source && !fallbackSrc) return null;
    return {
      ...(source || {}),
      url: source?.url || fallbackSrc || undefined,
    };
  }, [sourceSignature]);

  const identity = useMemo(
    () => resolveMediaCacheIdentity(normalizedSource),
    [normalizedSource, scopeVersion]
  );
  const canExposeRawFallback =
    !isAuthenticatedStorageSrc(fallbackSrc) &&
    (!isUnrenderableTemporarySrc(fallbackSrc) || Boolean(source?.file));
  const [src, setRetainedSrc] = useRetainedBlobObjectUrlState(
    identity ? null : canExposeRawFallback ? fallbackSrc : null
  );
  const [status, setStatus] = useState<MediaCacheStatus>(
    identity ? 'idle' : fallbackSrc ? 'raw-fallback' : 'idle'
  );
  const [error, setError] = useState<Error | null>(null);
  const currentRunRef = useRef(0);
  const currentSrcRef = useRef<string | null>(src);
  const currentIdentityKeyRef = useRef<string>('');

  const setResolvedSrc = useCallback(
    (nextSrc: string | null) => {
      currentSrcRef.current = nextSrc;
      setRetainedSrc(nextSrc);
    },
    [setRetainedSrc]
  );

  resetLocalStateRef.current = () => {
    currentRunRef.current += 1;
    currentIdentityKeyRef.current = '';
    setResolvedSrc(null);
    setStatus('idle');
    setError(null);
  };

  useEffect(() => {
    currentSrcRef.current = src;
  }, [src]);

  const identityKey = identity
    ? `${identity.cacheKey}:${identity.versionSignature}:${identity.sourceUrl}`
    : '';
  const shouldBypassMemoryCache =
    replaceCachedObjectUrl ||
    !preferMemoryCache ||
    (Boolean(identity?.temporary) &&
      isBlobObjectUrl(identity?.sourceUrl) &&
      !normalizedSource?.file);
  const shouldUseVersionStrictCache =
    Boolean(identity?.temporary) && Boolean(normalizedSource?.file);
  const cacheAllowStale = preferStale && !shouldUseVersionStrictCache;
  const cachedReadOptions = useMemo(() => {
    if (!shouldBypassMemoryCache) {
      return { allowStale: cacheAllowStale };
    }
    return replaceCachedObjectUrl
      ? {
          allowStale: cacheAllowStale,
          allowMemory: false,
          replaceObjectUrl: true,
        }
      : {
          allowStale: cacheAllowStale,
          allowMemory: false,
        };
  }, [cacheAllowStale, replaceCachedObjectUrl, shouldBypassMemoryCache]);
  const fetchOptions = useMemo(
    () =>
      shouldBypassMemoryCache || replaceCachedObjectUrl ? { replaceObjectUrl: true } : undefined,
    [replaceCachedObjectUrl, shouldBypassMemoryCache]
  );

  const load = useCallback(
    async (forceRefresh = false) => {
      const runId = currentRunRef.current + 1;
      currentRunRef.current = runId;
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      const isCurrent = () =>
        currentRunRef.current === runId &&
        isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot);
      const previousIdentityKey = currentIdentityKeyRef.current;
      const isSameIdentity = Boolean(identityKey && previousIdentityKey === identityKey);
      currentIdentityKeyRef.current = identityKey;
      const allowStaleMemoryHit = cacheAllowStale && isSameIdentity;
      const effectiveCachedReadOptions =
        allowStaleMemoryHit === cacheAllowStale
          ? cachedReadOptions
          : {
              ...cachedReadOptions,
              allowStale: allowStaleMemoryHit,
            };

      if (!enabled) {
        if (!isCurrent()) return;
        setResolvedSrc(fallbackSrc);
        setStatus(fallbackSrc ? 'raw-fallback' : 'idle');
        setError(null);
        return;
      }

      if (!identity) {
        if (!isCurrent()) return;
        if (!canExposeRawFallback && fallbackSrc) {
          setResolvedSrc(null);
          setStatus('error');
          setError(new Error('Temporary blob media source is not cacheable'));
          return;
        }
        setResolvedSrc(fallbackSrc);
        setStatus(fallbackSrc ? 'raw-fallback' : 'idle');
        setError(null);
        return;
      }

      if (!isSameIdentity && !forceRefresh) {
        if (!isCurrent()) return;
        setResolvedSrc(null);
      }

      const memoryHit = shouldBypassMemoryCache
        ? null
        : getCachedMediaObjectUrlSync(identity, { allowStale: allowStaleMemoryHit });
      if (memoryHit && !forceRefresh) {
        if (!isCurrent()) return;
        setResolvedSrc(memoryHit);
        setStatus('memory-hit');
        setError(null);
        return;
      }

      try {
        const cached = !forceRefresh
          ? await getCachedMediaObjectUrl(identity, effectiveCachedReadOptions)
          : null;
        if (cached && !forceRefresh) {
          if (!isCurrent()) return;
          setResolvedSrc(cached);
          setStatus('persistent-hit');
          setError(null);
          return;
        }

        if (!isCurrent()) return;
        setStatus((previous) =>
          currentSrcRef.current && previous !== 'raw-fallback' ? 'stale' : 'loading'
        );
        const fresh = forceRefresh
          ? await fetchAndStoreMedia(identity, {
              allowRevalidate: false,
              replaceObjectUrl: true,
            })
          : fetchOptions
            ? await fetchAndStoreMedia(identity, fetchOptions)
            : await fetchAndStoreMedia(identity);
        if (!isCurrent()) return;
        setResolvedSrc(fresh.objectUrl);
        setStatus(
          fresh.status === 'not-modified'
            ? 'persistent-hit'
            : fresh.status === 'fresh-memory-only'
              ? 'fresh-memory-only'
              : 'fresh'
        );
        setError(null);
      } catch (loadError) {
        if (!isCurrent()) return;
        const nextError = loadError instanceof Error ? loadError : new Error(String(loadError));
        setError(nextError);
        if (isSameIdentity && currentSrcRef.current) {
          setStatus('stale-error');
          return;
        }
        if (identity.temporary) {
          setResolvedSrc(null);
          setStatus('error');
          return;
        }
        setResolvedSrc(canExposeRawFallback ? fallbackSrc : null);
        setStatus('error');
      }
    },
    [
      canExposeRawFallback,
      enabled,
      fallbackSrc,
      identity,
      identityKey,
      preferStale,
      preferMemoryCache,
      replaceCachedObjectUrl,
      cacheAllowStale,
      shouldBypassMemoryCache,
      cachedReadOptions,
      fetchOptions,
      setResolvedSrc,
    ]
  );

  useEffect(() => {
    load(false).catch((loadError) => {
      setError(loadError instanceof Error ? loadError : new Error(String(loadError)));
      setStatus('error');
    });
    return () => {
      currentRunRef.current += 1;
    };
  }, [load, identityKey]);

  const refresh = useCallback(async () => {
    await load(true);
  }, [load]);

  const recoverFromImageError = useCallback(
    (failedSrc?: string | null): boolean => {
      const normalizedFailedSrc = String(failedSrc || '').trim();
      const currentSrc = currentSrcRef.current;
      const hasStableFallback = Boolean(
        fallbackSrc && !isTemporaryImageSrc(fallbackSrc) && !isAuthenticatedStorageSrc(fallbackSrc)
      );

      if (
        !normalizedFailedSrc ||
        !currentSrc ||
        normalizedFailedSrc !== currentSrc ||
        !isBlobObjectUrl(normalizedFailedSrc) ||
        (!hasStableFallback && !identity)
      ) {
        return false;
      }

      evictCachedMediaObjectUrl(identity, normalizedFailedSrc);
      if (hasStableFallback) {
        setResolvedSrc(fallbackSrc);
        setStatus('raw-fallback');
      } else {
        setResolvedSrc(null);
        setStatus('loading');
      }
      setError(null);

      Promise.resolve()
        .then(() => load(false))
        .catch((loadError) => {
          setError(loadError instanceof Error ? loadError : new Error(String(loadError)));
          setStatus('error');
        });

      return true;
    },
    [fallbackSrc, identity, load, setResolvedSrc]
  );

  return { src, status, error, refresh, recoverFromImageError };
};

import { MutableRefObject, useCallback, useEffect, useMemo, useState } from 'react';
import { downloadBlobWithXhr, type DownloadBlobResult } from '../../../services/httpProgress';
import {
  evictCachedPreviewObjectUrl,
  getCachedPreviewObjectUrl,
  savePreviewBlobToCache
} from '../../../services/previewCache';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent
} from '../../../services/privateCacheInvalidation';
import {
  getPrivateCacheScopeSegment
} from '../../../services/privateCacheScope';
import {
  isSafeStoragePreviewCandidateUrl,
  isStoragePreviewProxyUrl
} from '../../../services/storagePreviewService';
import { getErrorMessage } from '../../../utils/errorMessage';
import { usePrivateCacheScopeRevision } from '../../../hooks/usePrivateCacheScopeRevision';
import { useRetainedBlobObjectUrlState } from '../../../hooks/useRetainedBlobObjectUrlState';

export interface PreviewLoadFailure {
  url: string;
  httpStatus: number | null;
  message: string;
}

interface UseXhrImagePreviewOptions {
  enabled?: boolean;
}

interface PreviewDownloadEntry {
  requestKey: string;
  requestUrl: string;
  promise: Promise<DownloadBlobResult>;
  subscriberCount: number;
  started: boolean;
  resolve: (value: DownloadBlobResult) => void;
  reject: (reason?: unknown) => void;
}

interface PreviewDownloadHandle {
  promise: Promise<DownloadBlobResult>;
  release: () => void;
}

// --- Module-level download queue (deliberate singleton) ---
// These three variables form a cross-instance download deduplicator and
// concurrency limiter. They are intentionally module-scoped so that multiple
// useXhrImagePreview hook instances share the same in-flight registry and queue,
// preventing duplicate XHR requests for the same preview URL when the same
// image is rendered more than once on screen simultaneously.
const MAX_CONCURRENT_PREVIEW_DOWNLOADS = 4;
const inflightPreviewDownloads = new Map<string, PreviewDownloadEntry>();
const queuedPreviewDownloadKeys: string[] = [];
let activePreviewDownloadCount = 0;

const buildPreviewCacheKey = (candidateUrl: string, resetKey: string): string => {
  const normalizedCandidate = String(candidateUrl || '').trim();
  if (!normalizedCandidate || isStoragePreviewProxyUrl(normalizedCandidate)) {
    return normalizedCandidate;
  }
  const normalizedResetKey = String(resetKey || '').trim();
  return normalizedResetKey ? `${normalizedCandidate}::${normalizedResetKey}` : normalizedCandidate;
};

const buildPreviewRequestKey = (cacheKey: string): string =>
  `${getPrivateCacheScopeSegment()}:${cacheKey}`;

const removeQueuedPreviewDownload = (requestKey: string): void => {
  const queueIndex = queuedPreviewDownloadKeys.indexOf(requestKey);
  if (queueIndex >= 0) {
    queuedPreviewDownloadKeys.splice(queueIndex, 1);
  }
};

const pumpPreviewDownloadQueue = (): void => {
  while (
    activePreviewDownloadCount < MAX_CONCURRENT_PREVIEW_DOWNLOADS &&
    queuedPreviewDownloadKeys.length > 0
  ) {
    const nextRequestKey = queuedPreviewDownloadKeys.shift();
    if (!nextRequestKey) {
      continue;
    }

    const entry = inflightPreviewDownloads.get(nextRequestKey);
    if (!entry || entry.started) {
      continue;
    }
    if (entry.subscriberCount <= 0) {
      inflightPreviewDownloads.delete(nextRequestKey);
      continue;
    }

    entry.started = true;
    activePreviewDownloadCount += 1;

    void downloadBlobWithXhr({
      url: entry.requestUrl,
      withCredentials: entry.requestUrl.startsWith('/') && !entry.requestUrl.startsWith('//'),
      timeoutMs: 30000
    }).then(
      (result) => entry.resolve(result),
      (error) => entry.reject(error)
    ).finally(() => {
      activePreviewDownloadCount = Math.max(0, activePreviewDownloadCount - 1);
      if (inflightPreviewDownloads.get(nextRequestKey) === entry) {
        inflightPreviewDownloads.delete(nextRequestKey);
      }
      pumpPreviewDownloadQueue();
    });
  }
};

const acquirePreviewBlobDownload = (
  url: string,
  requestKey: string
): PreviewDownloadHandle => {
  const normalizedUrl = String(url || '').trim();
  const normalizedRequestKey = String(requestKey || '').trim() || normalizedUrl;
  if (!normalizedUrl) {
    return {
      promise: Promise.reject(new Error('Preview URL is empty')),
      release: () => undefined
    };
  }

  const existing = inflightPreviewDownloads.get(normalizedRequestKey);
  if (existing) {
    existing.subscriberCount += 1;
    let released = false;
    return {
      promise: existing.promise,
      release: () => {
        if (released) return;
        released = true;
        const latest = inflightPreviewDownloads.get(normalizedRequestKey);
        if (!latest) return;
        latest.subscriberCount = Math.max(0, latest.subscriberCount - 1);
        if (!latest.started && latest.subscriberCount === 0) {
          inflightPreviewDownloads.delete(normalizedRequestKey);
          removeQueuedPreviewDownload(normalizedRequestKey);
        }
      }
    };
  }

  // Initialise with no-ops; the Promise executor runs synchronously so these
  // are always replaced with the real resolve/reject before the entry is used.
  let resolvePromise: (value: DownloadBlobResult) => void = () => undefined;
  let rejectPromise: (reason?: unknown) => void = () => undefined;
  const promise = new Promise<DownloadBlobResult>((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });
  const entry: PreviewDownloadEntry = {
    requestKey: normalizedRequestKey,
    requestUrl: normalizedUrl,
    promise,
    subscriberCount: 1,
    started: false,
    resolve: resolvePromise,
    reject: rejectPromise
  };

  inflightPreviewDownloads.set(normalizedRequestKey, entry);
  queuedPreviewDownloadKeys.push(normalizedRequestKey);
  pumpPreviewDownloadQueue();

  let released = false;
  return {
    promise,
    release: () => {
      if (released) return;
      released = true;
      const latest = inflightPreviewDownloads.get(normalizedRequestKey);
      if (!latest) return;
      latest.subscriberCount = Math.max(0, latest.subscriberCount - 1);
      if (!latest.started && latest.subscriberCount === 0) {
        inflightPreviewDownloads.delete(normalizedRequestKey);
        removeQueuedPreviewDownload(normalizedRequestKey);
      }
    }
  };
};

/** @internal Exposed only for unit tests — do not import in production code. */
export const __resetInflightPreviewDownloadsForTest = (): void => {
  inflightPreviewDownloads.clear();
  queuedPreviewDownloadKeys.splice(0, queuedPreviewDownloadKeys.length);
  activePreviewDownloadCount = 0;
};

const parsePreviewErrorHttpStatus = (error: unknown): number | null => {
  if (error && typeof error === 'object' && 'status' in error) {
    const statusValue = Number((error as { status?: unknown }).status);
    if (Number.isFinite(statusValue) && statusValue > 0) {
      return statusValue;
    }
  }
  const message = getErrorMessage(error);
  const match = message.match(/HTTP\s+(\d{3})/i);
  if (!match) return null;
  const statusValue = Number(match[1]);
  return Number.isFinite(statusValue) ? statusValue : null;
};

export const useXhrImagePreview = (
  candidates: string[],
  failedPreviewUrlsRef: MutableRefObject<Set<string>>,
  resetKey: string,
  options: UseXhrImagePreviewOptions = {}
): {
  src: string | null;
  exhausted: boolean;
  lastFailure: PreviewLoadFailure | null;
  recoverFromImageError: (failedSrc?: string | null) => boolean;
} => {
  const { enabled = true } = options;
  const scopeVersion = usePrivateCacheScopeRevision();
  const [src, setRetainedSrc] = useRetainedBlobObjectUrlState(null);
  const [exhausted, setExhausted] = useState(false);
  const [lastFailure, setLastFailure] = useState<PreviewLoadFailure | null>(null);
  const [reloadRevision, setReloadRevision] = useState(0);
  const safeCandidates = useMemo(() => {
    const uniqueCandidates = new Set<string>();
    candidates.forEach((candidate) => {
      const normalizedCandidate = String(candidate || '').trim();
      if (!isSafeStoragePreviewCandidateUrl(normalizedCandidate)) {
        return;
      }
      uniqueCandidates.add(normalizedCandidate);
    });
    return Array.from(uniqueCandidates);
  }, [candidates]);
  const recoverFromImageError = useCallback(
    (failedSrc?: string | null): boolean => {
      const normalizedFailedSrc = String(failedSrc || '').trim();
      if (
        !normalizedFailedSrc ||
        normalizedFailedSrc !== src ||
        !normalizedFailedSrc.toLowerCase().startsWith('blob:')
      ) {
        return false;
      }

      const didEvict = safeCandidates.some((candidate) =>
        evictCachedPreviewObjectUrl(buildPreviewCacheKey(candidate, resetKey), normalizedFailedSrc)
      );
      if (!didEvict) return false;

      setRetainedSrc(null);
      setExhausted(false);
      setLastFailure(null);
      setReloadRevision((current) => current + 1);
      return true;
    },
    [resetKey, safeCandidates, setRetainedSrc, src]
  );

  useEffect(() => {
    let cancelled = false;
    let pendingRelease: (() => void) | null = null;
    const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
    const isCurrent = () =>
      !cancelled && isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot);

    const readPersistentCachedPreview = async (): Promise<string | null> => {
      for (const candidate of safeCandidates) {
        if (failedPreviewUrlsRef.current.has(candidate)) {
          continue;
        }

        const cacheKey = buildPreviewCacheKey(candidate, resetKey);
        const cachedObjectUrl = await getCachedPreviewObjectUrl(cacheKey, { allowMemory: false });
        if (!isCurrent()) return null;
        if (cachedObjectUrl) return cachedObjectUrl;
      }
      return null;
    };

    const loadPreview = async () => {
      setRetainedSrc(null);
      setExhausted(false);
      setLastFailure(null);
      for (const candidate of safeCandidates) {
        if (failedPreviewUrlsRef.current.has(candidate)) {
          continue;
        }

        const cacheKey = buildPreviewCacheKey(candidate, resetKey);
        const cachedObjectUrl = await getCachedPreviewObjectUrl(cacheKey, { allowMemory: false });
        if (!isCurrent()) return;
        if (cachedObjectUrl) {
          setRetainedSrc(cachedObjectUrl);
          return;
        }

        try {
          const requestHandle = acquirePreviewBlobDownload(candidate, buildPreviewRequestKey(cacheKey));
          pendingRelease = requestHandle.release;
          const { blob, headers } = await requestHandle.promise;
          if (!isCurrent()) return;
          const cachedObjectUrl = await savePreviewBlobToCache(cacheKey, blob, headers['content-type'] || null);
          if (!isCurrent()) return;
          if (!cachedObjectUrl) {
            throw new Error('Preview cache did not return an object URL');
          }
          setRetainedSrc(cachedObjectUrl);
          return;
        } catch (error) {
          if (!isCurrent()) return;
          const httpStatus = parsePreviewErrorHttpStatus(error);
          const message = getErrorMessage(error);
          failedPreviewUrlsRef.current.add(candidate);
          setLastFailure({
            url: candidate,
            httpStatus,
            message
          });
        } finally {
          pendingRelease?.();
          pendingRelease = null;
        }
      }
      if (!cancelled) {
        setExhausted(true);
      }
    };

    if (safeCandidates.length === 0) {
      setRetainedSrc(null);
      setExhausted(true);
      setLastFailure(null);
      return () => undefined;
    }

    if (!enabled) {
      setExhausted(false);
      setLastFailure(null);
      void readPersistentCachedPreview().then((cachedObjectUrl) => {
        if (!isCurrent()) return;
        setRetainedSrc(cachedObjectUrl);
      });
      return () => {
        cancelled = true;
      };
    }

    void loadPreview();
    return () => {
      cancelled = true;
      pendingRelease?.();
      pendingRelease = null;
    };
  }, [
    enabled,
    failedPreviewUrlsRef,
    reloadRevision,
    resetKey,
    safeCandidates,
    scopeVersion,
    setRetainedSrc
  ]);

  return { src, exhausted, lastFailure, recoverFromImageError };
};

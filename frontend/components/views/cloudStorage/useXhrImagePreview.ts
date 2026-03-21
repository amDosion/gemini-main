import { MutableRefObject, useEffect, useMemo, useState } from 'react';
import { downloadBlobWithXhr, type DownloadBlobResult } from '../../../services/httpProgress';
import {
  cachePreviewBlobObjectUrl,
  getCachedPreviewObjectUrl,
  getCachedPreviewObjectUrlSync,
  savePreviewBlobToCache
} from '../../../services/previewCache';
import {
  isSafeStoragePreviewCandidateUrl,
  isStoragePreviewProxyUrl
} from '../../../services/storagePreviewService';

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

  let resolvePromise!: (value: DownloadBlobResult) => void;
  let rejectPromise!: (reason?: unknown) => void;
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
  const message = error instanceof Error ? error.message : String(error || '');
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
): { src: string | null; exhausted: boolean; lastFailure: PreviewLoadFailure | null } => {
  const { enabled = true } = options;
  const [src, setSrc] = useState<string | null>(null);
  const [exhausted, setExhausted] = useState(false);
  const [lastFailure, setLastFailure] = useState<PreviewLoadFailure | null>(null);
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
  const immediateCachedSrc = useMemo(
    () =>
      safeCandidates
        .map((candidate) => getCachedPreviewObjectUrlSync(buildPreviewCacheKey(candidate, resetKey)))
        .find((candidate): candidate is string => typeof candidate === 'string' && candidate.length > 0) || null,
    [safeCandidates, resetKey]
  );

  useEffect(() => {
    let cancelled = false;
    let pendingRelease: (() => void) | null = null;

    const loadPreview = async () => {
      if (immediateCachedSrc) {
        setSrc(immediateCachedSrc);
      } else {
        setSrc(null);
      }
      setExhausted(false);
      setLastFailure(null);
      for (const candidate of safeCandidates) {
        if (failedPreviewUrlsRef.current.has(candidate)) {
          continue;
        }

        const cacheKey = buildPreviewCacheKey(candidate, resetKey);
        const cachedObjectUrl = await getCachedPreviewObjectUrl(cacheKey);
        if (cachedObjectUrl) {
          if (cancelled) return;
          setSrc(cachedObjectUrl);
          return;
        }
        if (cancelled) return;

        try {
          const requestHandle = acquirePreviewBlobDownload(candidate, cacheKey);
          pendingRelease = requestHandle.release;
          const { blob, headers } = await requestHandle.promise;
          await savePreviewBlobToCache(cacheKey, blob, headers['content-type'] || null);
          const objectUrl = cachePreviewBlobObjectUrl(cacheKey, blob) || URL.createObjectURL(blob);
          if (cancelled) return;
          setSrc(objectUrl);
          return;
        } catch (error) {
          const httpStatus = parsePreviewErrorHttpStatus(error);
          const message = error instanceof Error ? error.message : String(error || 'Unknown preview error');
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
      setSrc(null);
      setExhausted(true);
      setLastFailure(null);
      return () => undefined;
    }

    if (!enabled) {
      setSrc(immediateCachedSrc);
      setExhausted(false);
      setLastFailure(null);
      return () => undefined;
    }

    void loadPreview();
    return () => {
      cancelled = true;
      pendingRelease?.();
      pendingRelease = null;
    };
  }, [enabled, failedPreviewUrlsRef, immediateCachedSrc, resetKey, safeCandidates]);

  return { src, exhausted, lastFailure };
};

import React, { forwardRef, useCallback, useEffect, useMemo, useState } from 'react';
import { useCachedImageSrc } from '../../hooks/useCachedImageSrc';
import { useRetainedBlobObjectUrl } from '../../hooks/useRetainedBlobObjectUrl';
import { type MediaCacheSource } from '../../services/mediaCache';

export interface CachedImageProps
  extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  src?: string | null;
  source?: MediaCacheSource | null;
  cacheEnabled?: boolean;
  preferMemoryCache?: boolean;
  replaceCachedObjectUrl?: boolean;
  rawFallbackDelayMs?: number | null;
}

const isTemporaryImageSrc = (value: string | null | undefined): boolean => {
  const src = (value || '').trim().toLowerCase();
  return src.startsWith('blob:') || src.startsWith('data:') || src.startsWith('local-blob:');
};

const isAuthenticatedStorageSrc = (value: string | null | undefined): boolean => {
  const src = (value || '').trim();
  if (!src) return false;

  try {
    const parsed = new URL(src, window.location.origin);
    return parsed.origin === window.location.origin && parsed.pathname.startsWith('/api/storage/');
  } catch {
    return src.startsWith('/api/storage/');
  }
};

export const CachedImage = forwardRef<HTMLImageElement, CachedImageProps>(
  (
    {
      src,
      source,
      cacheEnabled = true,
      preferMemoryCache = true,
      replaceCachedObjectUrl = false,
      rawFallbackDelayMs = null,
      onError,
      ...imgProps
    },
    ref
  ) => {
    const cacheSource = useMemo<MediaCacheSource | null>(() => {
      if (!source && !src) return null;
      return {
        ...(source || {}),
        url: source?.url || src || undefined,
      };
    }, [source, src]);
    const [showRawFallback, setShowRawFallback] = useState(false);
    const [failedCachedSrc, setFailedCachedSrc] = useState<string | null>(null);

    const cached = useCachedImageSrc(cacheSource, {
      enabled: cacheEnabled,
      fallbackSrc: src || null,
      preferStale: true,
      preferMemoryCache,
      replaceCachedObjectUrl,
    });
    const canUseDelayedRawFallback =
      cacheEnabled &&
      Boolean(cacheSource) &&
      rawFallbackDelayMs !== null &&
      rawFallbackDelayMs !== undefined &&
      Number.isFinite(rawFallbackDelayMs) &&
      Boolean(src) &&
      !isTemporaryImageSrc(src) &&
      !isAuthenticatedStorageSrc(src);
    const shouldUseImmediateRawFallback =
      canUseDelayedRawFallback &&
      Math.max(0, rawFallbackDelayMs || 0) === 0;
    const canUseStableRawFallback =
      Boolean(src) && !isTemporaryImageSrc(src) && !isAuthenticatedStorageSrc(src);

    useEffect(() => {
      setShowRawFallback(false);
      setFailedCachedSrc(null);

      if (!canUseDelayedRawFallback || cached.src) return;

      const timer = window.setTimeout(() => {
        setShowRawFallback(true);
      }, Math.max(0, rawFallbackDelayMs || 0));

      return () => {
        window.clearTimeout(timer);
      };
    }, [cached.src, canUseDelayedRawFallback, rawFallbackDelayMs, src]);

    const shouldUseStableRawFallback =
      Boolean(failedCachedSrc) &&
      Boolean(cached.src) &&
      failedCachedSrc === cached.src &&
      canUseStableRawFallback;
    const shouldSuppressFailedCachedSrc =
      Boolean(failedCachedSrc) &&
      Boolean(cached.src) &&
      failedCachedSrc === cached.src &&
      !canUseStableRawFallback;
    const resolvedSrc = shouldSuppressFailedCachedSrc
      ? ''
      : (
          (shouldUseStableRawFallback ? src || '' : cached.src) ||
          (shouldUseImmediateRawFallback ? src || '' : '') ||
          (canUseDelayedRawFallback && showRawFallback ? src || '' : '') ||
          (cacheEnabled && cacheSource ? '' : src || '')
        );

    useRetainedBlobObjectUrl(resolvedSrc);

    const handleImageError = useCallback(
      (event: React.SyntheticEvent<HTMLImageElement, Event>) => {
        const failedSrc = event.currentTarget.getAttribute('src') || resolvedSrc;
        if (cached.recoverFromImageError(failedSrc)) {
          setFailedCachedSrc(failedSrc);
          return;
        }

        onError?.(event);
      },
      [cached, onError, resolvedSrc]
    );

    if (!resolvedSrc) return null;

    return (
      <img
        ref={ref}
        src={resolvedSrc}
        data-cache-status={cached.status}
        onError={handleImageError}
        {...imgProps}
      />
    );
  }
);

CachedImage.displayName = 'CachedImage';

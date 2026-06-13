import React, { useCallback, useEffect, useState } from 'react';
import { useRetainedBlobObjectUrl } from '../../hooks/useRetainedBlobObjectUrl';
import { isSafeInlineImageDataUrl } from '../../utils/safeMediaDataUrl';

const isBlobObjectUrl = (value: string | null | undefined): boolean =>
  String(value || '').trim().toLowerCase().startsWith('blob:');

const isFailedBlobForRenderedSrc = (
  renderedSrc: string | null | undefined,
  failedSrc: string | null | undefined
): boolean => isBlobObjectUrl(renderedSrc) && isBlobObjectUrl(failedSrc);

const isRenderableRetainedImageSrc = (value: string | null | undefined): boolean => {
  const src = (value || '').trim();
  if (!src) return false;
  const lowered = src.toLowerCase();
  if (lowered.startsWith('local-blob:')) return false;
  if (lowered.startsWith('data:')) return isSafeInlineImageDataUrl(src);
  return true;
};

export interface RetainedImageProps
  extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  src: string;
  onRecoverImageError?: (failedSrc?: string | null) => boolean;
  retainBlobUrl?: boolean;
}

export const RetainedImage: React.FC<RetainedImageProps> = ({
  src,
  onRecoverImageError,
  retainBlobUrl = true,
  onError,
  ...imgProps
}) => {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const normalizedSrc = src.trim();
  const renderedSrc = isRenderableRetainedImageSrc(normalizedSrc) ? normalizedSrc : '';
  useRetainedBlobObjectUrl(retainBlobUrl ? renderedSrc : null);

  useEffect(() => {
    setFailedSrc(null);
  }, [src]);

  const handleError = useCallback(
    (event: React.SyntheticEvent<HTMLImageElement, Event>) => {
      const failedSrc =
        event.currentTarget.currentSrc || event.currentTarget.getAttribute('src');
      if (onRecoverImageError?.(failedSrc)) {
        setFailedSrc(failedSrc);
        return;
      }
      if (isFailedBlobForRenderedSrc(renderedSrc, failedSrc)) {
        setFailedSrc(failedSrc);
      }
      onError?.(event);
    },
    [onError, onRecoverImageError, renderedSrc]
  );

  if (!renderedSrc || isFailedBlobForRenderedSrc(renderedSrc, failedSrc)) return null;

  return <img src={renderedSrc} onError={handleError} {...imgProps} />;
};

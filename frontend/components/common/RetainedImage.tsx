import React, { useCallback, useEffect, useState } from 'react';
import { useRetainedBlobObjectUrl } from '../../hooks/useRetainedBlobObjectUrl';

const isBlobObjectUrl = (value: string | null | undefined): boolean =>
  String(value || '').trim().toLowerCase().startsWith('blob:');

const isFailedBlobForRenderedSrc = (
  renderedSrc: string | null | undefined,
  failedSrc: string | null | undefined
): boolean => isBlobObjectUrl(renderedSrc) && isBlobObjectUrl(failedSrc);

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
  useRetainedBlobObjectUrl(retainBlobUrl ? src : null);

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
      if (isFailedBlobForRenderedSrc(src, failedSrc)) {
        setFailedSrc(failedSrc);
      }
      onError?.(event);
    },
    [onError, onRecoverImageError, src]
  );

  if (isFailedBlobForRenderedSrc(src, failedSrc)) return null;

  return <img src={src} onError={handleError} {...imgProps} />;
};

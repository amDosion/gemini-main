import React, { useCallback, useEffect, useState } from 'react';
import { useRetainedBlobObjectUrl } from '../../hooks/useRetainedBlobObjectUrl';

const isBlobObjectUrl = (value: string | null | undefined): boolean =>
  String(value || '').trim().toLowerCase().startsWith('blob:');

const isFailedBlobForRenderedSrc = (
  renderedSrc: string | null | undefined,
  failedSrc: string | null | undefined
): boolean => isBlobObjectUrl(renderedSrc) && isBlobObjectUrl(failedSrc);

export interface RetainedVideoProps
  extends Omit<React.VideoHTMLAttributes<HTMLVideoElement>, 'src'> {
  src?: string | null;
  onRecoverMediaError?: (failedSrc?: string | null) => boolean;
}

export interface RetainedAudioProps
  extends Omit<React.AudioHTMLAttributes<HTMLAudioElement>, 'src'> {
  src?: string | null;
  onRecoverMediaError?: (failedSrc?: string | null) => boolean;
}

export const RetainedVideo = React.forwardRef<HTMLVideoElement, RetainedVideoProps>(
  ({ src, onRecoverMediaError, onError, ...videoProps }, ref) => {
    const [failedSrc, setFailedSrc] = useState<string | null>(null);
    useRetainedBlobObjectUrl(src);

    useEffect(() => {
      setFailedSrc(null);
    }, [src]);

    const handleError = useCallback(
      (event: React.SyntheticEvent<HTMLVideoElement, Event>) => {
        const mediaSrc = event.currentTarget.currentSrc || event.currentTarget.getAttribute('src');
        if (onRecoverMediaError?.(mediaSrc)) {
          setFailedSrc(mediaSrc);
          return;
        }
        if (isFailedBlobForRenderedSrc(src, mediaSrc)) {
          setFailedSrc(mediaSrc);
        }
        onError?.(event);
      },
      [onError, onRecoverMediaError, src]
    );

    if (!src || isFailedBlobForRenderedSrc(src, failedSrc)) return null;
    return <video ref={ref} src={src} onError={handleError} {...videoProps} />;
  }
);

export const RetainedAudio = React.forwardRef<HTMLAudioElement, RetainedAudioProps>(
  ({ src, onRecoverMediaError, onError, ...audioProps }, ref) => {
    const [failedSrc, setFailedSrc] = useState<string | null>(null);
    useRetainedBlobObjectUrl(src);

    useEffect(() => {
      setFailedSrc(null);
    }, [src]);

    const handleError = useCallback(
      (event: React.SyntheticEvent<HTMLAudioElement, Event>) => {
        const mediaSrc = event.currentTarget.currentSrc || event.currentTarget.getAttribute('src');
        if (onRecoverMediaError?.(mediaSrc)) {
          setFailedSrc(mediaSrc);
          return;
        }
        if (isFailedBlobForRenderedSrc(src, mediaSrc)) {
          setFailedSrc(mediaSrc);
        }
        onError?.(event);
      },
      [onError, onRecoverMediaError, src]
    );

    if (!src || isFailedBlobForRenderedSrc(src, failedSrc)) return null;
    return <audio ref={ref} src={src} onError={handleError} {...audioProps} />;
  }
);

RetainedVideo.displayName = 'RetainedVideo';
RetainedAudio.displayName = 'RetainedAudio';

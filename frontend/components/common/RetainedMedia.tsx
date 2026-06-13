import React, { useCallback, useEffect, useState } from 'react';
import { useRetainedBlobObjectUrl } from '../../hooks/useRetainedBlobObjectUrl';
import {
  isSafeInlineAudioDataUrl,
  isSafeInlineVideoDataUrl,
} from '../../utils/safeMediaDataUrl';

const isBlobObjectUrl = (value: string | null | undefined): boolean =>
  String(value || '').trim().toLowerCase().startsWith('blob:');

const isFailedBlobForRenderedSrc = (
  renderedSrc: string | null | undefined,
  failedSrc: string | null | undefined
): boolean => isBlobObjectUrl(renderedSrc) && isBlobObjectUrl(failedSrc);

const isRenderableRetainedMediaSrc = (
  value: string | null | undefined,
  mediaFamily: 'audio' | 'video'
): boolean => {
  const src = (value || '').trim();
  if (!src) return false;
  const lowered = src.toLowerCase();
  if (lowered.startsWith('local-blob:')) return false;
  if (lowered.startsWith('blob:')) return true;
  if (lowered.startsWith('data:audio/')) {
    return mediaFamily === 'audio' && isSafeInlineAudioDataUrl(src);
  }
  if (lowered.startsWith('data:video/')) {
    return mediaFamily === 'video' && isSafeInlineVideoDataUrl(src);
  }
  return lowered.startsWith('/api/') || lowered.startsWith('http://') || lowered.startsWith('https://');
};

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
    const normalizedSrc = (src || '').trim();
    const renderedSrc = isRenderableRetainedMediaSrc(normalizedSrc, 'video') ? normalizedSrc : '';
    useRetainedBlobObjectUrl(renderedSrc);

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
        if (isFailedBlobForRenderedSrc(renderedSrc, mediaSrc)) {
          setFailedSrc(mediaSrc);
        }
        onError?.(event);
      },
      [onError, onRecoverMediaError, renderedSrc]
    );

    if (!renderedSrc || isFailedBlobForRenderedSrc(renderedSrc, failedSrc)) return null;
    return <video ref={ref} src={renderedSrc} onError={handleError} {...videoProps} />;
  }
);

export const RetainedAudio = React.forwardRef<HTMLAudioElement, RetainedAudioProps>(
  ({ src, onRecoverMediaError, onError, ...audioProps }, ref) => {
    const [failedSrc, setFailedSrc] = useState<string | null>(null);
    const normalizedSrc = (src || '').trim();
    const renderedSrc = isRenderableRetainedMediaSrc(normalizedSrc, 'audio') ? normalizedSrc : '';
    useRetainedBlobObjectUrl(renderedSrc);

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
        if (isFailedBlobForRenderedSrc(renderedSrc, mediaSrc)) {
          setFailedSrc(mediaSrc);
        }
        onError?.(event);
      },
      [onError, onRecoverMediaError, renderedSrc]
    );

    if (!renderedSrc || isFailedBlobForRenderedSrc(renderedSrc, failedSrc)) return null;
    return <audio ref={ref} src={renderedSrc} onError={handleError} {...audioProps} />;
  }
);

RetainedVideo.displayName = 'RetainedVideo';
RetainedAudio.displayName = 'RetainedAudio';

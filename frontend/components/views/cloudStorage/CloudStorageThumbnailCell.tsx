import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MutableRefObject } from 'react';
import { Folder, Play } from 'lucide-react';
import type { StorageBrowseItem } from '../../../types/storage';
import {
  buildStoragePreviewCandidates,
  getInitialStoragePreviewIndex,
  getNextStoragePreviewIndex
} from '../../../services/storagePreviewService';
import {
  createGeneratedThumb,
  getFileExtension,
  getFileKind
} from './filePresentation';
import { useXhrImagePreview } from './useXhrImagePreview';

interface CloudStorageThumbnailCellProps {
  item: StorageBrowseItem;
  failedPreviewUrlsRef: MutableRefObject<Set<string>>;
  storageRevision?: number | null;
  sizeClassName?: string;
  disablePreview?: boolean;
  disableVideoPreview?: boolean;
  visibilityRoot?: Element | null;
  previewRootMargin?: string;
}

export const CloudStorageThumbnailCell: React.FC<CloudStorageThumbnailCellProps> = ({
  item,
  failedPreviewUrlsRef,
  storageRevision,
  sizeClassName = 'h-11 w-11',
  disablePreview = false,
  disableVideoPreview = false,
  visibilityRoot = null,
  previewRootMargin = '240px'
}) => {
  const kind = getFileKind(item);
  const ext = getFileExtension(item.name);
  const previewAnchorRef = useRef<HTMLDivElement | null>(null);
  const [shouldLoadPreview, setShouldLoadPreview] = useState(() => kind !== 'image' && kind !== 'video');
  const [videoFrameReady, setVideoFrameReady] = useState(false);
  const videoElementRef = useRef<HTMLVideoElement | null>(null);
  const didRequestVideoFrameRef = useRef(false);
  const imagePreviewEnabled = shouldLoadPreview && !disablePreview;
  const videoPreviewEnabled = shouldLoadPreview && !disablePreview && !disableVideoPreview;
  const previewCandidates = useMemo(
    () => buildStoragePreviewCandidates(item, storageRevision),
    [item.url, item.previewUrl, storageRevision]
  );
  const [videoPreviewIndex, setVideoPreviewIndex] = useState(0);
  const [videoPreviewExhausted, setVideoPreviewExhausted] = useState(false);
  const generatedThumb = useMemo(() => createGeneratedThumb(kind, ext), [kind, ext]);
  const { src: imagePreviewSrc, exhausted: imagePreviewExhausted } = useXhrImagePreview(
    kind === 'image' ? previewCandidates : [],
    failedPreviewUrlsRef,
    `${item.path}:${item.url || ''}:${item.previewUrl || ''}:${storageRevision ?? ''}`,
    { enabled: imagePreviewEnabled }
  );

  useEffect(() => {
    if (kind !== 'image' && kind !== 'video') {
      setShouldLoadPreview(true);
      return;
    }

    if (shouldLoadPreview) {
      return;
    }

    if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
      setShouldLoadPreview(true);
      return;
    }

    const target = previewAnchorRef.current;
    if (!target) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
          setShouldLoadPreview(true);
          observer.disconnect();
        }
      },
      { root: visibilityRoot, rootMargin: previewRootMargin }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [kind, previewRootMargin, shouldLoadPreview, visibilityRoot]);

  useEffect(() => {
    if (kind !== 'video') {
      setVideoPreviewIndex(0);
      setVideoPreviewExhausted(false);
      return;
    }
    const nextState = getInitialStoragePreviewIndex(previewCandidates, failedPreviewUrlsRef.current);
    setVideoPreviewIndex(nextState.index);
    setVideoPreviewExhausted(nextState.exhausted);
  }, [kind, previewCandidates, failedPreviewUrlsRef]);

  const videoPreviewUrl = videoPreviewExhausted ? null : (previewCandidates[videoPreviewIndex] || null);

  const handleVideoPreviewError = useCallback(() => {
    const currentUrl = previewCandidates[videoPreviewIndex];
    if (currentUrl) {
      failedPreviewUrlsRef.current.add(currentUrl);
    }
    const nextState = getNextStoragePreviewIndex(
      previewCandidates,
      videoPreviewIndex,
      failedPreviewUrlsRef.current
    );
    setVideoPreviewIndex(nextState.index);
    setVideoPreviewExhausted(nextState.exhausted);
  }, [previewCandidates, videoPreviewIndex, failedPreviewUrlsRef]);

  useEffect(() => {
    didRequestVideoFrameRef.current = false;
    setVideoFrameReady(false);
  }, [videoPreviewUrl]);

  const requestVideoFrame = useCallback(() => {
    const video = videoElementRef.current;
    if (!video || didRequestVideoFrameRef.current) {
      return;
    }
    didRequestVideoFrameRef.current = true;

    try {
      if (Number.isFinite(video.duration) && video.duration > 0) {
        const safeTargetTime = Math.min(0.1, Math.max(0, video.duration - 0.05));
        if (safeTargetTime > 0) {
          video.currentTime = safeTargetTime;
          return;
        }
      }
    } catch (error) {
      console.warn('[CloudStorageThumbnailCell] Unable to request video frame', {
        path: item.path,
        error
      });
    }

    setVideoFrameReady(true);
  }, [item.path]);

  return (
    <div ref={previewAnchorRef} className={`${sizeClassName} shrink-0`}>
      {kind === 'directory' && (
        <div className="flex h-full w-full items-center justify-center rounded-xl border border-slate-700 bg-slate-800/80 text-slate-300">
          <Folder size={16} />
        </div>
      )}

      {kind === 'image' && imagePreviewSrc && (
        <img
          src={imagePreviewSrc}
          alt={item.name}
          className="h-full w-full rounded-xl border border-slate-700 bg-slate-900 object-contain p-1"
          loading="lazy"
        />
      )}

      {kind === 'image' && !imagePreviewSrc && !imagePreviewExhausted && (
        <img
          src={generatedThumb}
          alt={`${kind} thumbnail loading`}
          className="h-full w-full rounded-xl border border-slate-700 bg-slate-900 object-contain p-1 opacity-80"
          loading="lazy"
        />
      )}

      {kind === 'video' && videoPreviewEnabled && videoPreviewUrl && (
        <div className="relative h-full w-full overflow-hidden rounded-xl border border-slate-700 bg-black">
          <video
            ref={videoElementRef}
            src={videoPreviewUrl}
            className={`h-full w-full bg-black object-contain transition-opacity duration-150 ${
              videoFrameReady ? 'opacity-100' : 'opacity-0'
            }`}
            muted
            playsInline
            preload="metadata"
            onLoadedMetadata={requestVideoFrame}
            onLoadedData={() => setVideoFrameReady(true)}
            onSeeked={() => setVideoFrameReady(true)}
            onError={handleVideoPreviewError}
          />
          {!videoFrameReady && (
            <img
              src={generatedThumb}
              alt={`${kind} thumbnail loading`}
              className="absolute inset-0 h-full w-full rounded-xl bg-slate-900 object-contain p-1 opacity-80"
              loading="lazy"
            />
          )}
          <div className="absolute inset-0 flex items-center justify-center bg-black/20">
            <Play size={12} className="text-white" />
          </div>
        </div>
      )}

      {((kind === 'image' && !imagePreviewSrc && imagePreviewExhausted) ||
        (kind === 'video' && (!videoPreviewEnabled || !videoPreviewUrl)) ||
        (kind !== 'directory' && kind !== 'image' && kind !== 'video')) && (
        <div className="relative h-full w-full">
          <img
            src={generatedThumb}
            alt={`${kind} thumbnail`}
            className="h-full w-full rounded-xl border border-slate-700 bg-slate-900 object-contain p-1"
            loading="lazy"
          />
          {kind === 'video' && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/10">
              <Play size={12} className="text-white" />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

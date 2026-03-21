import React, { useEffect, useMemo, useState } from 'react';
import { Copy, Download, Play, X } from 'lucide-react';
import {
  ImageCarouselArrows
} from '../../common/ImageCarouselControls';
import type {
  StorageBrowseItem,
  StorageFileMetadataItem
} from '../../../types/storage';
import {
  createGeneratedThumb,
  formatBytes,
  getFileExtension,
  getFileKind,
  type FileKind
} from './filePresentation';
import { CloudStorageThumbnailCell } from './CloudStorageThumbnailCell';
import type { MutableRefObject } from 'react';

interface CloudStorageViewerOverlayProps {
  isOpen: boolean;
  currentViewerFile: StorageBrowseItem | null;
  currentViewerKind: FileKind | null;
  currentViewerMetadata: StorageFileMetadataItem | undefined;
  currentViewerImageSrc: string | null;
  currentViewerImageExhausted: boolean;
  currentViewerVideoSrc: string | null;
  viewerFiles: StorageBrowseItem[];
  viewerIndex: number;
  goViewerPrev: () => void;
  goViewerNext: () => void;
  selectViewerIndex: (index: number) => void;
  handleViewerPreviewError: () => void;
  onDownloadItem: (item: StorageBrowseItem) => Promise<void>;
  onCopyUrl: (item: StorageBrowseItem) => Promise<void>;
  failedPreviewUrlsRef: MutableRefObject<Set<string>>;
  storageRevision: number | null;
  onClose: () => void;
}

export const CloudStorageViewerOverlay: React.FC<CloudStorageViewerOverlayProps> = ({
  isOpen,
  currentViewerFile,
  currentViewerKind,
  currentViewerMetadata,
  currentViewerImageSrc,
  currentViewerImageExhausted,
  currentViewerVideoSrc,
  viewerFiles,
  viewerIndex,
  goViewerPrev,
  goViewerNext,
  selectViewerIndex,
  handleViewerPreviewError,
  onDownloadItem,
  onCopyUrl,
  failedPreviewUrlsRef,
  storageRevision,
  onClose
}) => {
  const [shouldLoadCurrentVideo, setShouldLoadCurrentVideo] = useState(false);
  const [thumbnailStripElement, setThumbnailStripElement] = useState<HTMLDivElement | null>(null);
  const [activeThumbnailPath, setActiveThumbnailPath] = useState<string | null>(null);

  useEffect(() => {
    setShouldLoadCurrentVideo(false);
  }, [currentViewerFile?.path, currentViewerKind, currentViewerVideoSrc]);

  useEffect(() => {
    if (!isOpen) {
      setThumbnailStripElement(null);
      setActiveThumbnailPath(null);
    }
  }, [isOpen]);

  const currentViewerNeighborPaths = useMemo(() => {
    if (viewerFiles.length <= 0) {
      return new Set<string>();
    }

    const nearbyPaths = new Set<string>();
    viewerFiles.forEach((file, index) => {
      const directDistance = Math.abs(index - viewerIndex);
      const wrapDistance = viewerFiles.length - directDistance;
      const circularDistance = Math.min(directDistance, wrapDistance);
      if (circularDistance <= 1) {
        nearbyPaths.add(file.path);
      }
    });
    return nearbyPaths;
  }, [viewerFiles, viewerIndex]);

  if (!isOpen || !currentViewerFile) {
    return null;
  }

  return (
    <div className="absolute inset-0 z-40 bg-slate-950/95 backdrop-blur-sm flex flex-col">
      <div className="px-4 md:px-6 py-3 border-b border-slate-800 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-white truncate">{currentViewerFile.name}</p>
          <p className="text-xs text-slate-400 truncate">{currentViewerFile.path}</p>
          {(currentViewerKind === 'image' || currentViewerKind === 'video') && (
            <p className="text-[11px] text-slate-500 truncate mt-1">
              {currentViewerMetadata?.contentType || 'unknown type'}
              {' · '}
              {formatBytes(currentViewerFile.size ?? currentViewerMetadata?.contentLength ?? null)}
              {currentViewerMetadata?.source ? ` · meta:${currentViewerMetadata.source}` : ''}
            </p>
          )}
        </div>
        <div className="shrink-0 flex items-center gap-2">
          <button
            type="button"
            onClick={() => void onDownloadItem(currentViewerFile)}
            className="px-2.5 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-300 hover:bg-slate-800 flex items-center gap-1"
          >
            <Download size={12} />
            Download
          </button>
          {currentViewerFile.url && (
            <button
              type="button"
              onClick={() => void onCopyUrl(currentViewerFile)}
              className="px-2.5 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-300 hover:bg-slate-800 flex items-center gap-1"
            >
              <Copy size={12} />
              Copy URL
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="px-2.5 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-300 hover:bg-slate-800 flex items-center gap-1"
          >
            <X size={12} />
            Close
          </button>
        </div>
      </div>

      <div className="flex-1 relative flex items-center justify-center overflow-hidden px-6 py-5">
        <ImageCarouselArrows
          itemCount={viewerFiles.length}
          onPrev={goViewerPrev}
          onNext={goViewerNext}
          prevTitle="上一项"
          nextTitle="下一项"
        />

        {currentViewerKind === 'image' && currentViewerImageSrc && (
          <img
            src={currentViewerImageSrc}
            alt={currentViewerFile.name}
            className="max-h-full max-w-full object-contain rounded-xl border border-slate-700 shadow-2xl"
          />
        )}

        {currentViewerKind === 'image' && !currentViewerImageSrc && !currentViewerImageExhausted && (
          <div className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900/80 p-6 md:p-8 flex flex-col items-center text-center gap-4">
            <img
              src={createGeneratedThumb('image', getFileExtension(currentViewerFile.name))}
              alt="image preview loading"
              className="h-28 w-28 rounded-2xl border border-slate-700 object-cover opacity-80"
            />
            <p className="text-sm text-slate-300">Loading image preview...</p>
          </div>
        )}

        {currentViewerKind === 'video' && currentViewerVideoSrc && !shouldLoadCurrentVideo && (
          <button
            type="button"
            onClick={() => setShouldLoadCurrentVideo(true)}
            className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900/80 p-6 md:p-8 flex flex-col items-center text-center gap-4 hover:border-slate-600 transition-colors"
          >
            <div className="relative">
              <img
                src={createGeneratedThumb('video', getFileExtension(currentViewerFile.name))}
                alt="video preview placeholder"
                className="h-28 w-28 rounded-2xl border border-slate-700 object-cover"
              />
              <div className="absolute inset-0 flex items-center justify-center rounded-2xl bg-black/20">
                <Play size={18} className="text-white" />
              </div>
            </div>
            <div>
              <p className="text-sm text-slate-200">Click to load video preview</p>
              <p className="mt-1 text-xs text-slate-400">
                Carousel browsing will not preload video bytes until you request playback.
              </p>
            </div>
          </button>
        )}

        {currentViewerKind === 'video' && currentViewerVideoSrc && shouldLoadCurrentVideo && (
          <video
            src={currentViewerVideoSrc}
            controls
            preload="metadata"
            playsInline
            onError={handleViewerPreviewError}
            className="max-h-full max-w-full rounded-xl border border-slate-700 shadow-2xl bg-black"
          />
        )}

        {(currentViewerKind === 'image' || currentViewerKind === 'video') &&
          ((currentViewerKind === 'image' && currentViewerImageExhausted && !currentViewerImageSrc) ||
            (currentViewerKind === 'video' && !currentViewerVideoSrc)) && (
            <div className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900/80 p-6 md:p-8 flex flex-col items-center text-center gap-4">
              <img
                src={createGeneratedThumb(currentViewerKind, getFileExtension(currentViewerFile.name))}
                alt={`${currentViewerKind} thumbnail`}
                className="h-28 w-28 rounded-2xl border border-slate-700 object-cover"
              />
              <div>
                <p className="text-sm text-slate-200">Inline preview is unavailable for this file.</p>
                <p className="text-xs text-slate-400 mt-1">
                  Type: {getFileExtension(currentViewerFile.name).toUpperCase() || 'FILE'} · Size: {formatBytes(currentViewerFile.size)}
                </p>
              </div>
            </div>
          )}

        {currentViewerKind && currentViewerKind !== 'image' && currentViewerKind !== 'video' && (
          <div className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900/80 p-6 md:p-8 flex flex-col items-center text-center gap-4">
            <img
              src={createGeneratedThumb(currentViewerKind, getFileExtension(currentViewerFile.name))}
              alt={`${currentViewerKind} thumbnail`}
              className="h-28 w-28 rounded-2xl border border-slate-700 object-cover"
            />
            <div>
              <p className="text-sm text-slate-200">Inline preview is unavailable for this file type.</p>
              <p className="text-xs text-slate-400 mt-1">
                Type: {getFileExtension(currentViewerFile.name).toUpperCase() || 'FILE'} · Size: {formatBytes(currentViewerFile.size)}
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-800 bg-slate-900/80">
        {viewerFiles.length > 1 && (
          <div
            ref={setThumbnailStripElement}
            className="flex items-center gap-3 py-3 px-4 md:px-6 overflow-x-auto custom-scrollbar"
          >
            {viewerFiles.map((file, index) => {
              const isCurrent = index === viewerIndex;
              const kind = getFileKind(file);
              const allowVideoPreview = kind !== 'video'
                ? true
                : currentViewerNeighborPaths.has(file.path) || activeThumbnailPath === file.path;
              return (
                <button
                  key={file.path || `${index}`}
                  type="button"
                  onClick={() => selectViewerIndex(index)}
                  onMouseEnter={() => setActiveThumbnailPath(file.path)}
                  onMouseLeave={() => setActiveThumbnailPath((current) => (current === file.path ? null : current))}
                  onFocus={() => setActiveThumbnailPath(file.path)}
                  onBlur={() => setActiveThumbnailPath((current) => (current === file.path ? null : current))}
                  className={`relative shrink-0 rounded-lg overflow-hidden transition-all duration-200 ${
                    isCurrent ? 'ring-2 ring-indigo-500 scale-110' : 'opacity-70 hover:opacity-100 hover:scale-105'
                  }`}
                  title={file.name}
                >
                  <CloudStorageThumbnailCell
                    item={file}
                    failedPreviewUrlsRef={failedPreviewUrlsRef}
                    storageRevision={storageRevision}
                    sizeClassName="h-14 w-14"
                    disableVideoPreview={!allowVideoPreview}
                    visibilityRoot={thumbnailStripElement}
                    previewRootMargin="96px"
                  />
                  {isCurrent && (
                    <div className="absolute inset-0 bg-indigo-500/15 pointer-events-none" />
                  )}
                </button>
              );
            })}

            <span className="ml-2 text-xs text-slate-400 font-mono">
              {viewerIndex + 1} / {viewerFiles.length}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { MutableRefObject } from 'react';
import { useImageCarousel } from '../../../hooks/useImageCarousel';
import type { StorageBrowseItem, StorageFileMetadataItem } from '../../../types/storage';
import {
  buildStoragePreviewCandidates,
  getInitialStoragePreviewIndex,
  getNextStoragePreviewIndex
} from '../../../services/storagePreviewService';
import {
  getFileKind,
  type FileKind
} from './filePresentation';
import { useXhrImagePreview } from './useXhrImagePreview';

interface UseCloudStorageViewerOptions {
  items: StorageBrowseItem[];
  selectedStorageId: string | null;
  currentPath: string;
  storageRevision: number | null;
  fileMetadataByUrl: Record<string, StorageFileMetadataItem>;
  failedPreviewUrlsRef: MutableRefObject<Set<string>>;
}

interface UseCloudStorageViewerResult {
  isViewerOpen: boolean;
  openViewer: (path: string) => void;
  closeViewer: () => void;
  viewerFiles: StorageBrowseItem[];
  viewerIndex: number;
  goViewerPrev: () => void;
  goViewerNext: () => void;
  selectViewerIndex: (index: number) => void;
  currentViewerFile: StorageBrowseItem | null;
  currentViewerKind: FileKind | null;
  currentViewerMetadata: StorageFileMetadataItem | undefined;
  currentViewerImageSrc: string | null;
  currentViewerImageExhausted: boolean;
  currentViewerVideoSrc: string | null;
  handleViewerPreviewError: () => void;
}

export function useCloudStorageViewer({
  items,
  selectedStorageId,
  currentPath,
  storageRevision,
  fileMetadataByUrl,
  failedPreviewUrlsRef
}: UseCloudStorageViewerOptions): UseCloudStorageViewerResult {
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [viewerStartPath, setViewerStartPath] = useState<string | null>(null);
  const [viewerPreviewIndex, setViewerPreviewIndex] = useState(0);
  const [viewerPreviewExhausted, setViewerPreviewExhausted] = useState(false);

  const viewerFiles = useMemo(
    () => items.filter((item) => {
      if (item.entryType !== 'file') {
        return false;
      }
      const kind = getFileKind(item);
      if (kind !== 'image' && kind !== 'video') {
        return false;
      }
      return buildStoragePreviewCandidates(item, storageRevision).length > 0;
    }),
    [items, storageRevision]
  );

  const {
    index: viewerIndex,
    setIndex: setViewerIndex,
    goPrev: goViewerPrev,
    goNext: goViewerNext,
    select: selectViewerIndex
  } = useImageCarousel({
    itemCount: viewerFiles.length,
    resetKey: isViewerOpen
      ? `${selectedStorageId || ''}:${currentPath}:${viewerStartPath || ''}:${storageRevision ?? ''}`
      : null,
    keyboardEnabled: isViewerOpen
  });

  const currentViewerFile = isViewerOpen ? viewerFiles[viewerIndex] || null : null;
  const currentViewerKind = currentViewerFile ? getFileKind(currentViewerFile) : null;
  const currentViewerMetadata = currentViewerFile?.metadata || (
    currentViewerFile?.url ? fileMetadataByUrl[currentViewerFile.url] : undefined
  );
  const currentViewerPreviewCandidates = useMemo(() => {
    if (!currentViewerFile || !currentViewerKind) return [];
    if (currentViewerKind !== 'image' && currentViewerKind !== 'video') return [];
    return buildStoragePreviewCandidates(currentViewerFile, storageRevision);
  }, [currentViewerFile, currentViewerKind, storageRevision]);
  const currentViewerImageCandidates = useMemo(
    () => (currentViewerKind === 'image' ? currentViewerPreviewCandidates : []),
    [currentViewerKind, currentViewerPreviewCandidates]
  );
  const { src: currentViewerImageSrc, exhausted: currentViewerImageExhausted } = useXhrImagePreview(
    currentViewerImageCandidates,
    failedPreviewUrlsRef,
    `${currentViewerFile?.path || ''}:${currentViewerFile?.url || ''}:${currentViewerFile?.previewUrl || ''}:${storageRevision ?? ''}`
  );

  useEffect(() => {
    if (currentViewerKind !== 'video') {
      setViewerPreviewIndex(0);
      setViewerPreviewExhausted(false);
      return;
    }
    const nextState = getInitialStoragePreviewIndex(currentViewerPreviewCandidates, failedPreviewUrlsRef.current);
    setViewerPreviewIndex(nextState.index);
    setViewerPreviewExhausted(nextState.exhausted);
  }, [currentViewerKind, currentViewerPreviewCandidates, currentViewerFile?.path, failedPreviewUrlsRef]);

  const currentViewerVideoSrc = viewerPreviewExhausted
    ? null
    : (currentViewerPreviewCandidates[viewerPreviewIndex] || null);

  const handleViewerPreviewError = useCallback(() => {
    const currentSrc = currentViewerVideoSrc;
    if (currentSrc) {
      failedPreviewUrlsRef.current.add(currentSrc);
    }
    const nextState = getNextStoragePreviewIndex(
      currentViewerPreviewCandidates,
      viewerPreviewIndex,
      failedPreviewUrlsRef.current
    );
    setViewerPreviewIndex(nextState.index);
    setViewerPreviewExhausted(nextState.exhausted);
  }, [currentViewerPreviewCandidates, currentViewerVideoSrc, viewerPreviewIndex, failedPreviewUrlsRef]);

  const closeViewer = useCallback(() => {
    setIsViewerOpen(false);
    setViewerStartPath(null);
  }, []);

  const openViewer = useCallback((path: string) => {
    setViewerStartPath(path);
    setIsViewerOpen(true);
  }, []);

  useEffect(() => {
    if (!isViewerOpen) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      closeViewer();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isViewerOpen, closeViewer]);

  useEffect(() => {
    if (!isViewerOpen || !viewerStartPath) {
      return;
    }
    const startIndex = viewerFiles.findIndex((file) => file.path === viewerStartPath);
    if (startIndex >= 0) {
      setViewerIndex(startIndex);
    } else {
      closeViewer();
    }
  }, [isViewerOpen, viewerStartPath, viewerFiles, setViewerIndex, closeViewer]);

  return {
    isViewerOpen,
    openViewer,
    closeViewer,
    viewerFiles,
    viewerIndex,
    goViewerPrev,
    goViewerNext,
    selectViewerIndex,
    currentViewerFile,
    currentViewerKind,
    currentViewerMetadata,
    currentViewerImageSrc,
    currentViewerImageExhausted,
    currentViewerVideoSrc,
    handleViewerPreviewError
  };
}

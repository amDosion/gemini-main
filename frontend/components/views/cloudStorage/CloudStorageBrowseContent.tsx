import React, { useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import { Cloud } from 'lucide-react';
import type { StorageBrowseItem, StorageFileMetadataItem } from '../../../types/storage';
import { CloudStorageFileListGrid } from './CloudStorageFileListGrid';

type ViewMode = 'list' | 'grid';

interface CloudStorageBrowseContentProps {
  showNoStorageConfig: boolean;
  showSelectStorageHint: boolean;
  showDisabledStorageHint: boolean;
  showLoadingDirectory: boolean;
  showBrowseError: boolean;
  error: string | null;
  showUnsupportedHint: boolean;
  message: string | null;
  showEmptyDirectoryHint: boolean;
  showNoSearchResultHint: boolean;
  showFileList: boolean;
  viewMode: ViewMode;
  pagedItems: StorageBrowseItem[];
  selectedPaths: Set<string>;
  onToggleSelectItem: (path: string) => void;
  onViewItem: (item: StorageBrowseItem) => void;
  onDownloadItem: (item: StorageBrowseItem) => Promise<void>;
  onCopyUrl: (item: StorageBrowseItem) => Promise<void>;
  onRenameItem: (item: StorageBrowseItem) => Promise<void>;
  onDeleteItem: (item: StorageBrowseItem) => Promise<void>;
  fileMetadataByUrl: Record<string, StorageFileMetadataItem>;
  failedPreviewUrlsRef: MutableRefObject<Set<string>>;
  storageRevision: number | null;
  suspendPreviewLoading?: boolean;
  autoLoadCursor?: string | null;
  loadingMore?: boolean;
  onAutoLoadMore?: () => void;
}

export const CloudStorageBrowseContent: React.FC<CloudStorageBrowseContentProps> = ({
  showNoStorageConfig,
  showSelectStorageHint,
  showDisabledStorageHint,
  showLoadingDirectory,
  showBrowseError,
  error,
  showUnsupportedHint,
  message,
  showEmptyDirectoryHint,
  showNoSearchResultHint,
  showFileList,
  viewMode,
  pagedItems,
  selectedPaths,
  onToggleSelectItem,
  onViewItem,
  onDownloadItem,
  onCopyUrl,
  onRenameItem,
  onDeleteItem,
  fileMetadataByUrl,
  failedPreviewUrlsRef,
  storageRevision,
  suspendPreviewLoading = false,
  autoLoadCursor = null,
  loadingMore = false,
  onAutoLoadMore
}) => {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const autoLoadSentinelRef = useRef<HTMLDivElement | null>(null);
  const requestedAutoLoadCursorRef = useRef<string | null>(null);

  useEffect(() => {
    if (!autoLoadCursor) {
      requestedAutoLoadCursorRef.current = null;
      return;
    }

    const root = scrollContainerRef.current;
    const target = autoLoadSentinelRef.current;
    if (!root || !target || !autoLoadCursor || loadingMore || !onAutoLoadMore) {
      return;
    }

    const triggerAutoLoad = () => {
      if (requestedAutoLoadCursorRef.current === autoLoadCursor) {
        return;
      }
      requestedAutoLoadCursorRef.current = autoLoadCursor;
      onAutoLoadMore();
    };

    if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
      triggerAutoLoad();
      return;
    }

    let triggered = false;
    const observer = new IntersectionObserver(
      (entries) => {
        if (triggered) {
          return;
        }
        if (!entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
          return;
        }
        triggered = true;
        triggerAutoLoad();
      },
      {
        root,
        rootMargin: '320px 0px'
      }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [autoLoadCursor, loadingMore, onAutoLoadMore, pagedItems.length, viewMode]);

  return (
    <div ref={scrollContainerRef} className="flex-1 overflow-y-auto custom-scrollbar">
      {showNoStorageConfig && (
        <div className="h-full flex flex-col items-center justify-center text-slate-400 px-6 text-center">
          <Cloud size={36} className="mb-3 text-slate-600" />
          <p className="text-sm">No cloud storage configuration.</p>
          <p className="text-xs text-slate-500 mt-1">Create one in Settings &gt; Storage.</p>
        </div>
      )}

      {showSelectStorageHint && (
        <div className="h-full flex items-center justify-center text-slate-400 text-sm">
          Select a storage on the left sidebar.
        </div>
      )}

      {showDisabledStorageHint && (
        <div className="p-6 text-sm text-slate-300">
          Selected storage is disabled. Enable it in Settings &gt; Storage first.
        </div>
      )}

      {showLoadingDirectory && (
        <div className="h-full flex items-center justify-center text-slate-400 text-sm">
          Loading directory...
        </div>
      )}

      {showBrowseError && (
        <div className="p-6 text-sm text-red-300">{error}</div>
      )}

      {showUnsupportedHint && (
        <div className="p-6 text-sm text-slate-300">
          {message || 'Current storage provider does not support directory browsing.'}
        </div>
      )}

      {showEmptyDirectoryHint && (
        <div className="h-full flex items-center justify-center text-slate-500 text-sm">
          Current directory is empty.
        </div>
      )}

      {showNoSearchResultHint && (
        <div className="h-full flex items-center justify-center text-slate-500 text-sm">
          No files matched your search.
        </div>
      )}

      {showFileList && (
        <CloudStorageFileListGrid
          viewMode={viewMode}
          pagedItems={pagedItems}
          selectedPaths={selectedPaths}
          onToggleSelectItem={onToggleSelectItem}
          onViewItem={onViewItem}
          onDownloadItem={onDownloadItem}
          onCopyUrl={onCopyUrl}
          onRenameItem={onRenameItem}
          onDeleteItem={onDeleteItem}
          fileMetadataByUrl={fileMetadataByUrl}
          failedPreviewUrlsRef={failedPreviewUrlsRef}
          storageRevision={storageRevision}
          suspendPreviewLoading={suspendPreviewLoading}
        />
      )}

      {showFileList && autoLoadCursor && (
        <div ref={autoLoadSentinelRef} className="px-4 md:px-6 py-3 text-center text-xs text-slate-500">
          {loadingMore ? 'Loading more...' : 'Scroll to load more'}
        </div>
      )}
    </div>
  );
};

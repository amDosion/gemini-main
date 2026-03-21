import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Cloud } from 'lucide-react';
import {
  StorageBrowseItem,
  StorageConfig
} from '../../types/storage';
import { useToastContext } from '../../contexts/ToastContext';
import { GenViewLayout } from '../common/GenViewLayout';
import { useCloudStorageActions } from './cloudStorage/useCloudStorageActions';
import { useCloudStorageDialogs } from './cloudStorage/useCloudStorageDialogs';
import { useCloudStorageViewer } from './cloudStorage/useCloudStorageViewer';
import { CloudStorageViewerOverlay } from './cloudStorage/CloudStorageViewerOverlay';
import { CloudStorageSidebar } from './cloudStorage/CloudStorageSidebar';
import { CloudStorageHeaderToolbar } from './cloudStorage/CloudStorageHeaderToolbar';
import { CloudStorageBrowseContent } from './cloudStorage/CloudStorageBrowseContent';
import { CloudStoragePaginationFooter } from './cloudStorage/CloudStoragePaginationFooter';
import { getFileKind } from './cloudStorage/filePresentation';
import { buildStoragePreviewCandidates } from '../../services/storagePreviewService';

interface CloudStorageViewProps {
  activeStorageId: string | null;
  storageConfigs: StorageConfig[];
  onClose: () => void;
}

type ViewMode = 'list' | 'grid';

export const CloudStorageView: React.FC<CloudStorageViewProps> = ({
  activeStorageId,
  storageConfigs,
  onClose
}) => {
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [pageNavigationLoading, setPageNavigationLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const failedPreviewUrlsRef = useRef<Set<string>>(new Set());
  const closeViewerRef = useRef<() => void>(() => undefined);
  const { showSuccess } = useToastContext();

  const resetTransientUiState = useCallback(() => {
    closeViewerRef.current();
  }, []);

  const {
    confirmDelete,
    confirmBatchDelete,
    promptRename,
    dialog: actionDialog
  } = useCloudStorageDialogs();

  const {
    selectedStorageId,
    setSelectedStorageId,
    currentPath,
    items,
    loading,
    loadingMore,
    browseError,
    error: actionError,
    setError,
    supported,
    message,
    nextCursor,
    totalItemCount,
    storageName,
    provider,
    storageRevision,
    selectedPaths,
    setSelectedPaths,
    busyAction,
    uploadProgress,
    fileMetadataByUrl,
    loadPath,
    openDirectory,
    refreshCurrentPath,
    ensureItemsLoaded,
    handleDeleteItem,
    handleRenameItem,
    handleBatchDelete,
    handleDownloadItem,
    handleBatchDownload,
    uploadFiles
  } = useCloudStorageActions({
    activeStorageId,
    storageConfigs,
    onBeforeLoadPath: resetTransientUiState,
    onActionNotice: showSuccess,
    confirmDelete,
    confirmBatchDelete,
    promptRename
  });

  const selectedStorage = useMemo(
    () => storageConfigs.find((config) => config.id === selectedStorageId) || null,
    [storageConfigs, selectedStorageId]
  );

  const orderedStorageConfigs = useMemo(() => {
    return [...storageConfigs].sort((left, right) => {
      if (left.id === activeStorageId && right.id !== activeStorageId) return -1;
      if (right.id === activeStorageId && left.id !== activeStorageId) return 1;
      if (left.enabled !== right.enabled) return left.enabled ? -1 : 1;
      return left.name.localeCompare(right.name);
    });
  }, [storageConfigs, activeStorageId]);

  const pathSegments = useMemo(() => {
    if (!currentPath) return [];
    return currentPath.split('/').filter(Boolean);
  }, [currentPath]);

  const directories = useMemo(
    () => items.filter((item) => item.entryType === 'directory'),
    [items]
  );

  const normalizedQuery = useMemo(() => searchQuery.trim().toLowerCase(), [searchQuery]);

  const filteredItems = useMemo(() => {
    if (!normalizedQuery) return items;
    return items.filter((item) => {
      const byName = item.name.toLowerCase().includes(normalizedQuery);
      const byPath = item.path.toLowerCase().includes(normalizedQuery);
      return byName || byPath;
    });
  }, [items, normalizedQuery]);

  const isFilteringLocally = normalizedQuery.length > 0;
  const resolvedTotalItemCount = useMemo(() => {
    if (isFilteringLocally) {
      return filteredItems.length;
    }
    const exactTotal = typeof totalItemCount === 'number' ? totalItemCount : 0;
    return Math.max(exactTotal, items.length);
  }, [filteredItems.length, isFilteringLocally, items.length, totalItemCount]);

  const directoryTotalItemCount = useMemo(() => {
    const exactTotal = typeof totalItemCount === 'number' ? totalItemCount : 0;
    return Math.max(exactTotal, items.length);
  }, [items.length, totalItemCount]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(resolvedTotalItemCount / pageSize)),
    [pageSize, resolvedTotalItemCount]
  );

  const loadedPages = useMemo(
    () => Math.max(1, Math.ceil((isFilteringLocally ? filteredItems.length : items.length) / pageSize)),
    [filteredItems.length, isFilteringLocally, items.length, pageSize]
  );

  const pagedItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }, [filteredItems, currentPage, pageSize]);

  const {
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
  } = useCloudStorageViewer({
    items,
    selectedStorageId,
    currentPath,
    storageRevision,
    fileMetadataByUrl,
    failedPreviewUrlsRef
  });

  useEffect(() => {
    closeViewerRef.current = closeViewer;
  }, [closeViewer]);

  const hasSelectableItems = filteredItems.length > 0;
  const visibleSelectedCount = useMemo(
    () => filteredItems.reduce((count, item) => (selectedPaths.has(item.path) ? count + 1 : count), 0),
    [filteredItems, selectedPaths]
  );

  useEffect(() => {
    setCurrentPage(1);
    setPageNavigationLoading(false);
  }, [selectedStorageId, currentPath, normalizedQuery, pageSize]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  useEffect(() => {
    failedPreviewUrlsRef.current.clear();
  }, [selectedStorageId, storageRevision]);

  const handleBreadcrumbClick = useCallback((index: number) => {
    if (!selectedStorageId) return;
    if (index < 0) {
      void loadPath(selectedStorageId, '');
      return;
    }
    const targetPath = pathSegments.slice(0, index + 1).join('/');
    void loadPath(selectedStorageId, targetPath);
  }, [selectedStorageId, loadPath, pathSegments]);

  const handleSelectStorage = useCallback((storageId: string) => {
    setSelectedStorageId(storageId);
  }, [setSelectedStorageId]);

  const toggleSelectItem = useCallback((path: string) => {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, [setSelectedPaths]);

  const handleBulkSelectAction = useCallback(() => {
    if (filteredItems.length === 0) return;

    const visiblePaths = filteredItems.map((item) => item.path);
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      const visibleSelectedCount = visiblePaths.reduce(
        (count, path) => (next.has(path) ? count + 1 : count),
        0
      );

      if (visibleSelectedCount === 0) {
        visiblePaths.forEach((path) => next.add(path));
        return next;
      }

      visiblePaths.forEach((path) => {
        if (next.has(path)) {
          next.delete(path);
        } else {
          next.add(path);
        }
      });
      return next;
    });
  }, [filteredItems, setSelectedPaths]);

  const handleCopyUrl = useCallback(async (item: StorageBrowseItem) => {
    if (!item.url) {
      setError('This file has no public URL.');
      return;
    }
    try {
      await navigator.clipboard.writeText(item.url);
      showSuccess(`URL copied: ${item.name}`);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to copy URL');
    }
  }, [showSuccess, setError]);

  const handleViewItem = useCallback((item: StorageBrowseItem) => {
    if (item.entryType === 'directory') {
      openDirectory(item.path);
      return;
    }
    const kind = getFileKind(item);
    if (kind !== 'image' && kind !== 'video') {
      setError('Carousel preview only supports image and video files.');
      return;
    }
    if (buildStoragePreviewCandidates(item, storageRevision).length === 0) {
      setError('This file has no preview source.');
      return;
    }
    openViewer(item.path);
  }, [openDirectory, openViewer, setError, storageRevision]);

  const openUploadPicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleUploadFiles = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (files.length === 0) return;
    await uploadFiles(files);
  }, [uploadFiles]);

  const handleSearchQueryChange = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode);
  }, []);

  const handlePageSizeChange = useCallback((nextPageSize: number) => {
    setPageSize(nextPageSize);
  }, []);

  const navigateToPage = useCallback(async (requestedPage: number) => {
    const safePage = Math.min(totalPages, Math.max(1, requestedPage));
    if (safePage === currentPage || pageNavigationLoading) {
      return;
    }

    setPageNavigationLoading(true);
    try {
      let resolvedPage = safePage;
      if (!isFilteringLocally) {
        const loadedCount = await ensureItemsLoaded(safePage * pageSize);
        const reachablePages = Math.max(1, Math.ceil(loadedCount / pageSize));
        resolvedPage = Math.min(safePage, reachablePages);
      }
      setCurrentPage(resolvedPage);
    } finally {
      setPageNavigationLoading(false);
    }
  }, [currentPage, ensureItemsLoaded, isFilteringLocally, pageNavigationLoading, pageSize, totalPages]);

  const handlePrevPage = useCallback(() => {
    void navigateToPage(currentPage - 1);
  }, [currentPage, navigateToPage]);

  const handlePageChange = useCallback((page: number) => {
    void navigateToPage(page);
  }, [navigateToPage]);

  const handleNextPage = useCallback(() => {
    void navigateToPage(currentPage + 1);
  }, [currentPage, navigateToPage]);

  const handleLoadMore = useCallback(() => {
    if (!selectedStorageId || !nextCursor || pageNavigationLoading) return;
    void loadPath(selectedStorageId, currentPath, nextCursor, true);
  }, [selectedStorageId, currentPath, nextCursor, loadPath, pageNavigationLoading]);

  const canBrowse = !!selectedStorageId && !!selectedStorage?.enabled;
  const actionDisabled = loading || loadingMore || busyAction || pageNavigationLoading;
  const showNoStorageConfig = storageConfigs.length === 0;
  const showSelectStorageHint = !showNoStorageConfig && !selectedStorageId;
  const showDisabledStorageHint = !!selectedStorageId && !selectedStorage?.enabled;
  const showLoadingDirectory = canBrowse && loading && items.length === 0;
  const showBrowseError = canBrowse && !loading && !!browseError;
  const showUnsupportedHint = canBrowse && !loading && !browseError && !supported;
  const showEmptyDirectoryHint = canBrowse && !loading && !browseError && supported && items.length === 0;
  const showNoSearchResultHint =
    canBrowse && !loading && !browseError && supported && items.length > 0 && filteredItems.length === 0;
  const showFileList = canBrowse && !browseError && supported && filteredItems.length > 0;

  const sidebarContent = (
    <CloudStorageSidebar
      storageName={storageName}
      selectedStorageName={selectedStorage?.name}
      provider={provider}
      selectedProvider={selectedStorage?.provider}
      orderedStorageConfigs={orderedStorageConfigs}
      selectedStorageId={selectedStorageId}
      activeStorageId={activeStorageId}
      currentPath={currentPath}
      directories={directories}
      onSelectStorage={handleSelectStorage}
      onClickRoot={() => handleBreadcrumbClick(-1)}
      onOpenDirectory={openDirectory}
    />
  );

  const mainContent = (
    <div className="h-full flex flex-col relative">
      <CloudStorageHeaderToolbar
        currentPath={currentPath}
        pathSegments={pathSegments}
        canBrowse={canBrowse}
        hasSelectableItems={hasSelectableItems}
        hasVisibleSelection={visibleSelectedCount > 0}
        selectedCount={selectedPaths.size}
        actionDisabled={actionDisabled}
        searchQuery={searchQuery}
        viewMode={viewMode}
        loading={loading}
        loadingMore={loadingMore}
        onBreadcrumbClick={handleBreadcrumbClick}
        onBulkSelectAction={handleBulkSelectAction}
        onBatchDownload={handleBatchDownload}
        onBatchDelete={handleBatchDelete}
        onSearchQueryChange={handleSearchQueryChange}
        onViewModeChange={handleViewModeChange}
        onOpenUploadPicker={openUploadPicker}
        onRefresh={refreshCurrentPath}
        onClose={onClose}
      />

      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleUploadFiles}
      />

      {uploadProgress && (
        <div className="px-4 md:px-6 py-2 border-b border-slate-800 bg-slate-900/70 text-xs text-slate-300">
          {`Uploading... ${uploadProgress.done}/${uploadProgress.total}`}
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="px-4 md:px-6 py-2 border-b border-amber-700/50 bg-amber-950/40 text-xs text-amber-100"
        >
          {actionError}
        </div>
      )}

      <CloudStorageBrowseContent
        showNoStorageConfig={showNoStorageConfig}
        showSelectStorageHint={showSelectStorageHint}
        showDisabledStorageHint={showDisabledStorageHint}
        showLoadingDirectory={showLoadingDirectory}
        showBrowseError={showBrowseError}
        error={browseError}
        showUnsupportedHint={showUnsupportedHint}
        message={message}
        showEmptyDirectoryHint={showEmptyDirectoryHint}
        showNoSearchResultHint={showNoSearchResultHint}
        showFileList={showFileList}
        viewMode={viewMode}
        pagedItems={pagedItems}
        selectedPaths={selectedPaths}
        onToggleSelectItem={toggleSelectItem}
        onViewItem={handleViewItem}
        onDownloadItem={handleDownloadItem}
        onCopyUrl={handleCopyUrl}
        onRenameItem={handleRenameItem}
        onDeleteItem={handleDeleteItem}
        fileMetadataByUrl={fileMetadataByUrl}
        failedPreviewUrlsRef={failedPreviewUrlsRef}
        storageRevision={storageRevision}
        suspendPreviewLoading={isViewerOpen}
        autoLoadCursor={!isFilteringLocally && currentPage === loadedPages && !pageNavigationLoading ? nextCursor : null}
        loadingMore={loadingMore}
        onAutoLoadMore={handleLoadMore}
      />

      {showFileList && (
        <CloudStoragePaginationFooter
          filteredItemCount={filteredItems.length}
          loadedItemCount={items.length}
          displayTotalItemCount={resolvedTotalItemCount}
          directoryTotalItemCount={directoryTotalItemCount}
          isFilteringLocally={isFilteringLocally}
          currentPage={currentPage}
          totalPages={totalPages}
          pageSize={pageSize}
          loading={loadingMore || pageNavigationLoading}
          onPageSizeChange={handlePageSizeChange}
          onPageChange={handlePageChange}
          onPrevPage={handlePrevPage}
          onNextPage={handleNextPage}
        />
      )}

      <CloudStorageViewerOverlay
        isOpen={isViewerOpen}
        currentViewerFile={currentViewerFile}
        currentViewerKind={currentViewerKind}
        currentViewerMetadata={currentViewerMetadata}
        currentViewerImageSrc={currentViewerImageSrc}
        currentViewerImageExhausted={currentViewerImageExhausted}
        currentViewerVideoSrc={currentViewerVideoSrc}
        viewerFiles={viewerFiles}
        viewerIndex={viewerIndex}
        goViewerPrev={goViewerPrev}
        goViewerNext={goViewerNext}
        selectViewerIndex={selectViewerIndex}
        handleViewerPreviewError={handleViewerPreviewError}
        onDownloadItem={handleDownloadItem}
        onCopyUrl={handleCopyUrl}
        failedPreviewUrlsRef={failedPreviewUrlsRef}
        storageRevision={storageRevision}
        onClose={closeViewer}
      />
    </div>
  );

  return (
    <>
      <GenViewLayout
        isMobileHistoryOpen={isMobileHistoryOpen}
        setIsMobileHistoryOpen={setIsMobileHistoryOpen}
        sidebarTitle="Cloud Storage"
        sidebarHeaderIcon={<Cloud size={14} />}
        sidebar={sidebarContent}
        main={mainContent}
        hideSessionSwitcher
      />
      {actionDialog}
    </>
  );
};

export default CloudStorageView;

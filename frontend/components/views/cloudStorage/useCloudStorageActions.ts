import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import {
  batchDeleteCloudStorageItems,
  browseCloudStoragePath,
  deleteCloudStorageItem,
  prepareCloudStorageDownload,
  renameCloudStorageItem,
  startPreparedCloudStorageDownload,
  uploadCloudStorageFiles
} from './cloudStorageActionService';
import {
  StorageBrowseItem,
  StorageConfig,
  StorageFileMetadataItem
} from '../../../types/storage';

function normalizeTotalCount(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return null;
  }
  return Math.max(0, Math.trunc(value));
}

export interface UseCloudStorageActionsOptions {
  activeStorageId: string | null;
  storageConfigs: StorageConfig[];
  onBeforeLoadPath?: () => void;
  onActionNotice?: (message: string) => void;
  confirmDelete: (item: StorageBrowseItem) => boolean | Promise<boolean>;
  confirmBatchDelete: (items: StorageBrowseItem[]) => boolean | Promise<boolean>;
  promptRename: (item: StorageBrowseItem) => string | null | Promise<string | null>;
}

export interface UseCloudStorageActionsResult {
  selectedStorageId: string | null;
  setSelectedStorageId: Dispatch<SetStateAction<string | null>>;
  currentPath: string;
  items: StorageBrowseItem[];
  loading: boolean;
  loadingMore: boolean;
  browseError: string | null;
  error: string | null;
  setError: Dispatch<SetStateAction<string | null>>;
  supported: boolean;
  message: string | null;
  nextCursor: string | null;
  totalItemCount: number | null;
  storageName: string;
  provider: string;
  storageRevision: number | null;
  selectedPaths: Set<string>;
  setSelectedPaths: Dispatch<SetStateAction<Set<string>>>;
  busyAction: boolean;
  uploadProgress: { done: number; total: number } | null;
  fileMetadataByUrl: Record<string, StorageFileMetadataItem>;
  requestedMetadataUrlsRef: MutableRefObject<Set<string>>;
  loadPath: (storageId: string, path: string, cursor?: string, append?: boolean) => Promise<void>;
  openDirectory: (path: string) => void;
  refreshCurrentPath: () => void;
  ensureItemsLoaded: (minimumItemCount: number) => Promise<number>;
  handleDeleteItem: (item: StorageBrowseItem) => Promise<void>;
  handleRenameItem: (item: StorageBrowseItem) => Promise<void>;
  handleBatchDelete: () => Promise<void>;
  handleDownloadItem: (item: StorageBrowseItem) => Promise<void>;
  handleBatchDownload: () => Promise<void>;
  uploadFiles: (files: File[]) => Promise<void>;
}

export function useCloudStorageActions({
  activeStorageId,
  storageConfigs,
  onBeforeLoadPath,
  onActionNotice,
  confirmDelete,
  confirmBatchDelete,
  promptRename
}: UseCloudStorageActionsOptions): UseCloudStorageActionsResult {
  const [selectedStorageId, setSelectedStorageId] = useState<string | null>(activeStorageId);
  const [currentPath, setCurrentPath] = useState('');
  const [items, setItems] = useState<StorageBrowseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [browseError, setBrowseError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [supported, setSupported] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [totalItemCount, setTotalItemCount] = useState<number | null>(null);
  const [storageName, setStorageName] = useState<string>('');
  const [provider, setProvider] = useState<string>('');
  const [storageRevision, setStorageRevision] = useState<number | null>(null);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [busyAction, setBusyAction] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null);
  const [fileMetadataByUrl, setFileMetadataByUrl] = useState<Record<string, StorageFileMetadataItem>>({});
  const requestedMetadataUrlsRef = useRef<Set<string>>(new Set());
  const itemsRef = useRef<StorageBrowseItem[]>([]);
  const nextCursorRef = useRef<string | null>(null);
  const currentPathRef = useRef(currentPath);
  const selectedStorageIdRef = useRef<string | null>(selectedStorageId);
  const appendLoadPromiseRef = useRef<Promise<void> | null>(null);

  const selectedStorage = useMemo(
    () => storageConfigs.find((config) => config.id === selectedStorageId) || null,
    [storageConfigs, selectedStorageId]
  );

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    nextCursorRef.current = nextCursor;
  }, [nextCursor]);

  useEffect(() => {
    currentPathRef.current = currentPath;
  }, [currentPath]);

  useEffect(() => {
    selectedStorageIdRef.current = selectedStorageId;
  }, [selectedStorageId]);

  const applyStorageRevision = useCallback((nextRevision?: number | null) => {
    if (typeof nextRevision !== 'number' || !Number.isFinite(nextRevision) || nextRevision < 0) return;
    setStorageRevision((prev) => {
      if (prev === null) return nextRevision;
      return nextRevision > prev ? nextRevision : prev;
    });
  }, []);

  const removeItemsFromLocalState = useCallback((removedItems: StorageBrowseItem[]) => {
    if (removedItems.length === 0) return;

    const removedPaths = new Set(removedItems.map((item) => item.path));
    const removedUrls = removedItems
      .map((item) => String(item.url || '').trim())
      .filter(Boolean);

    setItems((prev) => prev.filter((item) => !removedPaths.has(item.path)));
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      removedPaths.forEach((path) => next.delete(path));
      return next;
    });
    setTotalItemCount((prev) => (prev === null ? prev : Math.max(0, prev - removedPaths.size)));
    if (removedUrls.length > 0) {
      setFileMetadataByUrl((prev) => {
        const next = { ...prev };
        removedUrls.forEach((url) => {
          delete next[url];
          requestedMetadataUrlsRef.current.delete(url);
        });
        return next;
      });
    }
  }, []);

  const loadPath = useCallback(async (
    storageId: string,
    path: string,
    cursor?: string,
    append: boolean = false
  ) => {
    if (append && appendLoadPromiseRef.current) {
      await appendLoadPromiseRef.current;
      return;
    }

    const requestPromise = (async () => {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setBrowseError(null);
        setError(null);
        setMessage(null);
        setSelectedPaths(new Set());
        onBeforeLoadPath?.();
      }

      try {
        const browseResult = await browseCloudStoragePath(storageId, path, cursor, 200);
        if (browseResult.success === false) {
          if (append) {
            setError(browseResult.errorMessage);
          } else {
            itemsRef.current = [];
            nextCursorRef.current = null;
            currentPathRef.current = '';
            setBrowseError(browseResult.errorMessage);
            setItems([]);
            setNextCursor(null);
            setTotalItemCount(null);
          }
          return;
        }

        const { response, metadataPatch, metadataUrls } = browseResult;
        applyStorageRevision(response.storageRevision);
        setBrowseError(null);
        setSupported(response.supported);
        setMessage(response.message || null);
        setStorageName(response.storageName || '');
        setProvider(response.provider || '');
        currentPathRef.current = response.path || '';
        nextCursorRef.current = response.nextCursor || null;
        setCurrentPath(currentPathRef.current);
        setNextCursor(nextCursorRef.current);
        setTotalItemCount((prev) => {
          const nextTotalCount = normalizeTotalCount(response.totalCount);
          if (nextTotalCount === null) {
            return append ? prev : null;
          }
          return nextTotalCount;
        });
        const nextItems = append ? [...itemsRef.current, ...response.items] : response.items;
        itemsRef.current = nextItems;
        setItems(nextItems);

        metadataUrls.forEach((url) => {
          requestedMetadataUrlsRef.current.add(url);
        });

        if (metadataUrls.length > 0) {
          setFileMetadataByUrl((prev) => ({ ...prev, ...metadataPatch }));
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    })();

    if (append) {
      appendLoadPromiseRef.current = requestPromise;
    }

    try {
      await requestPromise;
    } finally {
      if (append && appendLoadPromiseRef.current === requestPromise) {
        appendLoadPromiseRef.current = null;
      }
    }
  }, [applyStorageRevision, onBeforeLoadPath]);

  useEffect(() => {
    if (selectedStorageId && storageConfigs.some((config) => config.id === selectedStorageId)) {
      return;
    }
    const nextId =
      (activeStorageId && storageConfigs.some((config) => config.id === activeStorageId) ? activeStorageId : null) ||
      storageConfigs.find((config) => config.enabled)?.id ||
      storageConfigs[0]?.id ||
      null;
    setSelectedStorageId(nextId);
  }, [selectedStorageId, activeStorageId, storageConfigs]);

  useEffect(() => {
    itemsRef.current = [];
    nextCursorRef.current = null;
    currentPathRef.current = '';
    setItems([]);
    setCurrentPath('');
    setBrowseError(null);
    setError(null);
    setSupported(true);
    setMessage(null);
    setNextCursor(null);
    setTotalItemCount(null);
    setSelectedPaths(new Set());
    setStorageName(selectedStorage?.name || '');
    setProvider(selectedStorage?.provider || '');
    appendLoadPromiseRef.current = null;
    requestedMetadataUrlsRef.current.clear();
    setFileMetadataByUrl({});
    setStorageRevision(null);

    if (!selectedStorageId) {
      return;
    }
    if (!selectedStorage?.enabled) {
      setSupported(false);
      setMessage('Selected storage is disabled. Enable it in Settings > Storage first.');
      return;
    }
    void loadPath(selectedStorageId, '');
  }, [selectedStorageId, selectedStorage, loadPath]);

  const openDirectory = useCallback((path: string) => {
    if (!selectedStorageId) return;
    void loadPath(selectedStorageId, path);
  }, [selectedStorageId, loadPath]);

  const refreshCurrentPath = useCallback(() => {
    if (!selectedStorageId) return;
    void loadPath(selectedStorageId, currentPath);
  }, [selectedStorageId, currentPath, loadPath]);

  const ensureItemsLoaded = useCallback(async (minimumItemCount: number) => {
    const targetCount = Math.max(0, Math.trunc(minimumItemCount));
    if (targetCount === 0) {
      return itemsRef.current.length;
    }

    while (itemsRef.current.length < targetCount) {
      const storageId = selectedStorageIdRef.current;
      const cursor = nextCursorRef.current;
      if (!storageId || !cursor) {
        break;
      }

      const previousCount = itemsRef.current.length;
      await loadPath(storageId, currentPathRef.current, cursor, true);

      if (!nextCursorRef.current) {
        break;
      }
      if (itemsRef.current.length <= previousCount && nextCursorRef.current === cursor) {
        break;
      }
    }
    return itemsRef.current.length;
  }, [loadPath]);

  const handleDeleteItem = useCallback(async (item: StorageBrowseItem) => {
    if (!selectedStorageId) return;
    const confirmed = await confirmDelete(item);
    if (!confirmed) return;

    setBusyAction(true);
    setError(null);
    try {
      const mutationResult = await deleteCloudStorageItem(selectedStorageId, item);
      if (mutationResult.success === false) {
        setError(mutationResult.errorMessage);
        return;
      }
      applyStorageRevision(mutationResult.storageRevision);
      if (mutationResult.noticeMessage) {
        onActionNotice?.(mutationResult.noticeMessage);
      }
      if (nextCursor) {
        await loadPath(selectedStorageId, currentPath);
      } else {
        removeItemsFromLocalState([item]);
      }
    } finally {
      setBusyAction(false);
    }
  }, [selectedStorageId, currentPath, nextCursor, loadPath, applyStorageRevision, confirmDelete, onActionNotice, removeItemsFromLocalState]);

  const handleRenameItem = useCallback(async (item: StorageBrowseItem) => {
    if (!selectedStorageId) return;
    const nextName = await promptRename(item);
    if (nextName === null) return;
    const newName = nextName.trim();
    if (!newName || newName === item.name) return;

    setBusyAction(true);
    setError(null);
    try {
      const mutationResult = await renameCloudStorageItem(selectedStorageId, item, newName);
      if (mutationResult.success === false) {
        setError(mutationResult.errorMessage);
        return;
      }
      applyStorageRevision(mutationResult.storageRevision);
      if (mutationResult.noticeMessage) {
        onActionNotice?.(mutationResult.noticeMessage);
      }
      await loadPath(selectedStorageId, currentPath);
    } finally {
      setBusyAction(false);
    }
  }, [selectedStorageId, currentPath, loadPath, applyStorageRevision, promptRename, onActionNotice]);

  const handleBatchDelete = useCallback(async () => {
    if (!selectedStorageId || selectedPaths.size === 0) return;

    const selectedItems = items.filter((item) => selectedPaths.has(item.path));
    if (selectedItems.length === 0) return;
    const confirmed = await confirmBatchDelete(selectedItems);
    if (!confirmed) return;

    setBusyAction(true);
    setError(null);
    try {
      const batchResult = await batchDeleteCloudStorageItems(selectedStorageId, selectedItems);
      if (!batchResult.success) {
        setError(batchResult.errorMessage);
        return;
      }

      applyStorageRevision(batchResult.storageRevision);
      const removedItems = batchResult.removedItems || [];
      if (nextCursor && removedItems.length > 0) {
        await loadPath(selectedStorageId, currentPath);
      } else {
        removeItemsFromLocalState(removedItems);
      }
      if (batchResult.errorMessage) {
        setError(batchResult.errorMessage);
      } else if (batchResult.noticeMessage) {
        onActionNotice?.(batchResult.noticeMessage);
      }
    } finally {
      setBusyAction(false);
    }
  }, [selectedStorageId, selectedPaths, items, currentPath, nextCursor, loadPath, applyStorageRevision, confirmBatchDelete, onActionNotice, removeItemsFromLocalState]);

  const runDownload = useCallback(async (downloadItems: StorageBrowseItem[]) => {
    if (!selectedStorageId || downloadItems.length === 0) return;

    setBusyAction(true);
    setError(null);
    try {
      const response = await prepareCloudStorageDownload(selectedStorageId, downloadItems);
      await startPreparedCloudStorageDownload(response.downloadUrl, response.fileName);

      const noticeSegments = [`Download started: ${response.fileName}`];
      if (response.skippedCount > 0) {
        noticeSegments.push(`skipped ${response.skippedCount} item(s)`);
      }
      onActionNotice?.(noticeSegments.join(' · '));
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to prepare download');
    } finally {
      setBusyAction(false);
    }
  }, [selectedStorageId, onActionNotice]);

  const handleDownloadItem = useCallback(async (item: StorageBrowseItem) => {
    await runDownload([item]);
  }, [runDownload]);

  const handleBatchDownload = useCallback(async () => {
    if (selectedPaths.size === 0) return;
    const downloadItems = items.filter((item) => selectedPaths.has(item.path));
    await runDownload(downloadItems);
  }, [items, runDownload, selectedPaths]);

  const uploadFiles = useCallback(async (files: File[]) => {
    const uploadList = Array.isArray(files) ? files : [];
    if (!selectedStorageId || uploadList.length === 0) return;

    setBusyAction(true);
    setError(null);
    setUploadProgress({ done: 0, total: uploadList.length });

    try {
      const uploadResult = await uploadCloudStorageFiles({
        files: uploadList,
        storageId: selectedStorageId,
        onProgress: setUploadProgress,
        onStorageRevision: applyStorageRevision
      });

      if (uploadResult.errorMessage) {
        setError(uploadResult.errorMessage);
      } else if (uploadResult.noticeMessage) {
        onActionNotice?.(uploadResult.noticeMessage);
      }

      await loadPath(selectedStorageId, currentPath);
    } finally {
      setUploadProgress(null);
      setBusyAction(false);
    }
  }, [selectedStorageId, currentPath, loadPath, applyStorageRevision, onActionNotice]);

  return {
    selectedStorageId,
    setSelectedStorageId,
    currentPath,
    items,
    loading,
    loadingMore,
    browseError,
    error,
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
    requestedMetadataUrlsRef,
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
  };
}

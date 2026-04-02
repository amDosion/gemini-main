// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useCloudStorageActions } from './useCloudStorageActions';
import type {
  StorageBatchDeleteResult,
  StorageBrowseItem,
  StorageBrowseResponse,
  StorageConfig,
  StorageItemMutationResult,
  StorageUploadResult
} from '../../../types/storage';

const {
  browseStorageMock,
  deleteStorageItemMock,
  renameStorageItemMock,
  batchDeleteStorageItemsMock,
  uploadStorageFileMock
} = vi.hoisted(() => ({
  browseStorageMock: vi.fn(),
  deleteStorageItemMock: vi.fn(),
  renameStorageItemMock: vi.fn(),
  batchDeleteStorageItemsMock: vi.fn(),
  uploadStorageFileMock: vi.fn()
}));

vi.mock('../../../services/db', () => ({
  db: {
    browseStorage: browseStorageMock,
    deleteStorageItem: deleteStorageItemMock,
    renameStorageItem: renameStorageItemMock,
    batchDeleteStorageItems: batchDeleteStorageItemsMock,
    uploadStorageFile: uploadStorageFileMock
  }
}));

const STORAGE_CONFIGS: StorageConfig[] = [{
  id: 'storage-1',
  name: 'Local Storage',
  provider: 'local',
  enabled: true,
  config: {},
  createdAt: 1,
  updatedAt: 1
}];

const createBrowseResponse = (
  items: StorageBrowseItem[],
  overrides: Partial<StorageBrowseResponse> = {}
): StorageBrowseResponse => ({
  storageId: 'storage-1',
  storageName: 'Local Storage',
  provider: 'local',
  path: '',
  supported: true,
  items,
  totalCount: items.length,
  hasMore: false,
  nextCursor: null,
  ...overrides
});

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const renderActionsHook = async (overrides: {
  activeStorageId?: string | null;
  storageConfigs?: StorageConfig[];
  onBeforeLoadPath?: () => void;
  onActionNotice?: (message: string) => void;
  confirmDelete?: (item: StorageBrowseItem) => boolean | Promise<boolean>;
  confirmBatchDelete?: (items: StorageBrowseItem[]) => boolean | Promise<boolean>;
  promptRename?: (item: StorageBrowseItem) => string | null | Promise<string | null>;
} = {}) => {
  const onActionNotice = overrides.onActionNotice ?? vi.fn();
  const confirmDelete = overrides.confirmDelete ?? vi.fn().mockReturnValue(true);
  const confirmBatchDelete = overrides.confirmBatchDelete ?? vi.fn().mockReturnValue(true);
  const promptRename = overrides.promptRename ?? vi.fn().mockReturnValue(null);
  const hook = renderHook(() =>
    useCloudStorageActions({
      activeStorageId: overrides.activeStorageId ?? 'storage-1',
      storageConfigs: overrides.storageConfigs ?? STORAGE_CONFIGS,
      onBeforeLoadPath: overrides.onBeforeLoadPath,
      onActionNotice,
      confirmDelete,
      confirmBatchDelete,
      promptRename
    })
  );
  await waitFor(() => {
    expect(browseStorageMock).toHaveBeenCalledTimes(1);
  });
  await waitFor(() => {
    expect(hook.result.current.loading).toBe(false);
  });
  return {
    ...hook,
    onActionNotice,
    confirmDelete,
    confirmBatchDelete,
    promptRename
  };
};

describe('useCloudStorageActions', () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    browseStorageMock.mockReset();
    deleteStorageItemMock.mockReset();
    renameStorageItemMock.mockReset();
    batchDeleteStorageItemsMock.mockReset();
    uploadStorageFileMock.mockReset();
  });

  it('deletes a single item successfully and updates local items without rebrowse', async () => {
    const item: StorageBrowseItem = {
      name: 'photo.png',
      path: '/photo.png',
      entryType: 'file',
      url: 'https://cdn.example.com/photo.png'
    };
    const deleteDeferred = createDeferred<StorageItemMutationResult>();

    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse([item]))
      .mockResolvedValueOnce(createBrowseResponse([]));
    deleteStorageItemMock.mockReturnValueOnce(deleteDeferred.promise);

    const confirmDelete = vi.fn().mockReturnValue(true);
    const { result, onActionNotice } = await renderActionsHook({ confirmDelete });

    let deletePromise!: Promise<void>;
    act(() => {
      deletePromise = result.current.handleDeleteItem(item);
    });

    await waitFor(() => {
      expect(result.current.busyAction).toBe(true);
    });
    expect(result.current.error).toBeNull();
    expect(onActionNotice).not.toHaveBeenCalled();

    await act(async () => {
      deleteDeferred.resolve({ success: true, storageRevision: 2 });
      await deletePromise;
    });

    await waitFor(() => {
      expect(result.current.busyAction).toBe(false);
    });
    expect(onActionNotice).toHaveBeenCalledWith('Deleted: photo.png');
    expect(result.current.error).toBeNull();
    expect(result.current.items).toEqual([]);
    expect(deleteStorageItemMock).toHaveBeenCalledWith(
      'storage-1',
      '/photo.png',
      false,
      'https://cdn.example.com/photo.png'
    );
    expect(browseStorageMock).toHaveBeenCalledTimes(1);
    expect(confirmDelete).toHaveBeenCalledWith(item);
  });

  it('tracks exact total count from browse and decrements it after a local delete', async () => {
    const item: StorageBrowseItem = {
      name: 'photo.png',
      path: '/photo.png',
      entryType: 'file',
      url: 'https://cdn.example.com/photo.png'
    };

    browseStorageMock.mockResolvedValueOnce(createBrowseResponse([item], {
      totalCount: 732
    }));
    deleteStorageItemMock.mockResolvedValueOnce({
      success: true,
      storageRevision: 2
    });

    const { result } = await renderActionsHook();

    expect(result.current.totalItemCount).toBe(732);

    await act(async () => {
      await result.current.handleDeleteItem(item);
    });

    expect(result.current.totalItemCount).toBe(731);
    expect(result.current.items).toEqual([]);
    expect(browseStorageMock).toHaveBeenCalledTimes(1);
  });

  it('sets error when single-item deletion fails', async () => {
    const item: StorageBrowseItem = {
      name: 'locked.txt',
      path: '/locked.txt',
      entryType: 'file',
      url: null
    };

    browseStorageMock.mockResolvedValueOnce(createBrowseResponse([item]));
    deleteStorageItemMock.mockResolvedValueOnce({
      success: false,
      message: 'Permission denied'
    });

    const confirmDelete = vi.fn().mockReturnValue(true);
    const { result, onActionNotice } = await renderActionsHook({ confirmDelete });

    await act(async () => {
      await result.current.handleDeleteItem(item);
    });

    expect(result.current.error).toBe('Permission denied');
    expect(onActionNotice).not.toHaveBeenCalled();
    expect(result.current.busyAction).toBe(false);
    expect(browseStorageMock).toHaveBeenCalledTimes(1);
    expect(confirmDelete).toHaveBeenCalledWith(item);
  });

  it('renames an item successfully and refreshes items', async () => {
    const item: StorageBrowseItem = {
      name: 'draft.md',
      path: '/draft.md',
      entryType: 'file',
      url: null
    };
    const renamedItem: StorageBrowseItem = {
      ...item,
      name: 'final.md',
      path: '/final.md'
    };

    const promptRename = vi.fn().mockReturnValue('final.md');
    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse([item]))
      .mockResolvedValueOnce(createBrowseResponse([renamedItem]));
    renameStorageItemMock.mockResolvedValueOnce({
      success: true,
      storageRevision: 5
    });

    const { result, onActionNotice } = await renderActionsHook({ promptRename });

    await act(async () => {
      await result.current.handleRenameItem(item);
    });

    expect(renameStorageItemMock).toHaveBeenCalledWith('storage-1', '/draft.md', 'final.md', false);
    expect(onActionNotice).toHaveBeenCalledWith('Renamed to: final.md');
    expect(result.current.error).toBeNull();
    expect(result.current.items[0]?.name).toBe('final.md');
    expect(result.current.busyAction).toBe(false);
    expect(browseStorageMock).toHaveBeenCalledTimes(2);
    expect(promptRename).toHaveBeenCalledWith(item);
  });

  it('keeps failed items visible after a partial batch delete without rebrowsing', async () => {
    const first: StorageBrowseItem = {
      name: 'a.txt',
      path: '/a.txt',
      entryType: 'file',
      url: 'https://cdn.example.com/a.txt'
    };
    const second: StorageBrowseItem = {
      name: 'folder',
      path: '/folder',
      entryType: 'directory',
      url: null
    };
    const batchResult: StorageBatchDeleteResult = {
      success: true,
      total: 2,
      successCount: 1,
      failureCount: 1,
      results: [{ success: true }, { success: false, message: 'in use' }],
      storageRevision: 7
    };

    browseStorageMock.mockResolvedValueOnce(createBrowseResponse([first, second]));
    batchDeleteStorageItemsMock.mockResolvedValueOnce(batchResult);

    const confirmBatchDelete = vi.fn().mockReturnValue(true);
    const { result, onActionNotice } = await renderActionsHook({ confirmBatchDelete });

    act(() => {
      result.current.setSelectedPaths(new Set(['/a.txt', '/folder']));
    });

    await act(async () => {
      await result.current.handleBatchDelete();
    });

    expect(batchDeleteStorageItemsMock).toHaveBeenCalledWith('storage-1', [
      { path: '/a.txt', isDirectory: false, fileUrl: 'https://cdn.example.com/a.txt' },
      { path: '/folder', isDirectory: true, fileUrl: undefined }
    ]);
    expect(result.current.error).toBe('Deleted 1/2. Some items failed.');
    expect(onActionNotice).not.toHaveBeenCalled();
    expect(result.current.selectedPaths.has('/a.txt')).toBe(false);
    expect(result.current.selectedPaths.has('/folder')).toBe(true);
    expect(result.current.busyAction).toBe(false);
    expect(result.current.items).toEqual([second]);
    expect(browseStorageMock).toHaveBeenCalledTimes(1);
    expect(confirmBatchDelete).toHaveBeenCalledWith([first, second]);
  });

  it('rebrowses the current path after a delete when unseen pages remain behind nextCursor', async () => {
    const pageOne: StorageBrowseItem = {
      name: 'page-1.txt',
      path: '/page-1.txt',
      entryType: 'file',
      url: 'https://cdn.example.com/page-1.txt'
    };
    const pageTwo: StorageBrowseItem = {
      name: 'page-2.txt',
      path: '/page-2.txt',
      entryType: 'file',
      url: 'https://cdn.example.com/page-2.txt'
    };
    const batchResult: StorageBatchDeleteResult = {
      success: true,
      total: 1,
      successCount: 1,
      failureCount: 0,
      results: [{ success: true }],
      storageRevision: 3
    };

    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse([pageOne], {
        path: '/paged',
        hasMore: true,
        nextCursor: 'cursor-2',
        storageRevision: 1
      }))
      .mockResolvedValueOnce(createBrowseResponse([pageTwo], {
        path: '/paged',
        hasMore: false,
        nextCursor: null,
        storageRevision: 2
      }));
    batchDeleteStorageItemsMock.mockResolvedValueOnce(batchResult);

    const confirmBatchDelete = vi.fn().mockReturnValue(true);
    const { result, onActionNotice } = await renderActionsHook({ confirmBatchDelete });

    expect(result.current.currentPath).toBe('/paged');
    expect(result.current.nextCursor).toBe('cursor-2');

    act(() => {
      result.current.setSelectedPaths(new Set(['/page-1.txt']));
    });

    await act(async () => {
      await result.current.handleBatchDelete();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.items).toEqual([pageTwo]);
    expect(result.current.nextCursor).toBeNull();
    expect(onActionNotice).toHaveBeenCalledWith('Deleted 1 items.');
    expect(browseStorageMock).toHaveBeenCalledTimes(2);
    expect(browseStorageMock).toHaveBeenNthCalledWith(2, 'storage-1', '/paged', undefined, 200);
    expect(confirmBatchDelete).toHaveBeenCalledWith([pageOne]);
  });

  it('tracks upload progress and refreshes items after upload', async () => {
    const fileA = new File(['a'], 'a.txt', { type: 'text/plain' });
    const fileB = new File(['b'], 'b.txt', { type: 'text/plain' });
    const uploadedItems: StorageBrowseItem[] = [
      { name: 'a.txt', path: '/a.txt', entryType: 'file', url: 'https://cdn.example.com/a.txt' },
      { name: 'b.txt', path: '/b.txt', entryType: 'file', url: 'https://cdn.example.com/b.txt' }
    ];
    const firstUpload = createDeferred<StorageUploadResult>();
    const secondUpload = createDeferred<StorageUploadResult>();

    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse([]))
      .mockResolvedValueOnce(createBrowseResponse(uploadedItems));
    uploadStorageFileMock
      .mockReturnValueOnce(firstUpload.promise)
      .mockReturnValueOnce(secondUpload.promise);

    const { result, onActionNotice } = await renderActionsHook();

    let uploadPromise!: Promise<void>;
    act(() => {
      uploadPromise = result.current.uploadFiles([fileA, fileB]);
    });

    await waitFor(() => {
      expect(result.current.busyAction).toBe(true);
      expect(result.current.uploadProgress).toEqual({ done: 0, total: 2 });
    });

    await act(async () => {
      firstUpload.resolve({ success: true, storageRevision: 9 });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.uploadProgress).toEqual({ done: 1, total: 2 });
    });

    await act(async () => {
      secondUpload.resolve({ success: true, storageRevision: 10 });
      await uploadPromise;
    });

    await waitFor(() => {
      expect(result.current.uploadProgress).toBeNull();
      expect(result.current.busyAction).toBe(false);
    });

    expect(result.current.error).toBeNull();
    expect(onActionNotice).toHaveBeenCalledWith('Uploaded 2 file(s).');
    expect(uploadStorageFileMock).toHaveBeenNthCalledWith(1, fileA, 'storage-1', 180000);
    expect(uploadStorageFileMock).toHaveBeenNthCalledWith(2, fileB, 'storage-1', 180000);
    expect(result.current.items).toEqual(uploadedItems);
    expect(browseStorageMock).toHaveBeenCalledTimes(2);
  });

  it('hydrates metadata cache from browse response metadata', async () => {
    const withMetadata: StorageBrowseItem = {
      name: 'cover.png',
      path: '/cover.png',
      entryType: 'file',
      url: ' https://cdn.example.com/cover.png ',
      metadata: {
        url: '',
        source: 'cache',
        contentType: 'image/png'
      }
    };
    const unavailableMetadata: StorageBrowseItem = {
      name: 'missing.png',
      path: '/missing.png',
      entryType: 'file',
      url: 'https://cdn.example.com/missing.png',
      metadata: {
        url: '',
        source: 'unavailable'
      }
    };

    browseStorageMock.mockResolvedValueOnce(createBrowseResponse([withMetadata, unavailableMetadata]));

    const { result } = await renderActionsHook();

    expect(result.current.fileMetadataByUrl).toEqual({
      'https://cdn.example.com/cover.png': {
        ...withMetadata.metadata,
        url: 'https://cdn.example.com/cover.png'
      }
    });
  });

  it('appends items when loading more with nextCursor', async () => {
    const firstPageItems: StorageBrowseItem[] = [
      { name: '1.txt', path: '/1.txt', entryType: 'file', url: 'https://cdn.example.com/1.txt' }
    ];
    const secondPageItems: StorageBrowseItem[] = [
      { name: '2.txt', path: '/2.txt', entryType: 'file', url: 'https://cdn.example.com/2.txt' }
    ];
    const loadMoreDeferred = createDeferred<StorageBrowseResponse>();

    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse(firstPageItems, {
        hasMore: true,
        nextCursor: 'cursor-2',
        storageRevision: 1
      }))
      .mockReturnValueOnce(loadMoreDeferred.promise);

    const { result } = await renderActionsHook();

    expect(result.current.items).toEqual(firstPageItems);
    expect(result.current.nextCursor).toBe('cursor-2');

    let loadMorePromise!: Promise<void>;
    act(() => {
      loadMorePromise = result.current.loadPath('storage-1', '', result.current.nextCursor || undefined, true);
    });

    await waitFor(() => {
      expect(result.current.loadingMore).toBe(true);
    });

    await act(async () => {
      loadMoreDeferred.resolve(createBrowseResponse(secondPageItems, {
        hasMore: false,
        nextCursor: null,
        storageRevision: 2
      }));
      await loadMorePromise;
    });

    expect(result.current.loadingMore).toBe(false);
    expect(result.current.items).toEqual([...firstPageItems, ...secondPageItems]);
    expect(result.current.nextCursor).toBeNull();
    expect(result.current.storageRevision).toBe(2);
    expect(browseStorageMock).toHaveBeenNthCalledWith(2, 'storage-1', '', 'cursor-2', 200);
  });

  it('loads more pages until the requested item count is available', async () => {
    const firstPageItems = Array.from({ length: 200 }, (_, index) => ({
      name: `${index + 1}.txt`,
      path: `/${index + 1}.txt`,
      entryType: 'file' as const,
      url: `https://cdn.example.com/${index + 1}.txt`
    }));
    const secondPageItems = Array.from({ length: 180 }, (_, index) => ({
      name: `${index + 201}.txt`,
      path: `/${index + 201}.txt`,
      entryType: 'file' as const,
      url: `https://cdn.example.com/${index + 201}.txt`
    }));

    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse(firstPageItems, {
        hasMore: true,
        nextCursor: 'cursor-2',
        totalCount: 380
      }))
      .mockResolvedValueOnce(createBrowseResponse(secondPageItems, {
        hasMore: false,
        nextCursor: null,
        totalCount: 380
      }));

    const { result } = await renderActionsHook();

    let loadedCount = 0;
    await act(async () => {
      loadedCount = await result.current.ensureItemsLoaded(350);
    });

    expect(loadedCount).toBe(380);
    expect(result.current.items).toHaveLength(380);
    expect(result.current.totalItemCount).toBe(380);
    expect(result.current.nextCursor).toBeNull();
    expect(browseStorageMock).toHaveBeenCalledTimes(2);
    expect(browseStorageMock).toHaveBeenNthCalledWith(2, 'storage-1', '', 'cursor-2', 200);
  });

  it('stops paging after an append-page failure instead of retrying the same cursor forever', async () => {
    const firstPageItems = Array.from({ length: 200 }, (_, index) => ({
      name: `${index + 1}.txt`,
      path: `/${index + 1}.txt`,
      entryType: 'file' as const,
      url: `https://cdn.example.com/${index + 1}.txt`
    }));

    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse(firstPageItems, {
        hasMore: true,
        nextCursor: 'cursor-2',
        totalCount: 380
      }))
      .mockRejectedValueOnce(new Error('Transient browse failure'));

    const { result } = await renderActionsHook();

    let loadedCount = 0;
    await act(async () => {
      loadedCount = await result.current.ensureItemsLoaded(350);
    });

    expect(loadedCount).toBe(200);
    expect(result.current.items).toHaveLength(200);
    expect(result.current.nextCursor).toBe('cursor-2');
    expect(result.current.error).toBe('Transient browse failure');
    expect(browseStorageMock).toHaveBeenCalledTimes(2);
    expect(browseStorageMock).toHaveBeenNthCalledWith(2, 'storage-1', '', 'cursor-2', 200);
  });

  it('resets state and loads root data for the newly selected storage', async () => {
    const storageConfigs: StorageConfig[] = [
      STORAGE_CONFIGS[0],
      {
        id: 'storage-2',
        name: 'Archive Storage',
        provider: 'local',
        enabled: true,
        config: {},
        createdAt: 2,
        updatedAt: 2
      }
    ];

    const rootDirectory: StorageBrowseItem = {
      name: 'photos',
      path: '/photos',
      entryType: 'directory',
      url: null
    };
    const photoInDir: StorageBrowseItem = {
      name: 'p1.png',
      path: '/photos/p1.png',
      entryType: 'file',
      url: 'https://cdn.example.com/photos/p1.png'
    };
    const archiveItem: StorageBrowseItem = {
      name: 'archive.zip',
      path: '/archive.zip',
      entryType: 'file',
      url: 'https://cdn.example.com/archive.zip'
    };

    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse([rootDirectory], { path: '' }))
      .mockResolvedValueOnce(createBrowseResponse([photoInDir], { path: '/photos' }))
      .mockResolvedValueOnce(createBrowseResponse([archiveItem], {
        storageId: 'storage-2',
        storageName: 'Archive Storage',
        path: ''
      }));

    const { result } = await renderActionsHook({ storageConfigs });

    act(() => {
      result.current.openDirectory('/photos');
    });
    await waitFor(() => {
      expect(result.current.currentPath).toBe('/photos');
    });
    expect(result.current.items).toEqual([photoInDir]);

    act(() => {
      result.current.setSelectedPaths(new Set(['/photos/p1.png']));
    });
    expect(result.current.selectedPaths.size).toBe(1);

    act(() => {
      result.current.setSelectedStorageId('storage-2');
    });

    await waitFor(() => {
      expect(browseStorageMock).toHaveBeenCalledTimes(3);
    });
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.selectedStorageId).toBe('storage-2');
    expect(result.current.currentPath).toBe('');
    expect(result.current.items).toEqual([archiveItem]);
    expect(result.current.selectedPaths.size).toBe(0);
    expect(browseStorageMock).toHaveBeenNthCalledWith(2, 'storage-1', '/photos', undefined, 200);
    expect(browseStorageMock).toHaveBeenNthCalledWith(3, 'storage-2', '', undefined, 200);
  });

  it('updates storageRevision from browse responses and mutation responses without rollback', async () => {
    const item: StorageBrowseItem = {
      name: 'draft.md',
      path: '/draft.md',
      entryType: 'file',
      url: null
    };
    const renamedItem: StorageBrowseItem = {
      ...item,
      name: 'final.md',
      path: '/final.md'
    };

    const promptRename = vi.fn().mockReturnValue('final.md');
    browseStorageMock
      .mockResolvedValueOnce(createBrowseResponse([item], { storageRevision: 4 }))
      .mockResolvedValueOnce(createBrowseResponse([renamedItem], { storageRevision: 5 }));
    renameStorageItemMock.mockResolvedValueOnce({
      success: true,
      storageRevision: 6
    });

    const { result } = await renderActionsHook({ promptRename });

    expect(result.current.storageRevision).toBe(4);

    await act(async () => {
      await result.current.handleRenameItem(item);
    });

    expect(result.current.items).toEqual([renamedItem]);
    expect(result.current.storageRevision).toBe(6);
    expect(renameStorageItemMock).toHaveBeenCalledTimes(1);
    expect(browseStorageMock).toHaveBeenCalledTimes(2);
    expect(promptRename).toHaveBeenCalledWith(item);
  });
});

// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { StorageBrowseItem, StorageConfig } from '../../types/storage';

const {
  browseStorageMock,
  deleteStorageItemMock,
  renameStorageItemMock,
  batchDeleteStorageItemsMock,
  uploadStorageFileMock,
  prepareStorageDownloadMock,
  showSuccessMock
} = vi.hoisted(() => ({
  browseStorageMock: vi.fn(),
  deleteStorageItemMock: vi.fn(),
  renameStorageItemMock: vi.fn(),
  batchDeleteStorageItemsMock: vi.fn(),
  uploadStorageFileMock: vi.fn(),
  prepareStorageDownloadMock: vi.fn(),
  showSuccessMock: vi.fn()
}));

vi.mock('../../services/db', () => ({
  db: {
    browseStorage: browseStorageMock,
    deleteStorageItem: deleteStorageItemMock,
    renameStorageItem: renameStorageItemMock,
    batchDeleteStorageItems: batchDeleteStorageItemsMock,
    uploadStorageFile: uploadStorageFileMock,
    prepareStorageDownload: prepareStorageDownloadMock
  }
}));

vi.mock('../../contexts/ToastContext', () => ({
  useToastContext: () => ({
    showSuccess: showSuccessMock
  })
}));

vi.mock('../common/GenViewLayout', () => ({
  GenViewLayout: ({ sidebar, main }: { sidebar: React.ReactNode; main: React.ReactNode }) => (
    <div>
      <div>{sidebar}</div>
      <div>{main}</div>
    </div>
  )
}));

vi.mock('./cloudStorage/useCloudStorageDialogs', () => ({
  useCloudStorageDialogs: () => ({
    confirmDelete: vi.fn().mockReturnValue(true),
    confirmBatchDelete: vi.fn().mockReturnValue(true),
    promptRename: vi.fn().mockReturnValue(null),
    dialog: null
  })
}));

vi.mock('./cloudStorage/useCloudStorageViewer', () => ({
  useCloudStorageViewer: () => ({
    isViewerOpen: false,
    openViewer: vi.fn(),
    closeViewer: vi.fn(),
    viewerFiles: [],
    viewerIndex: 0,
    goViewerPrev: vi.fn(),
    goViewerNext: vi.fn(),
    selectViewerIndex: vi.fn(),
    currentViewerFile: null,
    currentViewerKind: null,
    currentViewerMetadata: null,
    currentViewerImageSrc: null,
    currentViewerImageExhausted: false,
    currentViewerVideoSrc: null,
    handleViewerPreviewError: vi.fn()
  })
}));

vi.mock('./cloudStorage/CloudStorageThumbnailCell', () => ({
  CloudStorageThumbnailCell: ({ item }: { item: StorageBrowseItem }) => (
    <div data-testid={`thumbnail-${item.path}`} />
  )
}));

import CloudStorageView from './CloudStorageView';

const STORAGE_CONFIGS: StorageConfig[] = [{
  id: 'storage-1',
  name: 'Local Storage',
  provider: 'local',
  enabled: true,
  config: {},
  createdAt: 1,
  updatedAt: 1
}];

const createBrowseItem = (
  name: string,
  path: string,
  overrides: Partial<StorageBrowseItem> = {}
): StorageBrowseItem => ({
  name,
  path,
  entryType: 'file',
  url: `https://cdn.example.com${path}`,
  ...overrides
});

const createBrowseResponse = (
  items: StorageBrowseItem[],
  overrides: Record<string, unknown> = {}
) => ({
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

const renderCloudStorageView = async () => {
  render(
    <CloudStorageView
      activeStorageId="storage-1"
      storageConfigs={STORAGE_CONFIGS}
      onClose={() => undefined}
    />
  );

  await waitFor(() => {
    expect(browseStorageMock).toHaveBeenCalledTimes(1);
  });
};

const getFirstEnabledButton = (name: RegExp) =>
  screen.getAllByRole('button', { name }).find((button) => !button.hasAttribute('disabled')) || null;

describe('CloudStorageView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps the directory visible after a partial batch delete action error', async () => {
    const first = createBrowseItem('a.txt', '/a.txt');
    const second = createBrowseItem('b.txt', '/b.txt');

    browseStorageMock.mockResolvedValueOnce(createBrowseResponse([first, second]));
    batchDeleteStorageItemsMock.mockResolvedValueOnce({
      success: true,
      total: 2,
      successCount: 1,
      failureCount: 1,
      results: [{ success: true }, { success: false, message: 'locked' }],
      storageRevision: 2
    });

    await renderCloudStorageView();

    expect(screen.getByText('a.txt')).toBeTruthy();
    expect(screen.getByText('b.txt')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /select all/i }));
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));

    await waitFor(() => {
      expect(batchDeleteStorageItemsMock).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByRole('alert').textContent).toContain('Deleted 1/2. Some items failed.');
    expect(screen.queryByText('a.txt')).toBeNull();
    expect(screen.getByText('b.txt')).toBeTruthy();
    expect(screen.queryByText('Current directory is empty.')).toBeNull();
  });

  it('keeps the directory visible after download preparation fails', async () => {
    const file = createBrowseItem('report.pdf', '/report.pdf');

    browseStorageMock.mockResolvedValueOnce(createBrowseResponse([file]));
    prepareStorageDownloadMock.mockRejectedValueOnce(new Error('Download preparation failed'));

    await renderCloudStorageView();

    expect(screen.getByText('report.pdf')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /select all/i }));
    fireEvent.click(getFirstEnabledButton(/^download$/i)!);

    await waitFor(() => {
      expect(prepareStorageDownloadMock).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByRole('alert').textContent).toContain('Download preparation failed');
    expect(screen.getByText('report.pdf')).toBeTruthy();
    expect(screen.queryByText('Current directory is empty.')).toBeNull();
  });
});

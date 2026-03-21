// @vitest-environment jsdom
import React from 'react';
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StorageBrowseItem } from '../../../types/storage';

const {
  cloudStorageFileListGridMock,
  cloudStorageThumbnailCellMock,
  useXhrImagePreviewMock
} = vi.hoisted(() => ({
  cloudStorageFileListGridMock: vi.fn(),
  cloudStorageThumbnailCellMock: vi.fn(),
  useXhrImagePreviewMock: vi.fn()
}));

vi.mock('./CloudStorageFileListGrid', () => ({
  CloudStorageFileListGrid: (props: unknown) => {
    cloudStorageFileListGridMock(props);
    return null;
  }
}));

vi.mock('./CloudStorageThumbnailCell', () => ({
  CloudStorageThumbnailCell: (props: unknown) => {
    cloudStorageThumbnailCellMock(props);
    return null;
  }
}));

vi.mock('./useXhrImagePreview', () => ({
  useXhrImagePreview: useXhrImagePreviewMock
}));

import { CloudStorageBrowseContent } from './CloudStorageBrowseContent';
import { CloudStorageViewerOverlay } from './CloudStorageViewerOverlay';
import { useCloudStorageViewer } from './useCloudStorageViewer';

const createFileItem = (
  name: string,
  path: string,
  overrides: Partial<StorageBrowseItem> = {}
): StorageBrowseItem => ({
  name,
  path,
  entryType: 'file',
  url: `https://cdn.example.com${path}`,
  previewUrl: `/api/storage/preview?url=${encodeURIComponent(`https://cdn.example.com${path}`)}`,
  ...overrides
});

const getLastThumbnailPropsForPath = (path: string) => {
  const matchingCalls = cloudStorageThumbnailCellMock.mock.calls
    .map(([props]) => props as {
      item: StorageBrowseItem;
      disableVideoPreview?: boolean;
    })
    .filter((props) => props.item.path === path);
  expect(matchingCalls.length).toBeGreaterThan(0);
  return matchingCalls.at(-1)!;
};

describe('useCloudStorageViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useXhrImagePreviewMock.mockReturnValue({
      src: 'blob:preview-image',
      exhausted: false,
      lastFailure: null
    });
  });

  it('keeps the viewer file set limited to previewable image and video items', async () => {
    const image = createFileItem('photo.png', '/photo.png');
    const video = createFileItem('clip.mp4', '/clip.mp4', { url: null });
    const document = createFileItem('notes.pdf', '/notes.pdf');
    const missingUrlVideo = createFileItem('offline.mp4', '/offline.mp4', {
      url: null,
      previewUrl: null
    });
    const unsafeVideo = createFileItem('unsafe.mp4', '/unsafe.mp4', {
      url: 'file:///tmp/unsafe.mp4',
      previewUrl: 'javascript:alert(1)'
    });
    const directory: StorageBrowseItem = {
      name: 'albums',
      path: '/albums',
      entryType: 'directory',
      url: null
    };

    const { result, rerender } = renderHook(
      ({ items }) =>
        useCloudStorageViewer({
          items,
          selectedStorageId: 'storage-1',
          currentPath: '',
          storageRevision: 7,
          fileMetadataByUrl: {},
          failedPreviewUrlsRef: { current: new Set<string>() }
        }),
      {
        initialProps: {
          items: [image, video, document, missingUrlVideo, unsafeVideo, directory]
        }
      }
    );

    expect(result.current.viewerFiles.map((item) => item.path)).toEqual([
      '/photo.png',
      '/clip.mp4'
    ]);

    act(() => {
      result.current.openViewer('/clip.mp4');
    });

    await waitFor(() => {
      expect(result.current.isViewerOpen).toBe(true);
      expect(result.current.currentViewerFile?.path).toBe('/clip.mp4');
      expect(result.current.currentViewerKind).toBe('video');
    });

    rerender({
      items: [document, directory]
    });

    await waitFor(() => {
      expect(result.current.isViewerOpen).toBe(false);
      expect(result.current.currentViewerFile).toBeNull();
    });

    expect(result.current.viewerFiles).toEqual([]);
  });
});

describe('CloudStorageViewerOverlay', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps far video thumbnails gated until the user moves near them', async () => {
    const viewerFiles = [
      createFileItem('clip-1.mp4', '/clip-1.mp4'),
      createFileItem('clip-2.mp4', '/clip-2.mp4'),
      createFileItem('clip-3.mp4', '/clip-3.mp4'),
      createFileItem('clip-4.mp4', '/clip-4.mp4'),
      createFileItem('clip-5.mp4', '/clip-5.mp4')
    ];

    render(
      <CloudStorageViewerOverlay
        isOpen
        currentViewerFile={viewerFiles[2]}
        currentViewerKind="video"
        currentViewerMetadata={undefined}
        currentViewerImageSrc={null}
        currentViewerImageExhausted={false}
        currentViewerVideoSrc={viewerFiles[2].previewUrl || viewerFiles[2].url || null}
        viewerFiles={viewerFiles}
        viewerIndex={2}
        goViewerPrev={() => undefined}
        goViewerNext={() => undefined}
        selectViewerIndex={() => undefined}
        handleViewerPreviewError={() => undefined}
        onDownloadItem={async () => undefined}
        onCopyUrl={async () => undefined}
        failedPreviewUrlsRef={{ current: new Set<string>() }}
        storageRevision={7}
        onClose={() => undefined}
      />
    );

    expect(getLastThumbnailPropsForPath('/clip-1.mp4').disableVideoPreview).toBe(true);
    expect(getLastThumbnailPropsForPath('/clip-2.mp4').disableVideoPreview).toBe(false);
    expect(getLastThumbnailPropsForPath('/clip-3.mp4').disableVideoPreview).toBe(false);
    expect(getLastThumbnailPropsForPath('/clip-4.mp4').disableVideoPreview).toBe(false);
    expect(getLastThumbnailPropsForPath('/clip-5.mp4').disableVideoPreview).toBe(true);

    fireEvent.mouseEnter(screen.getByTitle('clip-5.mp4'));

    await waitFor(() => {
      expect(getLastThumbnailPropsForPath('/clip-5.mp4').disableVideoPreview).toBe(false);
    });
  });
});

describe('CloudStorageBrowseContent', () => {
  let intersectionObserverInstances: Array<{
    callback: IntersectionObserverCallback;
    disconnect: ReturnType<typeof vi.fn>;
    observe: ReturnType<typeof vi.fn>;
  }>;

  beforeEach(() => {
    vi.clearAllMocks();
    intersectionObserverInstances = [];

    class MockIntersectionObserver {
      callback: IntersectionObserverCallback;
      observe = vi.fn();
      disconnect = vi.fn();

      constructor(callback: IntersectionObserverCallback) {
        this.callback = callback;
        intersectionObserverInstances.push({
          callback,
          disconnect: this.disconnect,
          observe: this.observe
        });
      }
    }

    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('forwards viewer-open preview suppression to the browse grid surface', () => {
    const pagedItems = [createFileItem('cover.png', '/cover.png')];

    render(
      <CloudStorageBrowseContent
        showNoStorageConfig={false}
        showSelectStorageHint={false}
        showDisabledStorageHint={false}
        showLoadingDirectory={false}
        showBrowseError={false}
        error={null}
        showUnsupportedHint={false}
        message={null}
        showEmptyDirectoryHint={false}
        showNoSearchResultHint={false}
        showFileList
        viewMode="list"
        pagedItems={pagedItems}
        selectedPaths={new Set<string>()}
        onToggleSelectItem={() => undefined}
        onViewItem={() => undefined}
        onDownloadItem={async () => undefined}
        onCopyUrl={async () => undefined}
        onRenameItem={async () => undefined}
        onDeleteItem={async () => undefined}
        fileMetadataByUrl={{}}
        failedPreviewUrlsRef={{ current: new Set<string>() }}
        storageRevision={7}
        suspendPreviewLoading
      />
    );

    expect(cloudStorageFileListGridMock).toHaveBeenCalled();
    const lastProps = cloudStorageFileListGridMock.mock.calls.at(-1)?.[0] as {
      suspendPreviewLoading?: boolean;
    };
    expect(lastProps.suspendPreviewLoading).toBe(true);
  });

  it('auto-loads at the sentinel and only fires once per cursor token', async () => {
    const onAutoLoadMore = vi.fn();
    const pagedItems = [createFileItem('cover.png', '/cover.png')];
    const baseProps = {
      showNoStorageConfig: false,
      showSelectStorageHint: false,
      showDisabledStorageHint: false,
      showLoadingDirectory: false,
      showBrowseError: false,
      error: null,
      showUnsupportedHint: false,
      message: null,
      showEmptyDirectoryHint: false,
      showNoSearchResultHint: false,
      showFileList: true,
      viewMode: 'list' as const,
      pagedItems,
      selectedPaths: new Set<string>(),
      onToggleSelectItem: vi.fn(),
      onViewItem: vi.fn(),
      onDownloadItem: vi.fn().mockResolvedValue(undefined),
      onCopyUrl: vi.fn().mockResolvedValue(undefined),
      onRenameItem: vi.fn().mockResolvedValue(undefined),
      onDeleteItem: vi.fn().mockResolvedValue(undefined),
      fileMetadataByUrl: {},
      failedPreviewUrlsRef: { current: new Set<string>() },
      storageRevision: 7,
      autoLoadCursor: 'cursor-2',
      loadingMore: false,
      onAutoLoadMore
    };

    const { rerender } = render(<CloudStorageBrowseContent {...baseProps} />);

    expect(intersectionObserverInstances).toHaveLength(1);

    act(() => {
      intersectionObserverInstances[0]?.callback(
        [{ isIntersecting: true, intersectionRatio: 1 } as IntersectionObserverEntry],
        {} as IntersectionObserver
      );
    });

    expect(onAutoLoadMore).toHaveBeenCalledTimes(1);

    rerender(
      <CloudStorageBrowseContent
        {...baseProps}
        viewMode="grid"
      />
    );

    act(() => {
      intersectionObserverInstances.at(-1)?.callback(
        [{ isIntersecting: true, intersectionRatio: 1 } as IntersectionObserverEntry],
        {} as IntersectionObserver
      );
    });

    expect(onAutoLoadMore).toHaveBeenCalledTimes(1);

    rerender(
      <CloudStorageBrowseContent
        {...baseProps}
        autoLoadCursor="cursor-3"
        viewMode="list"
      />
    );

    act(() => {
      intersectionObserverInstances.at(-1)?.callback(
        [{ isIntersecting: true, intersectionRatio: 1 } as IntersectionObserverEntry],
        {} as IntersectionObserver
      );
    });

    expect(onAutoLoadMore).toHaveBeenCalledTimes(2);
  });
});

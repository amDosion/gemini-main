// @vitest-environment jsdom
import React, { useCallback, useRef, useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StorageBrowseItem } from '../../../types/storage';

const { thumbnailRenderCounts } = vi.hoisted(() => ({
  thumbnailRenderCounts: new Map<string, number>(),
}));

vi.mock('./CloudStorageThumbnailCell', () => ({
  CloudStorageThumbnailCell: ({ item }: { item: StorageBrowseItem }) => {
    thumbnailRenderCounts.set(item.path, (thumbnailRenderCounts.get(item.path) ?? 0) + 1);
    return <div data-testid={`thumbnail-${item.path}`} />;
  },
}));

import { CloudStorageFileListGrid } from './CloudStorageFileListGrid';

const ITEMS: StorageBrowseItem[] = [
  {
    name: 'alpha.png',
    path: '/alpha.png',
    entryType: 'file',
    url: 'https://cdn.example.com/alpha.png',
    size: 100,
  },
  {
    name: 'bravo.png',
    path: '/bravo.png',
    entryType: 'file',
    url: 'https://cdn.example.com/bravo.png',
    size: 200,
  },
  {
    name: 'charlie.png',
    path: '/charlie.png',
    entryType: 'file',
    url: 'https://cdn.example.com/charlie.png',
    size: 300,
  },
];

const renderCountFor = (path: string) => thumbnailRenderCounts.get(path) ?? 0;

function CloudStorageGridHarness() {
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const failedPreviewUrlsRef = useRef(new Set<string>());

  const handleToggleSelectItem = useCallback((path: string) => {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleViewItem = useCallback(() => undefined, []);
  const handleDownloadItem = useCallback(async () => undefined, []);
  const handleCopyUrl = useCallback(async () => undefined, []);
  const handleRenameItem = useCallback(async () => undefined, []);
  const handleDeleteItem = useCallback(async () => undefined, []);

  return (
    <CloudStorageFileListGrid
      viewMode="grid"
      pagedItems={ITEMS}
      selectedPaths={selectedPaths}
      onToggleSelectItem={handleToggleSelectItem}
      onViewItem={handleViewItem}
      onDownloadItem={handleDownloadItem}
      onCopyUrl={handleCopyUrl}
      onRenameItem={handleRenameItem}
      onDeleteItem={handleDeleteItem}
      fileMetadataByUrl={{}}
      failedPreviewUrlsRef={failedPreviewUrlsRef}
      storageRevision={1}
      suspendPreviewLoading={false}
    />
  );
}

describe('CloudStorageFileListGrid row render cache', () => {
  afterEach(() => {
    cleanup();
    thumbnailRenderCounts.clear();
  });

  it('keeps unrelated grid cards from rerendering when opening actions or selecting one item', () => {
    render(<CloudStorageGridHarness />);

    expect(renderCountFor('/alpha.png')).toBe(1);
    expect(renderCountFor('/bravo.png')).toBe(1);
    expect(renderCountFor('/charlie.png')).toBe(1);

    fireEvent.click(screen.getAllByTitle('Actions')[0]);

    expect(renderCountFor('/alpha.png')).toBe(2);
    expect(renderCountFor('/bravo.png')).toBe(1);
    expect(renderCountFor('/charlie.png')).toBe(1);

    fireEvent.click(screen.getAllByTitle('Select')[1]);

    expect(renderCountFor('/alpha.png')).toBe(2);
    expect(renderCountFor('/bravo.png')).toBe(2);
    expect(renderCountFor('/charlie.png')).toBe(1);
  });
});

// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StorageBrowseItem } from '../../../types/storage';

const { useXhrImagePreviewMock } = vi.hoisted(() => ({
  useXhrImagePreviewMock: vi.fn(),
}));

vi.mock('./useXhrImagePreview', () => ({
  useXhrImagePreview: useXhrImagePreviewMock,
}));

import { CloudStorageThumbnailCell } from './CloudStorageThumbnailCell';

describe('CloudStorageThumbnailCell cache-safe preview rendering', () => {
  const recoverFromImageError = vi.fn();

  beforeEach(() => {
    recoverFromImageError.mockReturnValue(true);
    useXhrImagePreviewMock.mockReturnValue({
      src: 'blob:cloud-storage-preview',
      exhausted: false,
      lastFailure: null,
      recoverFromImageError,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('does not add native lazy loading to object-url image previews', () => {
    const item: StorageBrowseItem = {
      name: 'photo.png',
      path: '/photo.png',
      entryType: 'file',
      url: '/api/storage/local-files/2026/05/31/photo.png',
    };

    render(
      <CloudStorageThumbnailCell
        item={item}
        failedPreviewUrlsRef={{ current: new Set<string>() }}
        storageRevision={1}
      />
    );

    const preview = screen.getByAltText('photo.png');
    expect(preview.getAttribute('src')).toBe('blob:cloud-storage-preview');
    expect(preview.getAttribute('loading')).toBeNull();
  });

  it('delegates stale object-url load failures back to the shared preview cache hook', () => {
    const item: StorageBrowseItem = {
      name: 'photo.png',
      path: '/photo.png',
      entryType: 'file',
      url: '/api/storage/local-files/2026/05/31/photo.png',
    };

    render(
      <CloudStorageThumbnailCell
        item={item}
        failedPreviewUrlsRef={{ current: new Set<string>() }}
        storageRevision={1}
      />
    );

    fireEvent.error(screen.getByAltText('photo.png'));

    expect(recoverFromImageError).toHaveBeenCalledWith('blob:cloud-storage-preview');
  });
});

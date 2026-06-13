// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from '../common/CachedImage';
import ImageModal from './ImageModal';

const cachedImageProps: CachedImageProps[] = [];
const { downloadSourceUrlInBrowserMock } = vi.hoisted(() => ({
  downloadSourceUrlInBrowserMock: vi.fn(),
}));

vi.mock('../../services/downloadService', () => ({
  downloadSourceUrlInBrowser: downloadSourceUrlInBrowserMock,
}));

vi.mock('../common/CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageProps.push(props);
    return <img data-testid="modal-cached-image" src={props.src || ''} alt={props.alt || ''} />;
  },
}));

describe('ImageModal', () => {
  beforeEach(() => {
    cachedImageProps.length = 0;
    downloadSourceUrlInBrowserMock.mockReset();
    downloadSourceUrlInBrowserMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('renders the fullscreen preview through CachedImage so it reuses the shared media cache', () => {
    render(
      <ImageModal
        isOpen
        imageUrl="/api/storage/local-files/2026/05/31/fullscreen.png"
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId('modal-cached-image')).toBeTruthy();
    expect(cachedImageProps).toHaveLength(1);
    expect(cachedImageProps[0]).toMatchObject({
      src: '/api/storage/local-files/2026/05/31/fullscreen.png',
      source: {
        url: '/api/storage/local-files/2026/05/31/fullscreen.png',
        mimeType: 'image/png',
      },
    });
  });

  it('routes fullscreen image downloads through the shared guarded download service', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-11T08:00:00.000Z'));

    render(
      <ImageModal
        isOpen
        imageUrl="/api/storage/local-files/2026/05/31/fullscreen.png"
        onClose={vi.fn()}
      />
    );

    screen.getByRole('button', { name: 'Download' }).click();

    expect(downloadSourceUrlInBrowserMock).toHaveBeenCalledWith({
      sourceUrl: '/api/storage/local-files/2026/05/31/fullscreen.png',
      fileName: 'gemini-generated-1781164800000.png',
    });
  });

  it('does not render unsafe fullscreen image URLs', () => {
    render(<ImageModal isOpen imageUrl="javascript:alert(1)" onClose={vi.fn()} />);

    expect(screen.queryByTestId('modal-cached-image')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Download' })).toBeNull();
    expect(cachedImageProps).toHaveLength(0);
  });

  it('allows same-origin blob fullscreen previews', () => {
    const blobUrl = `blob:${window.location.origin}/local-preview`;

    render(<ImageModal isOpen imageUrl={blobUrl} onClose={vi.fn()} />);

    expect(screen.getByTestId('modal-cached-image')).toBeTruthy();
    expect(cachedImageProps[0]).toMatchObject({
      src: blobUrl,
      source: {
        url: blobUrl,
        mimeType: 'image/png',
      },
    });
  });
});

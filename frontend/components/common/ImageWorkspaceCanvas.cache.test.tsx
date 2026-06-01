// @vitest-environment jsdom

import React from 'react';
import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Image as ImageIcon } from 'lucide-react';
import type { Attachment } from '../../types/types';
import type { CachedImageProps } from './CachedImage';
import { ImageWorkspaceCanvas } from './ImageWorkspaceCanvas';

const cachedImageProps: CachedImageProps[] = [];

vi.mock('./CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageProps.push(props);
    const imageProps = props.src ? { src: props.src } : {};
    return <img data-testid="workspace-cached-image" {...imageProps} alt={props.alt || ''} />;
  },
}));

const baseProps = {
  loadingState: 'idle',
  isCompareMode: false,
  originalImageUrl: null,
  zoom: 1,
  isDragging: false,
  canvasStyle: {},
  onWheel: vi.fn(),
  onMouseDown: vi.fn(),
  onMouseMove: vi.fn(),
  onMouseUp: vi.fn(),
  onZoomIn: vi.fn(),
  onZoomOut: vi.fn(),
  onReset: vi.fn(),
  headerIcon: ImageIcon,
  headerIconClassName: 'text-pink-400',
  headerLabel: 'Workspace',
  spinnerClassName: 'border-pink-500/30 border-t-pink-500',
  loadingText: { default: 'Loading' },
  compareConfig: {
    beforeLabel: 'Before',
    afterLabel: 'After',
    accentColor: 'pink' as const,
  },
  controlsAccentColor: 'pink' as const,
  emptyState: <div>No image</div>,
};

describe('ImageWorkspaceCanvas', () => {
  beforeEach(() => {
    cachedImageProps.length = 0;
  });

  afterEach(() => {
    cleanup();
  });

  it('uses durable attachment urls for the active carousel image and thumbnails', () => {
    const attachments: Attachment[] = [
      {
        id: 'att-main',
        name: 'main.png',
        mimeType: 'image/png',
        url: 'blob:https://gemini.dicry.cn:18443/revoked-main',
        tempUrl: 'data:image/png;base64,abc',
        cloudUrl: '/api/storage/local-files/2026/05/31/main.png',
      },
      {
        id: 'att-second',
        name: 'second.png',
        mimeType: 'image/png',
        cloudUrl: '/api/storage/local-files/2026/05/31/second.png',
      },
    ];
    const renderThumbnails = vi.fn(() => <div data-testid="workspace-thumbnails" />);

    render(
      <ImageWorkspaceCanvas
        {...baseProps}
        activeAttachments={attachments}
        activeImageUrl={null}
        carousel={{
          carouselIndex: 0,
          onCarouselPrev: vi.fn(),
          onCarouselNext: vi.fn(),
          onCarouselSelect: vi.fn(),
          getStableUrl: () => '/api/storage/local-files/2026/05/31/fallback.png',
          renderThumbnails,
        }}
      />
    );

    expect(cachedImageProps[0]).toMatchObject({
      src: '/api/storage/local-files/2026/05/31/main.png',
      source: expect.objectContaining({
        id: 'att-main',
        url: '/api/storage/local-files/2026/05/31/main.png',
        cloudUrl: '/api/storage/local-files/2026/05/31/main.png',
      }),
    });
    expect(renderThumbnails).toHaveBeenCalledWith(
      expect.objectContaining({
        items: expect.arrayContaining([
          expect.objectContaining({
            id: 'att-main',
            url: '/api/storage/local-files/2026/05/31/main.png',
            thumbUrl: '/api/storage/local-files/2026/05/31/main.png',
          }),
        ]),
      })
    );
  });

  it('renders file-only active attachments through CachedImage without asking callers for a blob url', () => {
    const file = new File(['local-canvas'], 'local-canvas.png', { type: 'image/png' });
    const attachments: Attachment[] = [
      {
        id: 'att-local-canvas',
        name: 'local-canvas.png',
        mimeType: 'image/png',
        file,
      },
    ];
    const getStableUrl = vi.fn(() => 'blob:should-not-be-created-by-canvas');

    render(
      <ImageWorkspaceCanvas
        {...baseProps}
        activeAttachments={attachments}
        activeImageUrl={null}
        carousel={{
          carouselIndex: 0,
          onCarouselPrev: vi.fn(),
          onCarouselNext: vi.fn(),
          onCarouselSelect: vi.fn(),
          getStableUrl,
        }}
      />
    );

    expect(cachedImageProps[0]).toMatchObject({
      src: null,
      source: expect.objectContaining({
        id: 'att-local-canvas',
        attachmentId: 'att-local-canvas',
        file,
        mimeType: 'image/png',
        name: 'local-canvas.png',
      }),
    });
    expect(getStableUrl).not.toHaveBeenCalled();
  });

  it('passes file-only carousel thumbnails to shared CachedImage sources instead of prebuilding blob urls', () => {
    const file = new File(['local-thumb'], 'local-thumb.png', { type: 'image/png' });
    const attachments: Attachment[] = [
      {
        id: 'att-local-thumb-a',
        name: 'local-thumb-a.png',
        mimeType: 'image/png',
        file,
      },
      {
        id: 'att-local-thumb-b',
        name: 'local-thumb-b.png',
        mimeType: 'image/png',
        cloudUrl: '/api/storage/local-files/2026/06/01/thumb-b.png',
      },
    ];
    const getStableUrl = vi.fn(() => 'blob:should-not-be-created-for-thumb');
    const renderThumbnails = vi.fn(() => <div data-testid="workspace-thumbnails" />);

    render(
      <ImageWorkspaceCanvas
        {...baseProps}
        activeAttachments={attachments}
        activeImageUrl={null}
        carousel={{
          carouselIndex: 0,
          onCarouselPrev: vi.fn(),
          onCarouselNext: vi.fn(),
          onCarouselSelect: vi.fn(),
          getStableUrl,
          renderThumbnails,
        }}
      />
    );

    expect(renderThumbnails).toHaveBeenCalledWith(
      expect.objectContaining({
        items: expect.arrayContaining([
          expect.objectContaining({
            id: 'att-local-thumb-a',
            url: null,
            thumbUrl: null,
            source: expect.objectContaining({
              id: 'att-local-thumb-a',
              file,
              mimeType: 'image/png',
            }),
          }),
        ]),
      })
    );
    expect(getStableUrl).not.toHaveBeenCalled();
  });

  it('does not reuse a stale activeImageUrl for the selected file-only carousel item', () => {
    const file = new File(['selected-file-only'], 'selected-file-only.png', { type: 'image/png' });
    const attachments: Attachment[] = [
      {
        id: 'att-selected-file-only',
        name: 'selected-file-only.png',
        mimeType: 'image/png',
        file,
      },
      {
        id: 'att-durable-neighbor',
        name: 'neighbor.png',
        mimeType: 'image/png',
        cloudUrl: '/api/storage/local-files/2026/06/01/neighbor.png',
      },
    ];

    render(
      <ImageWorkspaceCanvas
        {...baseProps}
        activeAttachments={attachments}
        activeImageUrl="/api/storage/local-files/2026/06/01/previous.png"
        carousel={{
          carouselIndex: 0,
          onCarouselPrev: vi.fn(),
          onCarouselNext: vi.fn(),
          onCarouselSelect: vi.fn(),
          getStableUrl: vi.fn(),
        }}
      />
    );

    expect(cachedImageProps[0]).toMatchObject({
      src: null,
      source: expect.objectContaining({
        id: 'att-selected-file-only',
        file,
        url: undefined,
      }),
    });
  });

  it('keeps local-blob active urls internal for file-backed canvas images', () => {
    const file = new File(['local-blob-canvas'], 'local-blob-canvas.png', {
      type: 'image/png',
    });
    const attachments: Attachment[] = [
      {
        id: 'att-local-blob-canvas',
        name: 'local-blob-canvas.png',
        mimeType: 'image/png',
        file,
      },
    ];

    render(
      <ImageWorkspaceCanvas
        {...baseProps}
        activeAttachments={attachments}
        activeImageUrl="local-blob:att-local-blob-canvas"
        carousel={{
          carouselIndex: 0,
          onCarouselPrev: vi.fn(),
          onCarouselNext: vi.fn(),
          onCarouselSelect: vi.fn(),
          getStableUrl: vi.fn(),
        }}
      />
    );

    expect(cachedImageProps[0]).toMatchObject({
      src: null,
      source: expect.objectContaining({
        id: 'att-local-blob-canvas',
        attachmentId: 'att-local-blob-canvas',
        file,
        url: undefined,
      }),
    });
    expect(document.querySelector('button[title="下载"]')).toBeNull();
  });
});

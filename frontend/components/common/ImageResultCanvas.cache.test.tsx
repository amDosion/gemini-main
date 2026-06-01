// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Attachment } from '../../types/types';
import type { CachedImageProps } from './CachedImage';
import { ImageResultCanvas } from './ImageResultCanvas';

const cachedImageProps: CachedImageProps[] = [];

vi.mock('./CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageProps.push(props);
    const imageProps = props.src ? { src: props.src } : {};
    return (
      <img
        data-testid="result-cached-image"
        {...imageProps}
        alt={props.alt || ''}
      />
    );
  },
}));

const baseCanvas = {
  zoom: 1,
  isDragging: false,
  canvasStyle: {},
  handleWheel: vi.fn(),
  handleMouseDown: vi.fn(),
  handleMouseMove: vi.fn(),
  handleMouseUp: vi.fn(),
  handleZoomIn: vi.fn(),
  handleZoomOut: vi.fn(),
  handleReset: vi.fn(),
};

describe('ImageResultCanvas cache-safe rendering', () => {
  beforeEach(() => {
    cachedImageProps.length = 0;
  });

  afterEach(() => {
    cleanup();
  });

  it('renders file-only result images through CachedImage without a raw URL', () => {
    const file = new File(['result-file-only'], 'result-file-only.png', {
      type: 'image/png',
    });
    const displayImages: Attachment[] = [
      {
        id: 'att-result-file-only',
        name: 'result-file-only.png',
        mimeType: 'image/png',
        file,
      },
    ];

    render(
      <ImageResultCanvas
        loadingState="idle"
        isBatchError={false}
        displayImages={displayImages}
        carouselItems={[
          {
            id: 'att-result-file-only',
            source: displayImages[0],
            alt: '缩略图 1',
          },
        ]}
        carouselIndex={0}
        handleCarouselPrev={vi.fn()}
        handleCarouselNext={vi.fn()}
        handleCarouselSelect={vi.fn()}
        onImageClick={vi.fn()}
        canvas={baseCanvas}
        mode="image-gen"
        accentColor="emerald"
        spinnerColorClass="border-emerald-500/30 border-t-emerald-500"
        spinnerBadgeText="GEN"
        spinnerBadgeColorClass="text-emerald-400"
        accentIconClass="text-emerald-400"
        carouselAccentTone="emerald"
        emptyState={<div>No image</div>}
      />
    );

    expect(screen.queryByText('No image')).toBeNull();
    expect(cachedImageProps[0]).toMatchObject({
      src: null,
      source: expect.objectContaining({
        id: 'att-result-file-only',
        attachmentId: 'att-result-file-only',
        file,
        url: undefined,
      }),
    });
    expect(document.querySelector('button[title="下载"]')).toBeNull();
  });
});

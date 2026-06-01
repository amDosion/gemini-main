// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from './CachedImage';
import { ImageCarouselThumbnails } from './ImageCarouselControls';

vi.mock('./CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => (
    <img
      data-testid="carousel-cached-thumb"
      src={props.src || ''}
      alt={props.alt || ''}
      onError={props.onError}
    />
  ),
}));

describe('ImageCarouselThumbnails cache recovery', () => {
  afterEach(() => {
    cleanup();
  });

  it('clears a failed thumbnail placeholder when the item receives a new durable url', () => {
    const { rerender } = render(
      <ImageCarouselThumbnails
        items={[
          { id: 'item-1', thumbUrl: 'blob:https://gemini.dicry.cn:18443/revoked-thumb' },
          { id: 'item-2', thumbUrl: '/api/storage/local-files/second.png' },
        ]}
        currentIndex={0}
        onSelect={vi.fn()}
      />
    );

    fireEvent.error(screen.getByAltText('缩略图 1'));
    expect(screen.queryByAltText('缩略图 1')).toBeNull();

    rerender(
      <ImageCarouselThumbnails
        items={[
          { id: 'item-1', thumbUrl: '/api/storage/local-files/first.png' },
          { id: 'item-2', thumbUrl: '/api/storage/local-files/second.png' },
        ]}
        currentIndex={0}
        onSelect={vi.fn()}
      />
    );

    expect(screen.getByAltText('缩略图 1')).toHaveAttribute(
      'src',
      '/api/storage/local-files/first.png'
    );
  });
});

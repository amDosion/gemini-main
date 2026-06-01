// @vitest-environment jsdom
import React from 'react';
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from './CachedImage';

const cachedImageSpy = vi.fn();

vi.mock('./CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageSpy(props);
    return <img alt={props.alt || ''} src={props.src || ''} data-testid="cached-compare-image" />;
  },
}));

import { ImageCompare } from './ImageCompare';

describe('ImageCompare cache integration', () => {
  afterEach(() => {
    cleanup();
    cachedImageSpy.mockClear();
  });

  it('renders compare sizer and both image layers through CachedImage', () => {
    render(
      <ImageCompare
        beforeImage="/api/storage/local-files/source.png"
        afterImage="/api/storage/local-files/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />
    );

    expect(cachedImageSpy).toHaveBeenCalledTimes(3);
    expect(cachedImageSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        src: '/api/storage/local-files/result.png',
        source: expect.objectContaining({ url: '/api/storage/local-files/result.png' }),
        'data-testid': 'image-compare-sizer',
      })
    );
    expect(cachedImageSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        src: '/api/storage/local-files/result.png',
        source: expect.objectContaining({ url: '/api/storage/local-files/result.png' }),
        alt: '编辑结果',
      })
    );
    expect(cachedImageSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        src: '/api/storage/local-files/source.png',
        source: expect.objectContaining({ url: '/api/storage/local-files/source.png' }),
        alt: '原图',
      })
    );
  });
});

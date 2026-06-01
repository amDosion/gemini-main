// @vitest-environment jsdom

import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { CachedImageProps } from '../common/CachedImage';
import ImageModal from './ImageModal';

const cachedImageProps: CachedImageProps[] = [];

vi.mock('../common/CachedImage', () => ({
  CachedImage: (props: CachedImageProps) => {
    cachedImageProps.push(props);
    return <img data-testid="modal-cached-image" src={props.src || ''} alt={props.alt || ''} />;
  },
}));

describe('ImageModal', () => {
  beforeEach(() => {
    cachedImageProps.length = 0;
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
});

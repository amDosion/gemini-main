// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { mockUseCachedImageSrc } = vi.hoisted(() => ({
  mockUseCachedImageSrc: vi.fn(),
}));

vi.mock('../../hooks/useCachedImageSrc', () => ({
  useCachedImageSrc: mockUseCachedImageSrc,
}));

import { ImageCompare } from './ImageCompare';

describe('ImageCompare', () => {
  beforeEach(() => {
    mockUseCachedImageSrc.mockImplementation((source) => ({
      src: source?.url ? `blob:cached-${source.url}` : null,
      status: 'persistent-hit',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError: vi.fn(() => false),
    }));
  });

  afterEach(() => {
    cleanup();
    mockUseCachedImageSrc.mockReset();
  });

  it('updates the comparison divider while dragging', () => {
    const { container } = render(
      <ImageCompare
        beforeImage="/source.png"
        afterImage="/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />,
    );

    const compare = container.firstElementChild as HTMLElement;
    expect(compare).toBeInTheDocument();

    vi.spyOn(compare, 'getBoundingClientRect').mockReturnValue({
      left: 0,
      top: 0,
      width: 200,
      height: 200,
      right: 200,
      bottom: 200,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    Object.defineProperty(compare, 'setPointerCapture', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(compare, 'releasePointerCapture', {
      configurable: true,
      value: vi.fn(),
    });

    fireEvent.pointerDown(compare, { clientX: 50, pointerId: 1 });
    fireEvent.pointerMove(compare, { clientX: 150, pointerId: 1 });

    expect(compare.querySelector('div[style*="left: 75%"]')).toBeInTheDocument();
  });

  it('renders a sizing image so absolutely positioned compare layers have visible dimensions', () => {
    render(
      <ImageCompare
        beforeImage="/source.png"
        afterImage="/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />,
    );

    const sizer = document.querySelector('[data-testid="image-compare-sizer"]') as HTMLImageElement | null;

    expect(sizer).toBeInTheDocument();
    expect(sizer).toHaveAttribute('src', 'blob:cached-/result.png');
    expect(sizer).toHaveAttribute('aria-hidden', 'true');
  });

  it('uses the shared image cache for compare layer sources', () => {
    render(
      <ImageCompare
        beforeImage="/api/storage/local-files/source.png"
        afterImage="/api/storage/local-files/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />,
    );

    expect(mockUseCachedImageSrc).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/api/storage/local-files/source.png' }),
      expect.objectContaining({ fallbackSrc: '/api/storage/local-files/source.png' })
    );
    expect(mockUseCachedImageSrc).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/api/storage/local-files/result.png' }),
      expect.objectContaining({ fallbackSrc: '/api/storage/local-files/result.png' })
    );
    expect(screen.getByAltText('编辑结果')).toHaveAttribute(
      'src',
      'blob:cached-/api/storage/local-files/result.png'
    );
    expect(screen.getByAltText('原图')).toHaveAttribute(
      'src',
      'blob:cached-/api/storage/local-files/source.png'
    );
  });

  it('reports failed cached blob compare images back to the shared cache hook', () => {
    const recoverBefore = vi.fn(() => true);
    const recoverAfter = vi.fn(() => true);

    mockUseCachedImageSrc
      .mockReturnValueOnce({
        src: 'blob:compare-after-sizer',
        status: 'memory-hit',
        error: null,
        refresh: vi.fn(),
        recoverFromImageError: vi.fn(() => true),
      })
      .mockReturnValueOnce({
        src: 'blob:compare-after-revoked',
        status: 'memory-hit',
        error: null,
        refresh: vi.fn(),
        recoverFromImageError: recoverAfter,
      })
      .mockReturnValueOnce({
        src: 'blob:compare-before-revoked',
        status: 'memory-hit',
        error: null,
        refresh: vi.fn(),
        recoverFromImageError: recoverBefore,
      });

    render(
      <ImageCompare
        beforeImage="/api/storage/local-files/source.png"
        afterImage="/api/storage/local-files/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />,
    );

    fireEvent.error(screen.getByAltText('编辑结果'));
    fireEvent.error(screen.getByAltText('原图'));

    expect(recoverAfter).toHaveBeenCalledWith('blob:compare-after-revoked');
    expect(recoverBefore).toHaveBeenCalledWith('blob:compare-before-revoked');
  });

  it('adjusts the source image opacity with the opacity slider', () => {
    render(
      <ImageCompare
        beforeImage="/source.png"
        afterImage="/result.png"
        beforeLabel="原图"
        afterLabel="编辑结果"
      />,
    );

    fireEvent.change(screen.getByLabelText('原图透明度'), { target: { value: '45' } });

    expect(screen.getByTestId('image-compare-before-layer')).toHaveStyle({ opacity: '0.45' });
  });
});

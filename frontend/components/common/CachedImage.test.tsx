// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mediaCacheMock = vi.hoisted(() => ({
  releaseMediaObjectUrl: vi.fn(),
  retainMediaObjectUrl: vi.fn(),
}));

vi.mock('../../hooks/useCachedImageSrc', () => ({
  useCachedImageSrc: vi.fn(() => ({
    src: 'blob:cached-image',
    status: 'persistent-hit',
    error: null,
    refresh: vi.fn(),
    recoverFromImageError: vi.fn(() => false),
  })),
}));

vi.mock('../../services/mediaCache', () => ({
  releaseMediaObjectUrl: mediaCacheMock.releaseMediaObjectUrl,
  retainMediaObjectUrl: mediaCacheMock.retainMediaObjectUrl,
}));

import { CachedImage } from './CachedImage';
import { useCachedImageSrc } from '../../hooks/useCachedImageSrc';

describe('CachedImage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: 'blob:cached-image',
      status: 'persistent-hit',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError: vi.fn(() => false),
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('renders the cache-resolved src instead of the fallback url', () => {
    render(
      <CachedImage
        source={{
          attachmentId: 'att-1',
          url: '/api/storage/local-files/generated/a.png',
          mimeType: 'image/png',
        }}
        src="/api/storage/local-files/generated/a.png"
        alt="Cached result"
      />
    );

    expect(screen.getByAltText('Cached result').getAttribute('src')).toBe('blob:cached-image');
  });

  it('passes memory cache preference to the shared image cache hook', () => {
    render(
      <CachedImage
        source={{
          attachmentId: 'att-no-memory',
          url: '/api/storage/local-files/generated/no-memory.png',
          mimeType: 'image/png',
        }}
        src="/api/storage/local-files/generated/no-memory.png"
        preferMemoryCache={false}
        replaceCachedObjectUrl
        alt="No memory preference"
      />
    );

    expect(vi.mocked(useCachedImageSrc).mock.calls.at(-1)?.[1]).toMatchObject({
      preferMemoryCache: false,
      replaceCachedObjectUrl: true,
    });
  });

  it('retains the blob url that is actually assigned to the image element', () => {
    const { unmount } = render(
      <CachedImage
        source={{
          attachmentId: 'att-retain-rendered',
          url: '/api/storage/local-files/generated/retain-rendered.png',
          mimeType: 'image/png',
        }}
        src="/api/storage/local-files/generated/retain-rendered.png"
        alt="Retained rendered blob"
      />
    );

    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith('blob:cached-image');

    unmount();

    expect(mediaCacheMock.releaseMediaObjectUrl).toHaveBeenCalledWith('blob:cached-image');
  });

  it('does not render a raw temporary blob fallback after cache recovery fails', () => {
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: null,
      status: 'error',
      error: new Error('revoked blob'),
      refresh: vi.fn(),
      recoverFromImageError: vi.fn(() => false),
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-revoked',
          url: 'blob:https://gemini.dicry.cn:18443/revoked-preview',
          mimeType: 'image/png',
        }}
        src="blob:https://gemini.dicry.cn:18443/revoked-preview"
        alt="Revoked result"
      />
    );

    expect(screen.queryByAltText('Revoked result')).toBeNull();
  });

  it('falls back to a durable raw src when a cached blob url is revoked before lazy loading', () => {
    const recoverFromImageError = vi.fn(() => true);
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: 'blob:https://gemini.dicry.cn:18443/revoked-cached-thumbnail',
      status: 'persistent-hit',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError,
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-stable',
          url: '/public/generated/stable.png',
          mimeType: 'image/png',
        }}
        src="/public/generated/stable.png"
        loading="lazy"
        alt="Recoverable thumbnail"
      />
    );

    const image = screen.getByAltText('Recoverable thumbnail');
    expect(image.getAttribute('src')).toBe(
      'blob:https://gemini.dicry.cn:18443/revoked-cached-thumbnail'
    );

    fireEvent.error(image);

    expect(screen.getByAltText('Recoverable thumbnail').getAttribute('src')).toBe(
      '/public/generated/stable.png'
    );
    expect(recoverFromImageError).toHaveBeenCalledWith(
      'blob:https://gemini.dicry.cn:18443/revoked-cached-thumbnail'
    );
  });

  it('does not notify parent failure handlers for recoverable cached blob errors', () => {
    const recoverFromImageError = vi.fn(() => true);
    const onError = vi.fn();
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: 'blob:https://gemini.dicry.cn:18443/recoverable-carousel-thumb',
      status: 'memory-hit',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError,
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-carousel-thumb',
          url: '/public/generated/carousel-thumb.png',
          mimeType: 'image/png',
        }}
        src="/public/generated/carousel-thumb.png"
        alt="Carousel thumb"
        onError={onError}
      />
    );

    fireEvent.error(screen.getByAltText('Carousel thumb'));

    expect(screen.getByAltText('Carousel thumb').getAttribute('src')).toBe(
      '/public/generated/carousel-thumb.png'
    );
    expect(recoverFromImageError).toHaveBeenCalledWith(
      'blob:https://gemini.dicry.cn:18443/recoverable-carousel-thumb'
    );
    expect(onError).not.toHaveBeenCalled();
  });

  it('can reveal a durable raw src after a delay while the cache is still loading', () => {
    vi.useFakeTimers();
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: null,
      status: 'loading',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError: vi.fn(() => false),
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-slow',
          url: '/public/generated/slow.png',
          mimeType: 'image/png',
        }}
        src="/public/generated/slow.png"
        rawFallbackDelayMs={250}
        alt="Slow result"
      />
    );

    expect(screen.queryByAltText('Slow result')).toBeNull();

    act(() => {
      vi.advanceTimersByTime(249);
    });
    expect(screen.queryByAltText('Slow result')).toBeNull();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.getByAltText('Slow result').getAttribute('src')).toBe(
      '/public/generated/slow.png'
    );
  });

  it('does not reveal authenticated storage urls as raw image fallbacks', () => {
    vi.useFakeTimers();
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: null,
      status: 'loading',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError: vi.fn(() => false),
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-auth-storage',
          url: '/api/storage/local-files/generated/auth-storage.png',
          mimeType: 'image/png',
        }}
        src="/api/storage/local-files/generated/auth-storage.png"
        rawFallbackDelayMs={250}
        alt="Authenticated storage result"
      />
    );

    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(screen.queryByAltText('Authenticated storage result')).toBeNull();
  });

  it('does not recover a failed cached storage blob by showing the authenticated raw storage url', () => {
    const recoverFromImageError = vi.fn(() => true);
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: 'blob:https://gemini.dicry.cn:18443/revoked-storage-thumbnail',
      status: 'persistent-hit',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError,
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-storage-recovery',
          url: '/api/storage/local-files/generated/storage-recovery.png',
          mimeType: 'image/png',
        }}
        src="/api/storage/local-files/generated/storage-recovery.png"
        alt="Storage recovery thumbnail"
      />
    );

    fireEvent.error(screen.getByAltText('Storage recovery thumbnail'));

    expect(screen.queryByAltText('Storage recovery thumbnail')).toBeNull();
    expect(recoverFromImageError).toHaveBeenCalledWith(
      'blob:https://gemini.dicry.cn:18443/revoked-storage-thumbnail'
    );
  });

  it('does not reveal an internal local blob key as a raw image fallback', () => {
    vi.useFakeTimers();
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: null,
      status: 'loading',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError: vi.fn(() => false),
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-local-file',
          url: 'local-blob:att-local-file',
          mimeType: 'image/png',
          file: new File(['local-file'], 'local-file.png', { type: 'image/png' }),
        }}
        src="local-blob:att-local-file"
        rawFallbackDelayMs={250}
        alt="Local file result"
      />
    );

    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(screen.queryByAltText('Local file result')).toBeNull();
  });

  it('shows the durable raw src immediately when the fallback delay is zero', () => {
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: null,
      status: 'loading',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError: vi.fn(() => false),
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-scroll',
          url: '/public/generated/scroll.png',
          mimeType: 'image/png',
        }}
        src="/public/generated/scroll.png"
        rawFallbackDelayMs={0}
        alt="Scrolling thumbnail"
      />
    );

    expect(screen.getByAltText('Scrolling thumbnail').getAttribute('src')).toBe(
      '/public/generated/scroll.png'
    );
  });

  it('shows the durable raw src immediately when zero-delay fallback is requested during idle cache lookup', () => {
    vi.mocked(useCachedImageSrc).mockReturnValue({
      src: null,
      status: 'idle',
      error: null,
      refresh: vi.fn(),
      recoverFromImageError: vi.fn(() => false),
    });

    render(
      <CachedImage
        source={{
          attachmentId: 'att-idle-cache',
          url: '/public/generated/idle-cache.png',
          mimeType: 'image/png',
        }}
        src="/public/generated/idle-cache.png"
        rawFallbackDelayMs={0}
        alt="Idle cache thumbnail"
      />
    );

    expect(screen.getByAltText('Idle cache thumbnail').getAttribute('src')).toBe(
      '/public/generated/idle-cache.png'
    );
  });
});

// @vitest-environment jsdom

import { act, render, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mediaCacheMock = vi.hoisted(() => ({
  evictCachedMediaObjectUrl: vi.fn(),
  fetchAndStoreMedia: vi.fn(),
  getCachedMediaObjectUrl: vi.fn(),
  getCachedMediaObjectUrlSync: vi.fn(),
  releaseMediaObjectUrl: vi.fn(),
  resolveMediaCacheIdentity: vi.fn(),
  retainMediaObjectUrl: vi.fn(),
}));

vi.mock('../services/mediaCache', () => ({
  evictCachedMediaObjectUrl: mediaCacheMock.evictCachedMediaObjectUrl,
  fetchAndStoreMedia: mediaCacheMock.fetchAndStoreMedia,
  getCachedMediaObjectUrl: mediaCacheMock.getCachedMediaObjectUrl,
  getCachedMediaObjectUrlSync: mediaCacheMock.getCachedMediaObjectUrlSync,
  releaseMediaObjectUrl: mediaCacheMock.releaseMediaObjectUrl,
  resolveMediaCacheIdentity: mediaCacheMock.resolveMediaCacheIdentity,
  retainMediaObjectUrl: mediaCacheMock.retainMediaObjectUrl,
}));

import { useCachedImageSrc } from './useCachedImageSrc';
import { runPrivateCacheResetHandlers } from '../services/privateCacheInvalidation';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('useCachedImageSrc', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setPrivateCacheUserScope(null);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValue(null);
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValue(null);
    mediaCacheMock.evictCachedMediaObjectUrl.mockReturnValue(false);
    mediaCacheMock.fetchAndStoreMedia.mockRejectedValue(new Error('cache fetch failed'));
    mediaCacheMock.resolveMediaCacheIdentity.mockImplementation((source) => {
      const sourceUrl = source?.url || '';
      if (!sourceUrl || sourceUrl.startsWith('data:') || sourceUrl.startsWith('blob:')) {
        return null;
      }
      return {
        cacheKey: `media:path:${sourceUrl}`,
        sourceUrl,
        canonicalUrl: sourceUrl,
        versionSignature: `url:${sourceUrl}`,
        userScope: 'default',
        persistable: true,
      };
    });
  });

  it('uses the raw fallback for non-persistent data urls', () => {
    const { result } = renderHook(() =>
      useCachedImageSrc({ url: 'data:image/png;base64,abc', mimeType: 'image/png' }, {
        fallbackSrc: 'data:image/png;base64,abc',
      })
    );

    expect(result.current.src).toBe('data:image/png;base64,abc');
    expect(result.current.status).toBe('raw-fallback');
    expect(mediaCacheMock.fetchAndStoreMedia).not.toHaveBeenCalled();
  });

  it('falls back to the new source url when a changed image cannot be fetched through cache', async () => {
    const { result, rerender } = renderHook(
      ({ url }) => useCachedImageSrc({ url, mimeType: 'image/png' }, { fallbackSrc: url }),
      { initialProps: { url: '/result-1.png' } }
    );

    await waitFor(() => {
      expect(result.current.src).toBe('/result-1.png');
    });

    rerender({ url: '/result-2.png' });

    await waitFor(() => {
      expect(result.current.src).toBe('/result-2.png');
    });
  });

  it('does not restart the same media fetch when callers pass equivalent inline source objects', async () => {
    const deferred = createDeferred<{
      objectUrl: string;
      status: 'fresh';
      metadata: null;
    }>();
    mediaCacheMock.fetchAndStoreMedia.mockReturnValue(deferred.promise);

    const { result, rerender } = renderHook(
      ({ renderTick }) =>
        useCachedImageSrc(
          { url: '/stable-result.png', mimeType: 'image/png' },
          { fallbackSrc: '/stable-result.png' }
        ),
      { initialProps: { renderTick: 0 } }
    );

    await waitFor(() => {
      expect(result.current.status).toBe('loading');
      expect(mediaCacheMock.fetchAndStoreMedia).toHaveBeenCalledTimes(1);
    });

    rerender({ renderTick: 1 });
    await Promise.resolve();
    expect(mediaCacheMock.fetchAndStoreMedia).toHaveBeenCalledTimes(1);

    await act(async () => {
      deferred.resolve({
        objectUrl: 'blob:stable-result',
        status: 'fresh',
        metadata: null,
      });
      await deferred.promise;
    });

    await waitFor(() => {
      expect(result.current.src).toBe('blob:stable-result');
    });
  });

  it('retains and releases cached blob object urls while the hook result is mounted', async () => {
    mediaCacheMock.fetchAndStoreMedia.mockResolvedValueOnce({
      objectUrl: 'blob:retained-hook-result',
      status: 'fresh',
      metadata: null,
    });

    const { result, unmount } = renderHook(() =>
      useCachedImageSrc(
        { url: '/api/storage/local-files/retained-hook-result.png', mimeType: 'image/png' },
        { fallbackSrc: '/api/storage/local-files/retained-hook-result.png' }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:retained-hook-result');
    });

    expect(mediaCacheMock.retainMediaObjectUrl).toHaveBeenCalledWith('blob:retained-hook-result');
    expect(mediaCacheMock.releaseMediaObjectUrl).not.toHaveBeenCalledWith(
      'blob:retained-hook-result'
    );

    unmount();

    expect(mediaCacheMock.releaseMediaObjectUrl).toHaveBeenCalledWith('blob:retained-hook-result');
  });

  it('retains a memory-hit blob before exposing it to a virtualized thumbnail render', async () => {
    const identity = {
      cacheKey: 'media:path:/api/storage/local-files/virtualized-thumbnail.png',
      sourceUrl: '/api/storage/local-files/virtualized-thumbnail.png',
      canonicalUrl: '/api/storage/local-files/virtualized-thumbnail.png',
      versionSignature: 'url:/api/storage/local-files/virtualized-thumbnail.png',
      userScope: 'default',
      persistable: true,
    };
    const retainCountsAtBlobRender: number[] = [];

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValue('blob:virtualized-thumbnail');

    const Probe = () => {
      const cached = useCachedImageSrc(
        {
          attachmentId: 'att-virtualized-thumbnail',
          url: '/api/storage/local-files/virtualized-thumbnail.png',
          mimeType: 'image/png',
        },
        { fallbackSrc: '/api/storage/local-files/virtualized-thumbnail.png' }
      );

      if (cached.src === 'blob:virtualized-thumbnail') {
        retainCountsAtBlobRender.push(mediaCacheMock.retainMediaObjectUrl.mock.calls.length);
      }

      return cached.src ? <img alt="Virtualized thumbnail" src={cached.src} /> : null;
    };

    render(<Probe />);

    await waitFor(() => {
      expect(retainCountsAtBlobRender.length).toBeGreaterThan(0);
    });
    expect(retainCountsAtBlobRender[0]).toBeGreaterThan(0);
  });

  it('rebuilds cache identity when a raw history attachment receives a snake_case durable url', async () => {
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/snake-history-preview';
    const durableUrl = '/api/storage/local-files/2026/06/01/snake-history-preview.png';
    const blobIdentity = {
      cacheKey: 'media:attachment:att-snake-history-preview',
      sourceUrl: staleBlobUrl,
      canonicalUrl: 'temporary:user-1:att-snake-history-preview',
      versionSignature: 'temp:snake-history-preview',
      userScope: 'user-1',
      persistable: true,
      temporary: true,
    };
    const durableIdentity = {
      cacheKey: 'media:path:snake-history-preview',
      sourceUrl: durableUrl,
      canonicalUrl: durableUrl,
      versionSignature: `url:${durableUrl}`,
      userScope: 'user-1',
      persistable: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockImplementation((source) => {
      if (source?.cloud_url === durableUrl) return durableIdentity;
      return blobIdentity;
    });
    mediaCacheMock.fetchAndStoreMedia.mockResolvedValue({
      objectUrl: 'blob:snake-history-loaded',
      status: 'fresh',
      metadata: null,
    });

    const { rerender } = renderHook(
      ({ cloudUrl }) =>
        useCachedImageSrc(
          {
            attachmentId: 'att-snake-history-preview',
            url: staleBlobUrl,
            cloud_url: cloudUrl,
            mimeType: 'image/png',
          },
          { fallbackSrc: staleBlobUrl }
        ),
      { initialProps: { cloudUrl: undefined as string | undefined } }
    );

    await waitFor(() => {
      expect(mediaCacheMock.fetchAndStoreMedia).toHaveBeenCalledWith(blobIdentity, {
        replaceObjectUrl: true,
      });
    });

    mediaCacheMock.fetchAndStoreMedia.mockClear();
    rerender({ cloudUrl: durableUrl });

    await waitFor(() => {
      expect(mediaCacheMock.fetchAndStoreMedia).toHaveBeenCalledWith(durableIdentity);
    });
  });

  it('forces a full media refetch when refresh is requested for a failed cached blob', async () => {
    const identity = {
      cacheKey: 'media:path:/api/storage/local-files/recover.png',
      sourceUrl: '/api/storage/local-files/recover.png',
      canonicalUrl: '/api/storage/local-files/recover.png',
      versionSignature: 'url:/api/storage/local-files/recover.png',
      userScope: 'default',
      persistable: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.fetchAndStoreMedia.mockResolvedValue({
      objectUrl: 'blob:recover-fresh',
      status: 'fresh',
      metadata: null,
    });

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-recover',
          url: '/api/storage/local-files/recover.png',
          mimeType: 'image/png',
        },
        { fallbackSrc: '/api/storage/local-files/recover.png' }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:recover-fresh');
    });

    mediaCacheMock.fetchAndStoreMedia.mockClear();

    await act(async () => {
      await result.current.refresh();
    });

    expect(mediaCacheMock.fetchAndStoreMedia).toHaveBeenCalledWith(identity, {
      allowRevalidate: false,
      replaceObjectUrl: true,
    });
  });

  it('recovers from a failed cached blob image by showing the stable fallback and reloading cache', async () => {
    const identity = {
      cacheKey: 'media:path:/public/recoverable-blob.png',
      sourceUrl: '/public/recoverable-blob.png',
      canonicalUrl: '/public/recoverable-blob.png',
      versionSignature: 'url:/public/recoverable-blob.png',
      userScope: 'default',
      persistable: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.fetchAndStoreMedia.mockResolvedValueOnce({
      objectUrl: 'blob:recoverable-before-error',
      status: 'fresh',
      metadata: null,
    });

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-recoverable-blob',
          url: '/public/recoverable-blob.png',
          mimeType: 'image/png',
        },
        { fallbackSrc: '/public/recoverable-blob.png' }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:recoverable-before-error');
    });

    mediaCacheMock.fetchAndStoreMedia.mockClear();
    mediaCacheMock.fetchAndStoreMedia.mockResolvedValueOnce({
      objectUrl: 'blob:recoverable-after-refresh',
      status: 'fresh',
      metadata: null,
    });

    act(() => {
      expect(result.current.recoverFromImageError('blob:recoverable-before-error')).toBe(true);
    });

    expect(result.current.src).toBe('/public/recoverable-blob.png');
    expect(result.current.status).toBe('raw-fallback');

    await waitFor(() => {
      expect(mediaCacheMock.fetchAndStoreMedia).toHaveBeenCalledWith(identity);
    });

    await waitFor(() => {
      expect(result.current.src).toBe('blob:recoverable-after-refresh');
    });
  });

  it('rebuilds a failed history thumbnail object url from persistent cache before hitting the backend', async () => {
    const identity = {
      cacheKey: 'media:path:/api/storage/local-files/persistent-recover.png',
      sourceUrl: '/api/storage/local-files/persistent-recover.png',
      canonicalUrl: '/api/storage/local-files/persistent-recover.png',
      versionSignature: 'url:/api/storage/local-files/persistent-recover.png',
      userScope: 'default',
      persistable: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync
      .mockReturnValueOnce('blob:persistent-recover-revoked')
      .mockReturnValue(null);
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValueOnce(
      'blob:persistent-recover-rebuilt'
    );

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-persistent-recover',
          url: '/api/storage/local-files/persistent-recover.png',
          mimeType: 'image/png',
        },
        { fallbackSrc: '/api/storage/local-files/persistent-recover.png' }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:persistent-recover-revoked');
    });

    mediaCacheMock.fetchAndStoreMedia.mockClear();

    act(() => {
      expect(result.current.recoverFromImageError('blob:persistent-recover-revoked')).toBe(true);
    });

    expect(mediaCacheMock.evictCachedMediaObjectUrl).toHaveBeenCalledWith(
      identity,
      'blob:persistent-recover-revoked'
    );
    expect(result.current.src).toBeNull();
    expect(result.current.status).toBe('loading');

    await waitFor(() => {
      expect(result.current.src).toBe('blob:persistent-recover-rebuilt');
    });
    expect(mediaCacheMock.getCachedMediaObjectUrl).toHaveBeenCalledWith(identity, {
      allowStale: true,
    });
    expect(mediaCacheMock.fetchAndStoreMedia).not.toHaveBeenCalled();
  });

  it('evicts a failed cached blob before virtualized history rows can reuse it', async () => {
    const identity = {
      cacheKey: 'media:path:/api/storage/local-files/stale-history-thumbnail.png',
      sourceUrl: '/api/storage/local-files/stale-history-thumbnail.png',
      canonicalUrl: '/api/storage/local-files/stale-history-thumbnail.png',
      versionSignature: 'url:/api/storage/local-files/stale-history-thumbnail.png',
      userScope: 'default',
      persistable: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValue(
      'blob:https://gemini.dicry.cn:18443/stale-history-thumbnail'
    );
    mediaCacheMock.fetchAndStoreMedia.mockResolvedValueOnce({
      objectUrl: 'blob:https://gemini.dicry.cn:18443/fresh-history-thumbnail',
      status: 'fresh',
      metadata: null,
    });

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-stale-history-thumbnail',
          url: '/api/storage/local-files/stale-history-thumbnail.png',
          mimeType: 'image/png',
        },
        { fallbackSrc: '/api/storage/local-files/stale-history-thumbnail.png' }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe(
        'blob:https://gemini.dicry.cn:18443/stale-history-thumbnail'
      );
    });

    act(() => {
      expect(
        result.current.recoverFromImageError(
          'blob:https://gemini.dicry.cn:18443/stale-history-thumbnail'
        )
      ).toBe(true);
    });

    expect(mediaCacheMock.evictCachedMediaObjectUrl).toHaveBeenCalledWith(
      identity,
      'blob:https://gemini.dicry.cn:18443/stale-history-thumbnail'
    );
    expect(result.current.src).toBeNull();
    expect(result.current.status).toBe('loading');
  });

  it('evicts a failed temporary history blob and reloads instead of reusing it while scrolling', async () => {
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/stale-temporary-history-thumbnail';
    const identity = {
      cacheKey: 'media:attachment:att-temporary-history-thumbnail',
      attachmentId: 'att-temporary-history-thumbnail',
      sourceUrl: staleBlobUrl,
      canonicalUrl: 'temporary:default:att-temporary-history-thumbnail',
      versionSignature: 'temp:stale-temporary-history-thumbnail',
      userScope: 'default',
      persistable: true,
      temporary: true,
    };

    mediaCacheMock.fetchAndStoreMedia.mockReset();
    mediaCacheMock.fetchAndStoreMedia.mockRejectedValue(new Error('cache fetch failed'));
    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync
      .mockReturnValueOnce(staleBlobUrl)
      .mockReturnValue(null);
    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-temporary-history-thumbnail',
          url: staleBlobUrl,
          mimeType: 'image/png',
          file: new Blob(['live-file-backed-thumbnail'], { type: 'image/png' }),
        },
        { fallbackSrc: staleBlobUrl }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe(staleBlobUrl);
    });

    act(() => {
      expect(result.current.recoverFromImageError(staleBlobUrl)).toBe(true);
    });

    mediaCacheMock.fetchAndStoreMedia.mockResolvedValueOnce({
      objectUrl: 'blob:https://gemini.dicry.cn:18443/reloaded-temporary-history-thumbnail',
      status: 'fresh',
      metadata: null,
    });

    expect(mediaCacheMock.evictCachedMediaObjectUrl).toHaveBeenCalledWith(
      identity,
      staleBlobUrl
    );
    expect(result.current.src).toBeNull();
    expect(result.current.status).toBe('loading');

    await waitFor(() => {
      expect(result.current.src).toBe(
        'blob:https://gemini.dicry.cn:18443/reloaded-temporary-history-thumbnail'
      );
    });
  });

  it('does not expose a temporary blob memory hit for persisted history rows without a live file', async () => {
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/stale-virtualized-history-row';
    const identity = {
      cacheKey: 'media:attachment:att-virtualized-history-row',
      attachmentId: 'att-virtualized-history-row',
      sourceUrl: staleBlobUrl,
      canonicalUrl: 'temporary:default:att-virtualized-history-row',
      versionSignature: 'temp:stale-virtualized-history-row',
      userScope: 'default',
      persistable: true,
      temporary: true,
    };
    const deferred = createDeferred<{
      objectUrl: string;
      status: 'fresh';
      metadata: null;
    }>();

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValue(staleBlobUrl);
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValue(null);
    mediaCacheMock.fetchAndStoreMedia.mockReturnValue(deferred.promise);

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-virtualized-history-row',
          url: staleBlobUrl,
          mimeType: 'image/png',
        },
        { fallbackSrc: staleBlobUrl }
      )
    );

    await waitFor(() => {
      expect(result.current.status).toBe('loading');
    });
    expect(result.current.src).toBeNull();
    expect(mediaCacheMock.getCachedMediaObjectUrlSync).not.toHaveBeenCalled();
    expect(mediaCacheMock.getCachedMediaObjectUrl).toHaveBeenCalledWith(identity, {
      allowMemory: false,
      allowStale: false,
    });

    await act(async () => {
      deferred.resolve({
        objectUrl: 'blob:https://gemini.dicry.cn:18443/rebuilt-virtualized-history-row',
        status: 'fresh',
        metadata: null,
      });
    });

    await waitFor(() => {
      expect(result.current.src).toBe(
        'blob:https://gemini.dicry.cn:18443/rebuilt-virtualized-history-row'
      );
    });
    expect(result.current.src).not.toBe(staleBlobUrl);
  });

  it('reuses durable memory hits for virtualized history thumbnails', async () => {
    const identity = {
      cacheKey: 'media:path:/api/storage/local-files/virtualized-durable.png',
      sourceUrl: '/api/storage/local-files/virtualized-durable.png',
      canonicalUrl: '/api/storage/local-files/virtualized-durable.png',
      versionSignature: 'url:/api/storage/local-files/virtualized-durable.png',
      userScope: 'default',
      persistable: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValue(
      'blob:https://gemini.dicry.cn:18443/stale-durable-virtualized-row'
    );
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValue(
      'blob:https://gemini.dicry.cn:18443/rebuilt-durable-virtualized-row'
    );

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-virtualized-durable',
          url: '/api/storage/local-files/virtualized-durable.png',
          mimeType: 'image/png',
        },
        {
          fallbackSrc: '/api/storage/local-files/virtualized-durable.png',
          preferMemoryCache: true,
        }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe(
        'blob:https://gemini.dicry.cn:18443/stale-durable-virtualized-row'
      );
    });
    expect(result.current.status).toBe('memory-hit');
    expect(mediaCacheMock.getCachedMediaObjectUrlSync).toHaveBeenCalledWith(identity, {
      allowStale: false,
    });
    expect(mediaCacheMock.getCachedMediaObjectUrl).not.toHaveBeenCalled();
  });

  it('does not reuse a stale durable memory object url after the source version changes', async () => {
    const oldIdentity = {
      cacheKey: 'media:path:/api/storage/local-files/versioned-history-thumbnail.png',
      sourceUrl: '/api/storage/local-files/versioned-history-thumbnail.png',
      canonicalUrl: '/api/storage/local-files/versioned-history-thumbnail.png',
      versionSignature: 'updated:1',
      userScope: 'default',
      persistable: true,
    };
    const newIdentity = {
      ...oldIdentity,
      versionSignature: 'updated:2',
    };

    mediaCacheMock.resolveMediaCacheIdentity
      .mockReturnValueOnce(oldIdentity)
      .mockReturnValue(newIdentity);
    mediaCacheMock.getCachedMediaObjectUrlSync
      .mockReturnValueOnce('blob:https://gemini.dicry.cn:18443/versioned-old')
      .mockReturnValue(null);
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValue(
      'blob:https://gemini.dicry.cn:18443/versioned-new'
    );

    const { result, rerender } = renderHook(
      ({ updatedAt }) =>
        useCachedImageSrc(
          {
            attachmentId: 'att-versioned-history-thumbnail',
            url: '/api/storage/local-files/versioned-history-thumbnail.png',
            mimeType: 'image/png',
            updatedAt,
          },
          {
            fallbackSrc: '/api/storage/local-files/versioned-history-thumbnail.png',
            preferMemoryCache: true,
          }
        ),
      { initialProps: { updatedAt: 1 } }
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:https://gemini.dicry.cn:18443/versioned-old');
    });

    rerender({ updatedAt: 2 });

    await waitFor(() => {
      expect(result.current.src).toBe('blob:https://gemini.dicry.cn:18443/versioned-new');
    });
    expect(mediaCacheMock.getCachedMediaObjectUrlSync).toHaveBeenLastCalledWith(newIdentity, {
      allowStale: false,
    });
    expect(result.current.src).not.toBe('blob:https://gemini.dicry.cn:18443/versioned-old');
  });

  it('bypasses memory blob urls for virtualized history thumbnails without probing blob urls', async () => {
    const staleObjectUrl =
      'blob:https://gemini.dicry.cn:18443/revoked-bypassed-history-thumbnail';
    const rebuiltObjectUrl =
      'blob:https://gemini.dicry.cn:18443/rebuilt-bypassed-history-thumbnail';
    const identity = {
      cacheKey: 'media:path:/api/storage/local-files/bypassed-history-thumbnail.png',
      sourceUrl: '/api/storage/local-files/bypassed-history-thumbnail.png',
      canonicalUrl: '/api/storage/local-files/bypassed-history-thumbnail.png',
      versionSignature: 'url:/api/storage/local-files/bypassed-history-thumbnail.png',
      userScope: 'default',
      persistable: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValue(staleObjectUrl);
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValue(rebuiltObjectUrl);

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-bypassed-history-thumbnail',
          url: '/api/storage/local-files/bypassed-history-thumbnail.png',
          mimeType: 'image/png',
        },
        {
          fallbackSrc: '/api/storage/local-files/bypassed-history-thumbnail.png',
          preferMemoryCache: false,
        }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe(rebuiltObjectUrl);
    });
    expect(result.current.src).not.toBe(staleObjectUrl);
    expect(mediaCacheMock.getCachedMediaObjectUrlSync).not.toHaveBeenCalled();
    expect(mediaCacheMock.getCachedMediaObjectUrl).toHaveBeenCalledWith(identity, {
      allowMemory: false,
      allowStale: false,
    });
    expect(mediaCacheMock.fetchAndStoreMedia).not.toHaveBeenCalled();
  });

  it('can request a rebuilt persistent object url for virtualized history thumbnails', async () => {
    const rebuiltObjectUrl =
      'blob:https://gemini.dicry.cn:18443/rebuilt-replace-history-thumbnail';
    const identity = {
      cacheKey: 'media:path:/api/storage/local-files/replace-history-thumbnail.png',
      sourceUrl: '/api/storage/local-files/replace-history-thumbnail.png',
      canonicalUrl: '/api/storage/local-files/replace-history-thumbnail.png',
      versionSignature: 'url:/api/storage/local-files/replace-history-thumbnail.png',
      userScope: 'default',
      persistable: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValue(
      'blob:https://gemini.dicry.cn:18443/stale-replace-history-thumbnail'
    );
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValue(rebuiltObjectUrl);

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-replace-history-thumbnail',
          url: '/api/storage/local-files/replace-history-thumbnail.png',
          mimeType: 'image/png',
        },
        {
          fallbackSrc: '/api/storage/local-files/replace-history-thumbnail.png',
          replaceCachedObjectUrl: true,
        }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe(rebuiltObjectUrl);
    });
    expect(mediaCacheMock.getCachedMediaObjectUrlSync).not.toHaveBeenCalled();
    expect(mediaCacheMock.getCachedMediaObjectUrl).toHaveBeenCalledWith(identity, {
      allowMemory: false,
      allowStale: false,
      replaceObjectUrl: true,
    });
    expect(mediaCacheMock.fetchAndStoreMedia).not.toHaveBeenCalled();
  });

  it('does not reuse a stale memory object url when the same temporary attachment id receives a new live file', async () => {
    const file = new File(['new-live-file'], 'upload.png', {
      type: 'image/png',
      lastModified: 2000,
    });
    const identity = {
      cacheKey: 'media:attachment:att-reused-live-file',
      attachmentId: 'att-reused-live-file',
      sourceUrl: 'blob:https://gemini.dicry.cn:18443/new-live-file-preview',
      canonicalUrl: 'temporary:default:att-reused-live-file',
      versionSignature: 'blob:upload.png:image/png:13:2000',
      userScope: 'default',
      persistable: true,
      temporary: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockImplementation((_identity, options) =>
      options?.allowStale ? 'blob:https://gemini.dicry.cn:18443/old-live-file-preview' : null
    );
    mediaCacheMock.fetchAndStoreMedia.mockResolvedValue({
      objectUrl: 'blob:https://gemini.dicry.cn:18443/new-live-file-cached',
      status: 'fresh',
      metadata: null,
    });

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-reused-live-file',
          url: 'blob:https://gemini.dicry.cn:18443/new-live-file-preview',
          mimeType: 'image/png',
          file,
        },
        {
          fallbackSrc: 'blob:https://gemini.dicry.cn:18443/new-live-file-preview',
        }
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:https://gemini.dicry.cn:18443/new-live-file-cached');
    });
    expect(result.current.src).not.toBe(
      'blob:https://gemini.dicry.cn:18443/old-live-file-preview'
    );
    expect(mediaCacheMock.getCachedMediaObjectUrlSync).toHaveBeenCalledWith(identity, {
      allowStale: false,
    });
  });

  it('handles blob source signatures when the File constructor is unavailable', () => {
    const originalFile = globalThis.File;
    Object.defineProperty(globalThis, 'File', {
      configurable: true,
      value: undefined,
    });

    try {
      expect(() =>
        renderHook(() =>
          useCachedImageSrc(
            {
              attachmentId: 'att-blob-no-file',
              url: '/blob-no-file.png',
              mimeType: 'image/png',
              file: new Blob(['blob-without-file-constructor'], { type: 'image/png' }),
            },
            { fallbackSrc: '/blob-no-file.png' }
          )
        )
      ).not.toThrow();
    } finally {
      Object.defineProperty(globalThis, 'File', {
        configurable: true,
        value: originalFile,
      });
    }
  });

  it('keeps temporary blob sources off the img element while their cache write continues in the background', async () => {
    const blobUrl = 'blob:https://gemini.dicry.cn:18443/local-preview';
    const identity = {
      cacheKey: 'media:attachment:att-local-blob',
      sourceUrl: blobUrl,
      canonicalUrl: 'temporary:user-1:att-local-blob',
      versionSignature: 'blob:local-preview',
      userScope: 'user-1',
      persistable: true,
      temporary: true,
    };
    const deferred = createDeferred<{
      objectUrl: string;
      status: 'fresh';
      metadata: null;
    }>();

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.fetchAndStoreMedia.mockReturnValue(deferred.promise);

    const { result, unmount } = renderHook(() =>
      useCachedImageSrc(
        { attachmentId: 'att-local-blob', url: blobUrl, mimeType: 'image/png' },
        { fallbackSrc: blobUrl }
      )
    );

    await waitFor(() => {
      expect(mediaCacheMock.fetchAndStoreMedia).toHaveBeenCalledWith(identity, {
        replaceObjectUrl: true,
      });
    });
    expect(result.current.src).toBeNull();
    expect(result.current.status).toBe('loading');

    unmount();
    deferred.resolve({
      objectUrl: 'blob:cached-local-preview',
      status: 'fresh',
      metadata: null,
    });
    await deferred.promise;
  });

  it('does not fall back to a raw temporary blob url when cache recovery fails', async () => {
    const blobUrl = 'blob:https://gemini.dicry.cn:18443/revoked-preview';
    const identity = {
      cacheKey: 'media:attachment:att-revoked-blob',
      sourceUrl: blobUrl,
      canonicalUrl: 'temporary:user-1:att-revoked-blob',
      versionSignature: 'temp:revoked-preview',
      userScope: 'user-1',
      persistable: true,
      temporary: true,
    };

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.fetchAndStoreMedia.mockRejectedValueOnce(new Error('revoked blob'));

    const { result } = renderHook(() =>
      useCachedImageSrc(
        { attachmentId: 'att-revoked-blob', url: blobUrl, mimeType: 'image/png' },
        { fallbackSrc: blobUrl }
      )
    );

    await waitFor(() => {
      expect(result.current.status).toBe('error');
    });
    expect(result.current.src).toBeNull();
    expect(result.current.error?.message).toBe('revoked blob');
  });

  it('does not expose a raw blob fallback when the source has no cache identity or file', async () => {
    const blobUrl = 'blob:https://gemini.dicry.cn:18443/untyped-history-preview';
    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(null);

    const { result } = renderHook(() =>
      useCachedImageSrc(
        { attachmentId: 'att-untyped-history-preview', url: blobUrl },
        { fallbackSrc: blobUrl }
      )
    );

    await waitFor(() => {
      expect(result.current.status).toBe('error');
    });
    expect(result.current.src).toBeNull();
    expect(mediaCacheMock.fetchAndStoreMedia).not.toHaveBeenCalled();
  });

  it('does not expose an internal local blob key when the source has no cache identity or file', async () => {
    const localBlobKey = 'local-blob:untyped-history-preview';
    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(null);

    const { result } = renderHook(() =>
      useCachedImageSrc(
        { attachmentId: 'att-untyped-local-history-preview', url: localBlobKey },
        { fallbackSrc: localBlobKey }
      )
    );

    await waitFor(() => {
      expect(result.current.status).toBe('error');
    });
    expect(result.current.src).toBeNull();
    expect(mediaCacheMock.fetchAndStoreMedia).not.toHaveBeenCalled();
  });

  it('ignores a late media fetch result after the private cache lifecycle changes', async () => {
    setPrivateCacheUserScope('user-1');
    const identity = {
      cacheKey: 'media:user-1:attachment:att-private',
      sourceUrl: '/api/storage/local-files/private.png',
      canonicalUrl: '/api/storage/local-files/private.png',
      versionSignature: 'url:/api/storage/local-files/private.png',
      userScope: 'user-1',
      persistable: true,
    };
    const deferred = createDeferred<{
      objectUrl: string;
      status: 'fresh';
      metadata: null;
    }>();

    mediaCacheMock.resolveMediaCacheIdentity.mockReturnValue(identity);
    mediaCacheMock.fetchAndStoreMedia.mockReturnValue(deferred.promise);

    const { result } = renderHook(() =>
      useCachedImageSrc(
        {
          attachmentId: 'att-private',
          url: '/api/storage/local-files/private.png',
          mimeType: 'image/png',
        },
        { fallbackSrc: '/api/storage/local-files/private.png' }
      )
    );

    await waitFor(() => {
      expect(result.current.status).toBe('loading');
    });

    act(() => {
      setPrivateCacheUserScope('user-2');
      runPrivateCacheResetHandlers();
    });

    await act(async () => {
      deferred.resolve({
        objectUrl: 'blob:user-one-private-late',
        status: 'fresh',
        metadata: null,
      });
      await deferred.promise;
    });

    expect(result.current.src).toBeNull();
    expect(result.current.status).toBe('idle');
  });
});

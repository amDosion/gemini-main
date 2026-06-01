// @vitest-environment jsdom
import { act, cleanup, render, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const {
  downloadBlobWithXhrMock,
  evictCachedPreviewObjectUrlMock,
  getCachedPreviewObjectUrlMock,
  releaseMediaObjectUrlMock,
  retainMediaObjectUrlMock,
  savePreviewBlobToCacheMock
} = vi.hoisted(() => ({
  downloadBlobWithXhrMock: vi.fn(),
  evictCachedPreviewObjectUrlMock: vi.fn(),
  getCachedPreviewObjectUrlMock: vi.fn(),
  releaseMediaObjectUrlMock: vi.fn(),
  retainMediaObjectUrlMock: vi.fn(),
  savePreviewBlobToCacheMock: vi.fn()
}));

vi.mock('../../../services/httpProgress', () => ({
  downloadBlobWithXhr: downloadBlobWithXhrMock
}));

vi.mock('../../../services/previewCache', () => ({
  evictCachedPreviewObjectUrl: evictCachedPreviewObjectUrlMock,
  getCachedPreviewObjectUrl: getCachedPreviewObjectUrlMock,
  savePreviewBlobToCache: savePreviewBlobToCacheMock
}));

vi.mock('../../../services/mediaCache', () => ({
  releaseMediaObjectUrl: releaseMediaObjectUrlMock,
  retainMediaObjectUrl: retainMediaObjectUrlMock
}));

import {
  __resetInflightPreviewDownloadsForTest,
  useXhrImagePreview
} from './useXhrImagePreview';
import { setPrivateCacheUserScope } from '../../../services/privateCacheScope';

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('useXhrImagePreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __resetInflightPreviewDownloadsForTest();
    setPrivateCacheUserScope(null);
    getCachedPreviewObjectUrlMock.mockResolvedValue(null);
    evictCachedPreviewObjectUrlMock.mockReturnValue(false);
    savePreviewBlobToCacheMock.mockResolvedValue('blob:preview-shared');
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:preview-fallback'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('deduplicates concurrent preview downloads for the same candidate url', async () => {
    const deferred = createDeferred<{
      blob: Blob;
      headers: Record<string, string>;
    }>();
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';

    downloadBlobWithXhrMock.mockReturnValue(deferred.promise);

    const firstFailedUrlsRef = { current: new Set<string>() };
    const secondFailedUrlsRef = { current: new Set<string>() };

    const firstHook = renderHook(() =>
      useXhrImagePreview([candidate], firstFailedUrlsRef, 'first')
    );
    const secondHook = renderHook(() =>
      useXhrImagePreview([candidate], secondFailedUrlsRef, 'second')
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(1);
    });

    deferred.resolve({
      blob: new Blob(['preview-bytes'], { type: 'image/png' }),
      headers: { 'content-type': 'image/png' }
    });

    await waitFor(() => {
      expect(firstHook.result.current.src).toBe('blob:preview-shared');
      expect(secondHook.result.current.src).toBe('blob:preview-shared');
    });
  });

  it('does not deduplicate an inflight storage preview download across private user scopes', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fprivate.png&rev=12';
    const firstDeferred = createDeferred<{
      blob: Blob;
      headers: Record<string, string>;
    }>();
    const secondDeferred = createDeferred<{
      blob: Blob;
      headers: Record<string, string>;
    }>();

    downloadBlobWithXhrMock
      .mockReturnValueOnce(firstDeferred.promise)
      .mockReturnValueOnce(secondDeferred.promise);

    setPrivateCacheUserScope('user-1');
    const firstHook = renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'same-reset')
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(1);
    });

    setPrivateCacheUserScope('user-2');
    const secondHook = renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'same-reset')
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(2);
    });

    firstHook.unmount();
    secondHook.unmount();

    await act(async () => {
      firstDeferred.resolve({
        blob: new Blob(['user-one-preview'], { type: 'image/png' }),
        headers: { 'content-type': 'image/png' }
      });
      secondDeferred.resolve({
        blob: new Blob(['user-two-preview'], { type: 'image/png' }),
        headers: { 'content-type': 'image/png' }
      });
      await Promise.all([firstDeferred.promise, secondDeferred.promise]);
    });
  });

  it('does not write a late storage preview blob after the private user scope changes', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Flate-private.png&rev=12';
    const firstDeferred = createDeferred<{
      blob: Blob;
      headers: Record<string, string>;
    }>();
    const secondDeferred = createDeferred<{
      blob: Blob;
      headers: Record<string, string>;
    }>();
    const oldScopeBlob = new Blob(['old-user-preview'], { type: 'image/png' });
    const newScopeBlob = new Blob(['new-user-preview'], { type: 'image/png' });

    downloadBlobWithXhrMock
      .mockReturnValueOnce(firstDeferred.promise)
      .mockReturnValueOnce(secondDeferred.promise);

    setPrivateCacheUserScope('user-1');
    renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'same-reset')
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(1);
    });

    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(2);
    });

    firstDeferred.resolve({
      blob: oldScopeBlob,
      headers: { 'content-type': 'image/png' }
    });
    await firstDeferred.promise;
    await Promise.resolve();
    await Promise.resolve();

    expect(savePreviewBlobToCacheMock).not.toHaveBeenCalledWith(
      expect.any(String),
      oldScopeBlob,
      expect.anything()
    );
    expect(URL.createObjectURL).not.toHaveBeenCalledWith(oldScopeBlob);

    secondDeferred.resolve({
      blob: newScopeBlob,
      headers: { 'content-type': 'image/png' }
    });
    await secondDeferred.promise;
    await Promise.resolve();
  });

  it('does not start a network preview request while disabled', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';

    renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'disabled', { enabled: false })
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).not.toHaveBeenCalled();
    });
  });

  it('keeps a persistent cached preview visible while disabled without reading memory blobs', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';

    getCachedPreviewObjectUrlMock.mockResolvedValue('blob:persistent-cached-preview');

    const { result } = renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'disabled-cached', { enabled: false })
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:persistent-cached-preview');
      expect(result.current.exhausted).toBe(false);
    });

    expect(getCachedPreviewObjectUrlMock).toHaveBeenCalledWith(candidate, { allowMemory: false });
    expect(downloadBlobWithXhrMock).not.toHaveBeenCalled();
  });

  it('retains and releases shared cached preview blob urls while visible', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';

    getCachedPreviewObjectUrlMock.mockResolvedValue('blob:cached-preview-retained');

    const { result, unmount } = renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'retained-preview', {
        enabled: false
      })
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:cached-preview-retained');
    });

    expect(retainMediaObjectUrlMock).toHaveBeenCalledWith('blob:cached-preview-retained');
    expect(releaseMediaObjectUrlMock).not.toHaveBeenCalledWith('blob:cached-preview-retained');

    unmount();

    expect(releaseMediaObjectUrlMock).toHaveBeenCalledWith('blob:cached-preview-retained');
  });

  it('retains a persistent cached preview blob before exposing it to a lazy thumbnail render', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';
    const retainCountsAtBlobRender: number[] = [];

    getCachedPreviewObjectUrlMock.mockResolvedValue('blob:lazy-preview-retained');

    const Probe = () => {
      const preview = useXhrImagePreview(
        [candidate],
        { current: new Set<string>() },
        'lazy-retained',
        { enabled: false }
      );

      if (preview.src === 'blob:lazy-preview-retained') {
        retainCountsAtBlobRender.push(retainMediaObjectUrlMock.mock.calls.length);
      }

      return preview.src ? <img alt="Lazy storage thumbnail" src={preview.src} /> : null;
    };

    render(<Probe />);

    await waitFor(() => {
      expect(retainCountsAtBlobRender.length).toBeGreaterThan(0);
    });
    expect(retainCountsAtBlobRender[0]).toBeGreaterThan(0);
  });

  it('evicts a failed cached preview blob and reloads the same candidate', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fstale.png&rev=12';
    let evicted = false;

    getCachedPreviewObjectUrlMock.mockImplementation(async () =>
      evicted ? null : 'blob:stale-storage-preview'
    );
    evictCachedPreviewObjectUrlMock.mockImplementation(() => {
      evicted = true;
      return true;
    });
    downloadBlobWithXhrMock.mockResolvedValueOnce({
      blob: new Blob(['fresh-preview'], { type: 'image/png' }),
      headers: { 'content-type': 'image/png' }
    });
    savePreviewBlobToCacheMock.mockResolvedValue('blob:fresh-storage-preview');

    const { result } = renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'stale-retry')
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:stale-storage-preview');
    });

    act(() => {
      expect(
        (result.current as any).recoverFromImageError('blob:stale-storage-preview')
      ).toBe(true);
    });

    expect(evictCachedPreviewObjectUrlMock).toHaveBeenCalledWith(
      candidate,
      'blob:stale-storage-preview'
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledWith({
        url: candidate,
        withCredentials: true,
        timeoutMs: 30000
      });
      expect(result.current.src).toBe('blob:fresh-storage-preview');
    });
  });

  it('does not create a separate temporary object url when shared preview cache cannot save', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';
    const candidates = [candidate];
    const failedPreviewUrlsRef = { current: new Set<string>() };
    savePreviewBlobToCacheMock.mockResolvedValue(null);
    downloadBlobWithXhrMock.mockResolvedValueOnce({
      blob: new Blob(['preview-fallback'], { type: 'image/png' }),
      headers: { 'content-type': 'image/png' }
    });

    const { result } = renderHook(() =>
      useXhrImagePreview(candidates, failedPreviewUrlsRef, 'fallback')
    );

    await waitFor(() => {
      expect(result.current.exhausted).toBe(true);
    });

    expect(result.current.src).toBeNull();
    expect(result.current.lastFailure).toMatchObject({
      url: candidate,
      httpStatus: null,
      message: 'Preview cache did not return an object URL'
    });
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
  });

  it('scopes direct-url persistent cache entries by reset key to avoid stale preview reuse', async () => {
    const candidate = 'https://cdn.example.com/photo.png';
    const scopedCacheKey = `${candidate}::storage-1:/photo.png:${candidate}:12`;

    getCachedPreviewObjectUrlMock.mockImplementation(async (key: string) =>
      key === scopedCacheKey ? 'blob:scoped-preview' : null
    );

    const { result, unmount } = renderHook(() =>
      useXhrImagePreview(
        [candidate],
        { current: new Set<string>() },
        'storage-1:/photo.png:https://cdn.example.com/photo.png:12'
      )
    );

    await waitFor(() => {
      expect(getCachedPreviewObjectUrlMock).toHaveBeenCalledWith(scopedCacheKey, {
        allowMemory: false
      });
      expect(result.current.src).toBe('blob:scoped-preview');
    });

    unmount();
    expect(downloadBlobWithXhrMock).not.toHaveBeenCalled();
  });

  it('does not reuse an inflight direct-url download across reset keys', async () => {
    const candidate = 'https://cdn.example.com/photo.png';
    const firstDeferred = createDeferred<{
      blob: Blob;
      headers: Record<string, string>;
    }>();
    const secondDeferred = createDeferred<{
      blob: Blob;
      headers: Record<string, string>;
    }>();

    downloadBlobWithXhrMock
      .mockReturnValueOnce(firstDeferred.promise)
      .mockReturnValueOnce(secondDeferred.promise);

    const firstHook = renderHook(() =>
      useXhrImagePreview(
        [candidate],
        { current: new Set<string>() },
        'storage-1:/photo.png:https://cdn.example.com/photo.png:12'
      )
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(1);
    });

    const secondHook = renderHook(() =>
      useXhrImagePreview(
        [candidate],
        { current: new Set<string>() },
        'storage-1:/photo.png:https://cdn.example.com/photo.png:13'
      )
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(2);
    });

    firstHook.unmount();
    secondHook.unmount();

    await act(async () => {
      firstDeferred.resolve({
        blob: new Blob(['preview-12'], { type: 'image/png' }),
        headers: { 'content-type': 'image/png' }
      });
      secondDeferred.resolve({
        blob: new Blob(['preview-13'], { type: 'image/png' }),
        headers: { 'content-type': 'image/png' }
      });
      await Promise.all([firstDeferred.promise, secondDeferred.promise]);
    });

    expect(downloadBlobWithXhrMock.mock.calls).toEqual([
      [{ url: candidate, withCredentials: false, timeoutMs: 30000 }],
      [{ url: candidate, withCredentials: false, timeoutMs: 30000 }]
    ]);
  });

  it('ignores unsafe preview candidate schemes and protocol-relative URLs instead of probing them', async () => {
    const { result } = renderHook(() =>
      useXhrImagePreview(
        ['file:///tmp/preview.png', 'javascript:alert(1)', '//evil.example/preview.png'],
        { current: new Set<string>() },
        'unsafe'
      )
    );

    await waitFor(() => {
      expect(result.current.src).toBeNull();
      expect(result.current.exhausted).toBe(true);
    });

    expect(getCachedPreviewObjectUrlMock).not.toHaveBeenCalled();
    expect(downloadBlobWithXhrMock).not.toHaveBeenCalled();
  });

  it('limits concurrent preview downloads and starts queued work only after a slot is released', async () => {
    const activeRequests = new Map<string, ReturnType<typeof createDeferred<{
      blob: Blob;
      headers: Record<string, string>;
    }>>>();

    downloadBlobWithXhrMock.mockImplementation(async ({ url }: { url: string }) => {
      const deferred = createDeferred<{
        blob: Blob;
        headers: Record<string, string>;
      }>();
      activeRequests.set(url, deferred);
      return deferred.promise;
    });

    const urls = Array.from({ length: 5 }, (_, index) =>
      `/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto-${index + 1}.png&rev=12`
    );

    const hooks = urls.map((candidate, index) =>
      renderHook(() =>
        useXhrImagePreview([candidate], { current: new Set<string>() }, `limit-${index}`)
      )
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(4);
    });

    await act(async () => {
      activeRequests.get(urls[0])?.resolve({
        blob: new Blob(['preview-1'], { type: 'image/png' }),
        headers: { 'content-type': 'image/png' }
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).toHaveBeenCalledTimes(5);
    });
  });
});

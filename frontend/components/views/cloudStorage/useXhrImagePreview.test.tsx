// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const {
  downloadBlobWithXhrMock,
  cachePreviewBlobObjectUrlMock,
  getCachedPreviewObjectUrlMock,
  getCachedPreviewObjectUrlSyncMock,
  savePreviewBlobToCacheMock
} = vi.hoisted(() => ({
  downloadBlobWithXhrMock: vi.fn(),
  cachePreviewBlobObjectUrlMock: vi.fn(),
  getCachedPreviewObjectUrlMock: vi.fn(),
  getCachedPreviewObjectUrlSyncMock: vi.fn(),
  savePreviewBlobToCacheMock: vi.fn()
}));

vi.mock('../../../services/httpProgress', () => ({
  downloadBlobWithXhr: downloadBlobWithXhrMock
}));

vi.mock('../../../services/previewCache', () => ({
  cachePreviewBlobObjectUrl: cachePreviewBlobObjectUrlMock,
  getCachedPreviewObjectUrl: getCachedPreviewObjectUrlMock,
  getCachedPreviewObjectUrlSync: getCachedPreviewObjectUrlSyncMock,
  savePreviewBlobToCache: savePreviewBlobToCacheMock
}));

import {
  __resetInflightPreviewDownloadsForTest,
  useXhrImagePreview
} from './useXhrImagePreview';

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
    getCachedPreviewObjectUrlSyncMock.mockReturnValue(null);
    getCachedPreviewObjectUrlMock.mockResolvedValue(null);
    cachePreviewBlobObjectUrlMock.mockReturnValue('blob:preview-shared');
    savePreviewBlobToCacheMock.mockResolvedValue(undefined);
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

  it('does not start a network preview request while disabled', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';

    renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'disabled', { enabled: false })
    );

    await waitFor(() => {
      expect(downloadBlobWithXhrMock).not.toHaveBeenCalled();
    });
  });

  it('keeps a sync-cached preview visible while disabled without starting a network request', async () => {
    const candidate = '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';

    getCachedPreviewObjectUrlSyncMock.mockReturnValue('blob:cached-preview');

    const { result } = renderHook(() =>
      useXhrImagePreview([candidate], { current: new Set<string>() }, 'disabled-cached', { enabled: false })
    );

    await waitFor(() => {
      expect(result.current.src).toBe('blob:cached-preview');
      expect(result.current.exhausted).toBe(false);
    });

    expect(getCachedPreviewObjectUrlMock).not.toHaveBeenCalled();
    expect(downloadBlobWithXhrMock).not.toHaveBeenCalled();
  });

  it('scopes direct-url memory cache entries by reset key to avoid stale preview reuse', async () => {
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
      expect(getCachedPreviewObjectUrlSyncMock).toHaveBeenCalledWith(scopedCacheKey);
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

    expect(getCachedPreviewObjectUrlSyncMock).not.toHaveBeenCalled();
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

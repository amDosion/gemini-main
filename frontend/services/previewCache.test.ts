// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mediaCacheMock = vi.hoisted(() => {
  const identity = {
    cacheKey: 'media:url:preview-photo',
    sourceUrl: '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12',
    canonicalUrl: 'preview:cloud-storage-preview:https://cdn.example.com/photo.png',
    versionSignature: 'rev:12',
    storageRevision: '12',
    userScope: 'preview-user',
    persistable: true,
  };

  return {
    identity,
    getCachedMediaObjectUrl: vi.fn(),
    getCachedMediaObjectUrlSync: vi.fn(),
    evictCachedMediaObjectUrl: vi.fn(),
    resolveMediaCacheIdentity: vi.fn(),
    saveMediaBlobToCache: vi.fn(),
    getDefaultMediaCacheUserScope: vi.fn(),
  };
});

vi.mock('./mediaCache', () => ({
  getCachedMediaObjectUrl: mediaCacheMock.getCachedMediaObjectUrl,
  getCachedMediaObjectUrlSync: mediaCacheMock.getCachedMediaObjectUrlSync,
  evictCachedMediaObjectUrl: mediaCacheMock.evictCachedMediaObjectUrl,
  resolveMediaCacheIdentity: mediaCacheMock.resolveMediaCacheIdentity,
  saveMediaBlobToCache: mediaCacheMock.saveMediaBlobToCache,
  getDefaultMediaCacheUserScope: mediaCacheMock.getDefaultMediaCacheUserScope,
}));

import {
  getCachedPreviewObjectUrl,
  evictCachedPreviewObjectUrl,
  clearPreviewCacheForLogout,
  savePreviewBlobToCache,
} from './previewCache';

const proxyUrl =
  '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12';

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
};

describe('previewCache shared media cache compatibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValue(null);
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValue(null);
    mediaCacheMock.evictCachedMediaObjectUrl.mockReturnValue(false);
    mediaCacheMock.getDefaultMediaCacheUserScope.mockReturnValue('preview-user');
    mediaCacheMock.resolveMediaCacheIdentity.mockImplementation((source) =>
      source?.url === proxyUrl ? mediaCacheMock.identity : null
    );
    mediaCacheMock.saveMediaBlobToCache.mockResolvedValue({
      objectUrl: 'blob:migrated-preview',
      status: 'fresh',
      metadata: null,
    });
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:legacy-memory'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('reads storage preview hits from the shared media cache first', async () => {
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValueOnce('blob:shared-preview');

    await expect(getCachedPreviewObjectUrl(proxyUrl)).resolves.toBe('blob:shared-preview');

    expect(mediaCacheMock.resolveMediaCacheIdentity).toHaveBeenCalledWith({
      url: proxyUrl,
      mimeType: 'image/png',
      userScope: 'preview-user',
    });
    expect(mediaCacheMock.getCachedMediaObjectUrl).toHaveBeenCalledWith(
      mediaCacheMock.identity,
      { allowStale: false }
    );
  });

  it('can bypass shared memory object urls and rebuild storage previews from persistent media cache', async () => {
    mediaCacheMock.getCachedMediaObjectUrlSync.mockImplementation(() => {
      throw new Error('preview memory cache should be bypassed');
    });
    mediaCacheMock.getCachedMediaObjectUrl.mockResolvedValueOnce('blob:persistent-preview');

    await expect(
      getCachedPreviewObjectUrl(proxyUrl, { allowMemory: false })
    ).resolves.toBe('blob:persistent-preview');

    expect(mediaCacheMock.getCachedMediaObjectUrlSync).not.toHaveBeenCalled();
    expect(mediaCacheMock.getCachedMediaObjectUrl).toHaveBeenCalledWith(
      mediaCacheMock.identity,
      { allowStale: false, allowMemory: false }
    );
  });

  it('uses version-strict shared memory reads through the async public API by default', async () => {
    mediaCacheMock.getCachedMediaObjectUrlSync.mockReturnValueOnce('blob:shared-memory');

    await expect(getCachedPreviewObjectUrl(proxyUrl)).resolves.toBe('blob:shared-memory');
    expect(mediaCacheMock.getCachedMediaObjectUrlSync).toHaveBeenCalledWith(
      mediaCacheMock.identity,
      { allowStale: false }
    );
    expect(mediaCacheMock.getCachedMediaObjectUrl).not.toHaveBeenCalled();
  });

  it('evicts failed storage preview object urls through the shared media cache', () => {
    mediaCacheMock.evictCachedMediaObjectUrl.mockReturnValueOnce(true);

    expect(evictCachedPreviewObjectUrl(proxyUrl, 'blob:failed-preview')).toBe(true);
    expect(mediaCacheMock.evictCachedMediaObjectUrl).toHaveBeenCalledWith(
      mediaCacheMock.identity,
      'blob:failed-preview'
    );
  });

  it('writes storage preview downloads to the shared media cache instead of the legacy cache', async () => {
    const legacyOpen = vi.fn();
    Object.defineProperty(window, 'caches', {
      configurable: true,
      value: { open: legacyOpen },
    });
    const blob = new Blob(['preview'], { type: 'image/png' });

    await savePreviewBlobToCache(proxyUrl, blob, 'image/png');

    expect(mediaCacheMock.saveMediaBlobToCache).toHaveBeenCalledWith(
      mediaCacheMock.identity,
      blob,
      { contentType: 'image/png' }
    );
    expect(legacyOpen).not.toHaveBeenCalled();
  });

  it('does not probe the legacy preview Cache Storage when shared media cache misses', async () => {
    const legacyOpen = vi.fn();
    Object.defineProperty(window, 'caches', {
      configurable: true,
      value: { open: legacyOpen },
    });

    await expect(getCachedPreviewObjectUrl(proxyUrl)).resolves.toBeNull();

    expect(mediaCacheMock.getCachedMediaObjectUrl).toHaveBeenCalledWith(
      mediaCacheMock.identity,
      { allowStale: false }
    );
    expect(legacyOpen).not.toHaveBeenCalled();
  });

  it('does not create a second preview cache when the shared cache save throws', async () => {
    mediaCacheMock.saveMediaBlobToCache.mockRejectedValueOnce(new Error('cache unavailable'));
    const blob = new Blob(['preview'], { type: 'image/png' });

    await savePreviewBlobToCache(proxyUrl, blob, 'image/png');

    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('does not write a late legacy preview object url after preview user scope changes', async () => {
    let previewScope = 'preview-user-1';
    const deferredSave = createDeferred<never>();
    const blob = new Blob(['late-preview'], { type: 'image/png' });
    mediaCacheMock.getDefaultMediaCacheUserScope.mockImplementation(() => previewScope);
    mediaCacheMock.saveMediaBlobToCache.mockReturnValueOnce(deferredSave.promise);

    const pendingSave = savePreviewBlobToCache(proxyUrl, blob, 'image/png');
    await Promise.resolve();

    previewScope = 'preview-user-2';
    deferredSave.reject(new Error('cache unavailable after scope switch'));

    await expect(pendingSave).resolves.toBeNull();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    await expect(getCachedPreviewObjectUrl(proxyUrl)).resolves.toBeNull();
  });

  it('writes remote direct URL preview downloads through the shared proxy media identity', async () => {
    const legacyOpen = vi.fn();
    Object.defineProperty(window, 'caches', {
      configurable: true,
      value: { open: legacyOpen },
    });
    const directUrl = 'https://cdn.example.com/photo.png';
    const scopedPreviewKey = `${directUrl}::storage-1:/photo.png:${directUrl}:42`;
    const proxyIdentity = {
      ...mediaCacheMock.identity,
      cacheKey: 'media:preview:remote-direct',
      sourceUrl: `/api/storage/preview?url=${encodeURIComponent(directUrl)}`,
      canonicalUrl: `preview:preview-user:${directUrl}`,
      versionSignature: `updated:${scopedPreviewKey}`,
      storageRevision: null,
    };
    const blob = new Blob(['direct-preview'], { type: 'image/png' });

    mediaCacheMock.resolveMediaCacheIdentity.mockImplementation((source) =>
      source?.url === proxyIdentity.sourceUrl ? proxyIdentity : null
    );

    await savePreviewBlobToCache(scopedPreviewKey, blob, 'image/png');

    expect(mediaCacheMock.resolveMediaCacheIdentity).toHaveBeenCalledWith({
      url: proxyIdentity.sourceUrl,
      mimeType: 'image/png',
      userScope: 'preview-user',
      updatedAt: scopedPreviewKey,
    });
    expect(mediaCacheMock.saveMediaBlobToCache).toHaveBeenCalledWith(
      proxyIdentity,
      blob,
      { contentType: 'image/png' }
    );
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(legacyOpen).not.toHaveBeenCalled();
  });

  it('writes same-origin direct preview fallback downloads through the shared media cache', async () => {
    const directUrl = '/api/storage/local-files/2026/05/31/direct-preview.png';
    const scopedPreviewKey = `${directUrl}::storage-1:/direct-preview.png:${directUrl}:42`;
    const directIdentity = {
      ...mediaCacheMock.identity,
      cacheKey: 'media:path:direct-preview',
      sourceUrl: directUrl,
      canonicalUrl: directUrl,
      versionSignature: `updated:${scopedPreviewKey}`,
      storageRevision: null,
    };
    const blob = new Blob(['direct-preview'], { type: 'image/png' });

    mediaCacheMock.resolveMediaCacheIdentity.mockImplementation((source) =>
      source?.url === directUrl ? directIdentity : null
    );

    await savePreviewBlobToCache(scopedPreviewKey, blob, 'image/png');

    expect(mediaCacheMock.resolveMediaCacheIdentity).toHaveBeenCalledWith({
      url: directUrl,
      mimeType: 'image/png',
      userScope: 'preview-user',
      updatedAt: scopedPreviewKey,
    });
    expect(mediaCacheMock.saveMediaBlobToCache).toHaveBeenCalledWith(
      directIdentity,
      blob,
      { contentType: 'image/png' }
    );
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('clears legacy preview cache state for logout', async () => {
    const deleteLegacyCache = vi.fn(async () => true);
    Object.defineProperty(window, 'caches', {
      configurable: true,
      value: { delete: deleteLegacyCache },
    });
    window.localStorage.setItem('cloud-storage-preview-meta-v1', JSON.stringify({ [proxyUrl]: Date.now() }));

    await clearPreviewCacheForLogout();

    expect(deleteLegacyCache).toHaveBeenCalledWith('cloud-storage-preview-v1');
    expect(window.localStorage.getItem('cloud-storage-preview-meta-v1')).toBeNull();
  });
});

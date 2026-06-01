// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';

const metadataStore = new Map<string, any>();

vi.mock('./mediaCacheIndexedDb', () => ({
  readMediaCacheMetadata: vi.fn(async (cacheKey: string) => metadataStore.get(cacheKey) || null),
  writeMediaCacheMetadata: vi.fn(async (metadata: any) => {
    metadataStore.set(metadata.cacheKey, metadata);
  }),
  deleteMediaCacheMetadata: vi.fn(async (cacheKey: string) => {
    metadataStore.delete(cacheKey);
  }),
  listMediaCacheMetadata: vi.fn(async () => Array.from(metadataStore.values())),
}));

import {
  createManagedMediaObjectUrl,
  evictCachedMediaObjectUrl,
  fetchAndStoreMedia,
  clearAllMediaCache,
  getMediaCacheDiagnosticsSnapshot,
  getCachedMediaObjectUrl,
  getCachedMediaObjectUrlSync,
  getMediaCacheStorageRequestUrl,
  releaseMediaObjectUrl,
  resetMediaCacheDiagnostics,
  resolveMediaCacheIdentity,
  retainMediaObjectUrl,
  revokeManagedMediaObjectUrl,
  saveMediaBlobToCache,
  __setMediaCacheDiagnosticsEnabledForTest,
  __setMediaCacheLimitsForTest,
  __resetMediaCacheForTest,
} from './mediaCache';
import { cacheManager } from './CacheManager';
import { setPrivateCacheUserScope } from './privateCacheScope';

const cacheEntries = new Map<string, Response>();
let rejectCachePut = false;

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
};

const installCacheStorageMock = () => {
  Object.defineProperty(window, 'caches', {
    configurable: true,
    value: {
      open: vi.fn(async () => ({
        match: vi.fn(async (request: RequestInfo | URL) => {
          const key = request instanceof Request ? request.url : String(request);
          const response = cacheEntries.get(key);
          return response ? response.clone() : undefined;
        }),
        put: vi.fn(async (request: RequestInfo | URL, response: Response) => {
          if (rejectCachePut) {
            throw new Error('quota exceeded');
          }
          const key = request instanceof Request ? request.url : String(request);
          cacheEntries.set(key, response.clone());
        }),
        delete: vi.fn(async (request: RequestInfo | URL) => {
          const key = request instanceof Request ? request.url : String(request);
          return cacheEntries.delete(key);
        }),
      })),
      delete: vi.fn(async () => {
        cacheEntries.clear();
        return true;
      }),
    },
  });
};

describe('mediaCache', () => {
  beforeEach(() => {
    metadataStore.clear();
    cacheEntries.clear();
    rejectCachePut = false;
    __setMediaCacheDiagnosticsEnabledForTest(false);
    __resetMediaCacheForTest();
    setPrivateCacheUserScope('user-1');
    installCacheStorageMock();
    vi.stubGlobal('fetch', vi.fn());
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
    vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      const size = typeof (blob as Blob).size === 'number' ? (blob as Blob).size : 0;
      return `blob:cached-${size}`;
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
  });

  it('returns a persistent Cache Storage hit without requesting the backend', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-1',
      url: '/api/storage/local-files/generated/a.png',
      mimeType: 'image/png',
      updatedAt: 1000,
      userScope: 'user-1',
    });

    expect(identity).toBeTruthy();
    const cacheKey = identity!.cacheKey;
    metadataStore.set(cacheKey, {
      cacheKey,
      sourceUrl: identity!.sourceUrl,
      canonicalUrl: identity!.canonicalUrl,
      versionSignature: identity!.versionSignature,
      contentType: 'image/png',
      cachedAt: Date.now(),
      lastAccessedAt: Date.now(),
      userScope: 'user-1',
    });
    cacheEntries.set(
      getMediaCacheStorageRequestUrl(cacheKey),
      new Response('cached-bytes', {
        headers: { 'Content-Type': 'image/png' },
      })
    );

    await expect(getCachedMediaObjectUrl(identity!)).resolves.toBe('blob:cached-12');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('does not replace a healthy shared object url when a history thumbnail skips the initial memory lookup', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:shared-history-thumbnail-${createdObjectUrlIndex}`;
    });

    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-shared-history-thumbnail',
      url: '/api/storage/local-files/generated/shared-history-thumbnail.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;

    const saved = await saveMediaBlobToCache(identity, await new Response('shared').blob(), {
      contentType: 'image/png',
    });

    await expect(getCachedMediaObjectUrl(identity, { allowMemory: false })).resolves.toBe(
      saved.objectUrl
    );
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);

    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(saved.objectUrl);
    vi.useRealTimers();
  });

  it('can rebuild a fresh object url from persistent cache when virtualized thumbnails opt out of memory reuse', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:rebuilt-virtual-thumbnail-${createdObjectUrlIndex}`;
    });

    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-rebuild-virtual-thumbnail',
      url: '/api/storage/local-files/generated/rebuild-virtual-thumbnail.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;

    const saved = await saveMediaBlobToCache(identity, await new Response('thumbnail').blob(), {
      contentType: 'image/png',
    });

    await expect(
      getCachedMediaObjectUrl(identity, {
        allowMemory: false,
        replaceObjectUrl: true,
      } as Parameters<typeof getCachedMediaObjectUrl>[1])
    ).resolves.toBe('blob:rebuilt-virtual-thumbnail-2');
    expect(URL.createObjectURL).toHaveBeenCalledTimes(2);

    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(saved.objectUrl);
    vi.useRealTimers();
  });

  it('rebuilds from persistent storage after a failed in-memory object url is evicted', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:rebuilt-persistent-${createdObjectUrlIndex}`;
    });

    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-rebuild-from-persistent',
      url: '/api/storage/local-files/generated/rebuild-from-persistent.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const staleObjectUrl = 'blob:https://gemini.dicry.cn:18443/stale-reused-history-thumb';
    const now = Date.now();

    cacheManager.set(`mediaObjectUrl:${identity.cacheKey}`, {
      objectUrl: staleObjectUrl,
      versionSignature: identity.versionSignature,
      updatedAt: now,
      lastAccessedAt: now,
    });
    metadataStore.set(identity.cacheKey, {
      cacheKey: identity.cacheKey,
      sourceUrl: identity.sourceUrl,
      canonicalUrl: identity.canonicalUrl,
      versionSignature: identity.versionSignature,
      contentType: 'image/png',
      cachedAt: now,
      lastAccessedAt: now,
      userScope: 'user-1',
    });
    cacheEntries.set(
      getMediaCacheStorageRequestUrl(identity.cacheKey),
      new Response('rebuilt-bytes', {
        headers: { 'Content-Type': 'image/png' },
      })
    );

    expect(evictCachedMediaObjectUrl(identity, staleObjectUrl)).toBe(true);

    await expect(getCachedMediaObjectUrl(identity, { allowMemory: false })).resolves.toBe(
      'blob:rebuilt-persistent-1'
    );
    expect(fetch).not.toHaveBeenCalled();
    expect(getCachedMediaObjectUrlSync(identity)).toBe('blob:rebuilt-persistent-1');
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(staleObjectUrl);
    vi.useRealTimers();
  });

  it('stores Blob bytes in Cache Storage and metadata in IndexedDB after a miss', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-2',
      url: '/api/storage/local-files/generated/b.png',
      mimeType: 'image/png',
      updatedAt: 2000,
      userScope: 'user-1',
    });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(
      new Response('fresh-bytes', {
        status: 200,
        headers: {
          'Content-Type': 'image/png',
          ETag: '"fresh-etag"',
        },
      })
    );

    const result = await fetchAndStoreMedia(identity!);

    expect(result.objectUrl).toBe('blob:cached-11');
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity!.cacheKey))).toBe(true);
    expect(metadataStore.get(identity!.cacheKey)).toMatchObject({
      cacheKey: identity!.cacheKey,
      versionSignature: identity!.versionSignature,
      etag: '"fresh-etag"',
      userScope: 'user-1',
    });
  });

  it('scopes attachment cache keys by user to prevent cross-account reuse', () => {
    const firstIdentity = resolveMediaCacheIdentity({
      attachmentId: 'shared-att-id',
      url: '/api/storage/local-files/generated/shared.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    });
    const secondIdentity = resolveMediaCacheIdentity({
      attachmentId: 'shared-att-id',
      url: '/api/storage/local-files/generated/shared.png',
      mimeType: 'image/png',
      userScope: 'user-2',
    });

    expect(firstIdentity?.cacheKey).toBeTruthy();
    expect(secondIdentity?.cacheKey).toBeTruthy();
    expect(firstIdentity?.cacheKey).not.toBe(secondIdentity?.cacheKey);
    expect(firstIdentity?.userScope).toBe('user-1');
    expect(secondIdentity?.userScope).toBe('user-2');
  });

  it('uses one global media key for the same durable storage url even when attachment metadata differs', () => {
    const withAttachment = resolveMediaCacheIdentity({
      attachmentId: 'att-durable-url',
      url: '/api/storage/local-files/generated/global-key.png',
      mimeType: 'image/png',
      updatedAt: 1000,
      userScope: 'user-1',
    });
    const withoutAttachment = resolveMediaCacheIdentity({
      url: '/api/storage/local-files/generated/global-key.png',
      mimeType: 'image/png',
      updatedAt: 1000,
      userScope: 'user-1',
    });
    const differentAttachment = resolveMediaCacheIdentity({
      attachmentId: 'att-durable-url-copy',
      url: '/api/storage/local-files/generated/global-key.png',
      mimeType: 'image/png',
      updatedAt: 1000,
      userScope: 'user-1',
    });

    expect(withAttachment?.cacheKey).toBeTruthy();
    expect(withAttachment?.cacheKey).toBe(withoutAttachment?.cacheKey);
    expect(withAttachment?.cacheKey).toBe(differentAttachment?.cacheKey);
    expect(withAttachment?.cacheKey).toContain(':path:');
  });

  it('does not read persistent media metadata written for another user scope', async () => {
    const firstIdentity = resolveMediaCacheIdentity({
      attachmentId: 'same-att-id',
      url: '/api/storage/local-files/generated/same.png',
      mimeType: 'image/png',
      updatedAt: 1000,
      userScope: 'user-1',
    })!;
    const secondIdentity = resolveMediaCacheIdentity({
      attachmentId: 'same-att-id',
      url: '/api/storage/local-files/generated/same.png',
      mimeType: 'image/png',
      updatedAt: 1000,
      userScope: 'user-2',
    })!;

    metadataStore.set(secondIdentity.cacheKey, {
      cacheKey: secondIdentity.cacheKey,
      sourceUrl: secondIdentity.sourceUrl,
      canonicalUrl: secondIdentity.canonicalUrl,
      versionSignature: secondIdentity.versionSignature,
      contentType: 'image/png',
      cachedAt: Date.now(),
      lastAccessedAt: Date.now(),
      userScope: 'user-1',
    });
    cacheEntries.set(
      getMediaCacheStorageRequestUrl(secondIdentity.cacheKey),
      new Response('wrong-user-bytes', {
        headers: { 'Content-Type': 'image/png' },
      })
    );

    await expect(getCachedMediaObjectUrl(secondIdentity)).resolves.toBeNull();
    expect(getCachedMediaObjectUrlSync(firstIdentity)).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('does not return cached media object urls for an identity outside the current private scope', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-stale-read-scope',
      url: '/api/storage/local-files/generated/stale-read-scope.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;

    setPrivateCacheUserScope('user-1');
    await saveMediaBlobToCache(identity, await new Response('read-scope').blob(), {
      contentType: 'image/png',
    });
    expect(getCachedMediaObjectUrlSync(identity)).toBe('blob:cached-10');

    setPrivateCacheUserScope('user-2');

    expect(getCachedMediaObjectUrlSync(identity)).toBeNull();
    await expect(getCachedMediaObjectUrl(identity)).resolves.toBeNull();
  });

  it('does not probe browser HTTP cache with only-if-cached when controlled cache misses', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-browser-cache',
      url: '/api/storage/local-files/generated/browser-cache.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    });
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.cache === 'only-if-cached' && init?.mode === 'same-origin') {
        throw new Error('browser HTTP cache probe should not run');
      }
      return new Response('backend-bytes', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      });
    });

    const result = await fetchAndStoreMedia(identity!);

    expect(result.objectUrl).toBe('blob:cached-13');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/storage/local-files/generated/browser-cache.png',
      expect.objectContaining({
        method: 'GET',
      })
    );
    expect(fetchMock.mock.calls[0][1]).not.toEqual(
      expect.objectContaining({
        cache: 'only-if-cached',
      })
    );
    expect(metadataStore.get(identity!.cacheKey)).toMatchObject({
      cacheKey: identity!.cacheKey,
      sourceUrl: '/api/storage/local-files/generated/browser-cache.png',
    });
  });

  it('caches temporary file-backed blob sources by attachment id without reusing the raw blob url', async () => {
    const file = new File(['local-bytes'], 'upload.png', { type: 'image/png' });
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-local-blob',
      url: 'blob:https://gemini.dicry.cn:18443/local-preview',
      mimeType: 'image/png',
      file,
      userScope: 'user-1',
    });

    expect(identity).toMatchObject({
      cacheKey: expect.stringMatching(/^media:[a-z0-9]+:attachment:att-local-blob$/),
      sourceUrl: 'blob:https://gemini.dicry.cn:18443/local-preview',
      userScope: 'user-1',
      persistable: true,
    });

    const result = await fetchAndStoreMedia(identity!);

    expect(fetch).not.toHaveBeenCalled();
    expect(result.objectUrl).toBe('blob:cached-11');
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity!.cacheKey))).toBe(true);
    expect(metadataStore.get(identity!.cacheKey)).toMatchObject({
      cacheKey: identity!.cacheKey,
      versionSignature: identity!.versionSignature,
      userScope: 'user-1',
    });
  });

  it('prefers a durable cloud url over a stale blob display url for the same attachment', () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-cloud-ready',
      url: 'blob:https://gemini.dicry.cn:18443/stale-preview',
      cloudUrl: '/api/storage/local-files/generated/cloud-ready.png',
      mimeType: 'image/png',
      uploadStatus: 'completed',
      userScope: 'user-1',
    });

    expect(identity).toMatchObject({
      cacheKey: expect.stringMatching(/^media:[a-z0-9]+:path:[a-z0-9]+$/),
      sourceUrl: '/api/storage/local-files/generated/cloud-ready.png',
      canonicalUrl: '/api/storage/local-files/generated/cloud-ready.png',
    });
    expect(identity?.temporary).toBeUndefined();
    expect(identity?.seedUrl).toBeNull();
  });

  it('prefers snake_case durable cloud urls over stale blob display urls from history payloads', () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-snake-cloud-ready',
      url: 'blob:https://gemini.dicry.cn:18443/stale-snake-preview',
      cloud_url: '/api/storage/local-files/generated/snake-cloud-ready.png',
      mimeType: 'image/png',
      uploadStatus: 'completed',
      userScope: 'user-1',
    } as any);

    expect(identity).toMatchObject({
      cacheKey: expect.stringMatching(/^media:[a-z0-9]+:path:[a-z0-9]+$/),
      sourceUrl: '/api/storage/local-files/generated/snake-cloud-ready.png',
      canonicalUrl: '/api/storage/local-files/generated/snake-cloud-ready.png',
    });
    expect(identity?.temporary).toBeUndefined();
  });

  it('recognizes raw snake_case image metadata before session normalization runs', () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-raw-snake-image',
      url: 'blob:https://gemini.dicry.cn:18443/raw-snake-image-preview',
      mime_type: 'image/png',
      upload_status: 'pending',
      upload_task_id: 'upload-raw-snake-image',
      userScope: 'user-1',
    });

    expect(identity).toMatchObject({
      cacheKey: expect.stringMatching(/^media:[a-z0-9]+:attachment:att-raw-snake-image$/),
      sourceUrl: 'blob:https://gemini.dicry.cn:18443/raw-snake-image-preview',
      versionSignature: 'upload:upload-raw-snake-image:pending',
      temporary: true,
    });
  });

  it('seeds the durable attachment cache from an already available data url without requesting storage', async () => {
    const inlineDataUrl = 'data:image/png;base64,aW5saW5lLWJ5dGVz';
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-inline-ready',
      url: inlineDataUrl,
      cloudUrl: '/api/storage/local-files/generated/inline-ready.png',
      mimeType: 'image/png',
      uploadStatus: 'completed',
      userScope: 'user-1',
    });

    expect(identity).toMatchObject({
      cacheKey: expect.stringMatching(/^media:[a-z0-9]+:path:[a-z0-9]+$/),
      sourceUrl: '/api/storage/local-files/generated/inline-ready.png',
      canonicalUrl: '/api/storage/local-files/generated/inline-ready.png',
    });

    const result = await fetchAndStoreMedia(identity!);

    expect(fetch).not.toHaveBeenCalled();
    expect(result.objectUrl).toBe('blob:cached-12');
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity!.cacheKey))).toBe(true);
    expect(metadataStore.get(identity!.cacheKey)).toMatchObject({
      cacheKey: identity!.cacheKey,
      sourceUrl: '/api/storage/local-files/generated/inline-ready.png',
      canonicalUrl: '/api/storage/local-files/generated/inline-ready.png',
      userScope: 'user-1',
    });
  });

  it('does not fetch a stale blob seed when a durable storage url is available', async () => {
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/stale-inline-preview';
    const durableUrl = '/api/storage/local-files/generated/blob-seed-durable.png';
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-stale-blob-seed',
      url: staleBlobUrl,
      cloudUrl: durableUrl,
      mimeType: 'image/png',
      uploadStatus: 'completed',
      userScope: 'user-1',
    })!;
    const requestedUrls: string[] = [];

    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const requestUrl = input instanceof Request ? input.url : String(input);
      requestedUrls.push(requestUrl);

      if (requestUrl === durableUrl) {
        return new Response('durable-bytes', {
          status: 200,
          headers: { 'Content-Type': 'image/png' },
        });
      }

      if (requestUrl.startsWith('blob:')) {
        throw new Error('stale blob seed should not be fetched');
      }

      throw new Error(`Unexpected media cache request: ${requestUrl}`);
    });

    await fetchAndStoreMedia(identity);

    expect(requestedUrls).toEqual([durableUrl]);
  });

  it('recovers a stale temporary blob identity through the attachment cloud url before fetching media', async () => {
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/revoked-preview';
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-stale-blob',
      url: staleBlobUrl,
      mimeType: 'image/png',
      userScope: 'user-1',
    });
    const requestedUrls: string[] = [];

    expect(identity).toMatchObject({
      cacheKey: expect.stringMatching(/^media:[a-z0-9]+:attachment:att-stale-blob$/),
      attachmentId: 'att-stale-blob',
      sourceUrl: staleBlobUrl,
      temporary: true,
    });

    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const requestUrl = input instanceof Request ? input.url : String(input);
      requestedUrls.push(requestUrl);

      if (requestUrl === '/api/attachments/att-stale-blob/cloud-url') {
        return new Response(
          JSON.stringify({
            url: '/api/storage/local-files/generated/recovered.png',
            uploadStatus: 'completed',
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (requestUrl === '/api/storage/local-files/generated/recovered.png') {
        return new Response('recovered-bytes', {
          status: 200,
          headers: { 'Content-Type': 'image/png' },
        });
      }

      if (requestUrl.startsWith('blob:')) {
        throw new Error('revoked blob should not be fetched before cloud-url recovery');
      }

      throw new Error(`Unexpected media cache request: ${requestUrl}`);
    });

    const result = await fetchAndStoreMedia(identity!);
    const durableIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-stale-blob',
      url: '/api/storage/local-files/generated/recovered.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;

    expect(result.objectUrl).toBe('blob:cached-15');
    expect(requestedUrls).toEqual([
      '/api/attachments/att-stale-blob/cloud-url',
      '/api/storage/local-files/generated/recovered.png',
    ]);
    expect(durableIdentity.cacheKey).toContain(':path:');
    expect(metadataStore.get(identity!.cacheKey)).toBeUndefined();
    expect(metadataStore.get(durableIdentity.cacheKey)).toMatchObject({
      cacheKey: durableIdentity.cacheKey,
      sourceUrl: '/api/storage/local-files/generated/recovered.png',
      canonicalUrl: '/api/storage/local-files/generated/recovered.png',
      userScope: 'user-1',
    });
  });

  it('does not fetch a raw temporary blob url when no source blob or durable url is available', async () => {
    const staleBlobUrl = 'blob:https://gemini.dicry.cn:18443/missing-history-thumbnail';
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-missing-history-thumbnail',
      url: staleBlobUrl,
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const requestedUrls: string[] = [];

    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const requestUrl = input instanceof Request ? input.url : String(input);
      requestedUrls.push(requestUrl);

      if (requestUrl === '/api/attachments/att-missing-history-thumbnail/cloud-url') {
        return new Response(JSON.stringify({ url: null, uploadStatus: 'pending' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      if (requestUrl.startsWith('blob:')) {
        throw new Error('raw blob urls should not be fetched after durable lookup misses');
      }

      throw new Error(`Unexpected temporary media request: ${requestUrl}`);
    });

    await expect(fetchAndStoreMedia(identity)).rejects.toThrow('Temporary blob media source');
    expect(requestedUrls).toEqual(['/api/attachments/att-missing-history-thumbnail/cloud-url']);
  });

  it('uses the global durable cache after a temporary attachment resolves to a cached storage url', async () => {
    const durableIdentity = resolveMediaCacheIdentity({
      url: '/api/storage/local-files/generated/recovered-cached.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    await saveMediaBlobToCache(durableIdentity, await new Response('already-cached').blob(), {
      contentType: 'image/png',
    });

    const tempIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-stale-blob-cached',
      url: 'blob:https://gemini.dicry.cn:18443/revoked-preview-cached',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const requestedUrls: string[] = [];

    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const requestUrl = input instanceof Request ? input.url : String(input);
      requestedUrls.push(requestUrl);

      if (requestUrl === '/api/attachments/att-stale-blob-cached/cloud-url') {
        return new Response(
          JSON.stringify({
            url: '/api/storage/local-files/generated/recovered-cached.png',
            uploadStatus: 'completed',
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      throw new Error(`Storage media should have been served from cache: ${requestUrl}`);
    });

    const result = await fetchAndStoreMedia(tempIdentity);

    expect(result.objectUrl).toBe('blob:cached-14');
    expect(requestedUrls).toEqual(['/api/attachments/att-stale-blob-cached/cloud-url']);
  });

  it('uses the durable cache when forced recovery resolves a temporary attachment', async () => {
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:forced-temp-recovery-${createdObjectUrlIndex}`;
    });

    const durableUrl = '/api/storage/local-files/generated/forced-temp-recovery.png';
    const durableIdentity = resolveMediaCacheIdentity({
      url: durableUrl,
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    await saveMediaBlobToCache(durableIdentity, await new Response('old-durable').blob(), {
      contentType: 'image/png',
    });

    const tempIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-forced-temp-recovery',
      url: 'blob:https://gemini.dicry.cn:18443/revoked-forced-temp',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const requestedUrls: string[] = [];

    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const requestUrl = input instanceof Request ? input.url : String(input);
      requestedUrls.push(requestUrl);

      if (requestUrl === '/api/attachments/att-forced-temp-recovery/cloud-url') {
        return new Response(JSON.stringify({ url: durableUrl, uploadStatus: 'completed' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      throw new Error(`Durable media should have been served from cache: ${requestUrl}`);
    });

    const recovered = await fetchAndStoreMedia(tempIdentity, {
      allowRevalidate: false,
      replaceObjectUrl: true,
    });

    expect(recovered.objectUrl).toBe('blob:forced-temp-recovery-1');
    expect(requestedUrls).toEqual(['/api/attachments/att-forced-temp-recovery/cloud-url']);
  });

  it('deduplicates durable storage downloads while a temporary attachment resolves to the same global media key', async () => {
    const durableUrl = '/api/storage/local-files/generated/resolved-dedupe.png';
    const tempIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-resolve-dedupe',
      url: 'blob:https://gemini.dicry.cn:18443/revoked-preview-dedupe',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const durableIdentity = resolveMediaCacheIdentity({
      url: durableUrl,
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const storageStarted = createDeferred<void>();
    const storageResponse = createDeferred<Response>();
    let storageRequestCount = 0;

    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const requestUrl = input instanceof Request ? input.url : String(input);

      if (requestUrl === '/api/attachments/att-resolve-dedupe/cloud-url') {
        return new Response(
          JSON.stringify({
            url: durableUrl,
            uploadStatus: 'completed',
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (requestUrl === durableUrl) {
        storageRequestCount += 1;
        storageStarted.resolve();
        const response = await storageResponse.promise;
        return response.clone();
      }

      throw new Error(`Unexpected media cache request: ${requestUrl}`);
    });

    const tempPromise = fetchAndStoreMedia(tempIdentity);
    await storageStarted.promise;
    const durablePromise = fetchAndStoreMedia(durableIdentity);
    await Promise.resolve();

    expect(storageRequestCount).toBe(1);

    storageResponse.resolve(
      new Response('resolved-dedupe', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      })
    );
    await expect(Promise.all([tempPromise, durablePromise])).resolves.toHaveLength(2);
  });

  it('deduplicates concurrent backend requests for the same cache key', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-3',
      url: '/api/storage/local-files/generated/c.png',
      mimeType: 'image/png',
      updatedAt: 3000,
      userScope: 'user-1',
    });
    vi.mocked(fetch).mockResolvedValue(
      new Response('one-request', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      })
    );

    await Promise.all([fetchAndStoreMedia(identity!), fetchAndStoreMedia(identity!)]);

    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('does not deduplicate different temporary file versions that reuse one attachment id', async () => {
    const firstIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-reused-temporary-version',
      url: 'blob:https://gemini.dicry.cn:18443/first-temporary-version',
      mimeType: 'image/png',
      file: new Blob(['a'], { type: 'image/png' }),
      userScope: 'user-1',
    })!;
    const secondIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-reused-temporary-version',
      url: 'blob:https://gemini.dicry.cn:18443/second-temporary-version',
      mimeType: 'image/png',
      file: new Blob(['bb'], { type: 'image/png' }),
      userScope: 'user-1',
    })!;

    expect(firstIdentity.cacheKey).toBe(secondIdentity.cacheKey);
    expect(firstIdentity.versionSignature).not.toBe(secondIdentity.versionSignature);

    const [firstResult, secondResult] = await Promise.all([
      fetchAndStoreMedia(firstIdentity),
      fetchAndStoreMedia(secondIdentity),
    ]);

    expect(firstResult.objectUrl).toBe('blob:cached-1');
    expect(secondResult.objectUrl).toBe('blob:cached-2');
    expect(URL.createObjectURL).toHaveBeenCalledTimes(2);
  });

  it('stores externally downloaded Blob bytes through the shared media cache', async () => {
    setPrivateCacheUserScope('cloud-storage-preview');
    const identity = resolveMediaCacheIdentity({
      url: '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fphoto.png&rev=12',
      mimeType: 'image/png',
      userScope: 'cloud-storage-preview',
    });

    const previewBlob = await new Response('xhr-preview', {
      headers: { 'Content-Type': 'image/png' },
    }).blob();
    const result = await saveMediaBlobToCache(identity!, previewBlob, {
      contentType: 'image/png',
    });

    expect(result.objectUrl).toBe('blob:cached-11');
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity!.cacheKey))).toBe(true);
    expect(metadataStore.get(identity!.cacheKey)).toMatchObject({
      cacheKey: identity!.cacheKey,
      versionSignature: 'rev:12',
      storageRevision: '12',
      userScope: 'cloud-storage-preview',
    });
  });

  it('falls back to memory-only object urls when persistent cache writes fail', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-memory-only',
      url: '/api/storage/local-files/generated/memory-only.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    });
    const previewBlob = await new Response('memory-only', {
      headers: { 'Content-Type': 'image/png' },
    }).blob();
    rejectCachePut = true;

    const result = await saveMediaBlobToCache(identity!, previewBlob, {
      contentType: 'image/png',
    });

    expect(result).toMatchObject({
      objectUrl: 'blob:cached-11',
      status: 'fresh-memory-only',
      metadata: null,
    });
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity!.cacheKey))).toBe(false);
    expect(metadataStore.has(identity!.cacheKey)).toBe(false);
  });

  it('does not persist media bytes when the private scope changes during a save', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-stale-scope-save',
      url: '/api/storage/local-files/generated/stale-scope-save.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const blob = await new Response('stale-scope').blob();
    const putStarted = createDeferred<void>();
    const releasePut = createDeferred<void>();

    Object.defineProperty(window, 'caches', {
      configurable: true,
      value: {
        open: vi.fn(async () => ({
          match: vi.fn(async () => undefined),
          put: vi.fn(async (request: RequestInfo | URL, response: Response) => {
            putStarted.resolve();
            await releasePut.promise;
            const key = request instanceof Request ? request.url : String(request);
            cacheEntries.set(key, response.clone());
          }),
          delete: vi.fn(async (request: RequestInfo | URL) => {
            const key = request instanceof Request ? request.url : String(request);
            return cacheEntries.delete(key);
          }),
        })),
      },
    });

    setPrivateCacheUserScope('user-1');
    const pendingSave = saveMediaBlobToCache(identity, blob, { contentType: 'image/png' });
    await putStarted.promise;

    setPrivateCacheUserScope('user-2');
    releasePut.resolve();

    await expect(pendingSave).rejects.toThrow('private lifecycle changed');
    expect(metadataStore.has(identity.cacheKey)).toBe(false);
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity.cacheKey))).toBe(false);
    expect(getCachedMediaObjectUrlSync(identity)).toBeNull();
  });

  it('does not persist media bytes for an identity created under a stale private scope', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-stale-identity-scope',
      url: '/api/storage/local-files/generated/stale-identity-scope.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const blob = await new Response('stale-identity').blob();

    setPrivateCacheUserScope('user-2');

    await expect(
      saveMediaBlobToCache(identity, blob, { contentType: 'image/png' })
    ).rejects.toThrow('private lifecycle changed');
    expect(metadataStore.has(identity.cacheKey)).toBe(false);
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity.cacheKey))).toBe(false);
    expect(getCachedMediaObjectUrlSync(identity)).toBeNull();
  });

  it('clears all persistent media cache entries for logout', async () => {
    const firstIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-clear-1',
      url: '/api/storage/local-files/generated/clear-1.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    });
    const secondIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-clear-2',
      url: '/api/storage/preview?url=https%3A%2F%2Fcdn.example.com%2Fclear-2.png&rev=2',
      mimeType: 'image/png',
      userScope: 'cloud-storage-preview',
    });
    const firstBlob = await new Response('clear-one').blob();
    const secondBlob = await new Response('clear-two').blob();

    await saveMediaBlobToCache(firstIdentity!, firstBlob, { contentType: 'image/png' });
    setPrivateCacheUserScope('cloud-storage-preview');
    await saveMediaBlobToCache(secondIdentity!, secondBlob, { contentType: 'image/png' });
    setPrivateCacheUserScope('user-1');

    expect(metadataStore.size).toBe(2);
    expect(cacheEntries.size).toBe(2);
    expect(getCachedMediaObjectUrlSync(firstIdentity!)).toBe('blob:cached-9');

    await clearAllMediaCache();

    expect(metadataStore.size).toBe(0);
    expect(cacheEntries.size).toBe(0);
    expect(getCachedMediaObjectUrlSync(firstIdentity!)).toBeNull();
  });

  it('clears orphan Cache Storage media entries that no longer have IndexedDB metadata', async () => {
    const orphanCacheKey = 'media:orphan-scope:attachment:orphan-entry';
    cacheEntries.set(
      getMediaCacheStorageRequestUrl(orphanCacheKey),
      new Response('orphan-bytes', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      })
    );

    await clearAllMediaCache();

    expect(metadataStore.size).toBe(0);
    expect(cacheEntries.size).toBe(0);
  });

  it('does not repopulate media caches when an in-flight fetch resolves after cache clear', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-inflight-clear',
      url: '/api/storage/local-files/generated/inflight-clear.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const deferredNetworkResponse = createDeferred<Response>();

    vi.mocked(fetch).mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.cache === 'only-if-cached') {
        return new Response(null, { status: 504 });
      }
      return deferredNetworkResponse.promise;
    });

    const pendingFetch = fetchAndStoreMedia(identity);
    await Promise.resolve();

    await clearAllMediaCache();
    deferredNetworkResponse.resolve(
      new Response('late-bytes', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      })
    );
    await pendingFetch;

    expect(metadataStore.has(identity.cacheKey)).toBe(false);
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity.cacheKey))).toBe(false);
    expect(getCachedMediaObjectUrlSync(identity)).toBeNull();
  });

  it('revokes memory-only fetch results after the last rendered retainer releases them', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:memory-only-volatile-${createdObjectUrlIndex}`;
    });

    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-memory-only-volatile',
      url: '/api/storage/local-files/generated/memory-only-volatile.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const deferredNetworkResponse = createDeferred<Response>();

    vi.mocked(fetch).mockImplementation(async () => deferredNetworkResponse.promise);

    const pendingFetch = fetchAndStoreMedia(identity);
    await Promise.resolve();

    await clearAllMediaCache();
    deferredNetworkResponse.resolve(
      new Response('volatile-bytes', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      })
    );

    const result = await pendingFetch;

    expect(result).toMatchObject({
      objectUrl: 'blob:memory-only-volatile-1',
      status: 'fresh-memory-only',
      metadata: null,
    });

    retainMediaObjectUrl(result.objectUrl);
    releaseMediaObjectUrl(result.objectUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(result.objectUrl);
    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(result.objectUrl);
    vi.useRealTimers();
  });

  it('does not persist a fetched media response when the private scope changes during fetch', async () => {
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-inflight-scope-change',
      url: '/api/storage/local-files/generated/inflight-scope-change.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const deferredNetworkResponse = createDeferred<Response>();

    vi.mocked(fetch).mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.cache === 'only-if-cached') {
        return new Response(null, { status: 504 });
      }
      return deferredNetworkResponse.promise;
    });

    setPrivateCacheUserScope('user-1');
    const pendingFetch = fetchAndStoreMedia(identity);
    await Promise.resolve();

    setPrivateCacheUserScope('user-2');
    deferredNetworkResponse.resolve(
      new Response('late-scope-bytes', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      })
    );

    await expect(pendingFetch).rejects.toThrow('private lifecycle changed');
    expect(metadataStore.has(identity.cacheKey)).toBe(false);
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity.cacheKey))).toBe(false);
    expect(getCachedMediaObjectUrlSync(identity)).toBeNull();
  });

  it('prunes least recently used persistent entries when the cache exceeds its entry limit', async () => {
    __setMediaCacheLimitsForTest({ maxEntries: 2, maxBytes: 1024 * 1024 });
    const identities = ['one', 'two', 'three'].map((name) =>
      resolveMediaCacheIdentity({
        attachmentId: `att-prune-${name}`,
        url: `/api/storage/local-files/generated/prune-${name}.png`,
        mimeType: 'image/png',
        userScope: 'user-1',
      })!
    );

    await saveMediaBlobToCache(identities[0], await new Response('prune-one').blob(), {
      contentType: 'image/png',
    });
    await saveMediaBlobToCache(identities[1], await new Response('prune-two').blob(), {
      contentType: 'image/png',
    });
    metadataStore.set(identities[0].cacheKey, {
      ...metadataStore.get(identities[0].cacheKey),
      lastAccessedAt: 1,
    });
    metadataStore.set(identities[1].cacheKey, {
      ...metadataStore.get(identities[1].cacheKey),
      lastAccessedAt: 2,
    });

    await saveMediaBlobToCache(identities[2], await new Response('prune-three').blob(), {
      contentType: 'image/png',
    });

    expect(metadataStore.has(identities[0].cacheKey)).toBe(false);
    expect(metadataStore.has(identities[1].cacheKey)).toBe(true);
    expect(metadataStore.has(identities[2].cacheKey)).toBe(true);
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identities[0].cacheKey))).toBe(false);
    expect(cacheEntries.size).toBe(2);
  });

  it('records diagnostics from the shared cache layer without per-component duplication', async () => {
    __setMediaCacheDiagnosticsEnabledForTest(true);
    resetMediaCacheDiagnostics();
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-diagnostics',
      url: '/api/storage/local-files/generated/diagnostics.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    vi.mocked(fetch).mockImplementation(async () => {
      return new Response('diagnostic-bytes', {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      });
    });

    await Promise.all([fetchAndStoreMedia(identity), fetchAndStoreMedia(identity)]);

    let snapshot = getMediaCacheDiagnosticsSnapshot();
    expect(snapshot.enabled).toBe(true);
    expect(snapshot.counters['network-fetch']).toBe(1);
    expect(snapshot.counters['network-dedupe']).toBe(1);
    expect(snapshot.counters['cache-write']).toBe(1);
    expect(
      snapshot.recentEvents.filter((event) => event.type === 'network-fetch')
    ).toHaveLength(1);

    __resetMediaCacheForTest();
    __setMediaCacheDiagnosticsEnabledForTest(true);
    setPrivateCacheUserScope('user-1');
    await getCachedMediaObjectUrl(identity);

    snapshot = getMediaCacheDiagnosticsSnapshot();
    expect(snapshot.counters['persistent-hit']).toBe(1);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('keeps diagnostics empty when diagnostics are disabled', async () => {
    __setMediaCacheDiagnosticsEnabledForTest(false);
    resetMediaCacheDiagnostics();
    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-diagnostics-disabled',
      url: '/api/storage/local-files/generated/diagnostics-disabled.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;

    await saveMediaBlobToCache(identity, await new Response('disabled').blob(), {
      contentType: 'image/png',
    });

    const snapshot = getMediaCacheDiagnosticsSnapshot();
    expect(snapshot.enabled).toBe(false);
    expect(snapshot.counters).toEqual({});
    expect(snapshot.recentEvents).toEqual([]);
  });

  it('does not create a persistent identity for data URLs', () => {
    const identity = resolveMediaCacheIdentity({
      url: 'data:image/png;base64,abc',
      mimeType: 'image/png',
      userScope: 'user-1',
    });

    expect(identity).toBeNull();
  });

  it('prunes in-memory object urls only within the active media user scope', () => {
    const userOneIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-user-one-memory',
      url: '/api/storage/local-files/generated/user-one-memory.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const userTwoIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-user-two-memory-active',
      url: '/api/storage/local-files/generated/user-two-memory-active.png',
      mimeType: 'image/png',
      userScope: 'user-2',
    })!;
    const now = Date.now();

    cacheManager.set(`mediaObjectUrl:${userOneIdentity.cacheKey}`, {
      objectUrl: 'blob:user-one-memory',
      versionSignature: userOneIdentity.versionSignature,
      updatedAt: now - 1000,
      lastAccessedAt: now - 1000,
    });

    for (let index = 0; index < 400; index += 1) {
      const identity = resolveMediaCacheIdentity({
        attachmentId: `att-user-two-memory-${index}`,
        url: `/api/storage/local-files/generated/user-two-memory-${index}.png`,
        mimeType: 'image/png',
        userScope: 'user-2',
      })!;
      cacheManager.set(`mediaObjectUrl:${identity.cacheKey}`, {
        objectUrl: `blob:user-two-memory-${index}`,
        versionSignature: identity.versionSignature,
        updatedAt: now - 500 + index,
        lastAccessedAt: now - 500 + index,
      });
    }
    cacheManager.set(`mediaObjectUrl:${userTwoIdentity.cacheKey}`, {
      objectUrl: 'blob:user-two-memory-active',
      versionSignature: userTwoIdentity.versionSignature,
      updatedAt: now,
      lastAccessedAt: now,
    });

    setPrivateCacheUserScope('user-2');
    expect(getCachedMediaObjectUrlSync(userTwoIdentity)).toBe('blob:user-two-memory-active');
    expect(getCachedMediaObjectUrlSync(userOneIdentity)).toBeNull();

    setPrivateCacheUserScope('user-1');
    expect(getCachedMediaObjectUrlSync(userOneIdentity)).toBe('blob:user-one-memory');
  });

  it('does not revoke an object url while a mounted image still retains it', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:retained-thumbnail-${createdObjectUrlIndex}`;
    });

    const firstIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-retained-thumbnail',
      url: '/api/storage/local-files/generated/retained-thumbnail.png',
      mimeType: 'image/png',
      updatedAt: 1,
      userScope: 'user-1',
    })!;
    const secondIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-retained-thumbnail',
      url: '/api/storage/local-files/generated/retained-thumbnail.png',
      mimeType: 'image/png',
      updatedAt: 2,
      userScope: 'user-1',
    })!;

    const first = await saveMediaBlobToCache(firstIdentity, await new Response('first').blob(), {
      contentType: 'image/png',
    });
    retainMediaObjectUrl(first.objectUrl);

    const second = await saveMediaBlobToCache(secondIdentity, await new Response('second').blob(), {
      contentType: 'image/png',
    });

    expect(first.objectUrl).toBe('blob:retained-thumbnail-1');
    expect(second.objectUrl).toBe('blob:retained-thumbnail-2');
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:retained-thumbnail-1');

    releaseMediaObjectUrl(first.objectUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:retained-thumbnail-1');
    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:retained-thumbnail-1');
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:retained-thumbnail-2');
    vi.useRealTimers();
  });

  it('does not synchronously revoke a retired object url when a virtualized thumbnail unmounts', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:virtualized-retired-${createdObjectUrlIndex}`;
    });

    const firstIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-virtualized-retired',
      url: '/api/storage/local-files/generated/virtualized-retired.png',
      mimeType: 'image/png',
      updatedAt: 1,
      userScope: 'user-1',
    })!;
    const secondIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-virtualized-retired',
      url: '/api/storage/local-files/generated/virtualized-retired.png',
      mimeType: 'image/png',
      updatedAt: 2,
      userScope: 'user-1',
    })!;

    const first = await saveMediaBlobToCache(firstIdentity, await new Response('first').blob(), {
      contentType: 'image/png',
    });
    retainMediaObjectUrl(first.objectUrl);

    await saveMediaBlobToCache(secondIdentity, await new Response('second').blob(), {
      contentType: 'image/png',
    });

    releaseMediaObjectUrl(first.objectUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(first.objectUrl);

    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(first.objectUrl);
    vi.useRealTimers();
  });

  it('defers revoking replaced unretained object urls so virtualized rows do not break pending image loads', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:virtualized-replace-${createdObjectUrlIndex}`;
    });

    const firstIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-virtualized-replace',
      url: '/api/storage/local-files/generated/virtualized-replace.png',
      mimeType: 'image/png',
      updatedAt: 1,
      userScope: 'user-1',
    })!;
    const secondIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-virtualized-replace',
      url: '/api/storage/local-files/generated/virtualized-replace.png',
      mimeType: 'image/png',
      updatedAt: 2,
      userScope: 'user-1',
    })!;

    const first = await saveMediaBlobToCache(firstIdentity, await new Response('first').blob(), {
      contentType: 'image/png',
    });
    const second = await saveMediaBlobToCache(secondIdentity, await new Response('second').blob(), {
      contentType: 'image/png',
    });

    expect(first.objectUrl).toBe('blob:virtualized-replace-1');
    expect(second.objectUrl).toBe('blob:virtualized-replace-2');
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:virtualized-replace-1');

    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:virtualized-replace-1');
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:virtualized-replace-2');
    vi.useRealTimers();
  });

  it('defers managed object url revocation until retainers release it', async () => {
    vi.useFakeTimers();
    const objectUrl = createManagedMediaObjectUrl(
      await new Response('managed-retained').blob()
    );

    expect(objectUrl).toBe('blob:cached-16');

    retainMediaObjectUrl(objectUrl);
    revokeManagedMediaObjectUrl(objectUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(objectUrl);

    releaseMediaObjectUrl(objectUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(objectUrl);
    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(objectUrl);
    vi.useRealTimers();
  });

  it('keeps a retained cached object url readable while a revoke is deferred', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:retained-readable-${createdObjectUrlIndex}`;
    });

    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-retained-readable',
      url: '/api/storage/local-files/generated/retained-readable.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;

    const saved = await saveMediaBlobToCache(identity, await new Response('readable').blob(), {
      contentType: 'image/png',
    });

    retainMediaObjectUrl(saved.objectUrl);
    revokeManagedMediaObjectUrl(saved.objectUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(saved.objectUrl);
    expect(getCachedMediaObjectUrlSync(identity)).toBe(saved.objectUrl);

    releaseMediaObjectUrl(saved.objectUrl);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(saved.objectUrl);
    expect(getCachedMediaObjectUrlSync(identity)).toBeNull();
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith(saved.objectUrl);

    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(saved.objectUrl);
    vi.useRealTimers();
  });

  it('does not revoke the same managed object url twice when cleanup paths repeat', async () => {
    const objectUrl = createManagedMediaObjectUrl(
      await new Response('managed-repeat-cleanup').blob()
    );

    expect(objectUrl).toBe('blob:cached-22');

    revokeManagedMediaObjectUrl(objectUrl);
    revokeManagedMediaObjectUrl(objectUrl);

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(objectUrl);
  });

  it('replaces an existing object url during forced recovery even when the version is unchanged', async () => {
    vi.useFakeTimers();
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:recovered-thumbnail-${createdObjectUrlIndex}`;
    });

    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-recover-thumbnail',
      url: '/api/storage/local-files/generated/recover-thumbnail.png',
      mimeType: 'image/png',
      updatedAt: 1,
      userScope: 'user-1',
    })!;

    const first = await saveMediaBlobToCache(identity, await new Response('first').blob(), {
      contentType: 'image/png',
      etag: '"first-etag"',
    });

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('second', {
        status: 200,
        headers: { 'Content-Type': 'image/png', ETag: '"second-etag"' },
      })
    );

    const recovered = await fetchAndStoreMedia(identity, {
      allowRevalidate: false,
      replaceObjectUrl: true,
    });

    expect(first.objectUrl).toBe('blob:recovered-thumbnail-1');
    expect(recovered.objectUrl).toBe('blob:recovered-thumbnail-2');
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:recovered-thumbnail-1');
    expect(fetch).toHaveBeenCalledWith(
      '/api/storage/local-files/generated/recover-thumbnail.png',
      expect.objectContaining({
        headers: expect.any(Headers),
      })
    );
    const fetchOptions = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
    expect((fetchOptions.headers as Headers).has('If-None-Match')).toBe(false);
    expect((fetchOptions.headers as Headers).has('If-Modified-Since')).toBe(false);
    vi.runOnlyPendingTimers();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:recovered-thumbnail-1');
    vi.useRealTimers();
  });

  it('evicts a failed in-memory object url without deleting persistent media bytes', async () => {
    let createdObjectUrlIndex = 0;
    vi.mocked(URL.createObjectURL).mockImplementation(() => {
      createdObjectUrlIndex += 1;
      return `blob:evict-failed-thumbnail-${createdObjectUrlIndex}`;
    });

    const identity = resolveMediaCacheIdentity({
      attachmentId: 'att-evict-failed-thumbnail',
      url: '/api/storage/local-files/generated/evict-failed-thumbnail.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;

    const saved = await saveMediaBlobToCache(identity, await new Response('cached').blob(), {
      contentType: 'image/png',
    });

    expect(saved.objectUrl).toBe('blob:evict-failed-thumbnail-1');
    expect(getCachedMediaObjectUrlSync(identity)).toBe('blob:evict-failed-thumbnail-1');

    expect(evictCachedMediaObjectUrl(identity, 'blob:other-thumbnail')).toBe(false);
    expect(getCachedMediaObjectUrlSync(identity)).toBe('blob:evict-failed-thumbnail-1');

    expect(evictCachedMediaObjectUrl(identity, saved.objectUrl)).toBe(true);
    expect(getCachedMediaObjectUrlSync(identity)).toBeNull();
    expect(metadataStore.has(identity.cacheKey)).toBe(true);
    expect(cacheEntries.has(getMediaCacheStorageRequestUrl(identity.cacheKey))).toBe(true);

    await expect(getCachedMediaObjectUrl(identity)).resolves.toBe('blob:evict-failed-thumbnail-2');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('does not return a failed object url from another in-memory media key', () => {
    const firstIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-failed-object-url-a',
      url: '/api/storage/local-files/generated/failed-object-url-a.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const secondIdentity = resolveMediaCacheIdentity({
      attachmentId: 'att-failed-object-url-b',
      url: '/api/storage/local-files/generated/failed-object-url-b.png',
      mimeType: 'image/png',
      userScope: 'user-1',
    })!;
    const failedObjectUrl = 'blob:https://gemini.dicry.cn:18443/reused-failed-thumbnail';
    const now = Date.now();

    cacheManager.set(`mediaObjectUrl:${firstIdentity.cacheKey}`, {
      objectUrl: failedObjectUrl,
      versionSignature: firstIdentity.versionSignature,
      updatedAt: now,
      lastAccessedAt: now,
    });
    cacheManager.set(`mediaObjectUrl:${secondIdentity.cacheKey}`, {
      objectUrl: failedObjectUrl,
      versionSignature: secondIdentity.versionSignature,
      updatedAt: now,
      lastAccessedAt: now,
    });

    expect(evictCachedMediaObjectUrl(firstIdentity, failedObjectUrl)).toBe(true);
    expect(getCachedMediaObjectUrlSync(secondIdentity)).toBeNull();
  });
});

// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager } from './CacheManager';
import { setPrivateCacheUserScope } from './privateCacheScope';

const mocks = vi.hoisted(() => ({
  fetchWorkflowPreviewImagesWithMeta: vi.fn(),
  fetchWorkflowPreviewMediaWithMeta: vi.fn(),
}));

vi.mock('./workflowHistoryService', () => ({
  fetchWorkflowPreviewImagesWithMeta: mocks.fetchWorkflowPreviewImagesWithMeta,
  fetchWorkflowPreviewMediaWithMeta: mocks.fetchWorkflowPreviewMediaWithMeta,
}));

import {
  __resetWorkflowPreviewCacheForTest,
  clearWorkflowPreviewCacheForLogout,
  getWorkflowPreviewImagesWithCache,
  getWorkflowPreviewMediaWithCache,
  readWorkflowPreviewImagesCacheEntry,
  readWorkflowPreviewMediaCacheEntry,
  writeWorkflowPreviewMediaCacheEntry,
  writeWorkflowPreviewImagesCacheEntry,
} from './workflowPreviewCache';

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
};

describe('workflowPreviewCache', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cacheManager.clearAll();
    setPrivateCacheUserScope('user-1');
    __resetWorkflowPreviewCacheForTest();
  });

  it('fails closed when an in-flight preview image request resolves after private cache clear', async () => {
    const deferredPreview = createDeferred<{
      imageUrls: string[];
      skippedCount: number;
      count: number;
    }>();
    mocks.fetchWorkflowPreviewImagesWithMeta.mockReturnValue(deferredPreview.promise);

    const pendingPreview = getWorkflowPreviewImagesWithCache('exec-after-clear', 8);
    await Promise.resolve();

    clearWorkflowPreviewCacheForLogout();
    deferredPreview.resolve({
      imageUrls: ['/api/storage/local-files/generated/workflow-preview.png'],
      skippedCount: 0,
      count: 1,
    });

    await expect(pendingPreview).resolves.toEqual({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });
    expect(readWorkflowPreviewImagesCacheEntry('exec-after-clear')).toBeNull();
  });

  it('fails closed when a late preview image request resolves in a different private scope', async () => {
    const deferredPreview = createDeferred<{
      imageUrls: string[];
      skippedCount: number;
      count: number;
    }>();
    mocks.fetchWorkflowPreviewImagesWithMeta.mockReturnValue(deferredPreview.promise);

    const pendingPreview = getWorkflowPreviewImagesWithCache('exec-scope-change', 8);
    await Promise.resolve();

    setPrivateCacheUserScope('user-2');
    deferredPreview.resolve({
      imageUrls: ['/api/storage/local-files/generated/user-one-preview.png'],
      skippedCount: 0,
      count: 1,
    });

    await expect(pendingPreview).resolves.toEqual({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });
    expect(readWorkflowPreviewImagesCacheEntry('exec-scope-change')).toBeNull();

    setPrivateCacheUserScope('user-1');
    expect(readWorkflowPreviewImagesCacheEntry('exec-scope-change')).toBeNull();
  });

  it('prunes workflow preview image cache only within the current private scope', () => {
    setPrivateCacheUserScope('user-1');
    writeWorkflowPreviewImagesCacheEntry('exec-user-1-old', {
      imageUrls: ['/api/storage/local-files/u1-old.png'],
      requestedLimit: 8,
      skippedCount: 0,
      count: 1,
      updatedAt: 1,
    });

    setPrivateCacheUserScope('user-2');
    for (let index = 0; index < 81; index += 1) {
      writeWorkflowPreviewImagesCacheEntry(`exec-user-2-${index}`, {
        imageUrls: [`/api/storage/local-files/u2-${index}.png`],
        requestedLimit: 8,
        skippedCount: 0,
        count: 1,
        updatedAt: 100 + index,
      });
    }

    setPrivateCacheUserScope('user-1');
    expect(readWorkflowPreviewImagesCacheEntry('exec-user-1-old')?.imageUrls).toEqual([
      '/api/storage/local-files/u1-old.png',
    ]);
  });

  it('does not store browser-local blob urls in workflow preview image cache entries', () => {
    writeWorkflowPreviewImagesCacheEntry('exec-stale-blob-image-cache', {
      imageUrls: [
        'blob:https://gemini.dicry.cn:18443/stale-workflow-preview',
        '/api/storage/local-files/workflow/persisted-preview.png',
      ],
      requestedLimit: 8,
      skippedCount: 0,
      count: 2,
      updatedAt: 1,
    });

    expect(readWorkflowPreviewImagesCacheEntry('exec-stale-blob-image-cache')?.imageUrls).toEqual([
      '/api/storage/local-files/workflow/persisted-preview.png',
    ]);
  });

  it('fails closed when a late preview media request resolves in a different private scope', async () => {
    const deferredPreview = createDeferred<any>();
    mocks.fetchWorkflowPreviewMediaWithMeta.mockReturnValue(deferredPreview.promise);

    const pendingPreview = getWorkflowPreviewMediaWithCache('exec-media-scope-change', 'video', 8);
    await Promise.resolve();

    setPrivateCacheUserScope('user-2');
    deferredPreview.resolve({
      mediaType: 'video',
      items: [
        {
          index: 0,
          sourceUrl: '/api/storage/local-files/generated/user-one-video.mp4',
          resolvedUrl: '/api/storage/local-files/generated/user-one-video.mp4',
          mimeType: 'video/mp4',
          fileName: 'user-one-video.mp4',
          previewUrl: '/api/storage/local-files/generated/user-one-video.mp4',
        },
      ],
      skippedCount: 0,
      count: 1,
    });

    await expect(pendingPreview).resolves.toEqual({
      mediaType: 'video',
      items: [],
      skippedCount: 0,
      count: 0,
    });
    expect(readWorkflowPreviewMediaCacheEntry('exec-media-scope-change', 'video')).toBeNull();

    setPrivateCacheUserScope('user-1');
    expect(readWorkflowPreviewMediaCacheEntry('exec-media-scope-change', 'video')).toBeNull();
  });

  it('prunes workflow preview media cache only within the current private scope', () => {
    setPrivateCacheUserScope('user-1');
    writeWorkflowPreviewMediaCacheEntry('exec-user-1-media-old', 'video', {
      items: [
        {
          index: 0,
          sourceUrl: '/api/storage/local-files/u1-old.mp4',
          resolvedUrl: '/api/storage/local-files/u1-old.mp4',
          mimeType: 'video/mp4',
          fileName: 'u1-old.mp4',
          previewUrl: '/api/storage/local-files/u1-old.mp4',
        },
      ],
      requestedLimit: 8,
      skippedCount: 0,
      count: 1,
      updatedAt: 1,
    });

    setPrivateCacheUserScope('user-2');
    for (let index = 0; index < 81; index += 1) {
      writeWorkflowPreviewMediaCacheEntry(`exec-user-2-media-${index}`, 'video', {
        items: [
          {
            index,
            sourceUrl: `/api/storage/local-files/u2-${index}.mp4`,
            resolvedUrl: `/api/storage/local-files/u2-${index}.mp4`,
            mimeType: 'video/mp4',
            fileName: `u2-${index}.mp4`,
            previewUrl: `/api/storage/local-files/u2-${index}.mp4`,
          },
        ],
        requestedLimit: 8,
        skippedCount: 0,
        count: 1,
        updatedAt: 100 + index,
      });
    }

    setPrivateCacheUserScope('user-1');
    expect(readWorkflowPreviewMediaCacheEntry('exec-user-1-media-old', 'video')?.items).toEqual([
        {
          index: 0,
          sourceUrl: '/api/storage/local-files/u1-old.mp4',
          resolvedUrl: '/api/storage/local-files/u1-old.mp4',
          mimeType: 'video/mp4',
          fileName: 'u1-old.mp4',
          previewUrl: '/api/storage/local-files/u1-old.mp4',
        },
      ]);
  });

  it('does not store browser-local blob preview urls in workflow preview media cache entries', () => {
    writeWorkflowPreviewMediaCacheEntry('exec-stale-blob-media-cache', 'video', {
      items: [
        {
          index: 1,
          sourceUrl: 'blob:https://gemini.dicry.cn:18443/stale-source-video',
          resolvedUrl: 'blob:https://gemini.dicry.cn:18443/stale-resolved-video',
          mimeType: 'video/mp4',
          fileName: 'stale.mp4',
          previewUrl: 'blob:https://gemini.dicry.cn:18443/stale-preview-video',
        },
        {
          index: 2,
          sourceUrl: '/api/storage/local-files/workflow/source-video.mp4',
          resolvedUrl: '/api/storage/local-files/workflow/resolved-video.mp4',
          mimeType: 'video/mp4',
          fileName: 'video.mp4',
          previewUrl: '/api/workflows/history/exec-stale-blob-media-cache/video/items/2',
        },
      ],
      requestedLimit: 8,
      skippedCount: 0,
      count: 2,
      updatedAt: 1,
    });

    expect(readWorkflowPreviewMediaCacheEntry('exec-stale-blob-media-cache', 'video')?.items).toEqual([
      {
        index: 2,
        sourceUrl: '/api/storage/local-files/workflow/source-video.mp4',
        resolvedUrl: '/api/storage/local-files/workflow/resolved-video.mp4',
        mimeType: 'video/mp4',
        fileName: 'video.mp4',
        previewUrl: '/api/workflows/history/exec-stale-blob-media-cache/video/items/2',
      },
    ]);
  });
});

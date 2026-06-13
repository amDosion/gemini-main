// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { readSeedMediaBlob } from './mediaCachePersistence';
import type { MediaCacheIdentity } from './mediaCacheTypes';

const makeIdentity = (seedUrl: string): MediaCacheIdentity => ({
  cacheKey: 'media:test:path:seed',
  sourceUrl: '/api/storage/local-files/generated/seed.png',
  canonicalUrl: '/api/storage/local-files/generated/seed.png',
  versionSignature: 'url:/api/storage/local-files/generated/seed.png',
  userScope: 'user-1',
  persistable: true,
  seedUrl,
});

describe('mediaCachePersistence readSeedMediaBlob', () => {
  it('decodes safe raster image data URL seeds', async () => {
    const result = await readSeedMediaBlob(makeIdentity('data:image/png;base64,YWJj'));

    expect(result).not.toBeNull();
    expect(result?.blob.type).toBe('image/png');
    expect(result?.blob.size).toBe(3);
    expect(result?.response.headers.get('Content-Type')).toBe('image/png');
  });

  it.each([
    ['inline svg', 'data:image/svg+xml;base64,PHN2Zy8+'],
    ['non-base64 image data', 'data:image/png,raw-bytes'],
    ['non-image data', 'data:text/html;base64,PHNjcmlwdD4='],
    ['invalid base64', 'data:image/png;base64,not-valid!'],
  ])('rejects unsafe %s seeds', async (_label, seedUrl) => {
    await expect(readSeedMediaBlob(makeIdentity(seedUrl))).resolves.toBeNull();
  });
});

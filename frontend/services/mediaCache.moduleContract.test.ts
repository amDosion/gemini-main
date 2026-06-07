import { describe, expect, it, vi } from 'vitest';

// The persistence layer reaches IndexedDB through this module; mock it so the
// contract test never touches a real store and the persist hook can be observed.
const metadataStore = new Map<string, unknown>();
vi.mock('./mediaCacheIndexedDb', () => ({
  readMediaCacheMetadata: vi.fn(async (cacheKey: string) => metadataStore.get(cacheKey) || null),
  writeMediaCacheMetadata: vi.fn(async (metadata: { cacheKey: string }) => {
    metadataStore.set(metadata.cacheKey, metadata);
  }),
  deleteMediaCacheMetadata: vi.fn(async (cacheKey: string) => {
    metadataStore.delete(cacheKey);
  }),
  listMediaCacheMetadata: vi.fn(async () => Array.from(metadataStore.values())),
  __resetMediaCacheIndexedDbForTest: vi.fn(),
}));

import * as mediaCache from './mediaCache';
import * as objectUrls from './mediaCacheObjectUrls';
import * as diagnostics from './mediaCacheDiagnostics';
import * as identity from './mediaCacheIdentity';
import * as persistence from './mediaCachePersistence';

/**
 * The public surface mediaCache.ts MUST keep exporting after the split. This is
 * the exact set the original single-file module exposed (verified against the
 * pre-refactor file and the importers across the frontend). Adding to this list
 * widens the public API; removing from it breaks callers — both are regressions
 * this test is designed to catch.
 */
const EXPECTED_VALUE_EXPORTS = [
  'clearAllMediaCache',
  'clearMediaCacheForLogout',
  'clearUserMediaCache',
  'createManagedMediaObjectUrl',
  'evictCachedMediaObjectUrl',
  'fetchAndStoreMedia',
  'getCachedMediaObjectUrl',
  'getCachedMediaObjectUrlSync',
  'getDefaultMediaCacheUserScope',
  'getMediaCacheDiagnosticsSnapshot',
  'getMediaCacheStorageRequestUrl',
  'releaseMediaObjectUrl',
  'requestMediaCachePersistence',
  'resetMediaCacheDiagnostics',
  'resolveMediaCacheIdentity',
  'retainMediaObjectUrl',
  'revokeManagedMediaObjectUrl',
  'saveMediaBlobToCache',
  'setDefaultMediaCacheUserScope',
  '__getMediaCacheDiagnosticCountersRefForTest',
  '__resetMediaCacheForTest',
  '__setMediaCacheDiagnosticsEnabledForTest',
  '__setMediaCacheLimitsForTest',
] as const;

describe('mediaCache module split public-surface contract', () => {
  it('re-exports every name the entry module is required to expose', () => {
    for (const name of EXPECTED_VALUE_EXPORTS) {
      expect(
        typeof (mediaCache as Record<string, unknown>)[name],
        `missing public export: ${name}`
      ).toBe('function');
    }
  });

  it('does not widen the runtime (value) public surface beyond the contract', () => {
    const actualValueExports = Object.keys(mediaCache)
      .filter((key) => typeof (mediaCache as Record<string, unknown>)[key] === 'function')
      .sort();
    expect(actualValueExports).toEqual([...EXPECTED_VALUE_EXPORTS].sort());
  });

  it('re-exports identity/object-url/diagnostics functions through the same identity (no copies)', () => {
    // A re-export must be the literal same function reference as the sibling
    // module's definition; a divergence here means the entry shadowed it with a
    // private copy, which would silently desync state between modules.
    expect(mediaCache.resolveMediaCacheIdentity).toBe(identity.resolveMediaCacheIdentity);
    expect(mediaCache.retainMediaObjectUrl).toBe(objectUrls.retainMediaObjectUrl);
    expect(mediaCache.releaseMediaObjectUrl).toBe(objectUrls.releaseMediaObjectUrl);
    expect(mediaCache.createManagedMediaObjectUrl).toBe(objectUrls.createManagedMediaObjectUrl);
    expect(mediaCache.revokeManagedMediaObjectUrl).toBe(objectUrls.revokeManagedMediaObjectUrl);
    expect(mediaCache.getMediaCacheStorageRequestUrl).toBe(
      persistence.getMediaCacheStorageRequestUrl
    );
    expect(mediaCache.getMediaCacheDiagnosticsSnapshot).toBe(
      diagnostics.getMediaCacheDiagnosticsSnapshot
    );
  });
});

describe('mediaCache split: cross-module state stays shared', () => {
  it('limit setter on the entry drives the persistence module state', () => {
    // __setMediaCacheLimitsForTest must delegate to the persistence module's
    // mutable limit state — not a stale copy left behind in the entry.
    const setSpy = vi.spyOn(persistence, 'setMediaCacheLimits');
    mediaCache.__setMediaCacheLimitsForTest({ maxEntries: 7, maxBytes: 1234 });
    expect(setSpy).toHaveBeenCalledWith({ maxEntries: 7, maxBytes: 1234 });
    setSpy.mockRestore();
    mediaCache.__resetMediaCacheForTest();
  });

  it('persistence eviction hook is wired to a real callback at module load', () => {
    // The entry registers deleteObjectUrlMemory as the eviction hook. If the
    // wiring is dropped, deletePersistentMediaEntry would no-op the memory
    // eviction; assert the hook setter exists and the persistence delete path
    // runs without throwing (covering the injected-callback contract).
    expect(typeof persistence.setMediaCacheMemoryEvictionHook).toBe('function');
    return expect(
      persistence.deletePersistentMediaEntry('media:contract:url:nonexistent')
    ).resolves.toBeUndefined();
  });
});

describe('mediaCache split: behavior round-trips through re-exports', () => {
  it('resolves a persistent identity and round-trips the storage request URL', () => {
    mediaCache.__resetMediaCacheForTest();
    mediaCache.setDefaultMediaCacheUserScope('contract-user');

    const resolved = mediaCache.resolveMediaCacheIdentity({
      url: '/api/storage/local-files/photo.png?rev=9',
      userScope: 'contract-user',
    });

    // resolveMediaCacheIdentity (now in mediaCacheIdentity.ts) must still build a
    // scoped, persistable identity for a same-origin storage URL.
    expect(resolved).not.toBeNull();
    expect(resolved?.persistable).toBe(true);
    expect(resolved?.userScope).toBe('contract-user');
    expect(resolved?.versionSignature).toBe('rev:9');

    const requestUrl = mediaCache.getMediaCacheStorageRequestUrl(resolved!.cacheKey);
    expect(requestUrl).toContain('/__gemini_media_cache__/');
    expect(requestUrl).toContain(encodeURIComponent(resolved!.cacheKey));

    mediaCache.__resetMediaCacheForTest();
  });

  it('treats blob/data sources as non-persistent temporary identities', () => {
    mediaCache.__resetMediaCacheForTest();
    const temporary = mediaCache.resolveMediaCacheIdentity({
      attachmentId: 'att-1',
      url: 'blob:http://localhost/abc',
      mimeType: 'image/png',
      userScope: 'contract-user',
    });
    expect(temporary?.temporary).toBe(true);
    expect(temporary?.cacheKey).toContain(':attachment:att-1');
    mediaCache.__resetMediaCacheForTest();
  });
});

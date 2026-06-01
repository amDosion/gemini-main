// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager, CACHE_DOMAINS } from './CacheManager';
import {
  writeCachedSessionsForMode,
  writeCurrentSessionIdForMode,
  readCachedSessionsForMode,
  readCurrentSessionIdForMode,
} from './sessionCache';
import {
  getPrivateCacheScopeSegment,
  scopedPrivateCacheKey,
  scopedPrivateSingletonCacheKey,
  setPrivateCacheUserScope,
} from './privateCacheScope';
import {
  registerPrivateCacheResetHandler,
} from './privateCacheInvalidation';

const mocks = vi.hoisted(() => ({
  clearMediaCacheForLogout: vi.fn(),
  clearPreviewCacheForLogout: vi.fn(),
}));

vi.mock('./mediaCache', () => ({
  clearMediaCacheForLogout: mocks.clearMediaCacheForLogout,
}));

vi.mock('./previewCache', () => ({
  clearPreviewCacheForLogout: mocks.clearPreviewCacheForLogout,
}));

import { clearPrivateClientCaches, getPrivateCacheClearTargets } from './privateClientCache';

describe('privateClientCache', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cacheManager.clearAll();
    setPrivateCacheUserScope('user-1');
    mocks.clearMediaCacheForLogout.mockResolvedValue(undefined);
    mocks.clearPreviewCacheForLogout.mockResolvedValue(undefined);
  });

  it('clears private memory cache domains without evicting public provider metadata', async () => {
    writeCachedSessionsForMode('chat', [
      { id: 's1', title: 's1', mode: 'chat', createdAt: 1, messages: [] },
    ]);
    writeCurrentSessionIdForMode('chat', 's1');
    cacheManager.set('models:abc123:google:visible', { models: [] });
    cacheManager.set(scopedPrivateCacheKey(CACHE_DOMAINS.MODE_CONTROLS_SCHEMA, 'google::gen::imagen'), { provider: 'google' });
    cacheManager.set(scopedPrivateCacheKey(CACHE_DOMAINS.ENHANCE_PROMPT_MODELS, 'google:vision:visible'), []);
    cacheManager.set(scopedPrivateCacheKey(CACHE_DOMAINS.AGENT_REGISTRY, '0::'), [{ id: 'agent-1' }]);
    cacheManager.set(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.PERSONAS), [{ id: 'p1' }]);
    cacheManager.set(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_PERSONA_ID), 'p1');
    cacheManager.set(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.STORAGE_CONFIGS), [{ id: 'st1' }]);
    cacheManager.set(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_STORAGE_ID), 'st1');
    cacheManager.set(CACHE_DOMAINS.PERSONAS, [{ id: 'legacy-p1' }]);
    cacheManager.set(CACHE_DOMAINS.PROVIDER_TEMPLATES, [{ id: 'google' }]);
    cacheManager.set(`${CACHE_DOMAINS.LLM_INSTANCES}google_google`, { id: 'google' });

    await clearPrivateClientCaches();

    expect(readCachedSessionsForMode('chat')).toBeNull();
    expect(readCurrentSessionIdForMode('chat')).toBeNull();
    expect(cacheManager.get('models:abc123:google:visible')).toBeNull();
    expect(cacheManager.get(scopedPrivateCacheKey(CACHE_DOMAINS.MODE_CONTROLS_SCHEMA, 'google::gen::imagen'))).toBeNull();
    expect(cacheManager.get(scopedPrivateCacheKey(CACHE_DOMAINS.ENHANCE_PROMPT_MODELS, 'google:vision:visible'))).toBeNull();
    expect(cacheManager.get(scopedPrivateCacheKey(CACHE_DOMAINS.AGENT_REGISTRY, '0::'))).toBeNull();
    expect(cacheManager.get(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.PERSONAS))).toBeNull();
    expect(cacheManager.get(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_PERSONA_ID))).toBeNull();
    expect(cacheManager.get(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.STORAGE_CONFIGS))).toBeNull();
    expect(cacheManager.get(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_STORAGE_ID))).toBeNull();
    expect(cacheManager.get(CACHE_DOMAINS.PERSONAS)).toBeNull();
    expect(cacheManager.get(CACHE_DOMAINS.PROVIDER_TEMPLATES)).toEqual([{ id: 'google' }]);
    expect(cacheManager.get(`${CACHE_DOMAINS.LLM_INSTANCES}google_google`)).toEqual({ id: 'google' });
    expect(mocks.clearMediaCacheForLogout).toHaveBeenCalledTimes(1);
    expect(mocks.clearPreviewCacheForLogout).toHaveBeenCalledTimes(1);
  });

  it('keeps private memory cache clear targets canonical and duplicate-free', () => {
    const targets = getPrivateCacheClearTargets();

    expect(new Set(targets.prefixes).size).toBe(targets.prefixes.length);
    expect(new Set(targets.exactKeys).size).toBe(targets.exactKeys.length);
    expect(targets.prefixes.filter((prefix) => prefix === `${CACHE_DOMAINS.MODELS}:`)).toHaveLength(1);
    expect(targets.prefixes).toContain(CACHE_DOMAINS.MODE_CONTROLS_SCHEMA);
    expect(targets.prefixes).toContain(CACHE_DOMAINS.ENHANCE_PROMPT_MODELS);
    expect(targets.prefixes).toContain(CACHE_DOMAINS.AGENT_REGISTRY);
    expect(targets.exactKeys).not.toContain(CACHE_DOMAINS.PROVIDER_TEMPLATES);
    expect(targets.prefixes).not.toContain(CACHE_DOMAINS.LLM_INSTANCES);
  });

  it('runs registered private cache reset handlers during private client cache clears', async () => {
    const registeredCacheKey = scopedPrivateCacheKey(
      CACHE_DOMAINS.ENHANCE_PROMPT_MODELS,
      'registered-private-cache'
    );
    const resetHandler = vi.fn(() => {
      cacheManager.set(registeredCacheKey, 'reset');
    });
    registerPrivateCacheResetHandler(resetHandler);

    await clearPrivateClientCaches();

    expect(resetHandler).toHaveBeenCalledTimes(1);
    expect(cacheManager.get(registeredCacheKey)).toBeNull();
  });

  it('runs private cache reset handlers after private cache entries are cleared', async () => {
    writeCachedSessionsForMode('image-gen', [
      { id: 'old-gen-session', title: 'old', mode: 'image-gen', createdAt: 1, messages: [] },
    ]);
    const privateModelKey = scopedPrivateCacheKey(CACHE_DOMAINS.MODELS, 'google:gen');
    cacheManager.set(privateModelKey, [{ id: 'private-model' }]);

    const observedDuringReset: Array<{
      sessions: unknown;
      privateModels: unknown;
    }> = [];
    registerPrivateCacheResetHandler(() => {
      observedDuringReset.push({
        sessions: readCachedSessionsForMode('image-gen'),
        privateModels: cacheManager.get(privateModelKey),
      });
    });

    await clearPrivateClientCaches();

    expect(observedDuringReset).toEqual([
      {
        sessions: null,
        privateModels: null,
      },
    ]);
  });

  it('clears legacy scoped keys that were created before scoped domain normalization', async () => {
    const scopeSegment = getPrivateCacheScopeSegment();
    const legacyModelKey = `${CACHE_DOMAINS.MODELS}${scopeSegment}:google:gen`;
    const legacyModeModelsKey = `${CACHE_DOMAINS.MODE_MODELS}${scopeSegment}:google:image-gen`;
    const legacyModelCatalogKey = `${CACHE_DOMAINS.MODEL_CATALOG}${scopeSegment}:google`;
    const unrelatedModelsLikeKey = `${CACHE_DOMAINS.MODELS}-public-metadata`;

    cacheManager.set(legacyModelKey, [{ id: 'legacy-model' }]);
    cacheManager.set(legacyModeModelsKey, [{ id: 'legacy-mode-model' }]);
    cacheManager.set(legacyModelCatalogKey, [{ id: 'legacy-catalog' }]);
    cacheManager.set(unrelatedModelsLikeKey, [{ id: 'public' }]);

    await clearPrivateClientCaches();

    expect(cacheManager.get(legacyModelKey)).toBeNull();
    expect(cacheManager.get(legacyModeModelsKey)).toBeNull();
    expect(cacheManager.get(legacyModelCatalogKey)).toBeNull();
    expect(cacheManager.get(unrelatedModelsLikeKey)).toEqual([{ id: 'public' }]);
  });
});

import { cacheManager, CACHE_DOMAINS } from './CacheManager';
import { clearMediaCacheForLogout } from './mediaCache';
import { clearPreviewCacheForLogout } from './previewCache';
import { runPrivateCacheResetHandlers } from './privateCacheInvalidation';
import { getPrivateCacheScopeSegment } from './privateCacheScope';
import {
  CURRENT_SESSION_ID_BY_MODE_PREFIX,
  SESSION_HAS_MORE_BY_MODE_PREFIX,
  SESSION_HISTORY_PREFERENCE_PREFIX,
  SESSION_HISTORY_STATES_PREFIX,
  SESSION_LIST_BY_MODE_PREFIX,
} from './sessionCache';
import { clearWorkflowPreviewCacheForLogout } from './workflowPreviewCache';

const uniqueStrings = (values: readonly string[]): string[] => Array.from(new Set(values));

const PRIVATE_CACHE_PREFIX_CANDIDATES = [
  SESSION_LIST_BY_MODE_PREFIX,
  CURRENT_SESSION_ID_BY_MODE_PREFIX,
  SESSION_HAS_MORE_BY_MODE_PREFIX,
  SESSION_HISTORY_STATES_PREFIX,
  SESSION_HISTORY_PREFERENCE_PREFIX,
  `${CACHE_DOMAINS.PROFILES}:`,
  `${CACHE_DOMAINS.PERSONAS}:`,
  `${CACHE_DOMAINS.STORAGE_CONFIGS}:`,
  `${CACHE_DOMAINS.ACTIVE_STORAGE_ID}:`,
  `${CACHE_DOMAINS.MODELS}:`,
  `${CACHE_DOMAINS.MODE_MODELS}:`,
  `${CACHE_DOMAINS.MODEL_CATALOG}:`,
  CACHE_DOMAINS.MODE_CONTROLS_SCHEMA,
  CACHE_DOMAINS.ENHANCE_PROMPT_MODELS,
  CACHE_DOMAINS.AGENT_REGISTRY,
  `${CACHE_DOMAINS.ACTIVE_PERSONA_ID}:`,
  `${CACHE_DOMAINS.CURRENT_SESSION_ID}:`,
] as const;

const PRIVATE_CACHE_EXACT_KEY_CANDIDATES = [
  CACHE_DOMAINS.SESSIONS,
  CACHE_DOMAINS.PROFILES,
  CACHE_DOMAINS.PERSONAS,
  CACHE_DOMAINS.STORAGE_CONFIGS,
  CACHE_DOMAINS.ACTIVE_STORAGE_ID,
  CACHE_DOMAINS.MODELS,
  CACHE_DOMAINS.MODE_MODELS,
  CACHE_DOMAINS.MODEL_CATALOG,
  CACHE_DOMAINS.ACTIVE_PERSONA_ID,
  CACHE_DOMAINS.CURRENT_SESSION_ID,
] as const;

export const getPrivateCacheClearTargets = (): {
  prefixes: string[];
  exactKeys: string[];
} => ({
  prefixes: uniqueStrings([
    ...PRIVATE_CACHE_PREFIX_CANDIDATES,
    `${CACHE_DOMAINS.MODELS}${getPrivateCacheScopeSegment()}:`,
    `${CACHE_DOMAINS.MODE_MODELS}${getPrivateCacheScopeSegment()}:`,
    `${CACHE_DOMAINS.MODEL_CATALOG}${getPrivateCacheScopeSegment()}:`,
  ]),
  exactKeys: uniqueStrings(PRIVATE_CACHE_EXACT_KEY_CANDIDATES),
});

const clearPrivateCacheManagerEntries = (): void => {
  const { prefixes, exactKeys } = getPrivateCacheClearTargets();

  for (const prefix of prefixes) {
    cacheManager.clearDomain(prefix);
  }

  for (const key of exactKeys) {
    cacheManager.remove(key);
  }
};

export const clearPrivateMemoryCaches = (): void => {
  clearWorkflowPreviewCacheForLogout();
  clearPrivateCacheManagerEntries();
  runPrivateCacheResetHandlers();
  clearPrivateCacheManagerEntries();
};

export const clearPrivateClientCaches = async (): Promise<void> => {
  clearPrivateMemoryCaches();
  await Promise.allSettled([
    clearMediaCacheForLogout(),
    clearPreviewCacheForLogout(),
  ]);
};

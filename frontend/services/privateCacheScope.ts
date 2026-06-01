const DEFAULT_PRIVATE_CACHE_SCOPE = 'anonymous';

let privateCacheUserScope = DEFAULT_PRIVATE_CACHE_SCOPE;
const privateCacheUserScopeListeners = new Set<() => void>();

const normalizeScope = (value: unknown): string => String(value || '').trim();

export const hashPrivateCacheKey = (value: string): string => {
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index);
  }
  return (hash >>> 0).toString(36);
};

export const setPrivateCacheUserScope = (userScope: string | null | undefined): void => {
  const nextScope = normalizeScope(userScope) || DEFAULT_PRIVATE_CACHE_SCOPE;
  if (nextScope === privateCacheUserScope) {
    return;
  }
  privateCacheUserScope = nextScope;
  for (const listener of Array.from(privateCacheUserScopeListeners)) {
    listener();
  }
};

export const getPrivateCacheUserScope = (): string => privateCacheUserScope;

export const subscribePrivateCacheUserScope = (listener: () => void): (() => void) => {
  privateCacheUserScopeListeners.add(listener);
  return () => {
    privateCacheUserScopeListeners.delete(listener);
  };
};

export const getPrivateCacheScopeSegment = (
  userScope: string | null | undefined = privateCacheUserScope
): string => hashPrivateCacheKey(normalizeScope(userScope) || DEFAULT_PRIVATE_CACHE_SCOPE);

const normalizeScopedCachePrefix = (prefix: string): string => {
  const normalizedPrefix = String(prefix || '').trim();
  if (!normalizedPrefix) return '';
  return normalizedPrefix.endsWith(':') ? normalizedPrefix : `${normalizedPrefix}:`;
};

export const scopedPrivateCacheKey = (
  prefix: string,
  stableKey: string,
  userScope?: string | null
): string => `${normalizeScopedCachePrefix(prefix)}${getPrivateCacheScopeSegment(userScope)}:${stableKey}`;

export const scopedPrivateCachePrefix = (
  prefix: string,
  userScope?: string | null
): string => `${normalizeScopedCachePrefix(prefix)}${getPrivateCacheScopeSegment(userScope)}:`;

export const scopedPrivateSingletonCacheKey = (
  domain: string,
  userScope?: string | null
): string => scopedPrivateCacheKey(`${domain}:`, 'value', userScope);

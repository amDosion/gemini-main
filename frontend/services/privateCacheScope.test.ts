import { beforeEach, describe, expect, it } from 'vitest';
import {
  getPrivateCacheUserScope,
  scopedPrivateCacheKey,
  scopedPrivateCachePrefix,
  scopedPrivateSingletonCacheKey,
  setPrivateCacheUserScope,
} from './privateCacheScope';

describe('privateCacheScope', () => {
  beforeEach(() => {
    setPrivateCacheUserScope(null);
  });

  it('creates stable but user-isolated cache keys for private domains', () => {
    setPrivateCacheUserScope('user-1');
    const userOneSessions = scopedPrivateCacheKey('sessions:mode:', 'chat');
    const userOnePersonas = scopedPrivateSingletonCacheKey('personas');

    setPrivateCacheUserScope('user-2');
    const userTwoSessions = scopedPrivateCacheKey('sessions:mode:', 'chat');
    const userTwoPersonas = scopedPrivateSingletonCacheKey('personas');

    expect(userOneSessions).not.toBe(userTwoSessions);
    expect(userOnePersonas).not.toBe(userTwoPersonas);

    setPrivateCacheUserScope('user-1');

    expect(scopedPrivateCacheKey('sessions:mode:', 'chat')).toBe(userOneSessions);
    expect(scopedPrivateSingletonCacheKey('personas')).toBe(userOnePersonas);
    expect(getPrivateCacheUserScope()).toBe('user-1');
  });

  it('creates a current-user prefix for scoped prefix scans', () => {
    setPrivateCacheUserScope('user-1');
    const userOnePrefix = scopedPrivateCachePrefix('sessions:mode:');

    setPrivateCacheUserScope('user-2');
    const userTwoPrefix = scopedPrivateCachePrefix('sessions:mode:');

    expect(userOnePrefix).not.toBe(userTwoPrefix);
    expect(scopedPrivateCacheKey('sessions:mode:', 'chat').startsWith(userTwoPrefix)).toBe(true);
  });

  it('normalizes scoped cache domains so callers cannot create unscannable keys', () => {
    setPrivateCacheUserScope('user-1');

    expect(scopedPrivateCacheKey('models', 'google')).toBe(
      scopedPrivateCacheKey('models:', 'google')
    );
    expect(scopedPrivateCachePrefix('models')).toBe(scopedPrivateCachePrefix('models:'));
    expect(scopedPrivateCacheKey('models', 'google').startsWith('models:')).toBe(true);
  });
});

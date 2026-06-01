import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager } from './CacheManager';

describe('CacheManager', () => {
  beforeEach(() => {
    vi.useRealTimers();
    cacheManager.clearAll();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('continues clearing a domain when one subscriber throws', () => {
    cacheManager.set('private:a', 'a');
    cacheManager.set('private:b', 'b');

    const unsubscribe = cacheManager.subscribe('private:a', () => {
      throw new Error('subscriber failed');
    });

    try {
      expect(() => cacheManager.clearDomain('private:')).not.toThrow();
      expect(cacheManager.get('private:a')).toBeNull();
      expect(cacheManager.get('private:b')).toBeNull();
    } finally {
      unsubscribe();
    }
  });

  it('notifies prefix subscribers even when their entry is already absent', () => {
    const observed: unknown[] = [];
    const unsubscribe = cacheManager.subscribe('private:stale', (value) => {
      observed.push(value);
    });

    try {
      cacheManager.clearDomain('private:');
      expect(observed).toEqual([null]);
    } finally {
      unsubscribe();
    }
  });

  it('notifies subscribers when an expired entry is evicted during read', () => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
    cacheManager.setTTL('expiring:', 10);
    cacheManager.set('expiring:item', 'cached-value');

    const observed: unknown[] = [];
    const unsubscribe = cacheManager.subscribe('expiring:item', (value) => {
      observed.push(value);
    });

    try {
      vi.setSystemTime(11);

      expect(cacheManager.get('expiring:item')).toBeNull();
      expect(observed).toEqual([null]);
    } finally {
      unsubscribe();
    }
  });
});

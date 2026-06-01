// @vitest-environment jsdom

import { act, render } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { CACHE_DOMAINS, cacheManager } from '../services/CacheManager';
import {
  scopedPrivateSingletonCacheKey,
  setPrivateCacheUserScope,
} from '../services/privateCacheScope';
import { useCacheSubscription } from './useCacheSubscription';

describe('useCacheSubscription', () => {
  beforeEach(() => {
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
  });

  it('does not expose the previous domain value during a domain switch render', () => {
    cacheManager.set('domain:user-1', ['user-1-value']);
    cacheManager.set('domain:user-2', ['user-2-value']);
    const renderValues: string[][] = [];

    function Probe({ domain }: { domain: string }) {
      const value = useCacheSubscription<string[]>(domain, []);
      renderValues.push(value);
      return null;
    }

    const { rerender } = render(<Probe domain="domain:user-1" />);

    expect(renderValues.at(-1)).toEqual(['user-1-value']);
    renderValues.length = 0;

    rerender(<Probe domain="domain:user-2" />);

    expect(renderValues[0]).toEqual(['user-2-value']);
  });

  it('returns the new fallback immediately when switching to an empty domain', () => {
    cacheManager.set('domain:user-1', ['user-1-value']);
    const renderValues: string[][] = [];

    function Probe({ domain, fallback }: { domain: string; fallback: string[] }) {
      const value = useCacheSubscription<string[]>(domain, fallback);
      renderValues.push(value);
      return null;
    }

    const { rerender } = render(<Probe domain="domain:user-1" fallback={[]} />);

    expect(renderValues.at(-1)).toEqual(['user-1-value']);
    renderValues.length = 0;

    rerender(<Probe domain="domain:user-2" fallback={['fallback-user-2']} />);

    expect(renderValues[0]).toEqual(['fallback-user-2']);
  });

  it('resubscribes scoped cache keys when private cache user scope changes without cache notifications', () => {
    setPrivateCacheUserScope('user-1');
    const renderValues: string[][] = [];

    function Probe() {
      const value = useCacheSubscription<string[]>(
        scopedPrivateSingletonCacheKey(CACHE_DOMAINS.PERSONAS),
        []
      );
      renderValues.push(value);
      return null;
    }

    render(<Probe />);

    expect(renderValues.at(-1)).toEqual([]);

    act(() => {
      setPrivateCacheUserScope('user-2');
      cacheManager.set(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.PERSONAS), ['user-2-value']);
    });

    expect(renderValues.at(-1)).toEqual(['user-2-value']);
  });
});

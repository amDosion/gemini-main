// @vitest-environment jsdom

import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { runPrivateCacheResetHandlers } from '../services/privateCacheInvalidation';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';
import {
  usePrivateCacheLifecycleRevision,
  usePrivateCacheScopeRevision,
} from './usePrivateCacheScopeRevision';

describe('usePrivateCacheScopeRevision', () => {
  beforeEach(() => {
    setPrivateCacheUserScope(null);
  });

  afterEach(() => {
    cleanup();
    setPrivateCacheUserScope(null);
  });

  it('increments once and runs the latest reset callback when private scope changes', () => {
    const firstReset = vi.fn();
    const secondReset = vi.fn();

    const hook = renderHook(
      ({ onScopeChange }) => usePrivateCacheScopeRevision(onScopeChange),
      { initialProps: { onScopeChange: firstReset } }
    );

    expect(hook.result.current).toBe(0);

    act(() => {
      setPrivateCacheUserScope('user-1');
    });

    expect(hook.result.current).toBe(1);
    expect(firstReset).toHaveBeenCalledTimes(1);

    hook.rerender({ onScopeChange: secondReset });

    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    expect(hook.result.current).toBe(2);
    expect(firstReset).toHaveBeenCalledTimes(1);
    expect(secondReset).toHaveBeenCalledTimes(1);
  });

  it('can include explicit private cache reset events in the same lifecycle revision', () => {
    const reset = vi.fn();
    const hook = renderHook(() =>
      usePrivateCacheLifecycleRevision(reset, { includeCacheReset: true })
    );

    expect(hook.result.current).toBe(0);

    act(() => {
      runPrivateCacheResetHandlers();
    });

    expect(hook.result.current).toBe(1);
    expect(reset).toHaveBeenCalledTimes(1);

    act(() => {
      setPrivateCacheUserScope('user-1');
    });

    expect(hook.result.current).toBe(2);
    expect(reset).toHaveBeenCalledTimes(2);
  });
});

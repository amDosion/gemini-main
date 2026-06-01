// @vitest-environment jsdom

import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import {
  scopedPrivateSingletonCacheKey,
  setPrivateCacheUserScope,
} from '../services/privateCacheScope';
import { clearPrivateMemoryCaches } from '../services/privateClientCache';
import { usePersonas } from './usePersonas';
import type { Persona } from '../types/types';
import { db } from '../services/db';

vi.mock('../services/db', () => ({
  db: {
    savePersonas: vi.fn(),
    getPersonas: vi.fn(),
  },
}));

vi.mock('uuid', () => ({
  v4: vi.fn(() => 'new-persona-id'),
}));

const persona = (id: string): Persona => ({
  id,
  name: id,
  description: `${id} description`,
  systemPrompt: `${id} prompt`,
  icon: 'bot',
  category: 'test',
});

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('usePersonas cache scope', () => {
  beforeEach(() => {
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
    vi.mocked(db.getPersonas).mockReset();
    vi.mocked(db.savePersonas).mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('keeps personas and active persona isolated by private cache user scope', async () => {
    setPrivateCacheUserScope('user-1');
    const first = renderHook(() => usePersonas({ personas: [persona('persona-user-1')] }));

    await waitFor(() => {
      expect(first.result.current.personas.map((item) => item.id)).toEqual(['persona-user-1']);
    });
    first.unmount();

    setPrivateCacheUserScope('user-2');
    const second = renderHook(() => usePersonas({ personas: [persona('persona-user-2')] }));

    await waitFor(() => {
      expect(second.result.current.personas.map((item) => item.id)).toEqual(['persona-user-2']);
    });
    second.unmount();

    setPrivateCacheUserScope('user-1');
    const restored = renderHook(() => usePersonas());

    expect(restored.result.current.personas.map((item) => item.id)).toEqual(['persona-user-1']);
    expect(restored.result.current.activePersonaId).toBe('persona-user-1');
  });

  it('does not repopulate a cleared private persona cache from a late refresh response', async () => {
    setPrivateCacheUserScope('user-1');
    const pendingPersonas = createDeferred<Persona[]>();
    vi.mocked(db.getPersonas).mockReturnValueOnce(pendingPersonas.promise);

    const hook = renderHook(() => usePersonas({ personas: [persona('persona-user-1')] }));
    await waitFor(() => {
      expect(hook.result.current.personas.map((item) => item.id)).toEqual(['persona-user-1']);
    });

    let refreshPromise!: Promise<void>;
    await act(async () => {
      refreshPromise = hook.result.current.refreshPersonas();
      await Promise.resolve();
    });

    clearPrivateMemoryCaches();
    setPrivateCacheUserScope('user-2');

    await act(async () => {
      pendingPersonas.resolve([persona('late-user-1-persona')]);
      await refreshPromise;
    });

    setPrivateCacheUserScope('user-1');
    expect(
      cacheManager.get<Persona[]>(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.PERSONAS))
    ).toBeNull();
    expect(
      cacheManager.get<string>(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_PERSONA_ID))
    ).toBeNull();
  });

  it('does not replay stale initial personas into a new private user scope', async () => {
    setPrivateCacheUserScope('user-1');
    const { result, rerender } = renderHook(
      ({ personas }) => usePersonas({ personas }),
      { initialProps: { personas: [persona('persona-user-1')] } }
    );

    await waitFor(() => {
      expect(result.current.personas.map((item) => item.id)).toEqual(['persona-user-1']);
      expect(result.current.activePersonaId).toBe('persona-user-1');
    });

    await act(async () => {
      setPrivateCacheUserScope('user-2');
    });

    expect(result.current.personas).toEqual([]);
    expect(result.current.activePersonaId).toBe('');

    rerender({ personas: [persona('persona-user-1')] });

    expect(result.current.personas).toEqual([]);
    expect(result.current.activePersonaId).toBe('');

    rerender({ personas: [persona('persona-user-2')] });

    await waitFor(() => {
      expect(result.current.personas.map((item) => item.id)).toEqual(['persona-user-2']);
      expect(result.current.activePersonaId).toBe('persona-user-2');
    });
  });

  it('does not allow a stale mutation callback to write into the previous private scope', async () => {
    setPrivateCacheUserScope('user-1');
    vi.mocked(db.savePersonas).mockResolvedValue(undefined);
    const hook = renderHook(() => usePersonas({ personas: [persona('persona-user-1')] }));

    await waitFor(() => {
      expect(hook.result.current.personas.map((item) => item.id)).toEqual(['persona-user-1']);
    });
    const staleCreatePersona = hook.result.current.createPersona;

    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    await expect(
      staleCreatePersona({
        name: 'stale-persona',
        description: 'stale description',
        systemPrompt: 'stale prompt',
        icon: 'bot',
        category: 'test',
      })
    ).rejects.toThrow('private cache scope changed');

    setPrivateCacheUserScope('user-1');
    expect(
      cacheManager.get<Persona[]>(scopedPrivateSingletonCacheKey(CACHE_DOMAINS.PERSONAS))
        ?.map((item) => item.id)
    ).toEqual(['persona-user-1']);
    expect(db.savePersonas).not.toHaveBeenCalled();
  });
});

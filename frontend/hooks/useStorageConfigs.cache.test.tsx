// @vitest-environment jsdom

import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import {
  scopedPrivateSingletonCacheKey,
  setPrivateCacheUserScope,
} from '../services/privateCacheScope';
import { clearPrivateMemoryCaches } from '../services/privateClientCache';
import { useStorageConfigs } from './useStorageConfigs';
import type { StorageConfig } from '../types/storage';
import { db } from '../services/db';

vi.mock('../services/db', () => ({
  db: {
    saveStorageConfig: vi.fn(),
    deleteStorageConfig: vi.fn(),
    setActiveStorageId: vi.fn(),
  },
}));

const storageConfig = (id: string): StorageConfig => ({
  id,
  name: id,
  provider: 'local',
  enabled: true,
  config: {},
  createdAt: 1,
  updatedAt: 1,
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

describe('useStorageConfigs cache scope', () => {
  beforeEach(() => {
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
    vi.mocked(db.saveStorageConfig).mockReset();
    vi.mocked(db.deleteStorageConfig).mockReset();
    vi.mocked(db.setActiveStorageId).mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('keeps storage configs and active storage isolated by private cache user scope', async () => {
    setPrivateCacheUserScope('user-1');
    const first = renderHook(() =>
      useStorageConfigs({
        storageConfigs: [storageConfig('storage-user-1')],
        activeStorageId: 'storage-user-1',
      })
    );

    await waitFor(() => {
      expect(first.result.current.storageConfigs.map((item) => item.id)).toEqual(['storage-user-1']);
    });
    first.unmount();

    setPrivateCacheUserScope('user-2');
    const second = renderHook(() =>
      useStorageConfigs({
        storageConfigs: [storageConfig('storage-user-2')],
        activeStorageId: 'storage-user-2',
      })
    );

    await waitFor(() => {
      expect(second.result.current.storageConfigs.map((item) => item.id)).toEqual(['storage-user-2']);
    });
    second.unmount();

    setPrivateCacheUserScope('user-1');
    const restored = renderHook(() => useStorageConfigs());

    expect(restored.result.current.storageConfigs.map((item) => item.id)).toEqual(['storage-user-1']);
    expect(restored.result.current.activeStorageId).toBe('storage-user-1');
  });

  it('does not repopulate cleared private storage cache from a late save response', async () => {
    setPrivateCacheUserScope('user-1');
    const pendingSave = createDeferred<void>();
    vi.mocked(db.saveStorageConfig).mockReturnValueOnce(pendingSave.promise);

    const hook = renderHook(() =>
      useStorageConfigs({
        storageConfigs: [storageConfig('storage-user-1')],
        activeStorageId: 'storage-user-1',
      })
    );
    await waitFor(() => {
      expect(hook.result.current.storageConfigs.map((item) => item.id)).toEqual(['storage-user-1']);
    });

    let savePromise!: Promise<void>;
    await act(async () => {
      savePromise = hook.result.current.handleSaveStorage(storageConfig('late-storage-user-1'));
      await Promise.resolve();
    });

    clearPrivateMemoryCaches();
    setPrivateCacheUserScope('user-2');

    await act(async () => {
      pendingSave.resolve();
      await savePromise;
    });

    setPrivateCacheUserScope('user-1');
    expect(
      cacheManager.get<StorageConfig[]>(
        scopedPrivateSingletonCacheKey(CACHE_DOMAINS.STORAGE_CONFIGS)
      )
    ).toBeNull();
  });

  it('does not replay stale initial storage configs into a new private user scope', async () => {
    setPrivateCacheUserScope('user-1');
    const { result, rerender } = renderHook(
      ({ initData }) => useStorageConfigs(initData),
      {
        initialProps: {
          initData: {
            storageConfigs: [storageConfig('storage-user-1')],
            activeStorageId: 'storage-user-1',
          },
        },
      }
    );

    await waitFor(() => {
      expect(result.current.storageConfigs.map((item) => item.id)).toEqual(['storage-user-1']);
      expect(result.current.activeStorageId).toBe('storage-user-1');
    });

    await act(async () => {
      setPrivateCacheUserScope('user-2');
    });

    expect(result.current.storageConfigs).toEqual([]);
    expect(result.current.activeStorageId).toBeNull();

    rerender({
      initData: {
        storageConfigs: [storageConfig('storage-user-1')],
        activeStorageId: 'storage-user-1',
      },
    });

    expect(result.current.storageConfigs).toEqual([]);
    expect(result.current.activeStorageId).toBeNull();

    rerender({
      initData: {
        storageConfigs: [storageConfig('storage-user-2')],
        activeStorageId: 'storage-user-2',
      },
    });

    await waitFor(() => {
      expect(result.current.storageConfigs.map((item) => item.id)).toEqual(['storage-user-2']);
      expect(result.current.activeStorageId).toBe('storage-user-2');
    });
  });

  it('does not allow a stale mutation callback to write into the previous private scope', async () => {
    setPrivateCacheUserScope('user-1');
    vi.mocked(db.saveStorageConfig).mockResolvedValue(undefined);
    const hook = renderHook(() =>
      useStorageConfigs({
        storageConfigs: [storageConfig('storage-user-1')],
        activeStorageId: 'storage-user-1',
      })
    );

    await waitFor(() => {
      expect(hook.result.current.storageConfigs.map((item) => item.id)).toEqual(['storage-user-1']);
    });
    const staleHandleSaveStorage = hook.result.current.handleSaveStorage;

    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    await expect(
      staleHandleSaveStorage(storageConfig('stale-storage-user-1'))
    ).rejects.toThrow('private cache scope changed');

    setPrivateCacheUserScope('user-1');
    expect(
      cacheManager.get<StorageConfig[]>(
        scopedPrivateSingletonCacheKey(CACHE_DOMAINS.STORAGE_CONFIGS)
      )?.map((item) => item.id)
    ).toEqual(['storage-user-1']);
    expect(db.saveStorageConfig).not.toHaveBeenCalled();
  });
});

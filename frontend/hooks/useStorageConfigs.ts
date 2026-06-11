import { useEffect, useCallback, useRef } from 'react';
import { StorageConfig } from '../types/storage';
import { db } from '../services/db';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from '../services/privateCacheInvalidation';
import { scopedPrivateSingletonCacheKey } from '../services/privateCacheScope';
import { useCacheSubscription, useCacheUpdater } from './useCacheSubscription';
import { usePrivateCacheScopeRevision } from './usePrivateCacheScopeRevision';

const EMPTY_STORAGE_CONFIGS: StorageConfig[] = [];

const getStorageConfigFingerprint = (configs: StorageConfig[]): string =>
  configs
    .map((config) =>
      [
        config.id,
        config.name,
        config.provider,
        config.enabled ? 'enabled' : 'disabled',
        config.createdAt,
        config.updatedAt,
        JSON.stringify(config.config || {}),
      ].join('\u0001')
    )
    .join('\u0002');

const getInitialStorageSignature = (initData: InitData | undefined): string | null => {
  if (!initData) return null;
  return `${initData.activeStorageId || ''}\u0003${getStorageConfigFingerprint(initData.storageConfigs || [])}`;
};

interface UseStorageConfigsReturn {
  storageConfigs: StorageConfig[];
  activeStorageId: string | null;
  handleSaveStorage: (config: StorageConfig) => Promise<void>;
  handleDeleteStorage: (id: string) => Promise<void>;
  handleActivateStorage: (id: string) => Promise<void>;
}

interface InitData {
  storageConfigs?: StorageConfig[];
  activeStorageId?: string | null;
}

export const useStorageConfigs = (initData?: InitData): UseStorageConfigsReturn => {
  const initDataSignature = getInitialStorageSignature(initData);
  const latestInitDataSignatureRef = useRef<string | null>(initDataSignature);
  const appliedInitDataSignatureRef = useRef<string | null>(null);
  const suppressedInitDataSignatureRef = useRef<string | null>(null);
  const storageConfigsCacheKey = scopedPrivateSingletonCacheKey(CACHE_DOMAINS.STORAGE_CONFIGS);
  const activeStorageIdCacheKey = scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_STORAGE_ID);

  // 订阅 CacheManager 中的数据
  const storageConfigs = useCacheSubscription<StorageConfig[]>(
    storageConfigsCacheKey,
    EMPTY_STORAGE_CONFIGS
  );
  const activeStorageId = useCacheSubscription<string | null>(activeStorageIdCacheKey, null);
  const { set: setStorageConfigsCache, update: updateStorageConfigsCache } = useCacheUpdater<
    StorageConfig[]
  >(storageConfigsCacheKey, EMPTY_STORAGE_CONFIGS);
  const { set: setActiveStorageIdCache } = useCacheUpdater<string | null>(
    activeStorageIdCacheKey,
    null
  );

  const isStorageCacheScopeCurrent = useCallback(
    (lifecycleSnapshot?: ReturnType<typeof capturePrivateCacheLifecycleSnapshot>): boolean => {
      const cacheKeysCurrent =
        storageConfigsCacheKey === scopedPrivateSingletonCacheKey(CACHE_DOMAINS.STORAGE_CONFIGS) &&
        activeStorageIdCacheKey === scopedPrivateSingletonCacheKey(CACHE_DOMAINS.ACTIVE_STORAGE_ID);
      if (!cacheKeysCurrent) return false;
      return lifecycleSnapshot ? isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot) : true;
    },
    [activeStorageIdCacheKey, storageConfigsCacheKey]
  );

  const assertStorageCacheScopeCurrent = useCallback((): void => {
    if (!isStorageCacheScopeCurrent()) {
      throw new Error('private cache scope changed');
    }
  }, [isStorageCacheScopeCurrent]);

  useEffect(() => {
    latestInitDataSignatureRef.current = initDataSignature;
  }, [initDataSignature]);

  usePrivateCacheScopeRevision(() => {
    suppressedInitDataSignatureRef.current = latestInitDataSignatureRef.current;
    appliedInitDataSignatureRef.current = null;
  });

  // 只接收当前用户 scope 下的新 initData；scope 切换后同一个旧对象不会被重新灌回
  useEffect(() => {
    if (!initData) {
      suppressedInitDataSignatureRef.current = null;
      appliedInitDataSignatureRef.current = null;
      return;
    }
    if (!initDataSignature) return;
    if (suppressedInitDataSignatureRef.current === initDataSignature) return;
    if (appliedInitDataSignatureRef.current === initDataSignature) return;

    appliedInitDataSignatureRef.current = initDataSignature;
    const configs = initData.storageConfigs || [];
    setStorageConfigsCache(configs);
    setActiveStorageIdCache(initData.activeStorageId || null);
  }, [initData, initDataSignature, setActiveStorageIdCache, setStorageConfigsCache]);

  const handleSaveStorage = useCallback(
    async (config: StorageConfig) => {
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      assertStorageCacheScopeCurrent();
      // 先写 DB
      await db.saveStorageConfig(config);
      if (!isStorageCacheScopeCurrent(lifecycleSnapshot)) {
        return;
      }
      // 增量更新缓存
      updateStorageConfigsCache((prev) => {
        const idx = prev.findIndex((c) => c.id === config.id);
        if (idx < 0) return [...prev, config];
        return prev.map((c, i) => (i === idx ? config : c));
      });
    },
    [assertStorageCacheScopeCurrent, isStorageCacheScopeCurrent, updateStorageConfigsCache]
  );

  const handleDeleteStorage = useCallback(
    async (id: string) => {
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      assertStorageCacheScopeCurrent();
      // 先写 DB
      await db.deleteStorageConfig(id);
      if (!isStorageCacheScopeCurrent(lifecycleSnapshot)) {
        return;
      }
      // 增量更新缓存
      updateStorageConfigsCache((prev) => prev.filter((c) => c.id !== id));
      if (activeStorageId === id) {
        // 与其他 handler 保持「先写 DB，scope 校验后再写缓存」的顺序
        await db.setActiveStorageId('');
        if (!isStorageCacheScopeCurrent(lifecycleSnapshot)) {
          return;
        }
        setActiveStorageIdCache(null);
      }
    },
    [
      activeStorageId,
      assertStorageCacheScopeCurrent,
      isStorageCacheScopeCurrent,
      setActiveStorageIdCache,
      updateStorageConfigsCache,
    ]
  );

  const handleActivateStorage = useCallback(
    async (id: string) => {
      const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
      assertStorageCacheScopeCurrent();
      // 先写 DB
      await db.setActiveStorageId(id);
      if (!isStorageCacheScopeCurrent(lifecycleSnapshot)) {
        return;
      }
      // 更新缓存
      setActiveStorageIdCache(id);
    },
    [assertStorageCacheScopeCurrent, isStorageCacheScopeCurrent, setActiveStorageIdCache]
  );

  return {
    storageConfigs,
    activeStorageId,
    handleSaveStorage,
    handleDeleteStorage,
    handleActivateStorage,
  };
};

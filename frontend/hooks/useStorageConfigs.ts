import { useEffect, useCallback, useRef } from 'react';
import { StorageConfig } from '../types/storage';
import { db } from '../services/db';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import { useCacheSubscription, useCacheUpdater } from './useCacheSubscription';

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
  const initializedRef = useRef(false);

  // 订阅 CacheManager 中的数据
  const storageConfigs = useCacheSubscription<StorageConfig[]>(CACHE_DOMAINS.STORAGE_CONFIGS, []);
  const activeStorageId = useCacheSubscription<string | null>(CACHE_DOMAINS.ACTIVE_STORAGE_ID, null);
  const configsUpdater = useCacheUpdater<StorageConfig[]>(CACHE_DOMAINS.STORAGE_CONFIGS, []);
  const activeIdUpdater = useCacheUpdater<string | null>(CACHE_DOMAINS.ACTIVE_STORAGE_ID, null);

  // initData 仅用于首次初始化
  useEffect(() => {
    if (!initData || initializedRef.current) return;
    const configs = initData.storageConfigs || [];
    if (configs.length > 0 || initData.activeStorageId) {
      initializedRef.current = true;
      configsUpdater.set(configs);
      activeIdUpdater.set(initData.activeStorageId || null);
    }
  }, [initData, configsUpdater, activeIdUpdater]);

  const handleSaveStorage = useCallback(async (config: StorageConfig) => {
    // 先写 DB
    await db.saveStorageConfig(config);
    // 增量更新缓存
    configsUpdater.update(prev => {
      const idx = prev.findIndex(c => c.id === config.id);
      if (idx >= 0) {
        return prev.map(c => c.id === config.id ? config : c);
      }
      return [...prev, config];
    });
  }, [configsUpdater]);

  const handleDeleteStorage = useCallback(async (id: string) => {
    // 先写 DB
    await db.deleteStorageConfig(id);
    // 增量更新缓存
    configsUpdater.update(prev => prev.filter(c => c.id !== id));
    if (activeStorageId === id) {
      activeIdUpdater.set(null);
      await db.setActiveStorageId('');
    }
  }, [activeStorageId, configsUpdater, activeIdUpdater]);

  const handleActivateStorage = useCallback(async (id: string) => {
    // 先写 DB
    await db.setActiveStorageId(id);
    // 更新缓存
    activeIdUpdater.set(id);
  }, [activeIdUpdater]);

  return {
    storageConfigs,
    activeStorageId,
    handleSaveStorage,
    handleDeleteStorage,
    handleActivateStorage
  };
};

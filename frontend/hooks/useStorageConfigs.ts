import { useState, useEffect, useCallback, useRef } from 'react';
import { StorageConfig } from '../types/storage';
import { db } from '../services/db';

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
  const [storageConfigs, setStorageConfigs] = useState<StorageConfig[]>([]);
  const [activeStorageId, setActiveStorageId] = useState<string | null>(null);
  const initializedRef = useRef(false);

  // initData 仅用于首次初始化，之后所有变更由本地操作驱动
  useEffect(() => {
    if (!initData) return;
    // 首次：直接写入
    if (!initializedRef.current) {
      const configs = initData.storageConfigs || [];
      if (configs.length > 0 || initData.activeStorageId) {
        initializedRef.current = true;
        setStorageConfigs(configs);
        setActiveStorageId(initData.activeStorageId || null);
      }
      return;
    }
    // 已初始化后：不再从 initData 同步，由本地操作驱动
  }, [initData]);

  const handleSaveStorage = useCallback(async (config: StorageConfig) => {
    await db.saveStorageConfig(config);
    // 增量更新：直接用操作数据更新 state，不重新获取
    setStorageConfigs(prev => {
      const idx = prev.findIndex(c => c.id === config.id);
      if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = config;
        return updated;
      }
      return [...prev, config];
    });
  }, []);

  const handleDeleteStorage = useCallback(async (id: string) => {
    await db.deleteStorageConfig(id);
    // 增量更新：直接移除，不重新获取
    setStorageConfigs(prev => prev.filter(c => c.id !== id));
    if (activeStorageId === id) {
      setActiveStorageId(null);
      await db.setActiveStorageId('');
    }
  }, [activeStorageId]);

  const handleActivateStorage = useCallback(async (id: string) => {
    await db.setActiveStorageId(id);
    setActiveStorageId(id);
  }, []);

  return {
    storageConfigs,
    activeStorageId,
    handleSaveStorage,
    handleDeleteStorage,
    handleActivateStorage
  };
};

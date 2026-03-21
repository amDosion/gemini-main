
import { useState, useEffect, useCallback } from 'react';
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

/**
 * 云存储配置管理 Hook
 * 管理云存储配置的增删改查和激活状态
 */
export const useStorageConfigs = (initData?: InitData): UseStorageConfigsReturn => {
  const [storageConfigs, setStorageConfigs] = useState<StorageConfig[]>([]);
  const [activeStorageId, setActiveStorageId] = useState<string | null>(null);

  // 从 initData 初始化云存储配置
  useEffect(() => {
    if (initData) {
      setStorageConfigs(initData.storageConfigs || []);
      setActiveStorageId(initData.activeStorageId || null);
    }
  }, [initData]);

  const handleSaveStorage = useCallback(async (config: StorageConfig) => {
    await db.saveStorageConfig(config);
    const configs = await db.getStorageConfigs();
    setStorageConfigs(configs);
  }, []);

  const handleDeleteStorage = useCallback(async (id: string) => {
    await db.deleteStorageConfig(id);
    const configs = await db.getStorageConfigs();
    setStorageConfigs(configs);
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

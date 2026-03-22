/**
 * React Hook: 订阅 CacheManager 中的数据变化
 * 
 * 用法:
 *   const configs = useCacheSubscription<StorageConfig[]>('storageConfigs', []);
 *   // configs 自动跟随缓存变化更新
 */

import { useState, useEffect, useCallback } from 'react';
import { cacheManager } from '../services/CacheManager';

/**
 * 订阅 CacheManager 中某个 domain 的数据
 * 缓存更新时自动触发组件重渲染
 */
export function useCacheSubscription<T>(domain: string, fallback: T): T {
  const [data, setData] = useState<T>(() => cacheManager.get<T>(domain) ?? fallback);

  useEffect(() => {
    // 初始读取
    const current = cacheManager.get<T>(domain);
    if (current !== null) {
      setData(current);
    }

    // 订阅变化
    const unsubscribe = cacheManager.subscribe<T>(domain, (newData) => {
      setData(newData ?? fallback);
    });

    return unsubscribe;
  }, [domain, fallback]);

  return data;
}

/**
 * 返回 CacheManager 的增量更新方法，绑定到指定 domain
 */
export function useCacheUpdater<T>(domain: string, fallback: T) {
  const set = useCallback((data: T) => {
    cacheManager.set(domain, data);
  }, [domain]);

  const update = useCallback((updater: (prev: T) => T) => {
    cacheManager.update(domain, updater, fallback);
  }, [domain, fallback]);

  const remove = useCallback(() => {
    cacheManager.remove(domain);
  }, [domain]);

  return { set, update, remove };
}

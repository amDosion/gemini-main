/**
 * React Hook: 订阅 CacheManager 中的数据变化
 *
 * 用法:
 *   const configs = useCacheSubscription<StorageConfig[]>('storageConfigs', []);
 *   // configs 自动跟随缓存变化更新
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { cacheManager } from '../services/CacheManager';
import { usePrivateCacheScopeRevision } from './usePrivateCacheScopeRevision';

interface CacheSubscriptionState<T> {
  domain: string;
  data: T;
}

function readCacheDomain<T>(domain: string, fallback: T): T {
  return cacheManager.get<T>(domain) ?? fallback;
}

/**
 * 订阅 CacheManager 中某个 domain 的数据
 * 缓存更新时自动触发组件重渲染
 *
 * fallback 通过 ref 镜像：避免调用方传入新引用（每渲染新对象/数组）触发 useEffect
 * 重 fire → 重新 subscribe/unsubscribe 抖动。useEffect deps 仅 [domain]，
 * subscribe callback 内读 fallbackRef.current。
 */
export function useCacheSubscription<T>(domain: string, fallback: T): T {
  const [state, setState] = useState<CacheSubscriptionState<T>>(() => ({
    domain,
    data: readCacheDomain(domain, fallback),
  }));
  const fallbackRef = useRef<T>(fallback);
  fallbackRef.current = fallback;

  const data = state.domain === domain
    ? state.data
    : readCacheDomain(domain, fallback);

  useEffect(() => {
    const current = readCacheDomain(domain, fallbackRef.current);
    setState({ domain, data: current });
    const unsubscribe = cacheManager.subscribe<T>(domain, (newData) => {
      setState({ domain, data: newData ?? fallbackRef.current });
    });
    return unsubscribe;
  }, [domain]);

  usePrivateCacheScopeRevision(() => {
    setState({ domain, data: readCacheDomain(domain, fallbackRef.current) });
  });

  return data;
}

/**
 * 返回 CacheManager 的增量更新方法，绑定到指定 domain
 */
export function useCacheUpdater<T>(domain: string, fallback: T) {
  const set = useCallback(
    (data: T) => {
      cacheManager.set(domain, data);
    },
    [domain]
  );

  const update = useCallback(
    (updater: (prev: T) => T) => {
      cacheManager.update(domain, updater, fallback);
    },
    [domain, fallback]
  );

  const remove = useCallback(() => {
    cacheManager.remove(domain);
  }, [domain]);

  return { set, update, remove };
}

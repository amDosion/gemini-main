/**
 * @file useCacheStatus.ts
 * @description 缓存状态 React Hook，提供缓存状态信息给 UI 组件。
 */

import { useState, useCallback, useEffect } from 'react';
import { cacheService } from '../services/cacheService';

/**
 * 缓存状态信息接口
 */
export interface CacheStatusInfo {
  /** 数据是否来自缓存 */
  isFromCache: boolean;
  /** 数据是否陈旧 */
  isStale: boolean;
  /** 是否正在刷新 */
  isRefreshing: boolean;
  /** 最后更新时间戳 */
  lastUpdated: number | null;
  /** 错误信息 */
  error: Error | null;
}

/**
 * useCacheStatus Hook 的返回类型
 */
export interface UseCacheStatusReturn extends CacheStatusInfo {
  /** 手动刷新方法 */
  refresh: () => Promise<void>;
  /** 更新缓存状态（供外部调用） */
  updateStatus: (fromCache: boolean, isStale: boolean, timestamp: number) => void;
}

/**
 * 缓存状态 Hook
 * 
 * @param key - 缓存键
 * @param refreshFn - 可选的刷新函数，用于手动刷新时调用
 * @returns 缓存状态信息和操作方法
 * 
 * @example
 * ```tsx
 * const { isFromCache, isStale, isRefreshing, refresh } = useCacheStatus('sessions', refreshSessions);
 * ```
 */
export function useCacheStatus(
  key: string,
  refreshFn?: () => Promise<any>
): UseCacheStatusReturn {
  // 状态
  const [isFromCache, setIsFromCache] = useState(false);
  const [isStale, setIsStale] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [error, setError] = useState<Error | null>(null);

  // 初始化时从 cacheService 获取状态
  useEffect(() => {
    const status = cacheService.getCacheStatus(key);
    if (status.isCached) {
      setIsFromCache(true);
      setIsStale(status.isStale);
      setLastUpdated(status.timestamp);
    }
  }, [key]);

  /**
   * 更新缓存状态（供外部调用，如 CachedDB 返回结果后）
   */
  const updateStatus = useCallback((fromCache: boolean, stale: boolean, timestamp: number) => {
    setIsFromCache(fromCache);
    setIsStale(stale);
    setLastUpdated(timestamp);
    setError(null);
  }, []);

  /**
   * 手动刷新方法
   */
  const refresh = useCallback(async () => {
    if (!refreshFn) {
      return;
    }

    setIsRefreshing(true);
    setError(null);

    try {
      await refreshFn();
      // 刷新后更新状态
      const status = cacheService.getCacheStatus(key);
      setIsFromCache(false); // 刚刷新的数据不是来自缓存
      setIsStale(false);
      setLastUpdated(status.timestamp ?? Date.now());
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsRefreshing(false);
    }
  }, [key, refreshFn]);

  return {
    isFromCache,
    isStale,
    isRefreshing,
    lastUpdated,
    error,
    refresh,
    updateStatus,
  };
}

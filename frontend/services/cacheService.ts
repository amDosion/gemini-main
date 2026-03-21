/**
 * @file cacheService.ts
 * @description 核心缓存服务，提供多层缓存策略（内存 + IndexedDB）。
 *
 * ## 设计原则
 * - 缓存优先：优先返回缓存数据，后台异步刷新
 * - 写穿透：写操作同时更新缓存和持久化存储
 * - 优雅降级：IndexedDB 不可用时降级到内存缓存
 * - TTL 管理：支持全局和特定数据类型的 TTL 配置
 * - LRU 清理：当缓存达到最大容量时，自动清理最少使用的条目
 */

import { idbCacheAdapter, CacheEntry, IDBCacheAdapter } from './idbCacheAdapter';

/**
 * 缓存配置选项
 */
export interface CacheConfig {
  defaultTTL: number;        // 默认生存时间（毫秒）
  maxEntries: number;        // 内存缓存中的最大条目数
  enablePersistence: boolean; // 是否启用 IndexedDB 持久化
}

/**
 * 缓存获取结果
 */
export interface CacheResult<T> {
  data: T;                   // 缓存数据
  fromCache: boolean;        // 是否来自缓存
  isStale: boolean;          // 数据是否陈旧
  timestamp: number;         // 数据时间戳
}

/**
 * 单个缓存条目的状态
 */
export interface CacheStatus {
  isCached: boolean;
  isStale: boolean;
  ttl: number;
  timestamp: number | null;
  lastAccess: number | null;
  accessCount: number;
}

/**
 * 缓存服务的统计信息
 */
export interface CacheStats {
  hits: number;
  misses: number;
  size: number;
  persistentAvailable: boolean;
  lastCleaned: number | null;
}

// 默认 TTL：12 小时
const DEFAULT_TTL = 12 * 60 * 60 * 1000;

/**
 * CacheService 提供了具有回退机制和后台刷新的多层缓存策略。
 */
class CacheService {
  private memoryCache: Map<string, CacheEntry<unknown>> = new Map();
  private config: CacheConfig;
  private stats: CacheStats = {
    hits: 0,
    misses: 0,
    size: 0,
    persistentAvailable: false,
    lastCleaned: null,
  };
  private ttlSettings: Map<string, number> = new Map();
  private isInitialized = false;
  private idbAdapter: IDBCacheAdapter;

  constructor(config?: Partial<CacheConfig>) {
    this.config = {
      defaultTTL: DEFAULT_TTL,
      maxEntries: 500,
      enablePersistence: true,
      ...config,
    };
    this.idbAdapter = idbCacheAdapter;
  }


  /**
   * 初始化缓存服务。
   * 如果启用了持久化，会从 IndexedDB 加载现有缓存到内存中。
   */
  async init(): Promise<void> {
    if (this.isInitialized) return;

    if (this.config.enablePersistence) {
      try {
        await this.idbAdapter.init();
        if (this.idbAdapter.isAvailable()) {
          // 从 IndexedDB 加载缓存到内存
          const allEntries = await this.idbAdapter.getAll();
          const now = Date.now();
          
          for (const [key, entry] of allEntries) {
            // 验证 TTL，清理过期条目
            if (entry.ttl > 0 && (now - entry.timestamp) > entry.ttl) {
              await this.idbAdapter.delete(key);
            } else {
              this.memoryCache.set(key, entry);
            }
          }
          this.stats.persistentAvailable = true;
        }
      } catch (error) {
        this.config.enablePersistence = false;
        this.stats.persistentAvailable = false;
      }
    }
    
    this.stats.size = this.memoryCache.size;
    this.isInitialized = true;
  }

  /**
   * 从缓存中获取数据。
   * 如果缓存未命中，则调用 fetcher 函数获取新数据并存入缓存。
   * 如果缓存命中但数据陈旧，则返回陈旧数据，并异步调用 fetcher 更新缓存。
   * @param key - 缓存键
   * @param fetcher - 用于获取新数据的异步函数
   * @param ttl - 本次操作的特定 TTL（毫秒）
   */
  async get<T>(key: string, fetcher: () => Promise<T>, ttl?: number): Promise<CacheResult<T>> {
    const entry = this.memoryCache.get(key) as CacheEntry<T> | undefined;

    if (entry) {
      this.stats.hits++;
      const now = Date.now();
      const entryTtl = ttl ?? this.getTTL(key) ?? entry.ttl ?? this.config.defaultTTL;
      const isStale = entryTtl > 0 && (now - entry.timestamp) > entryTtl;

      // 更新访问统计
      entry.lastAccess = now;
      entry.accessCount++;

      if (isStale) {
        // 返回陈旧数据，后台刷新（Stale-While-Revalidate）
        this.refresh<T>(key, fetcher, ttl).catch(() => {
          // Background refresh failed
        });
        return { data: entry.data, fromCache: true, isStale: true, timestamp: entry.timestamp };
      } else {
        // 返回有效缓存数据
        return { data: entry.data, fromCache: true, isStale: false, timestamp: entry.timestamp };
      }
    } else {
      // 缓存未命中
      this.stats.misses++;
      const newData = await fetcher();
      await this.set<T>(key, newData, ttl);
      return { data: newData, fromCache: false, isStale: false, timestamp: Date.now() };
    }
  }


  /**
   * 将数据写入缓存（写穿透）。
   * @param key - 缓存键
   * @param data - 要缓存的数据
   * @param ttl - 本次操作的特定 TTL（毫秒）
   */
  async set<T>(key: string, data: T, ttl?: number): Promise<void> {
    const now = Date.now();
    const dataType = key.split(':')[0];
    const entryTtl = ttl ?? this.ttlSettings.get(dataType) ?? this.config.defaultTTL;
    
    // 估算数据大小
    let size = 0;
    try {
      size = JSON.stringify(data).length;
    } catch {
      size = 0;
    }

    const entry: CacheEntry<T> = {
      key,
      data,
      timestamp: now,
      version: 1,
      ttl: entryTtl,
      accessCount: 0,
      lastAccess: now,
      size,
    };

    // 写入内存缓存
    this.memoryCache.set(key, entry);
    this.stats.size = this.memoryCache.size;

    // 写入 IndexedDB（如果可用）
    if (this.config.enablePersistence && this.idbAdapter.isAvailable()) {
      try {
        await this.idbAdapter.set(entry);
      } catch (error: unknown) {
        // 处理存储配额超限
        if (error instanceof Error && error.name === 'QuotaExceededError') {
          await this.cleanup();
          // 重试写入
          try {
            await this.idbAdapter.set(entry);
          } catch {
            // Failed to write to IndexedDB after cleanup
          }
        }
      }
    }

    // 检查是否需要清理
    if (this.memoryCache.size > this.config.maxEntries) {
      await this.cleanup();
    }
  }

  /**
   * 强制刷新指定键的缓存，绕过缓存直接调用 fetcher。
   * @param key - 缓存键
   * @param fetcher - 用于获取新数据的异步函数
   * @param ttl - 本次操作的特定 TTL（毫秒）
   */
  async refresh<T>(key: string, fetcher: () => Promise<T>, ttl?: number): Promise<CacheResult<T>> {
    const newData = await fetcher();
    await this.set(key, newData, ttl);
    return { data: newData, fromCache: false, isStale: false, timestamp: Date.now() };
  }

  /**
   * 从缓存中移除单个条目。
   * @param key - 缓存键
   */
  async invalidate(key: string): Promise<void> {
    if (this.memoryCache.delete(key)) {
      this.stats.size = this.memoryCache.size;
    }

    if (this.config.enablePersistence && this.idbAdapter.isAvailable()) {
      try {
        await this.idbAdapter.delete(key);
      } catch {
        // Failed to delete from IndexedDB
      }
    }
  }

  /**
   * 根据正则表达式模式失效缓存。
   * @param pattern - 用于匹配缓存键的正则表达式
   */
  async invalidatePattern(pattern: RegExp): Promise<void> {
    const keysToInvalidate: string[] = [];
    for (const key of this.memoryCache.keys()) {
      if (pattern.test(key)) {
        keysToInvalidate.push(key);
      }
    }
    
    await Promise.all(keysToInvalidate.map(key => this.invalidate(key)));
  }


  /**
   * 为特定数据类型设置 TTL。
   * @param dataType - 数据类型标识符 (例如: 'sessions', 'profiles')
   * @param ttl - 生存时间（毫秒）
   */
  setTTL(dataType: string, ttl: number): void {
    this.ttlSettings.set(dataType, ttl);
  }

  /**
   * 获取特定数据类型的 TTL。
   * @param dataType - 数据类型标识符
   */
  getTTL(dataType: string): number | undefined {
    return this.ttlSettings.get(dataType);
  }

  /**
   * 获取指定键的缓存状态。
   * @param key - 缓存键
   */
  getCacheStatus(key: string): CacheStatus {
    const entry = this.memoryCache.get(key);
    if (!entry) {
      return {
        isCached: false,
        isStale: false,
        ttl: 0,
        timestamp: null,
        lastAccess: null,
        accessCount: 0,
      };
    }

    const now = Date.now();
    const dataType = key.split(':')[0];
    const entryTtl = this.ttlSettings.get(dataType) ?? entry.ttl ?? this.config.defaultTTL;
    const isStale = entryTtl > 0 && (now - entry.timestamp) > entryTtl;

    return {
      isCached: true,
      isStale,
      ttl: entryTtl,
      timestamp: entry.timestamp,
      lastAccess: entry.lastAccess,
      accessCount: entry.accessCount,
    };
  }

  /**
   * 获取缓存服务的统计信息。
   */
  getStats(): CacheStats {
    return { ...this.stats, size: this.memoryCache.size };
  }

  /**
   * 清理缓存，移除超过最大限制的最少使用条目 (LRU)。
   */
  async cleanup(): Promise<void> {
    const now = Date.now();
    
    // 首先清理过期条目
    const expiredKeys: string[] = [];
    for (const [key, entry] of this.memoryCache) {
      if (entry.ttl > 0 && (now - entry.timestamp) > entry.ttl) {
        expiredKeys.push(key);
      }
    }
    
    for (const key of expiredKeys) {
      await this.invalidate(key);
    }
    
    // 如果仍超过限制，执行 LRU 清理
    if (this.memoryCache.size > this.config.maxEntries) {
      // 按 lastAccess 排序，删除最少使用的条目
      const sortedEntries = Array.from(this.memoryCache.values()).sort(
        (a, b) => a.lastAccess - b.lastAccess
      );

      const entriesToRemoveCount = this.memoryCache.size - this.config.maxEntries;
      const entriesToRemove = sortedEntries.slice(0, entriesToRemoveCount);

      for (const entry of entriesToRemove) {
        await this.invalidate(entry.key);
      }
    }
    
    this.stats.lastCleaned = now;
  }

  /**
   * 清空所有缓存。
   */
  async clear(): Promise<void> {
    this.memoryCache.clear();
    this.stats = { ...this.stats, hits: 0, misses: 0, size: 0 };
    
    if (this.config.enablePersistence && this.idbAdapter.isAvailable()) {
      try {
        await this.idbAdapter.clear();
      } catch {
        // Failed to clear IndexedDB
      }
    }
  }
}

// 导出 CacheService 的单例实例
export const cacheService = new CacheService();

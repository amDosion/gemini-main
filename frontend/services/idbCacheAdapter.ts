/**
 * @file idbCacheAdapter.ts
 * @description IndexedDB 缓存适配器，用于在浏览器中提供持久化缓存能力。
 *
 * ## 设计目标
 * - 提供一个符合 `IDBCacheAdapter` 接口的实现，利用 IndexedDB 进行客户端缓存。
 * - 封装 IndexedDB 的异步和事件驱动 API，提供基于 Promise 的友好接口。
 * - 优雅处理 IndexedDB 不可用或初始化失败的情况。
 * - 实现缓存数据的增、删、改、查、清空等核心功能。
 * - 提供 LRU（最近最少使用）或 TTL（生存时间）等缓存淘汰策略的支持能力。
 *
 * ## 主要功能
 * - **初始化**: `init()` - 连接数据库，创建 Object Store 和索引。
 * - **数据操作**: `get`, `set`, `delete`, `clear`, `getAll` - 核心 CRUD 操作。
 * - **缓存管理**: `deleteOldest` - 按时间戳删除最旧的条目，用于缓存淘汰。
 * - **状态检查**: `isAvailable` - 检查 IndexedDB 功能是否可用。
 * - **用量查询**: `getStorageUsage` - 获取存储空间使用情况。
 *
 * ## IndexedDB 结构
 * - **数据库 (Database)**: `flux_cache` (版本: 1)
 * - **对象仓库 (Object Store)**: `cache_entries`
 *   - **主键 (Key Path)**: `key`
 *   - **索引 (Indexes)**:
 *     - `timestamp`: 按创建/更新时间排序，用于淘汰策略。
 *     - `lastAccess`: 按最后访问时间排序，用于 LRU 淘汰策略。
 */

// 定义缓存条目的结构
export interface CacheEntry<T> {
  key: string;           // 缓存键，唯一标识
  data: T;               // 缓存的数据
  timestamp: number;     // 创建/更新时的时间戳 (毫秒)
  version: number;       // 数据版本号，用于乐观锁或数据更新检测
  ttl: number;           // 生存时间 (毫秒)，0 表示永不过期
  accessCount: number;   // 访问次数统计
  lastAccess: number;    // 最后访问时的时间戳
  size: number;          // 数据大小的估算值 (字节)
}

// 定义缓存适配器的接口
export interface IDBCacheAdapter {
  init(): Promise<void>;
  get<T>(key: string): Promise<CacheEntry<T> | null>;
  set<T>(entry: CacheEntry<T>): Promise<void>;
  delete(key: string): Promise<void>;
  clear(): Promise<void>;
  getAll(): Promise<Map<string, CacheEntry<any>>>;
  deleteOldest(count: number): Promise<void>;
  isAvailable(): boolean;
  getStorageUsage(): Promise<{ used: number; quota: number }>;
}


class IDBCacheAdapterImpl implements IDBCacheAdapter {
  private db: IDBDatabase | null = null;
  private available = false;
  private readonly dbName = 'flux_cache';
  private readonly storeName = 'cache_entries';

  /**
   * 初始化数据库。
   * 检查 IndexedDB 支持情况，并打开数据库，创建必要的 Object Store 和索引。
   */
  public init(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!('indexedDB' in window)) {
        console.warn('[IDBCacheAdapter] IndexedDB 不支持，缓存将被禁用');
        this.available = false;
        return resolve();
      }

      const request = indexedDB.open(this.dbName, 1);

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          const store = db.createObjectStore(this.storeName, { keyPath: 'key' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('lastAccess', 'lastAccess', { unique: false });
        }
      };

      request.onsuccess = (event) => {
        this.db = (event.target as IDBOpenDBRequest).result;
        this.available = true;
        console.log('[IDBCacheAdapter] IndexedDB 缓存初始化成功');
        resolve();
      };

      request.onerror = (event) => {
        console.error('[IDBCacheAdapter] IndexedDB 初始化失败:', (event.target as IDBOpenDBRequest).error);
        this.available = false;
        reject((event.target as IDBOpenDBRequest).error);
      };
    });
  }

  /**
   * 检查 IndexedDB 是否可用。
   * @returns {boolean} 如果 IndexedDB 已成功初始化，则返回 true。
   */
  public isAvailable(): boolean {
    return this.available && this.db !== null;
  }

  /**
   * 从缓存中获取一个条目。
   * 获取后会自动更新其 `lastAccess` 时间戳和 `accessCount`。
   * @param key - 缓存键。
   * @returns {Promise<CacheEntry<T> | null>} 缓存条目或 null。
   */
  public async get<T>(key: string): Promise<CacheEntry<T> | null> {
    if (!this.isAvailable()) return null;

    const entry = await this.performStoreAction<CacheEntry<T>>('readonly', (store) => {
      return store.get(key);
    });

    if (entry) {
      // 异步更新访问时间和计数，不阻塞读取操作
      this.updateAccessStats(key, entry.accessCount).catch(err => {
        console.error(`[IDBCacheAdapter] 更新访问统计失败 "${key}":`, err);
      });
    }

    return entry ?? null;
  }

  /**
   * 向缓存中设置一个条目。
   * 如果键已存在，则会覆盖现有条目。
   * @param entry - 要设置的缓存条目数据。
   */
  public set<T>(entry: CacheEntry<T>): Promise<void> {
    if (!this.isAvailable()) return Promise.resolve();
    
    return this.performStoreAction('readwrite', (store) => {
      return store.put(entry);
    });
  }

  /**
   * 从缓存中删除一个条目。
   * @param key - 缓存键。
   */
  public delete(key: string): Promise<void> {
    if (!this.isAvailable()) return Promise.resolve();
    return this.performStoreAction('readwrite', (store) => {
      return store.delete(key);
    });
  }

  /**
   * 清空所有缓存条目。
   */
  public clear(): Promise<void> {
    if (!this.isAvailable()) return Promise.resolve();
    return this.performStoreAction('readwrite', (store) => {
      return store.clear();
    });
  }


  /**
   * 获取所有缓存条目。
   * @returns {Promise<Map<string, CacheEntry<any>>>} 包含所有缓存条目的 Map。
   */
  public getAll(): Promise<Map<string, CacheEntry<any>>> {
    if (!this.isAvailable()) return Promise.resolve(new Map());

    return this.performStoreAction('readonly', (store) => {
      const request = store.openCursor();
      const allEntries = new Map<string, CacheEntry<any>>();

      return new Promise((resolve, reject) => {
        request.onsuccess = (event) => {
          const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
          if (cursor) {
            allEntries.set(cursor.key as string, cursor.value);
            cursor.continue();
          } else {
            resolve(allEntries);
          }
        };
        request.onerror = () => reject(request.error);
      });
    });
  }
  
  /**
   * 删除最旧的 `count` 个条目。
   * 基于 `timestamp` 索引进行排序，用于实现缓存淘汰。
   * @param count - 要删除的条目数量。
   */
  public deleteOldest(count: number): Promise<void> {
    if (!this.isAvailable() || count <= 0) return Promise.resolve();

    return this.performStoreAction('readwrite', (store) => {
      const index = store.index('timestamp');
      const request = index.openCursor();
      let deletedCount = 0;

      return new Promise<void>((resolve, reject) => {
        request.onsuccess = (event) => {
          const cursor = (event.target as IDBRequest<IDBCursor>).result;
          if (cursor && deletedCount < count) {
            cursor.delete();
            deletedCount++;
            cursor.continue();
          } else {
            resolve();
          }
        };
        request.onerror = () => reject(request.error);
      });
    });
  }

  /**
   * 获取存储使用情况。
   * 使用 `navigator.storage.estimate()` API (如果可用)。
   * @returns {Promise<{ used: number; quota: number }>} 存储使用量和配额。
   */
  public async getStorageUsage(): Promise<{ used: number, quota: number }> {
    if (navigator.storage && navigator.storage.estimate) {
      const estimation = await navigator.storage.estimate();
      return {
        used: estimation.usage ?? 0,
        quota: estimation.quota ?? 0,
      };
    }
    console.warn('[IDBCacheAdapter] StorageManager API 不可用，无法估算存储使用量');
    return { used: 0, quota: 0 };
  }

  /**
   * 辅助方法，用于执行 IndexedDB 事务和操作。
   * 封装了事务的创建、成功和失败处理。
   * @param mode - 事务模式 ('readonly' or 'readwrite')。
   * @param action - 在事务中执行的回调函数。
   * @returns {Promise<T>} 操作结果。
   */
  private performStoreAction<T>(
    mode: IDBTransactionMode,
    action: (store: IDBObjectStore) => IDBRequest | Promise<T>
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.db) {
        return reject(new Error('[IDBCacheAdapter] 数据库未初始化'));
      }

      try {
        const transaction = this.db.transaction(this.storeName, mode);
        const store = transaction.objectStore(this.storeName);

        const result = action(store);
        
        // 如果 action 返回的是一个 Promise，我们等待它完成
        if (result instanceof Promise) {
            result.then(resolve).catch(reject);
            return;
        }

        // 否则，我们假设它是一个 IDBRequest
        let resolved = false;
        result.onsuccess = () => {
            if (!resolved) {
                resolved = true;
                resolve(result.result);
            }
        };
        result.onerror = () => reject(result.error);
        
        transaction.oncomplete = () => {
            if (!resolved) {
                resolved = true;
                resolve(result.result);
            }
        };
        transaction.onerror = () => reject(transaction.error);
        
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 更新条目的访问统计信息。
   * @param key - 缓存键。
   * @param currentAccessCount - 当前的访问次数。
   */
  private updateAccessStats(key: string, currentAccessCount: number): Promise<void> {
    return this.performStoreAction('readwrite', (store) => {
        const getRequest = store.get(key);
        return new Promise<void>((resolve, reject) => {
            getRequest.onsuccess = () => {
                const entry = getRequest.result;
                if(entry) {
                    entry.lastAccess = Date.now();
                    entry.accessCount = (currentAccessCount || 0) + 1;
                    const putRequest = store.put(entry);
                    putRequest.onsuccess = () => resolve();
                    putRequest.onerror = () => reject(putRequest.error);
                } else {
                    // 条目可能在 get 和 update 之间被删除
                    resolve(); 
                }
            };
            getRequest.onerror = () => reject(getRequest.error);
        });
    });
  }
}

// 导出一个单例实例
export const idbCacheAdapter = new IDBCacheAdapterImpl();

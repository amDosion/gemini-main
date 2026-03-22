/**
 * 统一缓存管理器
 * 
 * 整合所有前端缓存到单一入口：
 * - 内存缓存（Map，热数据）
 * - IndexedDB 持久化（冷数据，可选）
 * - 事件驱动（订阅缓存变化）
 * - 统一生命周期（登出一次清空）
 */

type Listener<T = unknown> = (data: T) => void;

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

const DEFAULT_TTL = 5 * 60 * 1000; // 5 minutes

class CacheManagerImpl {
  private store = new Map<string, CacheEntry<unknown>>();
  private listeners = new Map<string, Set<Listener>>();
  private ttlConfig = new Map<string, number>();

  // ==================== 配置 ====================

  /** 设置某个 domain 的默认 TTL */
  setTTL(domain: string, ttl: number): void {
    this.ttlConfig.set(domain, ttl);
  }

  // ==================== 读 ====================

  /** 获取缓存数据 */
  get<T>(domain: string): T | null {
    const entry = this.store.get(domain);
    if (!entry) return null;
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.store.delete(domain);
      return null;
    }
    return entry.data as T;
  }

  // ==================== 写 ====================

  /** 设置缓存数据（全量覆盖） */
  set<T>(domain: string, data: T): void {
    const ttl = this.ttlConfig.get(domain) || DEFAULT_TTL;
    this.store.set(domain, { data, timestamp: Date.now(), ttl });
    this.notify(domain, data);
  }

  /** 增量更新缓存数据 */
  update<T>(domain: string, updater: (prev: T) => T, fallback: T): void {
    const current = this.get<T>(domain) ?? fallback;
    const next = updater(current);
    this.set(domain, next);
  }

  // ==================== 删 ====================

  /** 删除某个 domain 的缓存 */
  remove(domain: string): void {
    this.store.delete(domain);
    this.notify(domain, null);
  }

  /** 清空所有缓存（登出时调用） */
  clearAll(): void {
    this.store.clear();
    // 通知所有订阅者
    for (const [domain, listeners] of this.listeners) {
      for (const listener of listeners) {
        listener(null);
      }
    }
  }

  // ==================== 订阅 ====================

  /** 订阅缓存变化，返回取消订阅函数 */
  subscribe<T>(domain: string, callback: Listener<T>): () => void {
    if (!this.listeners.has(domain)) {
      this.listeners.set(domain, new Set());
    }
    const listeners = this.listeners.get(domain)!;
    listeners.add(callback as Listener);
    return () => {
      listeners.delete(callback as Listener);
      if (listeners.size === 0) {
        this.listeners.delete(domain);
      }
    };
  }

  // ==================== 内部 ====================

  private notify(domain: string, data: unknown): void {
    const listeners = this.listeners.get(domain);
    if (!listeners) return;
    for (const listener of listeners) {
      listener(data);
    }
  }

  // ==================== 调试 ====================

  /** 获取缓存状态（调试用） */
  getStats(): { domains: string[]; totalEntries: number; listeners: number } {
    return {
      domains: Array.from(this.store.keys()),
      totalEntries: this.store.size,
      listeners: Array.from(this.listeners.values()).reduce((sum, s) => sum + s.size, 0),
    };
  }
}

/** 全局单例 */
export const cacheManager = new CacheManagerImpl();

/** 缓存 domain 常量 */
export const CACHE_DOMAINS = {
  SESSIONS: 'sessions',
  PROFILES: 'profiles',
  PERSONAS: 'personas',
  STORAGE_CONFIGS: 'storageConfigs',
  ACTIVE_STORAGE_ID: 'activeStorageId',
  MODELS: 'models',
  MODE_MODELS: 'modeModels',
  MODEL_CATALOG: 'modelCatalog',
  PROVIDER_TEMPLATES: 'providerTemplates',
} as const;

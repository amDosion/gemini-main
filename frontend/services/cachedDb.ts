/**
 * @file cachedDb.ts
 * @description CachedDB 包装器，为 HybridDB 添加缓存层。
 *
 * ## 设计原则
 * - 包装现有 HybridDB，透明添加缓存能力
 * - 读取操作使用 Stale-While-Revalidate 策略
 * - 写入操作使用写穿透策略，同时失效相关缓存
 * - 提供强制刷新方法
 */

import { db, ConfigProfile } from './db';
import { cacheService, CacheResult } from './cacheService';
import { ChatSession, Persona } from '../types/types';
import { StorageConfig } from '../types/storage';

// 缓存键常量
const CACHE_KEYS = {
  SESSIONS: 'sessions',
  PROFILES: 'profiles',
  PERSONAS: 'personas',
  STORAGE_CONFIGS: 'storage_configs',
} as const;

// 默认 TTL 配置（毫秒）
const TTL_CONFIG = {
  sessions: 12 * 60 * 60 * 1000,      // 12 小时
  profiles: 12 * 60 * 60 * 1000,      // 12 小时
  personas: 24 * 60 * 60 * 1000,      // 24 小时
  storage_configs: 12 * 60 * 60 * 1000, // 12 小时
};

/**
 * CachedDB 类，为 HybridDB 添加缓存层
 */
class CachedDB {
  private initialized = false;

  /**
   * 初始化缓存服务和 TTL 配置
   */
  async init(): Promise<void> {
    if (this.initialized) return;

    await cacheService.init();

    // 设置各数据类型的 TTL
    cacheService.setTTL(CACHE_KEYS.SESSIONS, TTL_CONFIG.sessions);
    cacheService.setTTL(CACHE_KEYS.PROFILES, TTL_CONFIG.profiles);
    cacheService.setTTL(CACHE_KEYS.PERSONAS, TTL_CONFIG.personas);
    cacheService.setTTL(CACHE_KEYS.STORAGE_CONFIGS, TTL_CONFIG.storage_configs);

    this.initialized = true;
  }


  // ==================== 会话操作（带缓存） ====================

  /**
   * 获取会话列表（带缓存）
   */
  async getSessions(): Promise<CacheResult<ChatSession[]>> {
    return cacheService.get<ChatSession[]>(
      CACHE_KEYS.SESSIONS,
      () => db.getSessions()
    );
  }

  /**
   * 保存会话（写穿透）
   * 保存后失效会话列表缓存
   */
  async saveSession(session: ChatSession): Promise<void> {
    await db.saveSession(session);
    await cacheService.invalidate(CACHE_KEYS.SESSIONS);
  }

  /**
   * 删除会话
   * 删除后失效会话列表缓存
   */
  async deleteSession(id: string): Promise<void> {
    await db.deleteSession(id);
    await cacheService.invalidate(CACHE_KEYS.SESSIONS);
  }

  /**
   * 强制刷新会话列表
   */
  async refreshSessions(): Promise<CacheResult<ChatSession[]>> {
    return cacheService.refresh<ChatSession[]>(
      CACHE_KEYS.SESSIONS,
      () => db.getSessions()
    );
  }

  // ==================== 配置档案操作（带缓存） ====================

  /**
   * 获取配置档案列表（带缓存）
   */
  async getProfiles(): Promise<CacheResult<ConfigProfile[]>> {
    return cacheService.get<ConfigProfile[]>(
      CACHE_KEYS.PROFILES,
      () => db.getProfiles()
    );
  }

  /**
   * 保存配置档案（写穿透）
   */
  async saveProfile(profile: ConfigProfile): Promise<void> {
    await db.saveProfile(profile);
    await cacheService.invalidate(CACHE_KEYS.PROFILES);
  }

  /**
   * 删除配置档案
   */
  async deleteProfile(id: string): Promise<void> {
    await db.deleteProfile(id);
    await cacheService.invalidate(CACHE_KEYS.PROFILES);
  }

  /**
   * 强制刷新配置档案列表
   */
  async refreshProfiles(): Promise<CacheResult<ConfigProfile[]>> {
    return cacheService.refresh<ConfigProfile[]>(
      CACHE_KEYS.PROFILES,
      () => db.getProfiles()
    );
  }

  // ==================== 角色操作（带缓存） ====================

  /**
   * 获取角色列表（带缓存）
   */
  async getPersonas(): Promise<CacheResult<Persona[]>> {
    return cacheService.get<Persona[]>(
      CACHE_KEYS.PERSONAS,
      () => db.getPersonas()
    );
  }

  /**
   * 保存角色列表（写穿透）
   */
  async savePersonas(personas: Persona[]): Promise<void> {
    await db.savePersonas(personas);
    await cacheService.invalidate(CACHE_KEYS.PERSONAS);
  }

  /**
   * 强制刷新角色列表
   */
  async refreshPersonas(): Promise<CacheResult<Persona[]>> {
    return cacheService.refresh<Persona[]>(
      CACHE_KEYS.PERSONAS,
      () => db.getPersonas()
    );
  }


  // ==================== 存储配置操作（带缓存） ====================

  /**
   * 获取存储配置列表（带缓存）
   */
  async getStorageConfigs(): Promise<CacheResult<StorageConfig[]>> {
    return cacheService.get<StorageConfig[]>(
      CACHE_KEYS.STORAGE_CONFIGS,
      () => db.getStorageConfigs()
    );
  }

  /**
   * 保存存储配置（写穿透）
   */
  async saveStorageConfig(config: StorageConfig): Promise<void> {
    await db.saveStorageConfig(config);
    await cacheService.invalidate(CACHE_KEYS.STORAGE_CONFIGS);
  }

  /**
   * 删除存储配置
   */
  async deleteStorageConfig(id: string): Promise<void> {
    await db.deleteStorageConfig(id);
    await cacheService.invalidate(CACHE_KEYS.STORAGE_CONFIGS);
  }

  /**
   * 强制刷新存储配置列表
   */
  async refreshStorageConfigs(): Promise<CacheResult<StorageConfig[]>> {
    return cacheService.refresh<StorageConfig[]>(
      CACHE_KEYS.STORAGE_CONFIGS,
      () => db.getStorageConfigs()
    );
  }

  // ==================== 透传方法（不需要缓存） ====================

  /**
   * 获取当前激活的配置档案 ID
   */
  async getActiveProfileId(): Promise<string | null> {
    return db.getActiveProfileId();
  }

  /**
   * 设置当前激活的配置档案 ID
   */
  async setActiveProfileId(id: string): Promise<void> {
    return db.setActiveProfileId(id);
  }

  /**
   * 获取当前激活的存储配置 ID
   */
  async getActiveStorageId(): Promise<string | null> {
    return db.getActiveStorageId();
  }

  /**
   * 设置当前激活的存储配置 ID
   */
  async setActiveStorageId(id: string): Promise<void> {
    return db.setActiveStorageId(id);
  }

  // ==================== 缓存管理方法 ====================

  /**
   * 获取缓存统计信息
   */
  getCacheStats() {
    return cacheService.getStats();
  }

  /**
   * 获取指定键的缓存状态
   */
  getCacheStatus(key: string) {
    return cacheService.getCacheStatus(key);
  }

  /**
   * 清空所有缓存
   */
  async clearCache(): Promise<void> {
    await cacheService.clear();
  }
}

// 导出 CachedDB 的单例实例
export const cachedDb = new CachedDB();

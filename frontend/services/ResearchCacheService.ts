/**
 * @file ResearchCacheService.ts
 * @description 深度研究代理功能的缓存服务
 *
 * 该服务负责缓存深度研究的查询结果，以提高性能和减少重复请求。
 * 它使用浏览器的 localStorage 作为缓存存储，并提供以下功能：
 * 1. 为查询生成基于 SHA-256 的哈希缓存键。
 * 2. 如果查询结果存在于缓存中且未过期，则返回缓存结果。
 * 3. 将新的研究结果存入缓存，并设置默认24小时的过期时间。
 * 4. 自动和手动清理过期或全部的缓存条目。
 */

const CACHE_PREFIX = 'gemini-research-cache-';
const DEFAULT_TTL = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

/**
 * 缓存条目的结构定义
 */
interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

/**
 * @class ResearchCacheService
 * @description 管理深度研究结果的缓存。
 *
 * 这是一个单例类，提供了一套方法来获取、设置、清除缓存数据。
 * 缓存存储在 localStorage 中，并包含时间戳和 TTL（生存时间）以实现过期策略。
 */
class ResearchCacheService {
  /**
   * 将 ArrayBuffer 转换为十六进制字符串。
   * @param buffer - 需要转换的 ArrayBuffer。
   * @returns 十六进制表示的字符串。
   */
  private arrayBufferToHex(buffer: ArrayBuffer): string {
    return Array.from(new Uint8Array(buffer))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }

  /**
   * 生成缓存键。
   * 使用 SHA-256 哈希算法为查询和格式的组合生成一个唯一的键。
   *
   * @param query - 用户的查询字符串。
   * @param format - 结果的格式（例如 'json', 'markdown'）。
   * @returns 返回一个 Promise，解析为十六进制的哈希字符串。
   */
  public async generateCacheKey(query: string, format: string = 'default'): Promise<string> {
    const uniqueString = `${query.trim()}::${format.trim()}`;
    const encoder = new TextEncoder();
    const data = encoder.encode(uniqueString);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hash = this.arrayBufferToHex(hashBuffer);
    return `${CACHE_PREFIX}${hash}`;
  }

  /**
   * 从缓存中获取数据。
   *
   * @template T
   * @param query - 用户的查询字符串。
   * @param format - 结果的格式。
   * @returns 返回一个 Promise，解析为缓存的数据或 null（如果未找到或已过期）。
   */
  public async get<T>(query: string, format?: string): Promise<T | null> {
    try {
      const key = await this.generateCacheKey(query, format);
      const item = localStorage.getItem(key);

      if (!item) {
        return null;
      }

      const entry: CacheEntry<T> = JSON.parse(item);
      const isExpired = (Date.now() - entry.timestamp) > entry.ttl;

      if (isExpired) {
        // 如果数据已过期，从缓存中清除并返回 null
        await this.clear(query, format);
        return null;
      }

      return entry.data;
    } catch (error) {
      console.error('Failed to get cache entry:', error);
      return null;
    }
  }

  /**
   * 将数据存入缓存。
   *
   * @param query - 用户的查询字符串。
   * @param result - 要缓存的数据。
   * @param format - 结果的格式。
   * @param ttl - 缓存的生存时间（毫秒），默认为24小时。
   * @returns 返回一个 Promise，在数据成功存入后解析。
   */
  public async set(query: string, result: any, format?: string, ttl: number = DEFAULT_TTL): Promise<void> {
    try {
      const key = await this.generateCacheKey(query, format);
      const entry: CacheEntry<any> = {
        data: result,
        timestamp: Date.now(),
        ttl,
      };
      localStorage.setItem(key, JSON.stringify(entry));
    } catch (error) {
      console.error('Failed to set cache entry:', error);
    }
  }

  /**
   * 从缓存中清除指定的条目。
   *
   * @param query - 用户的查询字符串。
   * @param format - 结果的格式。
   * @returns 返回一个 Promise，在数据成功清除后解析。
   */
  public async clear(query: string, format?: string): Promise<void> {
    try {
      const key = await this.generateCacheKey(query, format);
      localStorage.removeItem(key);
    } catch (error) {
      console.error('Failed to clear cache entry:', error);
    }
  }

  /**
   * 清除所有已过期的缓存条目。
   *
   * @returns 返回一个 Promise，在清理完成后解析。
   */
  public async clearExpired(): Promise<void> {
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith(CACHE_PREFIX)) {
          const item = localStorage.getItem(key);
          if (item) {
            const entry: CacheEntry<any> = JSON.parse(item);
            if ((Date.now() - entry.timestamp) > entry.ttl) {
              localStorage.removeItem(key);
              i--;
            }
          }
        }
      }
    } catch (error) {
      console.error('Failed to clear expired cache entries:', error);
    }
  }

  /**
   * 清除所有与此服务相关的缓存条目。
   *
   * @returns 返回一个 Promise，在所有相关缓存被清除后解析。
   */
  public async clearAll(): Promise<void> {
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith(CACHE_PREFIX)) {
          localStorage.removeItem(key);
          i--;
        }
      }
    } catch (error) {
      console.error('Failed to clear all cache entries:', error);
    }
  }
}

// 导出一个单例实例
export const researchCacheService = new ResearchCacheService();

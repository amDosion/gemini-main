/**
 * LLM Factory - 基于后端 Provider 配置动态创建 Provider 实例
 * 
 * 架构说明：
 * - 后端通过 ProviderConfig 统一管理所有 Provider 配置
 * - 前端通过 /api/providers/templates API 获取配置（在应用启动时预加载）
 * - 所有 Provider 统一使用 UnifiedProviderClient（通过后端统一处理）
 * 
 * 优势：
 * - 单一数据源：配置由后端 ProviderConfig 统一管理
 * - 自动同步：新增 Provider 只需在后端配置，前端自动支持
 * - 减少维护：无需在前端硬编码 Provider 列表
 * - 统一架构：所有 Provider 都通过后端统一路由处理
 * 
 * 使用方式：
 * 1. 在应用启动时调用 LLMFactory.initialize() 预加载配置
 * 2. 调用 LLMFactory.getProvider() 获取 Provider 实例（同步，使用缓存的配置）
 */

import { ApiProtocol } from '../types/types';
import { ILLMProvider } from './providers/interfaces';
import { UnifiedProviderClient } from './providers/UnifiedProviderClient';
import { getProviderTemplates, AIProviderConfig } from './providers';
import { cacheManager, CACHE_DOMAINS } from './CacheManager';

export class LLMFactory {
  private static initialized: boolean = false;

  /** Cache key prefix for LLM provider instances */
  private static readonly INSTANCE_PREFIX = 'llmInstances:';

  /**
   * 初始化：从后端预加载 Provider 配置
   * 建议在应用启动时调用
   */
  static async initialize(): Promise<void> {
    if (this.initialized && cacheManager.get<AIProviderConfig[]>(CACHE_DOMAINS.PROVIDER_TEMPLATES)) {
      return;
    }

    try {
      await getProviderTemplates();
      this.initialized = true;
    } catch (error) {
      // 即使加载失败，也标记为已初始化，避免重复尝试
      this.initialized = true;
    }
  }

  /**
   * 根据 providerId 查找后端配置（同步，使用缓存）
   */
  private static findProviderConfig(providerId: string): AIProviderConfig | undefined {
    const templates = cacheManager.get<AIProviderConfig[]>(CACHE_DOMAINS.PROVIDER_TEMPLATES);
    if (!templates) {
      return undefined;
    }
    return templates.find(t => t.id === providerId);
  }

  /**
   * 根据后端配置动态创建 Provider 实例（同步）
   * 
   * 逻辑：
   * 所有 Provider 统一使用 UnifiedProviderClient（通过后端统一处理）
   * 
   * @param protocol The API protocol (google, openai)
   * @param providerId The specific provider ID (e.g., 'deepseek', 'tongyi')
   */
  static getProvider(protocol: ApiProtocol, providerId: string): ILLMProvider {
    const cacheKey = `${this.INSTANCE_PREFIX}${providerId}_${protocol}`;

    const cached = cacheManager.get<ILLMProvider>(cacheKey);
    if (cached) {
      return cached;
    }

    // ✅ 所有 Provider 统一使用 UnifiedProviderClient（通过后端统一处理）
    const provider: ILLMProvider = new UnifiedProviderClient(providerId);

    cacheManager.set(cacheKey, provider);
    return provider;
  }

  /**
   * 清除缓存（用于重新加载配置）
   */
  static clearCache(): void {
    cacheManager.clearDomain(this.INSTANCE_PREFIX);
    cacheManager.remove(CACHE_DOMAINS.PROVIDER_TEMPLATES);
    this.initialized = false;
  }
}

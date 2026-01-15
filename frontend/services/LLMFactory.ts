/**
 * LLM Factory - 基于后端 Provider 配置动态创建 Provider 实例
 * 
 * 架构说明：
 * - 后端通过 ProviderConfig 统一管理所有 Provider 配置
 * - 前端通过 /api/providers/templates API 获取配置（在应用启动时预加载）
 * - 所有 Provider 统一使用 UnifiedProviderClient（通过后端统一处理）
 * - OpenAIProvider 已废弃，内部也委托给 UnifiedProviderClient
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
import { OpenAIProvider } from './providers/openai/OpenAIProvider'; // 保留用于向后兼容
import { getProviderTemplates, AIProviderConfig } from './providers';

export class LLMFactory {
  // Cache by providerId (e.g., 'google', 'openai', 'deepseek', 'tongyi')
  private static instances: Map<string, ILLMProvider> = new Map();
  // Cache provider templates from backend
  private static providerTemplates: AIProviderConfig[] | null = null;
  private static templatesLoading: Promise<AIProviderConfig[]> | null = null;
  private static initialized: boolean = false;

  /**
   * 初始化：从后端预加载 Provider 配置
   * 建议在应用启动时调用
   */
  static async initialize(): Promise<void> {
    if (this.initialized && this.providerTemplates) {
      return;
    }

    try {
      this.providerTemplates = await getProviderTemplates();
      this.initialized = true;
    } catch (error) {
      console.warn('[LLMFactory] Failed to load provider templates, will use fallback logic:', error);
      // 即使加载失败，也标记为已初始化，避免重复尝试
      this.initialized = true;
    }
  }

  /**
   * 根据 providerId 查找后端配置（同步，使用缓存）
   */
  private static findProviderConfig(providerId: string): AIProviderConfig | undefined {
    if (!this.providerTemplates) {
      return undefined;
    }
    return this.providerTemplates.find(t => t.id === providerId);
  }

  /**
   * 根据后端配置动态创建 Provider 实例（同步）
   * 
 * 逻辑：
 * 1. 所有 Provider 统一使用 UnifiedProviderClient（通过后端统一处理）
 * 2. OpenAIProvider 保留用于向后兼容，但内部也委托给 UnifiedProviderClient
 * 3. 如果后端配置不存在，使用默认逻辑（向后兼容）
   * 
   * @param protocol The API protocol (google, openai)
   * @param providerId The specific provider ID (e.g., 'deepseek', 'tongyi')
   */
  static getProvider(protocol: ApiProtocol, providerId: string): ILLMProvider {
    const cacheKey = `${providerId}_${protocol}`;

    if (this.instances.has(cacheKey)) {
      return this.instances.get(cacheKey)!;
    }

    let provider: ILLMProvider;

    // ✅ 尝试从后端配置获取信息
    const config = this.findProviderConfig(providerId);

    if (config) {
      // ✅ 基于后端配置创建 Provider
      // 注意：OpenAIProvider 内部也委托给 UnifiedProviderClient，但保留用于向后兼容
      // 所有 Provider 统一使用 UnifiedProviderClient（通过后端统一处理）
      if (protocol === 'openai' && (providerId === 'openai' || providerId === 'custom')) {
        // ✅ 保留 OpenAIProvider 用于向后兼容（内部已委托给 UnifiedProviderClient）
        provider = new OpenAIProvider();
      } else {
        // ✅ 其他情况统一使用 UnifiedProviderClient（通过后端统一处理）
        provider = new UnifiedProviderClient(providerId);
      }
    } else {
      // ✅ 配置不存在，使用默认逻辑（向后兼容）
      // 所有 Provider 统一使用 UnifiedProviderClient（通过后端统一处理）
      if (protocol === 'openai' && (providerId === 'openai' || providerId === 'custom')) {
        // ✅ 保留 OpenAIProvider 用于向后兼容（内部已委托给 UnifiedProviderClient）
        provider = new OpenAIProvider();
      } else {
        // 默认使用 UnifiedProviderClient（通过后端统一处理）
        provider = new UnifiedProviderClient(providerId);
      }
    }

    this.instances.set(cacheKey, provider);
    return provider;
  }

  /**
   * 清除缓存（用于重新加载配置）
   */
  static clearCache(): void {
    this.instances.clear();
    this.providerTemplates = null;
    this.templatesLoading = null;
    this.initialized = false;
  }
}

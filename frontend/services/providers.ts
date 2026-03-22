/**
 * Provider Templates API 服务
 * 
 * 职责：
 * - 从后端 API 获取 Provider Templates 配置
 * - 提供缓存机制减少 API 调用
 * - 提供辅助函数
 * 
 * 创建时间: 2026-01-05
 * 更新时间: 2026-01-11 (Task 3.1: Enhanced with capabilities, modes, platformRouting)
 */

import { ApiProtocol } from '../types/types';
import { cacheManager, CACHE_DOMAINS } from './CacheManager';

/**
 * Provider capabilities configuration
 */
export interface ProviderCapabilities {
  vision?: boolean;
  thinking?: boolean;
  search?: boolean;
  codeExecution?: boolean;
  streaming?: boolean;
  functionCalling?: boolean;
}

/**
 * Platform routing configuration for Google modes
 */
export interface PlatformRoutingConfig {
  support: 'vertex_ai_only' | 'developer_api_only' | 'vertex_ai_preferred' | 'either';
  default: 'vertex_ai' | 'developer_api';
}

/**
 * Dual-client configuration
 */
export interface DualClientConfig {
  enabled: boolean;
  primaryClientType: string;
  secondaryClientType?: string;
  secondaryBaseUrl?: string;
}

/**
 * AI Provider Configuration (matches backend schema)
 */
export interface AIProviderConfig {
  id: string;
  name: string;
  protocol: ApiProtocol;
  baseUrl: string;
  defaultModel?: string;
  icon?: string;
  description: string;
  isCustom?: boolean;
  // Enhanced fields (Task 3.1)
  capabilities?: ProviderCapabilities;
  dualClient?: boolean | DualClientConfig;
  modes?: string[];
  platformRouting?: Record<string, PlatformRoutingConfig>;
}

/**
 * 从后端获取 Provider Templates
 */
export async function fetchProviderTemplates(): Promise<AIProviderConfig[]> {
  try {
    const response = await fetch('/api/providers/templates');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const templates = await response.json();
    return templates;
  } catch (error) {
    throw error;
  }
}

/**
 * 获取 Provider Templates（带缓存）
 */
export async function getProviderTemplates(forceRefresh = false): Promise<AIProviderConfig[]> {
  if (!forceRefresh) {
    const cached = cacheManager.get<AIProviderConfig[]>(CACHE_DOMAINS.PROVIDER_TEMPLATES);
    if (cached) {
      return cached;
    }
  }
  
  const templates = await fetchProviderTemplates();
  cacheManager.set(CACHE_DOMAINS.PROVIDER_TEMPLATES, templates);
  return templates;
}

/**
 * 清除缓存
 */
export function clearProviderTemplatesCache(): void {
  cacheManager.remove(CACHE_DOMAINS.PROVIDER_TEMPLATES);
}

/**
 * 根据 ID 获取 Provider Template
 */
export function getProviderTemplateById(
  id: string, 
  templates: AIProviderConfig[]
): AIProviderConfig | undefined {
  return templates.find(t => t.id === id);
}

/**
 * 检查 Provider 是否支持特定能力
 */
export function hasCapability(
  provider: AIProviderConfig,
  capability: keyof ProviderCapabilities
): boolean {
  return provider.capabilities?.[capability] === true;
}

/**
 * 检查 Provider 是否支持特定模式
 */
export function hasMode(
  provider: AIProviderConfig,
  mode: string
): boolean {
  return provider.modes?.includes(mode) === true;
}

/**
 * 获取 Provider 的平台路由配置
 */
export function getPlatformRouting(
  provider: AIProviderConfig,
  mode: string
): PlatformRoutingConfig | undefined {
  return provider.platformRouting?.[mode];
}

/**
 * 检查 Provider 是否支持双客户端模式
 */
export function hasDualClient(provider: AIProviderConfig): boolean {
  if (typeof provider.dualClient === 'boolean') {
    return provider.dualClient;
  }
  return provider.dualClient?.enabled === true;
}


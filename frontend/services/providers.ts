/**
 * Provider Templates API 服务
 * 
 * 职责：
 * - 从后端 API 获取 Provider Templates 配置
 * - 提供缓存机制减少 API 调用
 * - 提供辅助函数
 * 
 * 创建时间: 2026-01-05
 */

import { ApiProtocol } from '../types/types';

export interface AIProviderConfig {
  id: string;
  name: string;
  protocol: ApiProtocol;
  baseUrl: string;
  defaultModel?: string;
  icon?: string;
  description: string;
  isCustom?: boolean;
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
    console.log('[Provider Templates] Loaded', templates.length, 'templates from API');
    return templates;
  } catch (error) {
    console.error('[Provider Templates] Failed to fetch:', error);
    throw error;
  }
}

/**
 * Provider Templates 缓存
 */
let cachedTemplates: AIProviderConfig[] | null = null;

/**
 * 获取 Provider Templates（带缓存）
 */
export async function getProviderTemplates(forceRefresh = false): Promise<AIProviderConfig[]> {
  if (!forceRefresh && cachedTemplates) {
    console.log('[Provider Templates] Using cached templates');
    return cachedTemplates;
  }
  
  cachedTemplates = await fetchProviderTemplates();
  return cachedTemplates;
}

/**
 * 清除缓存
 */
export function clearProviderTemplatesCache(): void {
  cachedTemplates = null;
  console.log('[Provider Templates] Cache cleared');
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

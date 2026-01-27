/**
 * 分辨率工具函数
 * 
 * 这些函数用于动态获取比例和分辨率配置
 * UI 组件应使用这些函数而非直接访问映射表
 */

import { AspectRatioOption, ResolutionTierOption } from './types';
import {
  GOOGLE_GEN_1K_RESOLUTIONS,
  GOOGLE_GEN_2K_RESOLUTIONS,
  GOOGLE_GEN_4K_RESOLUTIONS,
  Z_IMAGE_1K_RESOLUTIONS,
  Z_IMAGE_1280_RESOLUTIONS,
  Z_IMAGE_1536_RESOLUTIONS,
  Z_IMAGE_2K_RESOLUTIONS,
  WAN26_IMAGE_RESOLUTIONS,
  WAN_T2I_1K_RESOLUTIONS,
  WAN_T2I_1280_RESOLUTIONS,
  WAN_T2I_1536_RESOLUTIONS,
} from './resolutions';
import {
  GOOGLE_GEN_ASPECT_RATIOS,
  Z_IMAGE_ASPECT_RATIOS,
  WAN26_IMAGE_ASPECT_RATIOS,
  TONGYI_GEN_ASPECT_RATIOS,
} from './aspectRatios';
import {
  GOOGLE_GEN_RESOLUTION_TIERS,
  Z_IMAGE_RESOLUTION_TIERS,
  TONGYI_GEN_RESOLUTION_TIERS,
} from './resolutions';

/**
 * 获取指定模型的分辨率映射表
 * @param provider 提供商: 'tongyi' | 'google'
 * @param modelId 模型ID（通义提供商需要）
 * @param tier 分辨率档位
 * @returns 分辨率映射表
 */
function getResolutionMap(
  provider: 'tongyi' | 'google',
  modelId: string | undefined,
  tier: string
): Record<string, string> {
  if (provider === 'google') {
    switch (tier) {
      case '1K': return GOOGLE_GEN_1K_RESOLUTIONS;
      case '2K': return GOOGLE_GEN_2K_RESOLUTIONS;
      case '4K': return GOOGLE_GEN_4K_RESOLUTIONS;
      default: return GOOGLE_GEN_1K_RESOLUTIONS;
    }
  }

  // 通义提供商
  if (modelId?.includes('z-image-turbo')) {
    switch (tier) {
      case '1K': return Z_IMAGE_1K_RESOLUTIONS;
      case '1.25K': return Z_IMAGE_1280_RESOLUTIONS;
      case '1.5K': return Z_IMAGE_1536_RESOLUTIONS;
      case '2K': return Z_IMAGE_2K_RESOLUTIONS;
      default: return Z_IMAGE_1280_RESOLUTIONS;
    }
  }

  if (modelId?.includes('wan2.6-image')) {
    return WAN26_IMAGE_RESOLUTIONS;
  }

  // wan2.x-t2i 系列模型（默认）
  switch (tier) {
    case '1K': return WAN_T2I_1K_RESOLUTIONS;
    case '1.25K': return WAN_T2I_1280_RESOLUTIONS;
    case '1.5K': return WAN_T2I_1536_RESOLUTIONS;
    default: return WAN_T2I_1280_RESOLUTIONS;
  }
}

/**
 * 获取像素分辨率
 * @param aspectRatio 比例值，如 "1:1"
 * @param tier 分辨率档位，如 "1K"
 * @param provider 提供商，如 "tongyi" | "google"
 * @param modelId 模型ID（可选，用于通义提供商区分模型）
 * @returns 像素分辨率，如 "1280*1280"；如果找不到则返回默认值
 * 
 * @example
 * getPixelResolution('1:1', '1K', 'tongyi', 'wan2.6-t2i') // "1280*1280"
 * getPixelResolution('16:9', '2K', 'google') // "2048*1152"
 */
export function getPixelResolution(
  aspectRatio: string,
  tier: string,
  provider: 'tongyi' | 'google',
  modelId?: string
): string {
  const resolutionMap = getResolutionMap(provider, modelId, tier);
  return resolutionMap[aspectRatio] || resolutionMap['1:1'] || '1024*1024';
}

/**
 * 获取带像素分辨率的比例标签
 * @param aspectRatio 比例值，如 "1:1"
 * @param tier 分辨率档位，如 "1K"
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 标签，如 "1:1 (1280×1280)"
 * 
 * @example
 * getAspectRatioLabel('1:1', '1K', 'tongyi', 'wan2.6-t2i') // "1:1 (1280×1280)"
 * getAspectRatioLabel('16:9', '2K', 'google') // "16:9 (2048×1152)"
 */
export function getAspectRatioLabel(
  aspectRatio: string,
  tier: string,
  provider: 'tongyi' | 'google',
  modelId?: string
): string {
  const pixelRes = getPixelResolution(aspectRatio, tier, provider, modelId);
  // 将 "1280*1280" 格式转换为 "1280×1280" 格式
  const formattedRes = pixelRes.replace('*', '×');
  return `${aspectRatio} (${formattedRes})`;
}

/**
 * 获取指定提供商和模型的可用比例列表
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 比例选项数组
 * 
 * @example
 * getAvailableAspectRatios('google') // 返回 Google 支持的 10 种比例
 * getAvailableAspectRatios('tongyi', 'z-image-turbo') // 返回 z-image-turbo 支持的 11 种比例
 */
export function getAvailableAspectRatios(
  provider: 'tongyi' | 'google',
  modelId?: string
): AspectRatioOption[] {
  if (provider === 'google') {
    return GOOGLE_GEN_ASPECT_RATIOS;
  }

  // 通义提供商
  if (modelId?.includes('z-image-turbo')) {
    return Z_IMAGE_ASPECT_RATIOS;
  }

  if (modelId?.includes('wan2.6-image')) {
    return WAN26_IMAGE_ASPECT_RATIOS;
  }

  // wan2.x-t2i 系列模型（默认）
  return TONGYI_GEN_ASPECT_RATIOS;
}

/**
 * 获取指定提供商和模型的可用分辨率档位列表
 * @param provider 提供商
 * @param modelId 模型ID（可选）
 * @returns 分辨率档位选项数组
 * 
 * @example
 * getAvailableResolutionTiers('google') // 返回 [1K, 2K]
 * getAvailableResolutionTiers('tongyi', 'z-image-turbo') // 返回 [1K, 1.25K, 1.5K, 2K]
 */
export function getAvailableResolutionTiers(
  provider: 'tongyi' | 'google',
  modelId?: string
): ResolutionTierOption[] {
  if (provider === 'google') {
    return GOOGLE_GEN_RESOLUTION_TIERS;
  }

  // 通义提供商
  if (modelId?.includes('z-image-turbo')) {
    return Z_IMAGE_RESOLUTION_TIERS;
  }

  if (modelId?.includes('wan2.6-image')) {
    // wan2.6-image 只有单档位，返回空数组表示不显示档位选择器
    return [];
  }

  // wan2.x-t2i 系列模型（默认）
  return TONGYI_GEN_RESOLUTION_TIERS;
}

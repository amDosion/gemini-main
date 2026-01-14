/**
 * @deprecated MediaFactory 已废弃，请使用 UnifiedProviderClient 代替
 * 
 * 新架构: 所有 Provider 统一使用 UnifiedProviderClient，通过后端统一路由处理
 * - 图片生成: UnifiedProviderClient('google').executeMode('image-gen', ...)
 * - 图片编辑: UnifiedProviderClient('google').executeMode('image-edit', ...)
 * - 视频生成: UnifiedProviderClient('google').executeMode('video-gen', ...)
 * - 音频生成: UnifiedProviderClient('google').executeMode('audio-gen', ...)
 * - 虚拟试穿: UnifiedProviderClient('google').executeMode('virtual-try-on', ...)
 * 
 * 迁移指南:
 * - 使用 UnifiedProviderClient 代替 MediaFactory
 * - 所有功能都通过后端统一处理，无需前端直接调用 SDK
 */

import { googleMediaStrategy } from "../providers/google/media"; // 保留用于向后兼容

/**
 * MediaFactory - 已废弃
 * 
 * 所有功能应使用 UnifiedProviderClient 代替
 */
export const MediaFactory = {
    getStrategy: (providerId: string) => {
        console.warn('[MediaFactory] ⚠️ MediaFactory 已废弃，请使用 UnifiedProviderClient 代替');
        // ✅ 保留用于向后兼容，但会显示警告
        switch (providerId) {
            case 'google':
            case 'google-custom':
                return googleMediaStrategy;
            default:
                return googleMediaStrategy; 
        }
    }
};

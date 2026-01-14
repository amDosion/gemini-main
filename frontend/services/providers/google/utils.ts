/**
 * @deprecated 此文件已废弃，请使用 UnifiedProviderClient 代替
 * 
 * Google Provider Utils - 已统一到 UnifiedProviderClient
 * 
 * 新架构: 所有 Provider 统一使用 UnifiedProviderClient，通过后端统一路由处理
 * - 不再需要前端直接创建 Google SDK 客户端
 * - 所有功能都通过后端统一处理
 * 
 * 迁移指南:
 * - 使用 UnifiedProviderClient('google') 代替 createGoogleClient()
 * - 所有功能都通过后端统一处理，无需前端直接调用 Google SDK
 */

import { GoogleGenAI } from "@google/genai"; // 保留用于向后兼容

/**
 * @deprecated 使用 UnifiedProviderClient('google') 代替
 */
export function getSdkOptions(apiKey: string, baseUrl: string) {
    console.warn('[getSdkOptions] ⚠️ 此函数已废弃，请使用 UnifiedProviderClient 代替');
    const options: any = { apiKey: apiKey || process.env.API_KEY };
    let apiVersion = 'v1beta'; // Default

    // If Custom URL is provided
    if (baseUrl && baseUrl.trim()) {
        let cleanUrl = baseUrl.trim().replace(/\/$/, '');
        
        // The GoogleGenAI SDK automatically appends '/v1beta' or '/v1'.
        // We strip these suffixes if the user included them to prevent duplication.
        // We also detect the user's intent (stable v1 vs beta) based on the suffix.
        if (cleanUrl.endsWith('/v1beta')) {
             apiVersion = 'v1beta';
             cleanUrl = cleanUrl.substring(0, cleanUrl.length - '/v1beta'.length);
        } else if (cleanUrl.endsWith('/v1')) {
             apiVersion = 'v1';
             cleanUrl = cleanUrl.substring(0, cleanUrl.length - '/v1'.length);
        }
        
        // Remove trailing slash again
        cleanUrl = cleanUrl.replace(/\/$/, '');

        // If the URL is not empty after stripping, use it
        if (cleanUrl) {
            options.baseUrl = cleanUrl;
        }
    }
    
    options.apiVersion = apiVersion;
    return options;
}

/**
 * @deprecated 使用 UnifiedProviderClient('google') 代替
 */
export function createGoogleClient(apiKey: string, baseUrl: string): GoogleGenAI {
    console.warn('[createGoogleClient] ⚠️ 此函数已废弃，请使用 UnifiedProviderClient 代替');
    const options = getSdkOptions(apiKey, baseUrl);
    return new GoogleGenAI(options);
}

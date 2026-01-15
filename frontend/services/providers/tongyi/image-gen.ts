/**
 * @deprecated 此文件已废弃，请使用 UnifiedProviderClient.executeMode('image-gen', ...) 代替
 * 
 * 通义图像生成 - 使用后端统一服务
 *
 * 旧后端端点: POST /api/generate/tongyi/image
 * 新后端端点: POST /api/modes/tongyi/image-gen
 *
 * 支持的模型:
 * - Z-Image 系列: z-image-turbo, z-image, z-image-omni-base
 * - Qwen 系列: qwen-image-plus
 * - WanV2 系列: wan2.6-t2i, wan2.5-t2i-preview, wan2.2-t2i-plus, etc.
 *
 * 认证方式:
 * - 使用 JWT Token (Authorization: Bearer <token>)
 * - API Key 由后端从数据库获取（更安全）
 */

import { ImageGenerationResult } from "../interfaces";
import { ChatOptions } from "../../../types/types";
import { getAccessToken } from "../../auth";

// --- 多图片响应解析（保留用于兼容性） ---
export function parseMultipleImages(data: any): ImageGenerationResult[] {
    const results: ImageGenerationResult[] = [];

    // 主要路径: output.choices[].message.content[{image: url}]
    if (data.output?.choices && Array.isArray(data.output.choices)) {
        for (const choice of data.output.choices) {
            const content = choice?.message?.content;
            if (Array.isArray(content)) {
                for (const item of content) {
                    if (item.image) {
                        results.push({
                            url: item.image,
                            mimeType: 'image/png'
                        });
                    }
                }
            }
        }
    }

    // 备用路径: output.results[].url
    if (results.length === 0 && data.output?.results && Array.isArray(data.output.results)) {
        for (const result of data.output.results) {
            if (result.url) {
                results.push({
                    url: result.url,
                    mimeType: 'image/png'
                });
            }
        }
    }

    return results;
}

// --- Text to Image (Main Entry) ---
export async function generateDashScopeImage(
    modelId: string,
    prompt: string,
    options: ChatOptions,
    _apiKey: string,      // 已弃用 - 后端从数据库获取
    _baseUrl?: string     // 已弃用 - 后端统一处理
): Promise<ImageGenerationResult[]> {

    console.log('[Image Gen] 调用后端图像生成服务');
    console.log('[Image Gen] Model:', modelId);
    console.log('[Image Gen] Prompt:', prompt.substring(0, 50) + '...');

    // 获取 JWT Token
    const token = getAccessToken();
    if (!token) {
        throw new Error('未登录，请先登录后再使用图像生成功能');
    }

    // 构建请求体
    const requestBody = {
        model_id: modelId,
        prompt: prompt,
        aspect_ratio: options.imageAspectRatio || '1:1',
        resolution: options.imageResolution || '1.25K',
        num_images: Math.min(Math.max(options.numberOfImages || 1, 1), 4),
        negative_prompt: options.negativePrompt || undefined,
        seed: (options.seed && options.seed > -1) ? options.seed : undefined,
        style: options.imageStyle || undefined
    };

    console.log('[Image Gen] 请求参数:', JSON.stringify(requestBody, null, 2));

    try {
        const response = await fetch('/api/generate/tongyi/image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('[Image Gen] 后端错误:', errorText);

            // 解析错误信息
            let errorMessage = '图像生成失败';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }

            // 特殊处理 401 未认证错误
            if (response.status === 401) {
                throw new Error(
                    '认证失败，请重新登录\n\n' +
                    `技术详情: ${errorMessage}`
                );
            }

            // 特殊处理 403 权限错误
            if (response.status === 403 || errorMessage.includes('403')) {
                throw new Error(
                    '当前 API Key 无法使用图像生成功能\n\n' +
                    '可能的原因:\n' +
                    '1. API Key 未开通图像生成权限\n' +
                    '2. 账户余额不足\n' +
                    '3. 模型未在阿里云控制台开通\n\n' +
                    '解决方法:\n' +
                    '1. 登录阿里云控制台: https://dashscope.console.aliyun.com/\n' +
                    '2. 检查账户余额和权限\n' +
                    '3. 开通对应的图像生成模型\n\n' +
                    `技术详情: ${errorMessage}`
                );
            }

            throw new Error(errorMessage);
        }

        const result = await response.json();
        console.log('[Image Gen] 后端响应:', JSON.stringify(result, null, 2));

        if (!result.success) {
            throw new Error(result.error || '图像生成失败');
        }

        if (!result.images || result.images.length === 0) {
            throw new Error('图像生成成功但未返回图片');
        }

        // 转换响应格式
        const images: ImageGenerationResult[] = result.images.map((img: any) => ({
            url: img.url,
            mimeType: img.mime_type || 'image/png'
        }));

        console.log(`[Image Gen] ✅ 生成成功: ${images.length} 张图片`);

        return images;

    } catch (error: any) {
        console.error('[Image Gen] ❌ 生成失败:', error);

        // 如果是我们自己抛出的错误，直接重新抛出
        if (error.message?.includes('API Key') || error.message?.includes('认证')) {
            throw error;
        }

        // 网络错误
        if (error.message?.includes('Failed to fetch') || error.message?.includes('NetworkError')) {
            throw new Error(
                '无法连接到后端服务\n\n' +
                '请确保:\n' +
                '1. 后端服务正在运行\n' +
                '2. 网络连接正常\n\n' +
                `技术详情: ${error.message}`
            );
        }

        // 其他错误
        throw new Error(`图像生成失败: ${error.message || '未知错误'}`);
    }
}

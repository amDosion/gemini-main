/**
 * @deprecated 此文件已废弃，请使用 UnifiedProviderClient.executeMode('image-edit', ...) 代替
 * 
 * 通义图片编辑 - 使用后端统一服务
 *
 * 旧后端端点: POST /api/generate/tongyi/image/edit
 * 新后端端点: POST /api/modes/tongyi/image-edit
 *
 * 认证方式:
 * - 使用 JWT Token (Authorization: Bearer <token>)
 * - API Key 由后端从数据库获取（更安全）
 *
 * 支持的模型:
 * - qwen-image-edit-plus (及其变体)
 * - wan2.6-image (推荐)
 * - wan2.5-i2i-preview (向后兼容)
 *
 * 图片输入支持:
 * - HTTPS URL: 后端自动下载并上传到 OSS
 * - oss:// URL: 后端直接使用
 * - Base64 data URI: 后端解码并上传到 OSS
 */

import { ImageGenerationResult } from "../interfaces";
import { Attachment, ChatOptions } from "../../../types/types";
import { QWEN_EDIT_RESOLUTIONS, WAN_EDIT_RESOLUTIONS } from "../../../controls";
import { getAccessToken } from "../../auth";

export async function editWanxImage(
    modelId: string,
    prompt: string,
    referenceImage: Attachment,
    options: ChatOptions,
    _apiKey?: string,      // 已弃用 - 后端从数据库获取
    _baseUrl?: string      // 已弃用 - 后端统一处理
): Promise<ImageGenerationResult> {

    console.log('[Image Edit] 调用后端图像编辑服务');
    console.log('[Image Edit] Model:', modelId);
    console.log('[Image Edit] Reference Image URL:', referenceImage.url?.substring(0, 60));

    // 获取 JWT Token
    const token = getAccessToken();
    if (!token) {
        throw new Error('未登录，请先登录后再使用图像编辑功能');
    }

    // 根据模型类型计算分辨率
    const isQwen = modelId.startsWith('qwen-');
    const isWan = modelId.startsWith('wan');

    const aspectRatio = options.imageAspectRatio || '1:1';
    let size: string;

    if (isQwen) {
        size = QWEN_EDIT_RESOLUTIONS[aspectRatio] || QWEN_EDIT_RESOLUTIONS['1:1'];
        console.log('[Image Edit] Qwen 模型 - Aspect Ratio:', aspectRatio, '→ Size:', size);
    } else if (isWan) {
        size = WAN_EDIT_RESOLUTIONS[aspectRatio] || WAN_EDIT_RESOLUTIONS['1:1'];
        console.log('[Image Edit] Wan 模型 - Aspect Ratio:', aspectRatio, '→ Size:', size);
    } else {
        // 默认使用 Wan 分辨率
        size = WAN_EDIT_RESOLUTIONS[aspectRatio] || WAN_EDIT_RESOLUTIONS['1:1'];
        console.log('[Image Edit] 未知模型，使用 Wan 默认分辨率 - Aspect Ratio:', aspectRatio, '→ Size:', size);
    }

    // 构建请求体（不再包含 api_key）
    const requestBody = {
        model: modelId,
        prompt: prompt,
        reference_image: {
            url: referenceImage.url || '',
            file_name: referenceImage.name || 'image.png'
        },
        options: {
            n: Math.min(Math.max(options.numberOfImages || 1, 1), 6),
            negative_prompt: options.negativePrompt || undefined,
            size: size,
            watermark: false,
            prompt_extend: true
        }
    };

    try {
        console.log('[Image Edit] 发送请求到后端...');

        const response = await fetch('/api/generate/tongyi/image/edit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('[Image Edit] 后端错误:', errorText);

            // 解析错误信息
            let errorMessage = '图像编辑失败';
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
                    '当前 API Key 无法使用图片编辑功能\n\n' +
                    '可能的原因:\n' +
                    '1. API Key 未开通图片编辑权限\n' +
                    '2. 账户余额不足\n' +
                    '3. 模型未在阿里云控制台开通\n\n' +
                    '解决方法:\n' +
                    '1. 登录阿里云控制台: https://dashscope.console.aliyun.com/\n' +
                    '2. 检查账户余额和权限\n' +
                    '3. 开通对应的图片编辑模型\n\n' +
                    `技术详情: ${errorMessage}`
                );
            }

            throw new Error(errorMessage);
        }

        const result = await response.json();

        console.log('[Image Edit] 编辑成功:', result.url?.substring(0, 60));

        return {
            url: result.url,
            mimeType: result.mime_type || 'image/png'
        };

    } catch (error: any) {
        console.error('[Image Edit] 编辑失败:', error);

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
        throw new Error(`图像编辑失败: ${error.message || '未知错误'}`);
    }
}

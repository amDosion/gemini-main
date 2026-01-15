/**
 * @deprecated 此文件已废弃，请使用 UnifiedProviderClient.executeMode('image-outpainting', ...) 代替
 * 
 * 通义图像扩展 (Out-Painting) - 使用后端统一服务
 *
 * 旧后端端点: POST /api/generate/tongyi/outpaint
 * 新后端端点: POST /api/modes/tongyi/image-outpainting
 *
 * 认证方式:
 * - 使用 JWT Token (Authorization: Bearer <token>)
 * - API Key 由后端从数据库获取（更安全）
 *
 * 支持模式: 'pixel' (offset), 'scale', 'ratio'
 */

import { ImageGenerationResult } from "../interfaces";
import { Attachment, ChatOptions } from "../../../types/types";
import { getAccessToken } from "../../auth";

export async function outPaintWanxImage(
    referenceImage: Attachment,
    options: ChatOptions,
    _apiKey?: string,      // 已弃用 - 后端从数据库获取
    _baseUrl?: string      // 已弃用 - 后端统一处理
): Promise<ImageGenerationResult> {

    console.log('[OutPainting] 调用后端扩图服务');

    // 获取 JWT Token
    const token = getAccessToken();
    if (!token) {
        throw new Error('未登录，请先登录后再使用扩图功能');
    }

    // 准备参数
    const opts = options.outPainting || {
        mode: 'scale',
        xScale: 2.0,
        yScale: 2.0,
        bestQuality: true,
        limitImageSize: true
    };

    // 构建后端请求参数（不再包含 api_key）
    const requestBody: any = {
        // 传递图片 URL，后端会处理 OSS 上传
        image_url: referenceImage.url || '',
        mode: opts.mode || 'scale'
    };

    // 根据模式添加对应参数
    if (opts.mode === 'offset' || (opts.mode as string) === 'pixel') {
        requestBody.mode = 'offset';
        requestBody.left_offset = opts.leftOffset || 0;
        requestBody.right_offset = opts.rightOffset || 0;
        requestBody.top_offset = opts.topOffset || 0;
        requestBody.bottom_offset = opts.bottomOffset || 0;
    } else if (opts.mode === 'ratio') {
        requestBody.mode = 'ratio';
        requestBody.angle = opts.angle || 0;
        requestBody.output_ratio = opts.outputRatio || "16:9";
    } else {
        requestBody.mode = 'scale';
        requestBody.x_scale = opts.xScale || 2.0;
        requestBody.y_scale = opts.yScale || 2.0;
    }

    console.log('[OutPainting] 参数:', requestBody);

    try {
        const response = await fetch('/api/generate/tongyi/outpaint', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errText = await response.text();
            let errorDetail = errText;
            try {
                const errJson = JSON.parse(errText);
                errorDetail = errJson.detail || errJson.error || errText;
            } catch {}

            // 特殊处理 401 未认证错误
            if (response.status === 401) {
                throw new Error(`认证失败，请重新登录\n\n技术详情: ${errorDetail}`);
            }

            throw new Error(`扩图服务错误 (${response.status}): ${errorDetail}`);
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(`扩图失败: ${result.error || '未知错误'}`);
        }

        if (!result.output_url) {
            throw new Error("扩图成功但未返回结果图片 URL");
        }

        console.log('[OutPainting] 扩图成功:', result.output_url.substring(0, 60));

        return {
            url: result.output_url,
            mimeType: 'image/png'
        };

    } catch (error: any) {
        console.error('[OutPainting] 扩图失败:', error);

        if (error.message?.includes('认证')) {
            throw error;
        }

        if (error.message?.includes('Failed to fetch') || error.message?.includes('NetworkError')) {
            throw new Error(
                '无法连接到后端服务\n\n' +
                '请确保后端服务正在运行\n\n' +
                `技术详情: ${error.message}`
            );
        }

        throw error;
    }
}


import { ImageGenerationResult } from "../interfaces";
import { Attachment, ChatOptions } from "../../../types/types";
import { ensureRemoteUrl } from "./image-utils";

/**
 * Implementation of DashScope Out-Painting (Expansion).
 * 
 * ✅ 优化：通过后端服务调用 DashScope API
 * 解决了前端代理转发时 X-DashScope-OssResourceResolve 头无法正确传递的问题
 * 
 * Supports modes: 'pixel' (offset), 'scale', and 'ratio'.
 */
export async function outPaintWanxImage(
    referenceImage: Attachment,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult> {
    
    // 1. 获取图片 URL
    // 如果是云存储 URL，直接使用；如果是 Base64/Blob，上传到 DashScope OSS
    const imageUrl = await ensureRemoteUrl(referenceImage, apiKey, baseUrl);

    // 2. 准备参数
    const opts = options.outPainting || {
        mode: 'scale',
        xScale: 2.0,
        yScale: 2.0,
        bestQuality: true,
        limitImageSize: true
    };

    // 3. 构建后端请求参数
    // 注意：best_quality、limit_image_size、add_watermark 由后端硬编码，前端不传递
    const requestBody: any = {
        image_url: imageUrl,
        api_key: apiKey,
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

    console.log('[OutPainting] 调用后端扩图服务:', imageUrl.substring(0, 60));
    console.log('[OutPainting] 参数:', requestBody);

    // 4. 调用后端扩图接口
    const response = await fetch('/api/image/out-painting', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
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
}

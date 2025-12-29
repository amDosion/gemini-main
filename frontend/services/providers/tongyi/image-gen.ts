
import { ImageGenerationResult } from "../interfaces";
import { ChatOptions } from "../../../types/types";
import { resolveDashUrl } from "./api";
import { 
    QWEN_EDIT_RESOLUTIONS,
    getPixelResolution
} from "../../../controls/constants";

// --- RESOLUTION MAPPING LOGIC ---

// Qwen-Image-Plus 分辨率（固定的5种）
function getQwenResolution(aspectRatio: string): string {
    return QWEN_EDIT_RESOLUTIONS[aspectRatio] || QWEN_EDIT_RESOLUTIONS['1:1'];
}

// 万相 V2 系列文生图分辨率 (wan2.x-t2i / wanx2.x-t2i)
// 使用 constants.ts 中的 getPixelResolution 函数
function getWanV2Resolution(aspectRatio: string, resolution: string = '1K', modelId?: string): string {
    return getPixelResolution(aspectRatio, resolution, 'tongyi', modelId);
}

// Z-Image 分辨率（使用 constants.ts 中的映射）
function getZImageResolution(aspectRatio: string, resolution: string = '1K', modelId?: string): string {
    return getPixelResolution(aspectRatio, resolution, 'tongyi', modelId || 'z-image-turbo');
}

// 判断是否为万相 V2 系列文生图模型 (wan2.x-t2i / wanx2.x-t2i)
// 文生图模型必须包含 "-t2i" 后缀
function isWanV2T2IModel(modelId: string): boolean {
    // 文生图模型必须包含 "-t2i" 后缀
    // 例如: wan2.6-t2i, wan2.5-t2i-preview, wan2.2-t2i-plus, wan2.2-t2i-flash
    //       wanx2.1-t2i-plus, wanx2.1-t2i-turbo, wanx2.0-t2i-turbo
    return modelId.includes('-t2i');
}

// 判断是否为 wan2.6-image 模型（仅支持图像编辑模式）
// 注意：wan2.6-image 的纯文生图模式需要 enable_interleave=true + 流式输出
// 由于流式输出的复杂性，当前仅在 image-edit 模式下支持此模型
// 如需纯文生图，请使用 wan2.x-t2i 系列模型
function isWan26ImageModel(modelId: string): boolean {
    return modelId === 'wan2.6-image';
}

// --- 多图片响应解析 ---
// 解析 DashScope API 响应中的多张图片
// 响应格式: output.choices[].message.content[{image: url}]
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
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult[]> {
    
    // Detect Model Type
    const isZImage = modelId.startsWith('z-image');
    const isQwen = modelId.includes('qwen');
    const isWanV2T2I = isWanV2T2IModel(modelId); // 万相 V2 系列文生图模型 (wan2.x-t2i / wanx2.x-t2i)
    const isWan26Image = isWan26ImageModel(modelId); // wan2.6-image 模型

    // --- Z-Image 系列 (使用 multimodal-generation 端点) ---
    if (isZImage) {
        return generateZImage(modelId, prompt, options, apiKey, baseUrl);
    }

    // --- wan2.6-image 模型 ---
    // 注意：wan2.6-image 在纯文生图模式下需要 enable_interleave=true + 流式输出
    // 当前实现不支持流式输出，因此 wan2.6-image 不应出现在 image-gen 模式中
    // 如果用户选择了此模型，抛出友好的错误提示
    if (isWan26Image) {
        throw new Error(
            'wan2.6-image 模型的纯文生图模式需要流式输出，当前暂不支持。\n' +
            '请使用以下替代方案：\n' +
            '- 文生图：使用 wan2.6-t2i 或其他 -t2i 系列模型\n' +
            '- 图像编辑：在 image-edit 模式下使用 wan2.6-image'
        );
    }

    // --- 万相 V2 系列文生图模型 (wan2.x-t2i / wanx2.x-t2i，使用 multimodal-generation 端点) ---
    // 这些模型必须包含 "-t2i" 后缀
    if (isWanV2T2I) {
        return generateWanV2Image(modelId, prompt, options, apiKey, baseUrl);
    }

    // --- Qwen-Image-Plus ---
    if (isQwen) {
        return generateQwenImage(modelId, prompt, options, apiKey, baseUrl);
    }
    
    // 不支持的模型
    throw new Error(`不支持的图像生成模型: ${modelId}。请使用 wan2.x-t2i 系列模型。`);
}

// --- Qwen-Image-Plus 专用生成函数 ---
async function generateQwenImage(
    modelId: string,
    prompt: string,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult[]> {
    
    const size = getQwenResolution(options.imageAspectRatio);
    const n = Math.min(Math.max(options.numberOfImages || 1, 1), 4);
    
    // Qwen-Image 使用 messages 格式
    const payload: any = {
        model: modelId,
        input: {
            messages: [{
                role: "user",
                content: [{ text: prompt }]
            }]
        },
        parameters: {
            size: size,
            n: n,
            prompt_extend: true,
            watermark: false
        }
    };
    
    if (options.negativePrompt) {
        payload.parameters.negative_prompt = options.negativePrompt;
    }
    
    console.log('[Qwen-Image] 请求参数:', JSON.stringify(payload, null, 2));
    
    const url = resolveDashUrl(baseUrl || '', 'image-generation', modelId);
    console.log('[Qwen-Image] 使用端点:', url);
    
    // 使用同步调用（与 Z-Image 相同的响应格式）
    const result = await submitQwenImageSync(url, payload, apiKey);
    
    return [result];
}

// --- Qwen-Image 同步调用 ---
async function submitQwenImageSync(
    endpoint: string,
    payload: any,
    apiKey: string
): Promise<ImageGenerationResult> {
    const safeKey = apiKey.trim();
    if (!safeKey) throw new Error("DashScope API Key is empty.");

    console.log('[Qwen-Image] 使用同步模式调用 API');

    const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${safeKey}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({ message: response.statusText }));
        const msg = err.message || err.code || response.status;
        console.error('[Qwen-Image] API 错误:', err);
        throw new Error(`Qwen-Image API Error: ${msg}`);
    }

    const data = await response.json();
    console.log('[Qwen-Image] API 响应:', JSON.stringify(data, null, 2));
    
    // 响应格式: output.choices[0].message.content[{image: url}]
    let resultUrl = null;
    
    if (data.output?.choices && data.output.choices.length > 0) {
        const content = data.output.choices[0]?.message?.content;
        if (Array.isArray(content)) {
            for (const item of content) {
                if (item.image) {
                    resultUrl = item.image;
                    break;
                }
            }
        }
    }
    
    // 备用路径
    if (!resultUrl && data.output?.results?.[0]?.url) {
        resultUrl = data.output.results[0].url;
    }
    
    if (!resultUrl) {
        console.error('[Qwen-Image] 未找到图片 URL，完整响应:', data);
        throw new Error("Qwen-Image API 返回成功但未找到图片 URL");
    }
    
    console.log('[Qwen-Image] ✅ 生成成功:', resultUrl.substring(0, 60));
    
    return {
        url: resultUrl,
        mimeType: 'image/png'
    };
}

// --- Z-Image 专用生成函数 ---
async function generateZImage(
    modelId: string,
    prompt: string,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult[]> {
    
    const size = getZImageResolution(options.imageAspectRatio, options.imageResolution, modelId);
    // z-image-turbo 只支持 1 张图片
    const maxN = modelId === 'z-image-turbo' ? 1 : 4;
    const n = Math.min(Math.max(options.numberOfImages || 1, 1), maxN);
    
    // Z-Image 使用 messages 格式（类似聊天）
    const payload: any = {
        model: modelId,
        input: {
            messages: [{
                role: "user",
                content: [{ text: prompt }]
            }]
        },
        parameters: {
            size: size,
            n: n
        }
    };
    
    // 可选参数
    if (options.negativePrompt) {
        payload.parameters.negative_prompt = options.negativePrompt;
    }
    if (options.seed && options.seed > -1) {
        payload.parameters.seed = options.seed;
    }
    
    console.log('[Z-Image] 请求参数:', JSON.stringify(payload, null, 2));
    
    // 获取正确的端点 (multimodal-generation)
    const url = resolveDashUrl(baseUrl || '', 'image-generation', modelId);
    console.log('[Z-Image] 使用端点:', url);
    
    // Z-Image 支持同步调用，返回多张图片
    const results = await submitZImageSync(url, payload, apiKey, n);
    
    return results;
}

// --- 万相 V2 系列专用生成函数 (wan2.x-t2i / wanx2.x-t2i) ---
// 根据官方文档，wan2.6-t2i 等模型使用 multimodal-generation 端点，HTTP 同步调用
async function generateWanV2Image(
    modelId: string,
    prompt: string,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
): Promise<ImageGenerationResult[]> {
    
    const size = getWanV2Resolution(options.imageAspectRatio, options.imageResolution, modelId);
    const n = Math.min(Math.max(options.numberOfImages || 1, 1), 4);
    
    // 万相 V2 系列使用 messages 格式（与官方 curl 示例一致）
    const payload: any = {
        model: modelId,
        input: {
            messages: [{
                role: "user",
                content: [{ text: prompt }]
            }]
        },
        parameters: {
            size: size,
            n: n,
            prompt_extend: true,  // 启用提示词扩展
            watermark: false      // 关闭水印
        }
    };
    
    // 可选参数
    if (options.negativePrompt) {
        payload.parameters.negative_prompt = options.negativePrompt;
    }
    if (options.seed && options.seed > -1) {
        payload.parameters.seed = options.seed;
    }
    
    console.log('[WanV2-T2I] 请求参数:', JSON.stringify(payload, null, 2));
    
    // 获取正确的端点 (multimodal-generation/generation)
    const url = resolveDashUrl(baseUrl || '', 'image-generation', modelId);
    console.log('[WanV2-T2I] 使用端点:', url);
    
    // 万相 V2 系列文生图模型使用同步调用，返回多张图片
    const results = await submitWanV2T2ISync(url, payload, apiKey, n);
    
    return results;
}

// --- 万相 V2 系列文生图同步调用 ---
// 响应格式: output.choices[].message.content[{image: url}]
async function submitWanV2T2ISync(
    endpoint: string,
    payload: any,
    apiKey: string,
    expectedCount: number = 1
): Promise<ImageGenerationResult[]> {
    const safeKey = apiKey.trim();
    if (!safeKey) throw new Error("DashScope API Key is empty.");

    console.log('[WanV2-T2I] 使用同步模式调用 API');

    const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${safeKey}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({ message: response.statusText }));
        const msg = err.message || err.code || response.status;
        console.error('[WanV2-T2I] API 错误:', err);
        throw new Error(`WanV2-T2I API Error: ${msg}`);
    }

    const data = await response.json();
    console.log('[WanV2-T2I] API 响应:', JSON.stringify(data, null, 2));
    
    // 使用统一的多图片解析函数
    const results = parseMultipleImages(data);
    
    if (results.length === 0) {
        console.error('[WanV2-T2I] 未找到图片 URL，完整响应:', data);
        throw new Error("WanV2-T2I API 返回成功但未找到图片 URL");
    }
    
    console.log(`[WanV2-T2I] ✅ 生成成功: ${results.length}/${expectedCount} 张图片`);
    
    return results;
}

// --- Z-Image 同步调用 ---
async function submitZImageSync(
    endpoint: string,
    payload: any,
    apiKey: string,
    expectedCount: number = 1
): Promise<ImageGenerationResult[]> {
    const safeKey = apiKey.trim();
    if (!safeKey) throw new Error("DashScope API Key is empty.");

    console.log('[Z-Image] 使用同步模式调用 API');

    const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${safeKey}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({ message: response.statusText }));
        const msg = err.message || err.code || response.status;
        console.error('[Z-Image] API 错误:', err);
        throw new Error(`Z-Image API Error: ${msg}`);
    }

    const data = await response.json();
    console.log('[Z-Image] API 响应:', JSON.stringify(data, null, 2));
    
    // 使用统一的多图片解析函数
    const results = parseMultipleImages(data);
    
    if (results.length === 0) {
        console.error('[Z-Image] 未找到图片 URL，完整响应:', data);
        throw new Error("Z-Image API 返回成功但未找到图片 URL");
    }
    
    console.log(`[Z-Image] ✅ 生成成功: ${results.length}/${expectedCount} 张图片`);
    
    return results;
}

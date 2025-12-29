
import { ImageGenerationResult } from "../interfaces";

// --- Constants (Defaults) ---
export const DEFAULT_DASH_BASE = "/api/dashscope"; 

/**
 * Dynamic Router for DashScope Services.
 * Returns the specific API endpoint based on the Model ID and Task Type.
 */
export function resolveDashUrl(baseUrl: string, endpointType: 'generation' | 'task' | 'file' | 'image-generation' | 'image-edit' | 'out-painting', modelId?: string): string {
    let root = baseUrl || DEFAULT_DASH_BASE;
    
    // Heuristic: If the user provided the OpenAI-compatible endpoint, strip the suffix to find the root.
    if (root.includes('/compatible-mode/v1')) {
        root = root.split('/compatible-mode/v1')[0];
    }
    if (root.endsWith('/v1')) {
        root = root.slice(0, -3);
    }
    root = root.replace(/\/$/, '');

    // CORS POLICY FIX:
    // Browser cannot call dashscope.aliyuncs.com directly due to CORS.
    // If the root is the official domain, switch to the local proxy path defined in vite.config.ts.
    // This assumes the app is running with a backend/proxy capable of forwarding /api/dashscope requests.
    if (root.includes('dashscope.aliyuncs.com')) {
        // console.debug('[DashScope] Detected official URL in browser. Switching to proxy:', DEFAULT_DASH_BASE);
        root = DEFAULT_DASH_BASE;
    }

    // --- Task & Model Routing Logic ---
    
    // 1. Files & Tasks (Common)
    if (endpointType === 'task') return `${root}/api/v1/tasks`;
    if (endpointType === 'file') return `${root}/api/v1/files`;

    // 2. Text Generation (Chat)
    if (endpointType === 'generation') {
        return `${root}/api/v1/services/aigc/text-generation/generation`;
    }

    // 3. Image Generation (Text-to-Image)
    // 根据官方文档，所有文生图模型都使用 multimodal-generation 端点
    // - Z-Image 系列: z-image-turbo, z-image, z-image-omni-base
    // - 万相 V2 系列: wan2.6-t2i, wan2.5-t2i-preview, wan2.2-t2i-plus 等
    // - Qwen-Image: qwen-image-plus
    if (endpointType === 'image-generation') {
        return `${root}/api/v1/services/aigc/multimodal-generation/generation`;
    }

    // 4. Image Editing (Inpainting/Repainting)
    if (endpointType === 'image-edit') {
        // 所有图片编辑模型都使用统一的 multimodal-generation 端点
        // 支持的模型：qwen-image-edit-plus, wan2.6-image 等
        return `${root}/api/v1/services/aigc/multimodal-generation/generation`;
    }

    // 5. Out-Painting
    if (endpointType === 'out-painting') {
        return `${root}/api/v1/services/aigc/image2image/out-painting`;
    }

    return root;
}

// --- File Upload (Backend Proxy Required in Browser) ---
export async function uploadDashScopeFile(file: File, apiKey: string, baseUrl?: string): Promise<string> {
    console.log('[DashScope Upload] Starting upload process...');
    console.log('[DashScope Upload] File:', file.name, 'Size:', file.size, 'bytes');
    
    // In browser environment, we MUST use backend proxy due to CORS restrictions
    // The proxy URL is always: /api/dashscope/api/v1/files (defined in vite.config.ts)
    const proxyUrl = `${DEFAULT_DASH_BASE}/api/v1/files`;
    
    console.log('[DashScope Upload] Using backend proxy...');
    console.log('[DashScope Upload] Proxy URL:', proxyUrl);
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('purpose', 'image-out-painting');
        
        const response = await fetch(proxyUrl, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${apiKey}`
            },
            body: formData,
            signal: AbortSignal.timeout(30000) // 30 second timeout for large files
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('[DashScope Upload] Backend proxy error:', errorText);
            throw new Error(`Backend proxy failed (${response.status}): ${errorText}`);
        }
        
        const data = await response.json();
        const ossUrl = data.data?.url;
        
        if (!ossUrl) {
            console.error('[DashScope Upload] No URL in response:', data);
            throw new Error('Backend proxy returned no OSS URL');
        }
        
        console.log('[DashScope Upload] ✅ Upload successful!');
        console.log('[DashScope Upload] OSS URL:', ossUrl);
        
        return ossUrl;
        
    } catch (e: any) {
        console.error('[DashScope Upload] ❌ Upload failed:', e);
        
        // Provide helpful error message
        if (e.message?.includes('Failed to fetch') || e.message?.includes('NetworkError')) {
            throw new Error(
                '无法连接到后端服务器。\n\n' +
                '请确保后端服务器正在运行：\n' +
                'cd backend && python -m uvicorn app.main:app --reload --port 8000\n\n' +
                '技术说明：浏览器环境中，DashScope API 调用必须通过后端代理，\n' +
                '因为 DashScope API 不支持跨域访问（CORS）。'
            );
        }
        
        throw new Error(`上传失败: ${e.message}`);
    }
}

// --- Sync Submit (同步调用) ---
// multimodal-generation API 默认支持同步调用（根据官方 curl 示例）
// 不需要添加 X-DashScope-Async 请求头
export async function submitSync(endpoint: string, payload: any, apiKey: string): Promise<ImageGenerationResult> {
    const safeKey = apiKey.trim();
    if (!safeKey) throw new Error("DashScope API Key is empty.");

    console.log('[DashScope] 使用同步模式调用 API');

    // 同步调用（不添加 X-DashScope-Async 请求头）
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${safeKey}`,
            'Content-Type': 'application/json',
            'X-DashScope-OssResourceResolve': 'enable' // 允许访问外部 URL
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({ message: response.statusText }));
        const msg = err.message || err.code || response.status;
        throw new Error(`DashScope API Error: ${msg}`);
    }

    const data = await response.json();
    
    // 详细日志：打印完整响应结构
    console.log('[DashScope] 同步调用响应:', JSON.stringify(data, null, 2));
    
    // 同步模式下，结果可能在多个不同的字段中
    let resultUrl = null;
    
    // 尝试各种可能的字段路径
    if (data.output) {
        // 1. output.results[0].url (常见格式)
        if (data.output.results && Array.isArray(data.output.results) && data.output.results.length > 0) {
            resultUrl = data.output.results[0].url;
        }
        // 2. output.url (简化格式)
        if (!resultUrl && data.output.url) {
            resultUrl = data.output.url;
        }
        // 3. output.output_image_url (某些模型)
        if (!resultUrl && data.output.output_image_url) {
            resultUrl = data.output.output_image_url;
        }
        // 4. output.data.image_url (Wan2.6 格式)
        if (!resultUrl && data.output.data) {
            if (Array.isArray(data.output.data.image_url)) {
                resultUrl = data.output.data.image_url[0];
            } else if (data.output.data.image_url) {
                resultUrl = data.output.data.image_url;
            }
        }
        // 5. output.task_id (如果返回的是异步任务)
        if (!resultUrl && data.output.task_id) {
            console.warn('[DashScope] API 返回了 task_id，可能需要异步轮询');
            throw new Error('API 返回了异步任务 ID，但当前使用的是同步模式。请检查 API 配置。');
        }
    }
    
    if (!resultUrl) {
        console.error('[DashScope] 同步调用成功但未找到图片 URL');
        console.error('[DashScope] 完整响应:', data);
        throw new Error("API 返回成功但未找到图片 URL");
    }
    
    console.log('[DashScope] 同步调用成功，图片 URL:', resultUrl.substring(0, 60));
    
    return {
        url: resultUrl,
        mimeType: 'image/png'
    };
}

// --- Async Task Polling ---
export async function submitAndPoll(endpoint: string, payload: any, apiKey: string): Promise<ImageGenerationResult> {
    const safeKey = apiKey.trim();
    if (!safeKey) throw new Error("DashScope API Key is empty.");

    // 1. Submit Task (Asynchronous)
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${safeKey}`,
            'Content-Type': 'application/json',
            'X-DashScope-Async': 'enable',
            'X-DashScope-OssResourceResolve': 'enable' // 允许访问外部 URL
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({ message: response.statusText }));
        const msg = err.message || err.code || response.status;
        throw new Error(`DashScope API Error: ${msg}`);
    }

    const data = await response.json();
    const taskId = data.output?.task_id;
    if (!taskId) throw new Error("No task_id returned from DashScope. Ensure X-DashScope-Async is enabled.");

    // 2. Poll Status
    let taskBase = '';
    // Construct task URL relative to the endpoint used (handling proxies)
    const apiV1Index = endpoint.indexOf('/api/v1/');
    if (apiV1Index !== -1) {
        taskBase = endpoint.substring(0, apiV1Index) + '/api/v1/tasks';
    } else {
        taskBase = '/api/dashscope/api/v1/tasks'; 
    }

    const maxRetries = 100; // ~5 minutes timeout
    let attempts = 0;

    while (attempts < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        attempts++;

        try {
            const taskResp = await fetch(`${taskBase}/${taskId}`, {
                headers: { 'Authorization': `Bearer ${safeKey}` }
            });

            if (!taskResp.ok) continue;

            const taskData = await taskResp.json();
            const status = taskData.output?.task_status;

            if (status === 'SUCCEEDED') {
                let resultUrl = taskData.output?.output_image_url;
                
                // Wanx V2 sometimes returns data in results array
                if (!resultUrl && taskData.output?.results) {
                    resultUrl = taskData.output.results[0]?.url;
                }
                // Generic fallback
                if (!resultUrl && taskData.output?.url) {
                    resultUrl = taskData.output.url;
                }
                // Wanx V2.5 Edit sometimes returns data.image_url array
                if (!resultUrl && taskData.output?.data?.image_url) {
                     resultUrl = Array.isArray(taskData.output.data.image_url) ? taskData.output.data.image_url[0] : taskData.output.data.image_url;
                }
                
                if (!resultUrl) {
                    console.error("Task Succeeded but URL missing:", taskData);
                    throw new Error("Task succeeded but no image URL found in response.");
                }
                
                return {
                    url: resultUrl,
                    mimeType: 'image/png'
                };
            } else if (status === 'FAILED') {
                throw new Error(`DashScope Task Failed: ${taskData.output?.message || taskData.output?.code || 'Unknown error'}`);
            }
        } catch (pollErr: any) {
            console.warn("Polling error:", pollErr);
            if (attempts > 5 && pollErr.message?.includes('Failed to fetch')) throw pollErr;
        }
    }
    throw new Error("Task timed out");
}

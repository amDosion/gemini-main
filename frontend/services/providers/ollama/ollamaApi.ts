/**
 * Ollama 模型管理 API 服务
 * 
 * 提供与后端 /api/ollama/* 端点的通信功能
 */
import type {
    OllamaModel,
    OllamaModelInfo,
    OllamaModelsResponse,
    DeleteModelResponse,
    PullProgress
} from '../../../types/ollama';

const API_BASE = '/api/ollama';

/**
 * 构建带查询参数的 URL
 */
function buildUrl(path: string, baseUrl: string, apiKey?: string): string {
    const url = new URL(`${API_BASE}${path}`, window.location.origin);
    url.searchParams.set('base_url', baseUrl);
    if (apiKey) {
        url.searchParams.set('api_key', apiKey);
    }
    return url.toString();
}

/**
 * 获取本地模型列表
 */
export async function getModels(
    baseUrl: string,
    apiKey?: string
): Promise<OllamaModel[]> {
    const url = buildUrl('/models', baseUrl, apiKey);
    
    const response = await fetch(url);
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail?.error || error.detail || 'Failed to fetch models');
    }
    
    const data: OllamaModelsResponse = await response.json();
    return data.models;
}

/**
 * 获取模型详情
 */
export async function getModelInfo(
    modelName: string,
    baseUrl: string,
    apiKey?: string
): Promise<OllamaModelInfo> {
    const url = buildUrl(`/models/${encodeURIComponent(modelName)}`, baseUrl, apiKey);
    
    const response = await fetch(url);
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        if (response.status === 404) {
            throw new Error(`Model '${modelName}' not found`);
        }
        throw new Error(error.detail?.error || error.detail || 'Failed to fetch model info');
    }
    
    return response.json();
}

/**
 * 删除模型
 */
export async function deleteModel(
    modelName: string,
    baseUrl: string,
    apiKey?: string
): Promise<DeleteModelResponse> {
    const url = buildUrl(`/models/${encodeURIComponent(modelName)}`, baseUrl, apiKey);
    
    const response = await fetch(url, {
        method: 'DELETE'
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        if (response.status === 404) {
            throw new Error(`Model '${modelName}' not found`);
        }
        throw new Error(error.detail?.error || error.detail || 'Failed to delete model');
    }
    
    return response.json();
}

/**
 * 下载模型 (SSE 流式)
 * 
 * @param modelName 模型名称
 * @param baseUrl Ollama API 地址
 * @param apiKey API 密钥 (可选)
 * @param onProgress 进度回调
 * @param signal AbortSignal 用于取消下载
 */
export async function pullModel(
    modelName: string,
    baseUrl: string,
    apiKey: string | undefined,
    onProgress: (progress: PullProgress) => void,
    signal?: AbortSignal
): Promise<void> {
    const response = await fetch(`${API_BASE}/pull`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            model: modelName,
            base_url: baseUrl,
            api_key: apiKey
        }),
        signal
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail?.error || error.detail || 'Failed to start model download');
    }
    
    const reader = response.body?.getReader();
    if (!reader) {
        throw new Error('Response body is not readable');
    }
    
    const decoder = new TextDecoder();
    let buffer = '';
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // 解析 SSE 事件
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    try {
                        const progress: PullProgress = JSON.parse(data);
                        onProgress(progress);
                        
                        // 检查是否完成或出错
                        if (progress.status === 'success') {
                            return;
                        }
                        if (progress.status === 'error' || progress.error) {
                            throw new Error(progress.error || 'Download failed');
                        }
                    } catch (e) {
                        if (e instanceof SyntaxError) {
                            console.warn('Failed to parse SSE data:', data);
                        } else {
                            throw e;
                        }
                    }
                }
            }
        }
    } finally {
        reader.releaseLock();
    }
}

/**
 * 格式化文件大小
 */
export function formatSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const k = 1024;
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`;
}

/**
 * 格式化日期时间
 */
export function formatDateTime(isoString: string): string {
    const date = new Date(isoString);
    return date.toLocaleString();
}

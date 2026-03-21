/**
 * Ollama API 客户端
 * 
 * 提供与 Ollama 服务交互的函数
 */
import type { 
    OllamaModel, 
    OllamaModelInfo, 
    OllamaModelsResponse,
    PullProgress 
} from '../../../types/ollama';

/**
 * 规范化 Ollama base URL
 * 移除尾部斜杠和 /v1 后缀（Ollama 原生 API 不使用 /v1 前缀）
 */
function normalizeBaseUrl(baseUrl: string): string {
    return baseUrl.replace(/\/+$/, '').replace(/\/v1$/i, '');
}

/**
 * 获取本地模型列表
 */
export async function getModels(baseUrl: string, apiKey?: string): Promise<OllamaModel[]> {
    const url = `${normalizeBaseUrl(baseUrl)}/api/tags`;
    
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    };
    if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
    }
    
    const response = await fetch(url, { headers });
    
    if (!response.ok) {
        throw new Error(`Failed to fetch models: ${response.status} ${response.statusText}`);
    }
    
    const data: OllamaModelsResponse = await response.json();
    return data.models || [];
}

/**
 * 获取模型详细信息
 */
export async function getModelInfo(
    modelName: string, 
    baseUrl: string, 
    apiKey?: string
): Promise<OllamaModelInfo> {
    const url = `${normalizeBaseUrl(baseUrl)}/api/show`;
    
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    };
    if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
    }
    
    const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name: modelName }),
    });
    
    if (!response.ok) {
        throw new Error(`Failed to fetch model info: ${response.status} ${response.statusText}`);
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
): Promise<void> {
    const url = `${normalizeBaseUrl(baseUrl)}/api/delete`;
    
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    };
    if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
    }
    
    const response = await fetch(url, {
        method: 'DELETE',
        headers,
        body: JSON.stringify({ name: modelName }),
    });
    
    if (!response.ok) {
        throw new Error(`Failed to delete model: ${response.status} ${response.statusText}`);
    }
}

/**
 * 下载模型（流式进度）
 */
export async function pullModel(
    modelName: string,
    baseUrl: string,
    apiKey?: string,
    onProgress?: (progress: PullProgress) => void,
    signal?: AbortSignal
): Promise<void> {
    const url = `${normalizeBaseUrl(baseUrl)}/api/pull`;
    
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    };
    if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
    }
    
    const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name: modelName, stream: true }),
        signal,
    });
    
    if (!response.ok) {
        throw new Error(`Failed to pull model: ${response.status} ${response.statusText}`);
    }
    
    if (!response.body) {
        throw new Error('Response body is null');
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (!line.trim()) continue;
                
                try {
                    const progress: PullProgress = JSON.parse(line);
                    onProgress?.(progress);
                    
                    if (progress.error) {
                        throw new Error(progress.error);
                    }
                } catch (e) {
                    if (e instanceof SyntaxError) {
                    } else {
                        throw e;
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
    const size = bytes / Math.pow(k, i);
    
    return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

/**
 * 格式化日期时间
 */
export function formatDateTime(isoString: string): string {
    try {
        const date = new Date(isoString);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return isoString;
    }
}

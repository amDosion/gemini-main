/**
 * 数据库服务 - 纯后端 API 模式
 * 所有数据存储在后端数据库，通过 API 访问
 */
import { ChatSession, Persona, ModelConfig } from '../types/types';
import { StorageConfig } from '../types/storage';

export interface ConfigProfile {
    id: string;
    name: string;
    providerId: string;
    apiKey: string;
    baseUrl: string;
    protocol: string;
    isProxy: boolean;
    hiddenModels: string[];
    cachedModelCount?: number;
    savedModels?: ModelConfig[];  // 存储完整的 ModelConfig 对象数组
    createdAt: number;
    updatedAt: number;
}

const API_BASE = '/api';
const API_TIMEOUT = 15000;

/**
 * 获取访问令牌
 */
function getAccessToken(): string | null {
    return localStorage.getItem('access_token');
}

class ApiDB {
    /**
     * 发送 API 请求
     */
    public async request<T>(
        endpoint: string,
        options?: RequestInit & { timeoutMs?: number }
    ): Promise<T> {
        const { timeoutMs = API_TIMEOUT, ...fetchOptions } = options || {};
        const externalSignal = fetchOptions.signal;
        const controller = new AbortController();
        let isTimeout = false;
        
        const timeoutId = setTimeout(() => {
            isTimeout = true;
            controller.abort();
        }, timeoutMs);

        if (externalSignal) {
            externalSignal.addEventListener('abort', () => controller.abort());
        }

        // ✅ 构建请求头，添加 Authorization header
        const headers: HeadersInit = {
            ...(fetchOptions.headers || {}),
        };
        
        // ✅ 添加 Authorization header（优先使用）
        const token = getAccessToken();
        if (token) {
            (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
        }

        try {
            const res = await fetch(`${API_BASE}${endpoint}`, {
                ...fetchOptions,
                headers,
                signal: controller.signal,
                credentials: 'include' // 携带 Cookie（向后兼容）
            });
            clearTimeout(timeoutId);

            if (!res.ok) {
                const errorText = await res.text().catch(() => '');
                throw new Error(`API Error: ${res.status} ${errorText}`);
            }
            return res.json();
        } catch (error) {
            clearTimeout(timeoutId);
            
            // 处理不同类型的 abort 错误
            if (error instanceof Error && error.name === 'AbortError') {
                if (isTimeout) {
                    throw new Error(`Request timeout after ${timeoutMs}ms: ${endpoint}`);
                } else if (externalSignal?.aborted) {
                    throw new Error('Request cancelled by user');
                }
            }
            
            throw error;
        }
    }

    // ==================== Sessions ====================
    async getSessions(): Promise<ChatSession[]> {
        return this.request<ChatSession[]>('/sessions');
    }

    async saveSession(session: ChatSession): Promise<void> {
        await this.request('/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(session),
            timeoutMs: 30000
        });
    }

    async deleteSession(id: string): Promise<void> {
        await this.request(`/sessions/${id}`, { method: 'DELETE' });
    }

    // ==================== Personas ====================
    async getPersonas(): Promise<Persona[]> {
        return await this.request<Persona[]>('/personas');
    }

    async savePersonas(personas: Persona[]): Promise<void> {
        await this.request('/personas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(personas)
        });
    }

    async resetPersonas(): Promise<Persona[]> {
        // 调用重置 API
        await this.request('/personas/reset', {
            method: 'POST'
        });
        // 重置后重新获取 Personas
        return await this.getPersonas();
    }

    // ==================== Profiles ====================
    async getProfiles(editMode: boolean = false): Promise<ConfigProfile[]> {
        // ✅ editMode=true 时，后端会解密 API Key 返回（用于 EditorTab 编辑）
        // editMode=false 时，返回加密的 API Key（用于 ProfilesTab 显示）
        const url = editMode ? '/profiles?edit_mode=true' : '/profiles';
        return this.request<ConfigProfile[]>(url);
    }

    async saveProfile(profile: ConfigProfile): Promise<void> {
        // ✅ 保存完整的 ModelConfig 对象数组到数据库
        // 后端会直接存储完整对象，前端加载时可以直接使用，无需再次调用 API
        await this.request('/profiles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(profile)
        });
    }

    async deleteProfile(id: string): Promise<void> {
        await this.request(`/profiles/${id}`, { method: 'DELETE' });
    }

    async getActiveProfileId(): Promise<string | null> {
        const data = await this.request<{ id: string | null }>('/active-profile');
        return data.id;
    }

    async setActiveProfileId(id: string): Promise<void> {
        await this.request('/active-profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
    }

    // ==================== Storage Configs ====================
    async getStorageConfigs(): Promise<StorageConfig[]> {
        return this.request<StorageConfig[]>('/storage/configs');
    }

    async saveStorageConfig(config: StorageConfig): Promise<void> {
        const configs = await this.getStorageConfigs();
        const exists = configs.some(c => c.id === config.id);
        if (exists) {
            await this.request(`/storage/configs/${config.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
        } else {
            await this.request('/storage/configs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
        }
    }

    async deleteStorageConfig(id: string): Promise<void> {
        await this.request(`/storage/configs/${id}`, { method: 'DELETE' });
    }

    async getActiveStorageId(): Promise<string | null> {
        const data = await this.request<{ storageId: string | null }>('/storage/active');
        return data.storageId;
    }

    async setActiveStorageId(id: string): Promise<void> {
        await this.request(`/storage/active/${id}`, { method: 'POST' });
    }

    // ==================== Attachments ====================
    async updateAttachmentUrl(
        sessionId: string,
        messageId: string,
        attachmentId: string,
        cloudUrl: string
    ): Promise<void> {
        await this.request(
            `/sessions/${sessionId}/messages/${messageId}/attachments/${attachmentId}/url`,
            {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: cloudUrl })
            }
        );
    }
}

export const db = new ApiDB();

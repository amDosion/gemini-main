/**
 * 数据库服务 - 纯后端 API 模式
 * 所有数据存储在后端数据库，通过 API 访问
 */
import { ChatSession, Persona, ModelConfig } from '../types/types';
import {
    StorageBatchDeleteRequestItem,
    StorageBatchDeleteResult,
    StorageFileMetadataBatchResponse,
    StorageFileMetadataItem,
    StorageBrowseResponse,
    StorageConfig,
    StorageDownloadPrepareResponse,
    StorageDownloadRequestItem,
    StorageItemMutationResult,
    StorageUploadResult
} from '../types/storage';
import { fetchWithTimeout, parseHttpError, readJsonResponse } from './http';

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

export interface SessionHistoryState {
    messageId: string;
    isFavorite: boolean;
    updatedAt?: number;
}

export interface SessionHistoryPreference {
    showFavoritesOnly: boolean;
    updatedAt?: number;
}

const API_BASE = '/api';
const API_TIMEOUT = 15000;

class ApiDB {
    /**
     * 发送 API 请求
     */
    public async request<T>(
        endpoint: string,
        options?: RequestInit & { timeoutMs?: number }
    ): Promise<T> {
        const { timeoutMs = API_TIMEOUT, ...fetchOptions } = options || {};

        try {
            const res = await fetchWithTimeout(`${API_BASE}${endpoint}`, {
                ...fetchOptions,
                withAuth: true,
                timeoutMs,
                timeoutMessage: () => `Request timeout after ${timeoutMs}ms: ${endpoint}`,
                abortMessage: 'Request cancelled by user',
            });

            if (!res.ok) {
                const parsedError = await parseHttpError(res, '');
                const suffix = parsedError.message ? ` ${parsedError.message}` : '';
                throw new Error(`API Error: ${res.status}${suffix}`);
            }
            return readJsonResponse<T>(res);
        } catch (error) {
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

    async getSessionHistoryStates(sessionId: string): Promise<SessionHistoryState[]> {
        const res = await this.request<{ states?: SessionHistoryState[] }>(`/sessions/${sessionId}/history-states`);
        return Array.isArray(res?.states) ? res.states : [];
    }

    async updateSessionHistoryState(
        sessionId: string,
        messageId: string,
        payload: { isFavorite: boolean }
    ): Promise<SessionHistoryState> {
        return this.request<SessionHistoryState>(`/sessions/${sessionId}/history-states/${messageId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    }

    async getSessionHistoryPreference(sessionId: string): Promise<SessionHistoryPreference> {
        const res = await this.request<SessionHistoryPreference>(`/sessions/${sessionId}/history-preferences`);
        return {
            showFavoritesOnly: !!res?.showFavoritesOnly,
            updatedAt: res?.updatedAt
        };
    }

    async updateSessionHistoryPreference(
        sessionId: string,
        payload: { showFavoritesOnly: boolean }
    ): Promise<SessionHistoryPreference> {
        return this.request<SessionHistoryPreference>(`/sessions/${sessionId}/history-preferences`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
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
        // ✅ Query 参数使用 camelCase（中间件自动转换为 snake_case）
        const url = editMode ? '/profiles?editMode=true' : '/profiles';
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

    async browseActiveStorage(path: string = '', cursor?: string, limit: number = 200): Promise<StorageBrowseResponse> {
        const params = new URLSearchParams();
        params.set('limit', String(limit));
        if (path) {
            params.set('path', path);
        }
        if (cursor) {
            params.set('cursor', cursor);
        }
        return this.request<StorageBrowseResponse>(`/storage/active/browse?${params.toString()}`);
    }

    async browseStorage(storageId: string, path: string = '', cursor?: string, limit: number = 200): Promise<StorageBrowseResponse> {
        const params = new URLSearchParams();
        params.set('limit', String(limit));
        if (path) {
            params.set('path', path);
        }
        if (cursor) {
            params.set('cursor', cursor);
        }
        return this.request<StorageBrowseResponse>(`/storage/browse/${encodeURIComponent(storageId)}?${params.toString()}`);
    }

    async getStorageFileMetadataBatch(
        urls: string[],
        forceRefresh: boolean = false
    ): Promise<StorageFileMetadataBatchResponse> {
        const normalized = Array.from(
            new Set(
                (Array.isArray(urls) ? urls : [])
                    .map((url) => String(url || '').trim())
                    .filter(Boolean)
            )
        ).slice(0, 100);

        if (normalized.length === 0) {
            return { items: [], total: 0 };
        }

        return this.request<StorageFileMetadataBatchResponse>('/storage/metadata/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                urls: normalized,
                forceRefresh
            })
        });
    }

    async getStorageFileMetadata(urls: string[], forceRefresh: boolean = false): Promise<StorageFileMetadataItem[]> {
        const response = await this.getStorageFileMetadataBatch(urls, forceRefresh);
        return Array.isArray(response?.items) ? response.items : [];
    }

    async deleteStorageItem(
        storageId: string,
        path: string,
        isDirectory: boolean = false,
        fileUrl?: string
    ): Promise<StorageItemMutationResult> {
        return this.request<StorageItemMutationResult>('/storage/items/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                storageId,
                path,
                isDirectory,
                fileUrl
            })
        });
    }

    async batchDeleteStorageItems(
        storageId: string,
        items: StorageBatchDeleteRequestItem[]
    ): Promise<StorageBatchDeleteResult> {
        return this.request<StorageBatchDeleteResult>('/storage/items/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                storageId,
                items
            })
        });
    }

    async prepareStorageDownload(
        storageId: string,
        items: StorageDownloadRequestItem[]
    ): Promise<StorageDownloadPrepareResponse> {
        return this.request<StorageDownloadPrepareResponse>('/storage/items/downloads', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                storageId,
                items
            })
        });
    }

    async renameStorageItem(
        storageId: string,
        path: string,
        newName: string,
        isDirectory: boolean = false
    ): Promise<StorageItemMutationResult> {
        return this.request<StorageItemMutationResult>('/storage/items/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                storageId,
                path,
                newName,
                isDirectory
            })
        });
    }

    async uploadStorageFile(
        file: File,
        storageId?: string,
        timeoutMs: number = 120000
    ): Promise<StorageUploadResult> {
        const formData = new FormData();
        formData.append('file', file);
        const endpoint = storageId
            ? `/storage/upload?storageId=${encodeURIComponent(storageId)}`
            : '/storage/upload';
        return this.request<StorageUploadResult>(endpoint, {
            method: 'POST',
            body: formData,
            timeoutMs
        });
    }

}

export const db = new ApiDB();

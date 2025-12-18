

import { ChatSession, Persona, ModelConfig } from '../../types';
import { StorageConfig } from '../types/storage';
import { DEFAULT_PERSONAS } from '../config/personas';

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
    savedModels?: ModelConfig[];
    createdAt: number;
    updatedAt: number;
}

const API_BASE = '/api';
const API_TIMEOUT = 15000; // 15秒超时（给后端足够时间处理大型会话数据，包含大量附件时需要更长时间）

// --- Local Storage Adapter (Cloud Mode) ---
class LocalStorageDB {
    private get<T>(key: string, def: T): T {
        try {
            const val = localStorage.getItem(key);
            return val ? JSON.parse(val) : def;
        } catch (e) { return def; }
    }

    private set(key: string, val: any) {
        try {
            localStorage.setItem(key, JSON.stringify(val));
        } catch (e: any) {
            // ✅ 如果是配额超出错误，尝试清理旧数据
            if (e.name === 'QuotaExceededError') {
                console.warn('[LocalStorageDB] 存储配额已满，尝试清理旧会话数据...');
                this.cleanupOldSessions();
                // 重试一次
                try {
                    localStorage.setItem(key, JSON.stringify(val));
                } catch {
                    console.error('[LocalStorageDB] 清理后仍无法保存，放弃');
                }
            } else {
                throw e;
            }
        }
    }

    /**
     * 清理旧会话数据以释放 LocalStorage 空间
     * 保留最近 10 个会话，删除其余的
     */
    private cleanupOldSessions() {
        try {
            const sessions = this.get<any[]>('flux_sessions', []);
            if (sessions.length > 10) {
                // 按创建时间排序，保留最新的 10 个
                const sorted = sessions.sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
                const kept = sorted.slice(0, 10);
                localStorage.setItem('flux_sessions', JSON.stringify(kept));
                console.log(`[LocalStorageDB] 已清理 ${sessions.length - 10} 个旧会话`);
            }
        } catch (e) {
            console.error('[LocalStorageDB] 清理失败:', e);
        }
    }

    async getSessions(): Promise<ChatSession[]> {
        return this.get<ChatSession[]>('flux_sessions', []);
    }
    async saveSession(session: ChatSession): Promise<void> {
        const sessions = await this.getSessions();
        const idx = sessions.findIndex(s => s.id === session.id);
        if (idx >= 0) sessions[idx] = session;
        else sessions.unshift(session);
        this.set('flux_sessions', sessions);
    }
    async deleteSession(id: string): Promise<void> {
        const sessions = await this.getSessions();
        this.set('flux_sessions', sessions.filter(s => s.id !== id));
    }

    async getPersonas(): Promise<Persona[]> {
        return this.get<Persona[]>('flux_personas', DEFAULT_PERSONAS);
    }
    async savePersonas(personas: Persona[]): Promise<void> {
        this.set('flux_personas', personas);
    }

    async getProfiles(): Promise<ConfigProfile[]> {
        return this.get<ConfigProfile[]>('flux_profiles', []);
    }
    async saveProfile(profile: ConfigProfile): Promise<void> {
        const profiles = await this.getProfiles();
        const idx = profiles.findIndex(p => p.id === profile.id);
        if (idx >= 0) profiles[idx] = profile;
        else profiles.push(profile);
        this.set('flux_profiles', profiles);
    }
    async deleteProfile(id: string): Promise<void> {
        const profiles = await this.getProfiles();
        this.set('flux_profiles', profiles.filter(p => p.id !== id));
    }
    async getActiveProfileId(): Promise<string | null> {
        return this.get<string | null>('flux_active_profile_id', null);
    }
    async setActiveProfileId(id: string): Promise<void> {
        this.set('flux_active_profile_id', id);
    }

    // 存储配置
    async getStorageConfigs(): Promise<StorageConfig[]> {
        return this.get<StorageConfig[]>('flux_storage_configs', []);
    }
    async saveStorageConfig(config: StorageConfig): Promise<void> {
        const configs = await this.getStorageConfigs();
        const idx = configs.findIndex(c => c.id === config.id);
        if (idx >= 0) configs[idx] = config;
        else configs.push(config);
        this.set('flux_storage_configs', configs);
    }
    async deleteStorageConfig(id: string): Promise<void> {
        const configs = await this.getStorageConfigs();
        this.set('flux_storage_configs', configs.filter(c => c.id !== id));
    }
    async getActiveStorageId(): Promise<string | null> {
        return this.get<string | null>('flux_active_storage_id', null);
    }
    async setActiveStorageId(id: string): Promise<void> {
        this.set('flux_active_storage_id', id);
    }
}

// --- API Adapter (Local Server Mode) ---
class ApiDB {
    private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
        // 添加超时控制
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);
        
        try {
            const res = await fetch(`${API_BASE}${endpoint}`, {
                ...options,
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            if (!res.ok) throw new Error(`API Error: ${res.status}`);
            return res.json();
        } catch (error) {
            clearTimeout(timeoutId);
            throw error;
        }
    }

    async getSessions() { return this.request<ChatSession[]>('/sessions'); }
    async saveSession(s: ChatSession) { await this.request('/sessions', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(s)}); }
    async deleteSession(id: string) { await this.request(`/sessions/${id}`, { method: 'DELETE'}); }

    async getPersonas() {
        try { return await this.request<Persona[]>('/personas'); }
        catch { return DEFAULT_PERSONAS; }
    }
    async savePersonas(p: Persona[]) { await this.request('/personas', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(p)}); }

    async getProfiles() { return this.request<ConfigProfile[]>('/profiles'); }
    async saveProfile(p: ConfigProfile) { await this.request('/profiles', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(p)}); }
    async deleteProfile(id: string) { await this.request(`/profiles/${id}`, { method: 'DELETE'}); }

    async getActiveProfileId() {
        const data = await this.request<{id: string | null}>('/active-profile');
        return data.id;
    }
    async setActiveProfileId(id: string) { await this.request('/active-profile', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id})}); }

    // 存储配置
    async getStorageConfigs() { return this.request<StorageConfig[]>('/storage/configs'); }
    async saveStorageConfig(config: StorageConfig) {
        const exists = await this.request<StorageConfig[]>('/storage/configs').then(configs => configs.some(c => c.id === config.id));
        if (exists) {
            await this.request(`/storage/configs/${config.id}`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config)});
        } else {
            await this.request('/storage/configs', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config)});
        }
    }
    async deleteStorageConfig(id: string) { await this.request(`/storage/configs/${id}`, { method: 'DELETE'}); }
    async getActiveStorageId() {
        const data = await this.request<{storageId: string | null}>('/storage/active');
        return data.storageId;
    }
    async setActiveStorageId(id: string) { await this.request(`/storage/active/${id}`, { method: 'POST'}); }
}

// --- Hybrid Adapter ---
class HybridDB {
    private local = new LocalStorageDB();
    private api = new ApiDB();
    private useApi: boolean | null = null; // null = 未检测, true = 后端可用, false = 后端不可用
    private checkingBackend: Promise<boolean> | null = null; // 防止并发检测

    /**
     * 检测后端是否可用（只在首次调用时执行一次）
     * 
     * 检测策略：
     * 1. 尝试调用一个真实的 API 端点（/api/sessions）
     * 2. 如果成功获取响应（无论状态码），说明后端在运行
     * 3. 如果超时或网络错误（AbortError, TypeError），说明后端未启动
     */
    private async checkBackendAvailable(): Promise<boolean> {
        // 如果已经检测过，直接返回结果
        if (this.useApi !== null) {
            return this.useApi;
        }

        // 如果正在检测中，等待检测完成
        if (this.checkingBackend) {
            return this.checkingBackend;
        }

        // 开始检测
        this.checkingBackend = (async () => {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);
                
                // ✅ 使用健康检查端点检测后端
                const res = await fetch(`/health?t=${Date.now()}`, {
                    method: 'GET',
                    signal: controller.signal,
                    cache: 'no-store',
                    headers: {
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                        'Expires': '0'
                    }
                });
                
                clearTimeout(timeoutId);
                
                // ✅ 只有返回 200 状态码才认为后端可用
                if (res.ok) {
                    this.useApi = true;
                    console.log("✅ 后端 API 已连接 - 使用数据库存储 (PostgreSQL/SQLite)");
                    return true;
                } else {
                    // HTTP 错误（404, 500 等）= 后端有问题
                    this.useApi = false;
                    console.warn(`⚠️ 后端 API 返回错误 (${res.status}) - 使用 LocalStorage`);
                    return false;
                }
            } catch (e: any) {
                // ✅ 网络错误或超时 = 后端不可用
                this.useApi = false;
                console.warn("⚠️ 后端 API 不可用 - 使用 LocalStorage");
                return false;
            } finally {
                this.checkingBackend = null;
            }
        })();

        return this.checkingBackend;
    }

    /**
     * 混合执行：根据后端可用性选择使用 API 或 LocalStorage
     * 
     * 策略：
     * 1. 首次调用时检测后端
     * 2. 如果后端可用，始终使用 API（不降级到 LocalStorage）
     * 3. 只有在后端完全不可用时才使用 LocalStorage
     * 
     * ⚠️ 注意：当后端可用但 API 调用失败时，直接抛出错误，不降级到 LocalStorage
     * 这样可以避免 LocalStorage 配额问题，并让用户知道真正的错误原因
     */
    private async exec<T>(
        apiCall: () => Promise<T>,
        localCall: () => Promise<T>
    ): Promise<T> {
        // 首次调用时检测后端
        const backendAvailable = await this.checkBackendAvailable();
        
        // 如果检测结果为"不可用"，直接使用 LocalStorage
        if (!backendAvailable) {
            return localCall();
        }
        
        // 如果检测结果为"可用"，使用 API（不降级）
        // API 调用失败时直接抛出错误，让上层处理
        return await apiCall();
    }

    getSessions() { return this.exec(() => this.api.getSessions(), () => this.local.getSessions()); }
    saveSession(s: ChatSession) { return this.exec(() => this.api.saveSession(s), () => this.local.saveSession(s)); }
    deleteSession(id: string) { return this.exec(() => this.api.deleteSession(id), () => this.local.deleteSession(id)); }

    getPersonas() { return this.exec(() => this.api.getPersonas(), () => this.local.getPersonas()); }
    savePersonas(p: Persona[]) { return this.exec(() => this.api.savePersonas(p), () => this.local.savePersonas(p)); }

    getProfiles() { return this.exec(() => this.api.getProfiles(), () => this.local.getProfiles()); }
    saveProfile(p: ConfigProfile) { return this.exec(() => this.api.saveProfile(p), () => this.local.saveProfile(p)); }
    deleteProfile(id: string) { return this.exec(() => this.api.deleteProfile(id), () => this.local.deleteProfile(id)); }

    getActiveProfileId() { return this.exec(() => this.api.getActiveProfileId(), () => this.local.getActiveProfileId()); }
    setActiveProfileId(id: string) { return this.exec(() => this.api.setActiveProfileId(id), () => this.local.setActiveProfileId(id)); }

    // 存储配置
    getStorageConfigs() { return this.exec(() => this.api.getStorageConfigs(), () => this.local.getStorageConfigs()); }
    saveStorageConfig(config: StorageConfig) { return this.exec(() => this.api.saveStorageConfig(config), () => this.local.saveStorageConfig(config)); }
    deleteStorageConfig(id: string) { return this.exec(() => this.api.deleteStorageConfig(id), () => this.local.deleteStorageConfig(id)); }
    getActiveStorageId() { return this.exec(() => this.api.getActiveStorageId(), () => this.local.getActiveStorageId()); }
    setActiveStorageId(id: string) { return this.exec(() => this.api.setActiveStorageId(id), () => this.local.setActiveStorageId(id)); }
}

export const db = new HybridDB();

// 导出 HybridDB 类型供 cachedDb 使用
export type { ConfigProfile };

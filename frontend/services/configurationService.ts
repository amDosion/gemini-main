
import { db, ConfigProfile } from './db';
import { getProviderTemplates, getProviderTemplateById, AIProviderConfig } from './providers';
import { ApiProtocol } from '../types/types';

// Full settings interface for one-time fetch
export interface FullSettings {
    profiles: ConfigProfile[];
    activeProfileId: string | null;
    activeProfile: ConfigProfile | null;
    dashscopeKey: string;
}

// Derived runtime config
// ✅ protocol 可以为 null，表示用户尚未配置任何 Provider
export interface ActiveAppConfig {
    apiKey: string;
    baseUrl: string;
    protocol: ApiProtocol | null;  // ✅ 允许 null，表示未配置
    providerId: string;
    hiddenModels: string[];
    isProxy: boolean;
}

class ConfigurationService {
    
    // --- Full Settings (One-time Fetch) ---
    public async getFullSettings(): Promise<FullSettings> {
        return await db.request<FullSettings>('/settings/full');
    }
    
    // --- Profile Management ---
    public async getProfiles(): Promise<ConfigProfile[]> {
        return db.getProfiles();
    }

    public async saveProfile(profile: ConfigProfile): Promise<void> {
        await db.saveProfile(profile);
    }

    public async deleteProfile(id: string): Promise<void> {
        const activeId = await db.getActiveProfileId();
        await db.deleteProfile(id);
        
        // If we deleted the active profile, switch to another
        if (activeId === id) {
            const remaining = await db.getProfiles();
            if (remaining.length > 0) {
                await db.setActiveProfileId(remaining[0].id);
            }
        }
    }

    public async getActiveProfileId(): Promise<string | null> {
        return db.getActiveProfileId();
    }

    public async setActiveProfileId(id: string): Promise<void> {
        await db.setActiveProfileId(id);
    }

    // --- Provider Metadata ---
    public async getAllProviders(): Promise<AIProviderConfig[]> {
        // 从后端 API 获取 Provider Templates
        return getProviderTemplates();
    }

    /**
     * Retrieves the runtime configuration based on the Active Profile.
     */
    public async getActiveConfig(): Promise<ActiveAppConfig> {
        let profileId = await db.getActiveProfileId();
        const profiles = await db.getProfiles();
        
        let activeProfile = profiles.find(p => p.id === profileId);
        
        if (!activeProfile) {
            // Fallback if ID is invalid or missing
            if (profiles.length > 0) {
                activeProfile = profiles[0];
                await db.setActiveProfileId(activeProfile.id);
            } else {
                // Emergency Default
                return {
                    apiKey: '',
                    baseUrl: '',
                    protocol: 'google',
                    providerId: 'google',
                    hiddenModels: [],
                    isProxy: false
                };
            }
        }

        // 获取 Provider Templates 并查找匹配的配置
        const templates = await getProviderTemplates();
        const staticDef = getProviderTemplateById(activeProfile.providerId, templates);
        
        // Merge Profile with Defaults
        return {
            apiKey: activeProfile.apiKey,
            baseUrl: activeProfile.baseUrl || (staticDef?.baseUrl || ''),
            protocol: (activeProfile.protocol as ApiProtocol) || (staticDef?.protocol || 'openai'),
            providerId: activeProfile.providerId,
            hiddenModels: activeProfile.hiddenModels || [],
            isProxy: activeProfile.isProxy
        };
    }

    // Helper to get DashScope key specifically (Legacy support for logic that needs it directly)
    // Now we try to find *any* profile using 'tongyi' provider
    public async getDashScopeKey(): Promise<string> {
        const profiles = await db.getProfiles();
        const tongyiProfile = profiles.find(p => p.providerId === 'tongyi');
        return tongyiProfile?.apiKey || '';
    }
}

export const configService = new ConfigurationService();

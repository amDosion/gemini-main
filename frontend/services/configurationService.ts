
import { db, ConfigProfile } from './db';
import { STATIC_AI_PROVIDERS, getStaticProviderConfig, AIProviderConfig } from '../config/aiProviders';
import { ApiProtocol } from '../types/types';

// Full settings interface for one-time fetch
export interface FullSettings {
    profiles: ConfigProfile[];
    activeProfileId: string | null;
    activeProfile: ConfigProfile | null;
    dashscopeKey: string;
}

// Derived runtime config
export interface ActiveAppConfig {
    apiKey: string;
    baseUrl: string;
    protocol: ApiProtocol;
    providerId: string;
    hiddenModels: string[];
    isProxy: boolean;
}

class ConfigurationService {
    
    // --- Full Settings (One-time Fetch) ---
    public async getFullSettings(): Promise<FullSettings> {
        return await db.execMixed(
            () => db.getApi().request<FullSettings>('/settings/full'),
            async () => {
                // LocalStorage 降级方案
                const profiles = await db.getLocal().getProfiles();
                const activeProfileId = await db.getLocal().getActiveProfileId();
                const activeProfile = profiles.find(p => p.id === activeProfileId) || null;
                const dashscopeKey = profiles.find(p => p.providerId === 'tongyi')?.apiKey || '';

                return {
                    profiles,
                    activeProfileId,
                    activeProfile,
                    dashscopeKey
                };
            }
        );
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
        // We removed the custom provider dynamic creation feature logic for simplicity
        // as per user request to "forbid custom way" (dynamic providers).
        // We just return the static list.
        return STATIC_AI_PROVIDERS;
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

        const staticDef = getStaticProviderConfig(activeProfile.providerId);
        
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


import { useState, useEffect } from 'react';
import { ApiProtocol } from '../../types';
import { llmService } from '../services/llmService';
import { configService, ActiveAppConfig } from '../services/configurationService';
import { AIProviderConfig } from '../config/aiProviders';
import { ConfigProfile } from '../services/db';

export interface AppConfig extends ActiveAppConfig {
  dashscopeApiKey: string;
}

export const useSettings = () => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [config, setConfig] = useState<AppConfig>({
    apiKey: '',
    baseUrl: '',
    protocol: 'google',
    providerId: 'google',
    hiddenModels: [],
    isProxy: false,
    dashscopeApiKey: ''
  });

  const [profiles, setProfiles] = useState<ConfigProfile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);

  // Load settings on mount
  useEffect(() => {
    refreshSettings();
  }, []);

  const refreshSettings = async () => {
      // 1. Get Profiles
      const allProfiles = await configService.getProfiles();
      setProfiles(allProfiles);
      
      const activeId = await configService.getActiveProfileId();
      setActiveProfileId(activeId);

      // 2. Get Active Config
      const activeConfig = await configService.getActiveConfig();
      const dsKey = await configService.getDashScopeKey();

      // Intelligent Key Resolution for Google
      let finalApiKey = activeConfig.apiKey;
      if (!finalApiKey && activeConfig.providerId === 'google') {
          finalApiKey = process.env.API_KEY || '';
      }

      // Runtime vs Storage Separation logic fix:
      // Previous logic aggressively cleared URL if !isProxy. 
      // This broke Ollama/Local which are "Standard" (not custom proxy) but rely on a specific BaseURL.
      // We only want to clear it for Google Standard to defer to SDK defaults.
      let effectiveBaseUrl = activeConfig.baseUrl;
      if (activeConfig.protocol === 'google' && !activeConfig.isProxy) {
          effectiveBaseUrl = '';
      }

      const newAppConfig: AppConfig = {
          ...activeConfig,
          apiKey: finalApiKey,
          baseUrl: effectiveBaseUrl,
          dashscopeApiKey: dsKey
      };

      setConfig(newAppConfig);
      
      // Propagate to Singleton
      llmService.setConfig(
          newAppConfig.apiKey, 
          newAppConfig.baseUrl, 
          newAppConfig.protocol as ApiProtocol, 
          newAppConfig.providerId
      );
  };

  // --- Profile Actions ---

  const saveProfile = async (profile: ConfigProfile) => {
      await configService.saveProfile(profile);
      await refreshSettings();
  };

  const deleteProfile = async (id: string) => {
      await configService.deleteProfile(id);
      await refreshSettings();
  };

  const activateProfile = async (id: string) => {
      await configService.setActiveProfileId(id);
      await refreshSettings();
  };

  // Legacy Wrapper for simple saves (used by quick provider switchers)
  const saveSettings = async (
    apiKey: string, 
    baseUrl: string, 
    hiddenModels: string[], 
    protocol: ApiProtocol,
    dashscopeApiKey: string,
    onSaved?: () => void,
    targetProviderId?: string
  ) => {
     // This legacy method is becoming less relevant with Profiles, 
     // but we can map it to "Update Active Profile" for compatibility.
     if (activeProfileId) {
         const current = profiles.find(p => p.id === activeProfileId);
         if (current) {
             await saveProfile({
                 ...current,
                 apiKey,
                 baseUrl,
                 hiddenModels,
                 protocol
             });
         }
     }
     if (onSaved) onSaved();
  };

  return {
    isSettingsOpen,
    setIsSettingsOpen,
    config,
    hiddenModelIds: config.hiddenModels,
    providers: [], // No longer used dynamically in the old way
    profiles,
    activeProfileId,
    saveProfile,
    deleteProfile,
    activateProfile,
    saveSettings, // Deprecated but kept for signature compat
    refreshSettings
  };
};

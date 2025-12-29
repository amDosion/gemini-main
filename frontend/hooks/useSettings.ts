
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ApiProtocol } from '../types/types';
import { llmService } from '../services/llmService';
import { configService, ActiveAppConfig, FullSettings } from '../services/configurationService';
import { ConfigProfile } from '../services/db';

export interface AppConfig extends ActiveAppConfig {
  dashscopeApiKey: string;
}

/**
 * Creates a cross-window synchronization channel.
 * It uses BroadcastChannel if available, otherwise falls back to using localStorage.
 */
const createSyncChannel = () => {
  const channelName = 'settings-sync';
  const messageType = 'settings-updated';

  // Use BroadcastChannel if supported
  if (typeof BroadcastChannel !== 'undefined') {
    const bc = new BroadcastChannel(channelName);
    return {
      postMessage: () => bc.postMessage(messageType),
      onmessage: (handler: (event: MessageEvent) => void) => {
        bc.onmessage = (event) => {
          if (event.data === messageType) {
            handler(event);
          }
        };
      },
      close: () => bc.close(),
    };
  }

  // Fallback implementation using localStorage for older browsers
  const localStorageKey = 'gemini-settings-sync';
  let storageListener: ((event: StorageEvent) => void) | null = null;

  return {
    postMessage: () => {
      // Set a value in localStorage to trigger 'storage' event in other tabs
      localStorage.setItem(localStorageKey, Date.now().toString());
      // Remove it immediately as we only care about the event, not the value
      localStorage.removeItem(localStorageKey);
    },
    onmessage: (handler: (event: Partial<MessageEvent>) => void) => {
      storageListener = (event: StorageEvent) => {
        if (event.key === localStorageKey) {
          handler({ data: messageType } as Partial<MessageEvent>);
        }
      };
      window.addEventListener('storage', storageListener);
    },
    close: () => {
      if (storageListener) {
        window.removeEventListener('storage', storageListener);
      }
    },
  };
};

/**
 * Creates a debounced function that delays invoking `func` until after `delay`
 * milliseconds have elapsed since the last time the debounced function was invoked.
 * @param func The function to debounce.
 * @param delay The number of milliseconds to delay.
 * @returns A new debounced function.
 */
const debounce = <F extends (...args: any[]) => void>(func: F, delay: number) => {
  let timeoutId: NodeJS.Timeout | null = null;
  return (...args: Parameters<F>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
    }, delay);
  };
};

export const useSettings = () => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  
  // ✅ 使用单一状态存储完整配置
  const [fullSettings, setFullSettings] = useState<FullSettings | null>(null);
  const [cacheTimestamp, setCacheTimestamp] = useState<number | null>(null);
  
  const channelRef = useRef<ReturnType<typeof createSyncChannel> | null>(null);
  const debouncedRefreshRef = useRef<(() => void) | undefined>(undefined);
  
  // ✅ 从 fullSettings 派生其他状态，使用 useMemo 稳定引用
  const profiles = useMemo(() => fullSettings?.profiles || [], [fullSettings?.profiles]);
  const activeProfileId = fullSettings?.activeProfileId || null;
  const activeProfile = fullSettings?.activeProfile || null;
  
  // ✅ 使用 useMemo 稳定 hiddenModels 数组引用
  const hiddenModels = useMemo(() => 
    activeProfile?.hiddenModels || [], 
    [activeProfile?.hiddenModels?.join(',')]
  );
  
  // ✅ 构造 AppConfig
  const config: AppConfig = useMemo(() => ({
    apiKey: activeProfile?.apiKey || '',
    baseUrl: activeProfile?.baseUrl || '',
    protocol: (activeProfile?.protocol as ApiProtocol) || 'google',
    providerId: activeProfile?.providerId || 'google',
    hiddenModels,
    isProxy: activeProfile?.isProxy || false,
    dashscopeApiKey: fullSettings?.dashscopeKey || ''
  }), [
    activeProfile?.apiKey,
    activeProfile?.baseUrl,
    activeProfile?.protocol,
    activeProfile?.providerId,
    hiddenModels,
    activeProfile?.isProxy,
    fullSettings?.dashscopeKey
  ]);

  const isCacheExpired = (timestamp: number | null): boolean => {
    if (!timestamp) {
      return true; // Always refresh if no timestamp is set
    }
    const CACHE_EXPIRY_TIME = 30000; // 30 seconds
    return Date.now() - timestamp > CACHE_EXPIRY_TIME;
  };

  /**
   * Notifies other browser tabs/windows that settings have been updated.
   */
  const notifyOtherTabs = () => {
    if (channelRef.current) {
      channelRef.current.postMessage();
    }
  };

  // ✅ 先声明 refreshSettings 函数
  const refreshSettings = useCallback(async () => {
    try {
      const data = await configService.getFullSettings();
      setFullSettings(data);
      setCacheTimestamp(Date.now()); // Update timestamp after successful fetch

      const activeProfile = data.activeProfile;

      if (!activeProfile) {
        llmService.setConfig('', '', 'google', 'google');
        return;
      }

      let { apiKey, baseUrl, protocol, providerId, isProxy } = activeProfile;

      // Intelligent Key Resolution for Google: Use environment variable as a fallback.
      if (providerId === 'google' && !apiKey) {
        apiKey = process.env.API_KEY || '';
      }

      // Clear baseUrl for Google Standard mode to let the SDK use its default.
      if (protocol === 'google' && !isProxy) {
        baseUrl = '';
      }

      // Propagate the resolved and effective configuration to the global service singleton.
      llmService.setConfig(
        apiKey,
        baseUrl,
        protocol as ApiProtocol,
        providerId
      );
    } catch (error) {
      console.error('Failed to load settings:', error);
      // Keep the previous state unchanged if loading fails
    }
  }, []);

  // ✅ 然后创建 debounced 版本（在 refreshSettings 声明之后）
  useEffect(() => {
    debouncedRefreshRef.current = debounce(refreshSettings, 500);
  }, [refreshSettings]);

  // Load settings on mount
  useEffect(() => {
    refreshSettings();
  }, [refreshSettings]);

  // Check cache expiry on window focus
  useEffect(() => {
    const handleFocus = () => {
      if (isCacheExpired(cacheTimestamp)) {
        refreshSettings();
      }
    };

    window.addEventListener('focus', handleFocus);

    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [cacheTimestamp, refreshSettings]);

  // Cross-window synchronization
  useEffect(() => {
    channelRef.current = createSyncChannel();

    channelRef.current.onmessage(() => {
      // When a message is received, refresh settings to sync state
      refreshSettings();
    });

    // Cleanup on unmount
    return () => {
      if (channelRef.current) {
        channelRef.current.close();
      }
    };
  }, [refreshSettings]);

  // --- Profile Actions ---

  const saveProfile = async (profile: ConfigProfile, autoActivate: boolean = false) => {
      await configService.saveProfile(profile);
      if (autoActivate) {
          await configService.setActiveProfileId(profile.id);
      }
      await refreshSettings();
      notifyOtherTabs(); // Notify other tabs of the change
  };

  const deleteProfile = async (id: string) => {
      await configService.deleteProfile(id);
      await refreshSettings();
      notifyOtherTabs(); // Notify other tabs of the change
  };

  const activateProfile = async (id: string) => {
    if (!fullSettings) {
      console.error("Settings not initialized, cannot activate a profile.");
      return;
    }

    const previousActiveProfileId = fullSettings.activeProfileId;
    const previousActiveProfile = fullSettings.activeProfile;
    const newActiveProfile = fullSettings.profiles.find(p => p.id === id);

    if (!newActiveProfile) {
      console.error(`Profile with id "${id}" not found.`);
      return;
    }

    // Layer 1 - Fast Response: Optimistically update state for quick UI response
    setFullSettings(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        activeProfileId: id,
        activeProfile: newActiveProfile,
      };
    });

    const profileForLlm = { ...newActiveProfile };

    // Apply Google API Key resolution if necessary
    if (profileForLlm.providerId === 'google' && !profileForLlm.apiKey) {
      profileForLlm.apiKey = process.env.API_KEY || '';
    }

    // Clear baseUrl for non-proxied Google provider to use SDK default
    if (profileForLlm.protocol === 'google' && !profileForLlm.isProxy) {
      profileForLlm.baseUrl = '';
    }

    // Immediately update the LLM service with the resolved configuration
    llmService.setConfig(
      profileForLlm.apiKey || '',
      profileForLlm.baseUrl || '',
      profileForLlm.protocol as ApiProtocol,
      profileForLlm.providerId
    );

    try {
      // Layer 2 - Backend Update: Persist the active profile change
      await configService.setActiveProfileId(id);

      // Layer 3 - Async Refresh: Silently refresh all settings to ensure consistency (debounced)
      if (debouncedRefreshRef.current) {
        debouncedRefreshRef.current();
      }
    } catch (error) {
      console.error('Failed to activate profile on the backend:', error);

      // Rollback optimistic UI update
      setFullSettings(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          activeProfileId: previousActiveProfileId,
          activeProfile: previousActiveProfile,
        };
      });

      // Also rollback llmService config if it was changed
      if (previousActiveProfile) {
        llmService.setConfig(
          previousActiveProfile.apiKey || '',
          previousActiveProfile.baseUrl || '',
          previousActiveProfile.protocol as ApiProtocol,
          previousActiveProfile.providerId
        );
      }
    }
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
    hiddenModelIds: hiddenModels,
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

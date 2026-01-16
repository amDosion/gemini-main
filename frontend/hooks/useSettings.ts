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

export const useSettings = (
  initialData?: {
    profiles: ConfigProfile[];
    activeProfileId: string | null;
    activeProfile: ConfigProfile | null;
    dashscopeKey: string;
  }
) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Initialize fullSettings with initialData if provided, otherwise null
  const [fullSettings, setFullSettings] = useState<FullSettings | null>(
    initialData ? {
      profiles: initialData.profiles,
      activeProfileId: initialData.activeProfileId,
      activeProfile: initialData.activeProfile,
      dashscopeKey: initialData.dashscopeKey
    } : null
  );
  const [cacheTimestamp, setCacheTimestamp] = useState<number | null>(null);

  const channelRef = useRef<ReturnType<typeof createSyncChannel> | null>(null);
  const debouncedRefreshRef = useRef<(() => void) | undefined>(undefined);
  
  // ✅ 修复：使用 ref 追踪是否已从 initialData 初始化，避免覆盖后续的状态更新
  const isInitializedFromDataRef = useRef(false);

  // ✅ 修复：只在首次加载时从 initialData 设置 fullSettings，不覆盖后续更新
  useEffect(() => {
    // 只在以下情况下初始化：
    // 1. initialData 存在
    // 2. fullSettings 为 null（首次加载）
    // 3. 尚未从 initialData 初始化过
    if (initialData && !fullSettings && !isInitializedFromDataRef.current) {
      setFullSettings({
        profiles: initialData.profiles,
        activeProfileId: initialData.activeProfileId,
        activeProfile: initialData.activeProfile,
        dashscopeKey: initialData.dashscopeKey
      });
      isInitializedFromDataRef.current = true;
    }
  }, [initialData, fullSettings]);

  // From fullSettings derive other states, use useMemo for stable reference
  const profiles = useMemo(() => fullSettings?.profiles || [], [fullSettings?.profiles]);
  const activeProfileId = fullSettings?.activeProfileId || null;

  
  // ✅ 修复：如果 activeProfile 为 null 但 activeProfileId 存在，从 profiles 中查找
  const activeProfile = useMemo(() => {
    if (fullSettings?.activeProfile) {
      return fullSettings.activeProfile;
    }
    // 回退：如果后端返回的 activeProfile 为 null，尝试从 profiles 中查找
    if (activeProfileId && profiles.length > 0) {
      const found = profiles.find(p => p.id === activeProfileId);
      if (found) {
        return found;
      }
    }
    return null;
  }, [fullSettings?.activeProfile, activeProfileId, profiles]);

  // Use useMemo for stable hiddenModels array reference
  const hiddenModels = useMemo(() =>
    activeProfile?.hiddenModels || [],
    [activeProfile?.hiddenModels?.join(',')]
  );

  // Construct AppConfig
  const config: AppConfig = useMemo(() => ({
    apiKey: activeProfile?.apiKey || '',
    baseUrl: activeProfile?.baseUrl || '',
    protocol: (activeProfile?.protocol as ApiProtocol) || null,
    providerId: activeProfile?.providerId || '',
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

  // Declare refreshSettings function without authentication checks
  const refreshSettings = useCallback(async () => {
    try {
      const data = await configService.getFullSettings();
      setFullSettings(data);
      setCacheTimestamp(Date.now()); // Update timestamp after successful fetch

      const activeProfile = data.activeProfile;

      if (!activeProfile) {
        // User has no configured Profile, clear llmService config
        // The frontend will detect unconfigured state and prompt the user
        llmService.setConfig('', '', null, '');
        return;
      }

      let { apiKey, baseUrl, protocol, providerId, isProxy } = activeProfile;

      // Intelligent Key Resolution for Google: Use environment variable as a fallback.
      if (providerId === 'google' && !apiKey) {
        apiKey = process.env.API_KEY || '';
      }

      // Propagate the resolved and effective configuration to the global service singleton.
      llmService.setConfig(
        apiKey,
        baseUrl,
        protocol as ApiProtocol,
        providerId
      );
    } catch (error: any) {
      // ✅ 静默处理 401 错误（用户未登录或 token 过期）
      const errorMessage = error?.message || String(error || '');
      if (errorMessage.includes('401') || errorMessage.includes('Unauthorized') || errorMessage.includes('Authentication required')) {
        // 用户未登录，静默失败，不打印错误
        return;
      }
      // 其他错误正常打印
      console.error('Failed to load settings:', error);
      // Keep the previous state unchanged if loading fails
    }
  }, []);

  // Create debounced version of refreshSettings
  useEffect(() => {
    debouncedRefreshRef.current = debounce(refreshSettings, 500);
  }, [refreshSettings]);

  // Check cache expiry on window focus
  useEffect(() => {
    const handleFocus = () => {
      // ✅ 检查用户是否已登录（通过检查 token）
      const token = localStorage.getItem('access_token');
      if (!token) {
        // 用户未登录，不刷新设置
        return;
      }
      
      // Only refresh if cache is expired and we have settings loaded
      if (fullSettings && isCacheExpired(cacheTimestamp)) {
        refreshSettings();
      }
    };

    window.addEventListener('focus', handleFocus);

    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [cacheTimestamp, refreshSettings, fullSettings]);

  // Cross-window synchronization
  useEffect(() => {
    channelRef.current = createSyncChannel();

    channelRef.current.onmessage(() => {
      // Synchronize refresh settings only if we have settings loaded
      if (fullSettings) {
        refreshSettings();
      }
    });

    // Cleanup on unmount
    return () => {
      if (channelRef.current) {
        channelRef.current.close();
      }
    };
  }, [refreshSettings, fullSettings]);

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
      console.error("[useSettings] Settings not initialized, cannot activate a profile.");
      return;
    }

    const previousActiveProfileId = fullSettings.activeProfileId;
    const previousActiveProfile = fullSettings.activeProfile;
    const newActiveProfile = fullSettings.profiles.find(p => p.id === id);

    if (!newActiveProfile) {
      console.error(`[useSettings] Profile with id "${id}" not found.`);
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

      // ✅ 修复：通知其他标签页同步状态
      notifyOtherTabs();

    } catch (error) {
      console.error('[useSettings] ❌ 后端更新失败，回滚状态:', error);

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
      
      // ✅ 抛出错误，让调用方（Header.tsx）知道切换失败
      throw error;
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
    activeProfile, // ✅ 返回 activeProfile
    saveProfile,
    deleteProfile,
    activateProfile,
    saveSettings, // Deprecated but kept for signature compat
    refreshSettings
  };
};

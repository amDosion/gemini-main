import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ApiProtocol } from '../types/types';
import { llmService } from '../services/llmService';
import { configService, ActiveAppConfig, FullSettings } from '../services/configurationService';
import { ConfigProfile } from '../services/db';
import { getErrorMessage } from '../utils/errorMessage';
import { debounce } from '../utils/debounce';
import { clearEnhancePromptModelsCache } from './useEnhancePromptModels';
import {
  capturePrivateCacheLifecycleSnapshot,
  isPrivateCacheLifecycleSnapshotCurrent,
} from '../services/privateCacheInvalidation';
import { usePrivateCacheScopeRevision } from './usePrivateCacheScopeRevision';

export interface AppConfig extends ActiveAppConfig {
  dashscopeApiKey: string;
}

const buildProfileCacheFingerprint = (profile: ConfigProfile | null | undefined): string => {
  if (!profile) return 'no-profile';
  const updatedAt = Number(profile.updatedAt || 0);
  const providerId = String(profile.providerId || '');
  const hiddenModels = Array.isArray(profile.hiddenModels) ? profile.hiddenModels.join(',') : '';
  return `${profile.id}|${providerId}|${updatedAt}|${hiddenModels}`;
};

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

export const useSettings = (initialData?: {
  profiles: ConfigProfile[];
  activeProfileId: string | null;
  activeProfile: ConfigProfile | null;
  dashscopeKey: string;
}) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Initialize fullSettings with initialData if provided, otherwise null
  const [fullSettings, setFullSettings] = useState<FullSettings | null>(
    initialData
      ? {
          profiles: initialData.profiles,
          activeProfileId: initialData.activeProfileId,
          activeProfile: initialData.activeProfile,
          dashscopeKey: initialData.dashscopeKey,
        }
      : null
  );
  const [cacheTimestamp, setCacheTimestamp] = useState<number | null>(null);

  const channelRef = useRef<ReturnType<typeof createSyncChannel> | null>(null);
  const debouncedRefreshRef = useRef<(() => void) | undefined>(undefined);
  const profileCacheFingerprintRef = useRef(
    buildProfileCacheFingerprint(initialData?.activeProfile || null)
  );
  const refreshSeqRef = useRef(0);
  const latestInitialDataRef = useRef<typeof initialData>(initialData);
  const appliedInitialDataRef = useRef<typeof initialData>(initialData);

  useEffect(() => {
    latestInitialDataRef.current = initialData;
  }, [initialData]);

  usePrivateCacheScopeRevision(() => {
    refreshSeqRef.current += 1;
    appliedInitialDataRef.current = latestInitialDataRef.current;
    profileCacheFingerprintRef.current = buildProfileCacheFingerprint(null);
    setFullSettings(null);
    setCacheTimestamp(null);
    llmService.setConfig('', '', null, '');
    llmService.clearModelCache();
    clearEnhancePromptModelsCache();
  });

  // ✅ 只接收当前用户 scope 下的新 initialData；scope 切换后同一个旧对象不会被重新灌回
  useEffect(() => {
    if (
      initialData &&
      !fullSettings &&
      appliedInitialDataRef.current !== initialData
    ) {
      setFullSettings({
        profiles: initialData.profiles,
        activeProfileId: initialData.activeProfileId,
        activeProfile: initialData.activeProfile,
        dashscopeKey: initialData.dashscopeKey,
      });
      appliedInitialDataRef.current = initialData;
      profileCacheFingerprintRef.current = buildProfileCacheFingerprint(initialData.activeProfile);
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
      const found = profiles.find((p) => p.id === activeProfileId);
      if (found) {
        return found;
      }
    }
    return null;
  }, [fullSettings?.activeProfile, activeProfileId, profiles]);

  // Use useMemo for stable hiddenModels array reference
  const hiddenModels = useMemo(
    () => activeProfile?.hiddenModels || [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeProfile?.hiddenModels]
  );

  // Construct AppConfig
  const config: AppConfig = useMemo(
    () => ({
      apiKey: activeProfile?.apiKey || '',
      baseUrl: activeProfile?.baseUrl || '',
      protocol: (activeProfile?.protocol as ApiProtocol) || null,
      providerId: activeProfile?.providerId || '',
      hiddenModels,
      isProxy: activeProfile?.isProxy || false,
      dashscopeApiKey: fullSettings?.dashscopeKey || '',
    }),
    [
      activeProfile?.apiKey,
      activeProfile?.baseUrl,
      activeProfile?.protocol,
      activeProfile?.providerId,
      hiddenModels,
      activeProfile?.isProxy,
      fullSettings?.dashscopeKey,
    ]
  );

  const isCacheExpired = (timestamp: number | null): boolean => {
    if (!timestamp) {
      return true; // Always refresh if no timestamp is set
    }
    const CACHE_EXPIRY_TIME = 30000; // 30 seconds
    return Date.now() - timestamp > CACHE_EXPIRY_TIME;
  };

  const invalidateProviderCaches = async (providerIds: Array<string | null | undefined>) => {
    // 当前页内存缓存立刻清理
    llmService.clearModelCache();
    clearEnhancePromptModelsCache();

    const targets = Array.from(
      new Set(providerIds.map((id) => String(id || '').trim()).filter(Boolean))
    );

    if (targets.length === 0) return;

    await Promise.all(
      targets.map(async (providerId) => {
        await configService.clearProviderModelCache(providerId);
      })
    );
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
    const lifecycleSnapshot = capturePrivateCacheLifecycleSnapshot();
    const seq = ++refreshSeqRef.current;

    try {
      const data = await configService.getFullSettings();

      if (
        seq !== refreshSeqRef.current ||
        !isPrivateCacheLifecycleSnapshotCurrent(lifecycleSnapshot)
      ) {
        return;
      }

      setFullSettings(data);
      setCacheTimestamp(Date.now()); // Update timestamp after successful fetch

      const activeProfile = data.activeProfile;
      const nextFingerprint = buildProfileCacheFingerprint(activeProfile);
      const profileChanged = profileCacheFingerprintRef.current !== nextFingerprint;
      if (profileChanged) {
        llmService.clearModelCache();
        clearEnhancePromptModelsCache();
        profileCacheFingerprintRef.current = nextFingerprint;
      }

      if (!activeProfile) {
        // User has no configured Profile, clear llmService config
        // The frontend will detect unconfigured state and prompt the user
        llmService.setConfig('', '', null, '');
        return;
      }

      let { apiKey, baseUrl, protocol, providerId, isProxy } = activeProfile;

      // 不再走 import.meta.env.VITE_API_KEY fallback——build-time 注入会把 provider key
      // 编译进前端 bundle（明文可提取）。请通过 profile UI 配置 Google API key，
      // 后端会加密存储并代为调用。
      if (providerId === 'google' && !apiKey) {
        apiKey = '';
      }

      // Propagate the resolved and effective configuration to the global service singleton.
      llmService.setConfig(apiKey, baseUrl, protocol as ApiProtocol, providerId);
    } catch (error: unknown) {
      // ✅ 静默处理 401 错误（用户未登录或 token 过期）
      const errorMessage = getErrorMessage(error);
      if (
        errorMessage.includes('401') ||
        errorMessage.includes('Unauthorized') ||
        errorMessage.includes('Authentication required')
      ) {
        // 用户未登录，静默失败，不打印错误
        return;
      }
      // Keep the previous state unchanged if loading fails
      console.error('[useSettings] refreshSettings failed:', error)
    }
  }, []);

  // Create debounced version of refreshSettings
  useEffect(() => {
    debouncedRefreshRef.current = debounce(refreshSettings, 500);
  }, [refreshSettings]);

  // Check cache expiry on window focus
  useEffect(() => {
    const handleFocus = () => {
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
      if (debouncedRefreshRef.current) {
        debouncedRefreshRef.current();
      } else {
        refreshSettings();
      }
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
    const previousState = fullSettings;
    const previousProfile = previousState?.profiles.find((p) => p.id === profile.id) || null;
    const previousActiveProfileId = previousState?.activeProfileId || null;
    const previousActiveProfile =
      previousState?.profiles.find((p) => p.id === previousActiveProfileId) || null;

    // 先做同页即时更新，保证 Header 和模型选择器立即响应
    setFullSettings((prev) => {
      if (!prev) return prev;

      const existingIndex = prev.profiles.findIndex((p) => p.id === profile.id);
      const normalizedProfile: ConfigProfile = {
        ...profile,
        hiddenModels: profile.hiddenModels || [],
        savedModels: profile.savedModels || [],
        cachedModelCount: profile.cachedModelCount ?? profile.savedModels?.length ?? 0,
      };

      const nextProfiles = [...prev.profiles];
      if (existingIndex >= 0) {
        nextProfiles[existingIndex] = {
          ...nextProfiles[existingIndex],
          ...normalizedProfile,
        };
      } else {
        nextProfiles.push(normalizedProfile);
      }

      const nextActiveProfileId = autoActivate ? normalizedProfile.id : prev.activeProfileId;
      const nextActiveProfile = nextProfiles.find((p) => p.id === nextActiveProfileId) || null;

      let nextDashscopeKey = prev.dashscopeKey;
      if (normalizedProfile.providerId === 'tongyi' && normalizedProfile.apiKey) {
        nextDashscopeKey = normalizedProfile.apiKey;
      }

      return {
        ...prev,
        profiles: nextProfiles,
        activeProfileId: nextActiveProfileId,
        activeProfile: nextActiveProfile,
        dashscopeKey: nextDashscopeKey,
      };
    });

    // 当前激活配置发生变化时，先清理模型缓存，避免 Header 仍显示旧模型列表
    if (autoActivate || activeProfileId === profile.id) {
      llmService.clearModelCache();
      clearEnhancePromptModelsCache();
    }

    try {
      await configService.saveProfile(profile);
      if (autoActivate) {
        await configService.setActiveProfileId(profile.id);
      }
      await invalidateProviderCaches([
        profile.providerId,
        previousProfile?.providerId,
        autoActivate ? previousActiveProfile?.providerId : null,
      ]);
      await refreshSettings();
      notifyOtherTabs(); // Notify other tabs of the change
    } catch (error) {
      // 后端失败时回滚 optimistic 更新
      if (previousState) {
        setFullSettings(previousState);
      }
      throw error;
    }
  };

  const deleteProfile = async (id: string) => {
    const previousProfile = fullSettings?.profiles.find((p) => p.id === id) || null;
    const previousActiveProfile =
      fullSettings?.profiles.find((p) => p.id === fullSettings?.activeProfileId) || null;
    await configService.deleteProfile(id);
    await invalidateProviderCaches([
      previousProfile?.providerId,
      previousActiveProfile?.providerId,
    ]);
    await refreshSettings();
    notifyOtherTabs(); // Notify other tabs of the change
  };

  const activateProfile = async (id: string) => {
    if (!fullSettings) {
      return;
    }

    const previousActiveProfileId = fullSettings.activeProfileId;
    const previousActiveProfile = fullSettings.activeProfile;
    const newActiveProfile = fullSettings.profiles.find((p) => p.id === id);

    if (!newActiveProfile) {
      return;
    }

    // Layer 1 - Fast Response: Optimistically update state for quick UI response
    setFullSettings((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        activeProfileId: id,
        activeProfile: newActiveProfile,
      };
    });

    const profileForLlm = { ...newActiveProfile };

    // 见上方说明：不再使用 build-time env fallback，避免 provider key 编译进前端 bundle
    if (profileForLlm.providerId === 'google' && !profileForLlm.apiKey) {
      profileForLlm.apiKey = '';
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
    llmService.clearModelCache();
    clearEnhancePromptModelsCache();
    profileCacheFingerprintRef.current = buildProfileCacheFingerprint(profileForLlm);

    try {
      // Layer 2 - Backend Update: Persist the active profile change
      await configService.setActiveProfileId(id);
      await invalidateProviderCaches([profileForLlm.providerId, previousActiveProfile?.providerId]);
      // Re-sync from backend to avoid local state drifting from persisted state.
      await refreshSettings();

      // ✅ 修复：通知其他标签页同步状态
      notifyOtherTabs();
    } catch (error) {
      // Rollback optimistic UI update
      setFullSettings((prev) => {
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
        profileCacheFingerprintRef.current = buildProfileCacheFingerprint(previousActiveProfile);
      } else {
        profileCacheFingerprintRef.current = buildProfileCacheFingerprint(null);
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
      const current = profiles.find((p) => p.id === activeProfileId);
      if (current) {
        await saveProfile({
          ...current,
          apiKey,
          baseUrl,
          hiddenModels,
          protocol,
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
    refreshSettings,
  };
};

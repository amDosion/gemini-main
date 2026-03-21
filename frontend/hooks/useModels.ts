import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { ModelConfig, AppMode, ModeCatalogItem } from '../types/types';
import { llmService } from '../services/llmService';

const isValidModelConfig = (m: Record<string, unknown>): m is ModelConfig => {
  return m &&
    typeof m === 'object' &&
    typeof m.id === 'string' &&
    typeof m.name === 'string' &&
    m.capabilities &&
    typeof m.capabilities === 'object';
};

const normalizeModels = (models: unknown): ModelConfig[] => {
  if (!Array.isArray(models)) return [];
  return models.filter(isValidModelConfig);
};

const normalizeModeCatalog = (catalog: unknown): ModeCatalogItem[] => {
  if (!Array.isArray(catalog)) return [];
  return catalog.filter((item: Record<string, unknown>): item is ModeCatalogItem => {
    return item &&
      typeof item === 'object' &&
      typeof item.id === 'string' &&
      typeof item.label === 'string' &&
      typeof item.hasModels === 'boolean' &&
      typeof item.availableModelCount === 'number';
  });
};

export const useModels = (
  configReady: boolean,
  providerId: string,
  appMode: AppMode,
  profileCacheKey: string = 'no-profile',
  initialSavedModels: ModelConfig[] = [],
  initialModeCatalog: ModeCatalogItem[] = [],
  initialChatModels: ModelConfig[] = [],
  initialDefaultModelId: string | null = null
) => {
  const [availableModels, setAvailableModels] = useState<ModelConfig[]>([]);
  const [modeModels, setModeModels] = useState<ModelConfig[]>([]);
  const [modeCatalog, setModeCatalog] = useState<ModeCatalogItem[]>([]);
  const [modeDefaultModelId, setModeDefaultModelId] = useState<string | null>(null);
  const [currentModelId, setCurrentModelId] = useState<string>('');
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  const normalizedSavedModels = useMemo(
    () => normalizeModels(initialSavedModels),
    [initialSavedModels]
  );
  const normalizedInitialModeCatalog = useMemo(
    () => normalizeModeCatalog(initialModeCatalog),
    [initialModeCatalog]
  );
  const normalizedInitialChatModels = useMemo(
    () => normalizeModels(initialChatModels),
    [initialChatModels]
  );
  const savedModelsFingerprint = useMemo(
    () => normalizedSavedModels.map(model => model.id).join('|'),
    [normalizedSavedModels]
  );
  const savedModelsRef = useRef<ModelConfig[]>(normalizedSavedModels);

  // ✅ 使用 null 作为初始值，表示"尚未从 configReady=true 状态获取过"
  // 这样可以区分"首次从 false→true"和"true→true 期间的实际变更"
  const prevProviderIdRef = useRef<string | null>(null);
  const prevProfileCacheKeyRef = useRef<string | null>(null);
  const prevModeProviderIdRef = useRef<string | null>(null);
  const prevModeProfileCacheKeyRef = useRef<string | null>(null);
  const prevSavedModelsFingerprintRef = useRef<string>(savedModelsFingerprint);
  const modeRequestSeqRef = useRef(0);
  const allRequestSeqRef = useRef(0);
  const userSelectedModelRef = useRef(false);

  // 手动选择模型时打标，避免后续自动切换覆盖用户意图
  const setCurrentModelIdWithUserFlag = useCallback((id: string | ((prev: string) => string)) => {
    if (typeof id === 'function') {
      setCurrentModelId(prev => {
        const next = id(prev);
        if (next && next !== prev) userSelectedModelRef.current = true;
        return next;
      });
      return;
    }

    setCurrentModelId(prev => {
      if (id && id !== prev) userSelectedModelRef.current = true;
      return id;
    });
  }, []);

  useEffect(() => {
    savedModelsRef.current = normalizedSavedModels;
  }, [savedModelsFingerprint, normalizedSavedModels]);

  // 首次渲染优先使用初始化接口携带的 modeCatalog，避免导航等待模型接口返回。
  useEffect(() => {
    if (!configReady || normalizedInitialModeCatalog.length === 0) {
      return;
    }
    setModeCatalog(prev => (prev.length > 0 ? prev : normalizedInitialModeCatalog));
  }, [configReady, normalizedInitialModeCatalog]);

  // 首屏优先使用初始化接口携带的 saved_models，避免模型选择器闪空。
  useEffect(() => {
    if (!configReady) {
      prevSavedModelsFingerprintRef.current = savedModelsFingerprint;
      return;
    }

    const savedModelsChanged = prevSavedModelsFingerprintRef.current !== savedModelsFingerprint;
    prevSavedModelsFingerprintRef.current = savedModelsFingerprint;

    const savedModels = savedModelsRef.current;
    if (!savedModelsChanged || savedModels.length === 0) {
      return;
    }

    userSelectedModelRef.current = false;
    setAvailableModels(savedModels);
    setIsLoadingModels(false);
  }, [configReady, savedModelsFingerprint]);

  // Provider/profile 变化时加载完整模型列表（用于模式导航与 provider 级模型池）。
  useEffect(() => {
    if (!configReady) {
      setAvailableModels([]);
      setModeCatalog([]);
      setCurrentModelId('');
      // ✅ configReady=false 时不更新 prev ref（保持 null），
      // 这样首次 configReady=true 时不会误判为"变更"
      return;
    }

    // ✅ 首次 configReady=true：prev ref 为 null，这是"初始化"而非"变更"
    const isFirstActivation = prevProviderIdRef.current === null;
    const providerChanged = !isFirstActivation && prevProviderIdRef.current !== providerId;
    const profileChanged = !isFirstActivation && prevProfileCacheKeyRef.current !== profileCacheKey;

    // 更新 prev ref
    prevProviderIdRef.current = providerId;
    prevProfileCacheKeyRef.current = profileCacheKey;

    if (providerChanged) {
      userSelectedModelRef.current = false;
      setModeCatalog([]);
      setCurrentModelId('');
    }
    if (providerChanged || profileChanged) {
      llmService.clearModelCache();
    }

    // ✅ 首次激活：如果 init 数据已提供完整模型列表和 modeCatalog，跳过 API 请求
    if (isFirstActivation) {
      const hasInitAllModels = normalizedSavedModels.length > 0;
      const hasInitModeCatalog = normalizedInitialModeCatalog.length > 0;
      if (hasInitAllModels && hasInitModeCatalog) {
        return;
      }
      // init 数据不完整，回退到正常请求
    }

    let cancelled = false;
    const requestId = ++allRequestSeqRef.current;

    const loadAllModels = async () => {
      try {
        const useCache = !(providerChanged || profileChanged);
        const payload = await llmService.getAvailableModelsPayload(useCache);
        const models = normalizeModels(payload.models);
        if (cancelled || requestId !== allRequestSeqRef.current) return;
        setAvailableModels(models);
        setModeCatalog(normalizeModeCatalog(payload.modeCatalog));
      } catch (error) {
        if (!cancelled && requestId === allRequestSeqRef.current) {
          setAvailableModels([]);
          setModeCatalog([]);
        }
      }
    };

    loadAllModels();

    return () => {
      cancelled = true;
    };
  }, [configReady, providerId, profileCacheKey]);

  // 当前 mode 的模型列表完全由后端按 provider 模型集合 + mode 过滤返回。
  useEffect(() => {
    if (!configReady) {
      setModeModels([]);
      setModeDefaultModelId(null);
      setIsLoadingModels(false);
      // ✅ 同样不更新 prev ref
      return;
    }

    // ✅ 首次 configReady=true：prev ref 为 null
    const isFirstModeActivation = prevModeProviderIdRef.current === null;
    const modeProviderChanged = !isFirstModeActivation && prevModeProviderIdRef.current !== providerId;
    const modeProfileChanged = !isFirstModeActivation && prevModeProfileCacheKeyRef.current !== profileCacheKey;

    prevModeProviderIdRef.current = providerId;
    prevModeProfileCacheKeyRef.current = profileCacheKey;

    // ✅ 首次激活 + chat 模式：如果 init 数据已提供 chatModels，直接使用
    if (isFirstModeActivation && appMode === 'chat' && normalizedInitialChatModels.length > 0) {
      setModeModels(normalizedInitialChatModels);
      setModeDefaultModelId(initialDefaultModelId);
      setIsLoadingModels(false);
      return;
    }

    let cancelled = false;
    const requestId = ++modeRequestSeqRef.current;

    // 模式切换时立即清空旧模式模型，避免展示/使用陈旧模型。
    setIsLoadingModels(true);
    setModeModels([]);
    setModeDefaultModelId(null);

    const loadModeModels = async () => {
      try {
        // provider/profile 切换后的首轮模式请求绕过缓存，避免窗口期读到旧模型列表
        const shouldBypassCache = modeProviderChanged || modeProfileChanged;
        const payload = await llmService.getAvailableModelsPayload(!shouldBypassCache, appMode);
        const models = normalizeModels(payload.models);
        if (cancelled || requestId !== modeRequestSeqRef.current) return;
        setModeModels(models);
        setModeDefaultModelId(payload.defaultModelId || null);
      } catch (error) {
        if (!cancelled && requestId === modeRequestSeqRef.current) {
          setModeModels([]);
          setModeDefaultModelId(null);
        }
      } finally {
        if (!cancelled && requestId === modeRequestSeqRef.current) {
          setIsLoadingModels(false);
        }
      }
    };

    loadModeModels();

    return () => {
      cancelled = true;
    };
  }, [configReady, providerId, appMode, profileCacheKey, savedModelsFingerprint]);

  // 当前模式模型（由后端按 mode 过滤返回）
  const visibleModels = useMemo(() => {
    return modeModels;
  }, [modeModels]);

  // 完整模型（供模式导航和能力展示）
  const allVisibleModels = useMemo(() => {
    return availableModels;
  }, [availableModels]);

  // 当可见模型集变化时，保证 currentModelId 有效
  useEffect(() => {
    if (visibleModels.length === 0) {
      setCurrentModelId('');
      return;
    }

    setCurrentModelId(prev => {
      if (prev && visibleModels.some(m => m.id === prev)) {
        return prev;
      }

      if (modeDefaultModelId && visibleModels.some(m => m.id === modeDefaultModelId)) {
        userSelectedModelRef.current = false;
        return modeDefaultModelId;
      }

      userSelectedModelRef.current = false;
      return visibleModels[0].id;
    });
  }, [visibleModels, appMode, modeDefaultModelId]);

  const activeModelConfig = useMemo(() => {
    return visibleModels.find(m => m.id === currentModelId) || visibleModels[0];
  }, [visibleModels, currentModelId]);

  const refreshModels = useCallback(async () => {
    if (!configReady) return;

    setIsLoadingModels(true);
    userSelectedModelRef.current = false;

    try {
      const [allPayload, filteredPayload] = await Promise.all([
        llmService.getAvailableModelsPayload(false),
        llmService.getAvailableModelsPayload(false, appMode)
      ]);
      setAvailableModels(normalizeModels(allPayload.models));
      setModeCatalog(normalizeModeCatalog(allPayload.modeCatalog));
      setModeModels(normalizeModels(filteredPayload.models));
      setModeDefaultModelId(filteredPayload.defaultModelId || null);
    } catch (error) {
      setAvailableModels([]);
      setModeCatalog([]);
      setModeModels([]);
      setModeDefaultModelId(null);
      setCurrentModelId('');
    } finally {
      setIsLoadingModels(false);
    }
  }, [configReady, appMode]);

  return {
    availableModels,
    visibleModels,
    allVisibleModels,
    modeCatalog,
    currentModelId,
    setCurrentModelId: setCurrentModelIdWithUserFlag,
    activeModelConfig,
    isLoadingModels,
    isModelMenuOpen,
    setIsModelMenuOpen,
    refreshModels
  };
};


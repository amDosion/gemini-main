import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { ModelConfig, AppMode, ModeCatalogItem } from '../types/types';
import { llmService } from '../services/llmService';

const isValidModelConfig = (m: unknown): m is ModelConfig => {
  if (!m || typeof m !== 'object') return false;
  const obj = m as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.name === 'string' &&
    !!obj.capabilities &&
    typeof obj.capabilities === 'object'
  );
};

const normalizeModels = (models: unknown): ModelConfig[] => {
  if (!Array.isArray(models)) return [];
  return models.filter(isValidModelConfig);
};

const normalizeModeCatalog = (catalog: unknown): ModeCatalogItem[] => {
  if (!Array.isArray(catalog)) return [];
  return catalog.filter((item: unknown): item is ModeCatalogItem => {
    if (!item || typeof item !== 'object') return false;
    const obj = item as Record<string, unknown>;
    return (
      typeof obj.id === 'string' &&
      typeof obj.label === 'string' &&
      typeof obj.hasModels === 'boolean' &&
      typeof obj.availableModelCount === 'number'
    );
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
    () => normalizedSavedModels.map((model) => model.id).join('|'),
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
      setCurrentModelId((prev) => {
        const next = id(prev);
        if (next && next !== prev) userSelectedModelRef.current = true;
        return next;
      });
      return;
    }

    setCurrentModelId((prev) => {
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
    setModeCatalog((prev) => (prev.length > 0 ? prev : normalizedInitialModeCatalog));
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

  // ✅ B-4: 合并 "all-models" 和 "mode-models" 两个 effect 为单个 effect,
  // 一次 Promise.all 同时拉两份 payload,统一 setState,避免双请求 + 双 re-render。
  useEffect(() => {
    if (!configReady) {
      setAvailableModels([]);
      setModeCatalog([]);
      setModeModels([]);
      setModeDefaultModelId(null);
      setCurrentModelId('');
      setIsLoadingModels(false);
      // configReady=false 时不更新 prev ref(保持 null),
      // 这样首次 configReady=true 时不会误判为"变更"
      return;
    }

    // 首次 configReady=true: prev ref 为 null,这是"初始化"而非"变更"
    const isFirstActivation = prevProviderIdRef.current === null;
    const providerChanged = !isFirstActivation && prevProviderIdRef.current !== providerId;
    const profileChanged = !isFirstActivation && prevProfileCacheKeyRef.current !== profileCacheKey;

    // 更新两组 prev ref(原本由两个 effect 各管一份,合并后一并更新)
    prevProviderIdRef.current = providerId;
    prevProfileCacheKeyRef.current = profileCacheKey;
    prevModeProviderIdRef.current = providerId;
    prevModeProfileCacheKeyRef.current = profileCacheKey;

    if (providerChanged) {
      userSelectedModelRef.current = false;
      setModeCatalog([]);
      setCurrentModelId('');
    }
    if (providerChanged || profileChanged) {
      llmService.clearModelCache();
    }

    // 首次激活快路径: init 数据已含 all-models + modeCatalog + chat-models → 跳过 fetch
    if (isFirstActivation) {
      const hasInitAllModels = normalizedSavedModels.length > 0;
      const hasInitModeCatalog = normalizedInitialModeCatalog.length > 0;
      const hasInitChatModels = appMode === 'chat' && normalizedInitialChatModels.length > 0;
      if (hasInitAllModels && hasInitModeCatalog && hasInitChatModels) {
        setModeModels(normalizedInitialChatModels);
        setModeDefaultModelId(initialDefaultModelId);
        setIsLoadingModels(false);
        return;
      }
      // init 数据不完整,回退到正常请求
    }

    let cancelled = false;
    const allRequestId = ++allRequestSeqRef.current;
    const modeRequestId = ++modeRequestSeqRef.current;

    // 模式切换时立即清空旧模式模型,避免展示/使用陈旧模型
    setIsLoadingModels(true);
    setModeModels([]);
    setModeDefaultModelId(null);

    const shouldBypassCache = providerChanged || profileChanged;

    const loadModels = async () => {
      try {
        const [allPayload, modePayload] = await Promise.all([
          llmService.getAvailableModelsPayload(!shouldBypassCache),
          llmService.getAvailableModelsPayload(!shouldBypassCache, appMode),
        ]);
        if (
          cancelled ||
          allRequestId !== allRequestSeqRef.current ||
          modeRequestId !== modeRequestSeqRef.current
        ) {
          return;
        }
        // 一轮 batched setState
        setAvailableModels(normalizeModels(allPayload.models));
        setModeCatalog(normalizeModeCatalog(allPayload.modeCatalog));
        setModeModels(normalizeModels(modePayload.models));
        setModeDefaultModelId(modePayload.defaultModelId || null);
      } catch (error) {
        if (
          !cancelled &&
          allRequestId === allRequestSeqRef.current &&
          modeRequestId === modeRequestSeqRef.current
        ) {
          setAvailableModels([]);
          setModeCatalog([]);
          setModeModels([]);
          setModeDefaultModelId(null);
        }
      } finally {
        if (!cancelled && modeRequestId === modeRequestSeqRef.current) {
          setIsLoadingModels(false);
        }
      }
    };

    loadModels();

    return () => {
      cancelled = true;
    };
  }, [configReady, providerId, profileCacheKey, appMode]);

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

    setCurrentModelId((prev) => {
      if (prev && visibleModels.some((m) => m.id === prev)) {
        return prev;
      }

      if (modeDefaultModelId && visibleModels.some((m) => m.id === modeDefaultModelId)) {
        userSelectedModelRef.current = false;
        return modeDefaultModelId;
      }

      userSelectedModelRef.current = false;
      return visibleModels[0].id;
    });
  }, [visibleModels, appMode, modeDefaultModelId]);

  const activeModelConfig = useMemo(() => {
    return visibleModels.find((m) => m.id === currentModelId) || visibleModels[0];
  }, [visibleModels, currentModelId]);

  const refreshModels = useCallback(async () => {
    if (!configReady) return;

    setIsLoadingModels(true);
    userSelectedModelRef.current = false;

    try {
      const [allPayload, filteredPayload] = await Promise.all([
        llmService.getAvailableModelsPayload(false),
        llmService.getAvailableModelsPayload(false, appMode),
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
    refreshModels,
  };
};

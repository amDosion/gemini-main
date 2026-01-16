import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { ModelConfig, AppMode } from '../types/types';
import { llmService } from '../services/llmService';
import { filterModelsByAppMode } from '../utils/modelFilter';

export const useModels = (
    configReady: boolean, 
    hiddenModelIds: string[], 
    providerId: string,
    cachedModels: ModelConfig[] | undefined,
    appMode: AppMode
) => {
  const [availableModels, setAvailableModels] = useState<ModelConfig[]>([]);
  const [currentModelId, setCurrentModelId] = useState<string>("");
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  
  // ✅ 跟踪上一个 providerId 和 appMode，用于检测切换
  const prevProviderIdRef = useRef<string>(providerId);
  const prevAppModeRef = useRef<AppMode>(appMode);
  
  // ✅ 跟踪用户是否手动选择了模型（通过 setCurrentModelId 直接调用）
  const userSelectedModelRef = useRef<boolean>(false);
  
  // ✅ 检测提供商是否切换
  const providerChanged = prevProviderIdRef.current !== providerId;
  // ✅ 检测应用模式是否切换
  const appModeChanged = prevAppModeRef.current !== appMode;

  // ✅ 根据 appMode 过滤模型（前端过滤，避免每次模式切换都调用 API）
  const filteredModelsByMode = useMemo(() => {
      return filterModelsByAppMode(availableModels, appMode);
  }, [availableModels, appMode]);

  // ✅ 提取 selectBestModel 为 useCallback，使其可以在多处使用
  // 注意：现在传入的 models 是完整的模型列表，需要根据 appMode 过滤
  const internalSelectBestModel = useCallback((models: ModelConfig[], forceReset: boolean) => {
      if (!models || models.length === 0) {
          setCurrentModelId("");
          return;
      }
      
      // ✅ 第一步：根据 appMode 过滤模型
      const modeFiltered = filterModelsByAppMode(models, appMode);
      
      // ✅ 第二步：排除隐藏模型
      const visible = modeFiltered.filter(m => !hiddenModelIds.includes(m.id));
      
      if (visible.length === 0) {
          setCurrentModelId("");
          return;
      }

      setCurrentModelId(prev => {
          // ✅ appMode 变化时，总是切换到新模式下的第一个可用模型
          // 如果用户之前选择了模型，但该模型在新模式下不可用，自动切换
          if (!forceReset && !providerChanged && prev && userSelectedModelRef.current) {
              const isPrevModelVisible = visible.find(m => m.id === prev);
              if (isPrevModelVisible) {
                  // 用户选择的模型在新模式下仍然可用，保留选择
                  return prev;
              }
              // 用户选择的模型在新模式下不可用，清除用户选择标志，自动切换
              userSelectedModelRef.current = false;
          }
          
          // ✅ 自动选择第一个可见模型
          // 如果 forceReset 或提供商切换，重置用户选择标志
          if (forceReset || providerChanged) {
              userSelectedModelRef.current = false;
          }
          return visible[0].id;
      });
  }, [hiddenModelIds, providerChanged, appMode]);

  // ✅ 包装 setCurrentModelId，标记为用户手动选择
  const setCurrentModelIdWithUserFlag = useCallback((id: string | ((prev: string) => string)) => {
      if (typeof id === 'function') {
          setCurrentModelId(prev => {
              const newId = id(prev);
              // 只有当新ID与旧ID不同时，才标记为用户选择
              if (newId !== prev && newId) {
                  userSelectedModelRef.current = true;
              }
              return newId;
          });
      } else {
          // 只有当新ID与当前ID不同时，才标记为用户选择
          setCurrentModelId(prev => {
              if (id !== prev && id) {
                  userSelectedModelRef.current = true;
              }
              return id;
          });
      }
  }, []);

  // ✅ 处理 appMode 变化时的模型选择（不重新获取模型，只在前端过滤）
  useEffect(() => {
    if (!configReady || availableModels.length === 0) return;
    
    if (appModeChanged) {
      prevAppModeRef.current = appMode;
      
      // ✅ 检查当前模型在新模式下是否可用
      const modeFiltered = filterModelsByAppMode(availableModels, appMode);
      const visible = modeFiltered.filter(m => !hiddenModelIds.includes(m.id));
      const isCurrentModelVisible = currentModelId && visible.find(m => m.id === currentModelId);
      
      // ✅ 如果用户选择了模型（通过 useModeSwitch），且该模型在新模式下可用，保留选择
      if (userSelectedModelRef.current && isCurrentModelVisible) {
        return; // 保留用户选择，不执行自动选择
      }
      
      // ✅ 否则，清除用户选择标志，自动选择新模式下的第一个模型
      userSelectedModelRef.current = false;
      // ✅ 使用当前可用的完整模型列表，根据新 appMode 过滤并选择
      internalSelectBestModel(availableModels, false);
    }
  }, [appMode, appModeChanged, availableModels, internalSelectBestModel, configReady, currentModelId, hiddenModelIds]);

  // Main effect to handle model loading and updates
  // ✅ 只在 providerId 变化时重新获取模型，appMode 变化不触发重新获取
  useEffect(() => {
    if (!configReady) return;

    // ✅ 更新 refs
    if (providerChanged) {
      prevProviderIdRef.current = providerId;
      // ✅ 提供商切换时，重置用户选择标志并清空当前模型选择
      userSelectedModelRef.current = false;
      setCurrentModelId("");
    }

    // Inlined fetchModels logic
    const internalFetchModels = async (useCache: boolean) => {
      setIsLoadingModels(true);

      try {
        // ✅ 不传递 appMode 给后端，总是获取完整模型列表
        // 前端会根据 appMode 进行过滤，避免每次模式切换都调用 API
        const models = await llmService.getAvailableModels(useCache);
        
        if (models && models.length > 0) {
          setAvailableModels(models);
          // ✅ 使用完整模型列表，根据当前 appMode 过滤并选择
          // 只有在提供商切换或首次加载（!useCache）时才强制重置
          internalSelectBestModel(models, providerChanged || !useCache);
        } else {
          setAvailableModels([]);
          setCurrentModelId("");
        }
      } catch (e) {
        console.error("Failed to fetch models", e);
        setAvailableModels([]);
        setCurrentModelId("");
      } finally {
        setIsLoadingModels(false);
      }
    };

    // ✅ 验证 cachedModels 的数据格式
    const isValidModelConfig = (m: any): m is ModelConfig => {
        return m &&
               typeof m === 'object' &&
               typeof m.id === 'string' &&
               typeof m.name === 'string' &&
               m.capabilities &&
               typeof m.capabilities === 'object';
    };

    const hasValidCachedModels = cachedModels &&
                                  cachedModels.length > 0 &&
                                  cachedModels.every(isValidModelConfig);

    // ✅ 优先使用缓存，避免不必要的 API 调用
    if (hasValidCachedModels) {
        setAvailableModels(cachedModels);
        setIsLoadingModels(false);
        // ✅ 使用完整模型列表，根据当前 appMode 过滤并选择
        internalSelectBestModel(cachedModels, providerChanged);
    } else {
      if (cachedModels && cachedModels.length > 0) {
        console.warn('[useModels] Invalid cachedModels format detected, fetching from API instead:', cachedModels[0]);
      }
      internalFetchModels(true);
    }
  }, [configReady, providerId, cachedModels, hiddenModelIds, internalSelectBestModel, providerChanged]);

  /**
   * Forces a refresh of the model list from the provider, bypassing any cache.
   */
  const refreshModels = useCallback(async () => {
      setIsLoadingModels(true);
      // ✅ 刷新时重置用户选择标志，因为这是主动刷新操作
      userSelectedModelRef.current = false;

      try {
        // ✅ 不传递 appMode，获取完整模型列表
        const models = await llmService.getAvailableModels(false);
        
        if (models && models.length > 0) {
          setAvailableModels(models);
          // ✅ 使用完整模型列表，根据当前 appMode 过滤并选择
          internalSelectBestModel(models, true);
        } else {
          setAvailableModels([]);
          setCurrentModelId("");
        }
      } catch (e) {
        console.error("Failed to refresh models", e);
        setAvailableModels([]);
        setCurrentModelId("");
      } finally {
        setIsLoadingModels(false);
      }
  }, [internalSelectBestModel]);

  const activeModelConfig = useMemo(() => {
    const found = availableModels.find(m => m.id === currentModelId);
    const fallback = filteredModelsByMode[0];
    const result = found || fallback;
    return result;
  }, [availableModels, currentModelId, filteredModelsByMode]);

  // ✅ visibleModels 现在根据 appMode 过滤，排除隐藏模型
  const visibleModels = useMemo(() => {
    return filteredModelsByMode.filter(m => !hiddenModelIds.includes(m.id));
  }, [filteredModelsByMode, hiddenModelIds]);

  return {
    availableModels,
    visibleModels,
    currentModelId,
    setCurrentModelId: setCurrentModelIdWithUserFlag,
    activeModelConfig,
    isLoadingModels,
    isModelMenuOpen,
    setIsModelMenuOpen,
    refreshModels
  };
};

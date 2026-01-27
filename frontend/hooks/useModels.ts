import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { ModelConfig, AppMode } from '../types/types';
import { llmService } from '../services/llmService';
import { filterModelsByAppMode } from '../utils/modelFilter';
import { db } from '../services/db';
import { ImagenConfigResponse } from '../types/imagen-config';

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

  // ✅ 用于存储最新的 internalSelectBestModel 函数引用，避免将其加入依赖数组
  const selectBestModelRef = useRef<(models: ModelConfig[], forceReset: boolean) => void>();

  // ✅ 用于防止 Vertex AI 配置重复请求
  const vertexAIConfigCacheRef = useRef<{ timestamp: number; data: any } | null>(null);
  const VERTEX_AI_CACHE_TTL = 30000; // 30秒缓存

  // ✅ 检测提供商是否切换
  const providerChanged = prevProviderIdRef.current !== providerId;
  // ✅ 检测应用模式是否切换
  const appModeChanged = prevAppModeRef.current !== appMode;

  /**
   * 合并 Vertex AI 模型到 Google 提供商模型列表
   * ✅ 使用内存缓存避免重复请求 /api/vertex-ai/config
   * @param googleModels Google API 返回的模型列表
   * @returns 合并后的模型列表
   */
  const mergeVertexAIModels = useCallback(async (googleModels: ModelConfig[]): Promise<ModelConfig[]> => {
    // 只在 Google 提供商时合并
    if (providerId !== 'google') {
      return googleModels;
    }

    try {
      // ✅ 检查缓存是否有效（30秒内）
      const now = Date.now();
      let vertexAIConfig: ImagenConfigResponse | null = null;

      if (
        vertexAIConfigCacheRef.current &&
        now - vertexAIConfigCacheRef.current.timestamp < VERTEX_AI_CACHE_TTL
      ) {
        // 使用缓存
        vertexAIConfig = vertexAIConfigCacheRef.current.data;
        console.log('[useModels] Using cached Vertex AI config');
      } else {
        // 缓存过期或不存在，发起请求
        console.log('[useModels] Fetching Vertex AI config...');
        vertexAIConfig = await db.request<ImagenConfigResponse>('/vertex-ai/config');
        // 更新缓存
        vertexAIConfigCacheRef.current = {
          timestamp: now,
          data: vertexAIConfig
        };
      }

      if (!vertexAIConfig?.savedModels || vertexAIConfig.savedModels.length === 0) {
        // 没有 Vertex AI 配置或没有保存的模型，直接返回 Google 模型
        return googleModels;
      }

      // 创建模型映射（以 ID 为键）
      const mergedMap = new Map<string, ModelConfig>();

      // 1. 首先添加所有 Google API 模型
      googleModels.forEach(model => {
        mergedMap.set(model.id, model);
      });

      // 2. 然后添加 Vertex AI 保存的模型
      vertexAIConfig.savedModels.forEach((vertexModel: ModelConfig) => {
        const existing = mergedMap.get(vertexModel.id);

        if (existing) {
          // 模型已存在，合并 capabilities（Vertex AI 的优先级更高）
          mergedMap.set(vertexModel.id, {
            ...existing,
            capabilities: {
              vision: vertexModel.capabilities?.vision ?? existing.capabilities.vision,
              search: vertexModel.capabilities?.search ?? existing.capabilities.search,
              reasoning: vertexModel.capabilities?.reasoning ?? existing.capabilities.reasoning,
              coding: vertexModel.capabilities?.coding ?? existing.capabilities.coding
            },
            // 如果 Vertex AI 模型有更完整的描述，使用它
            description: vertexModel.description || existing.description,
            contextWindow: vertexModel.contextWindow || existing.contextWindow
          });
        } else {
          // 新模型，直接添加（确保格式正确）
          mergedMap.set(vertexModel.id, {
            id: vertexModel.id,
            name: vertexModel.name || vertexModel.id,
            description: vertexModel.description || `Model: ${vertexModel.id}`,
            capabilities: vertexModel.capabilities || {
              vision: false,
              search: false,
              reasoning: false,
              coding: false
            },
            contextWindow: vertexModel.contextWindow || 0
          });
        }
      });

      const mergedModels = Array.from(mergedMap.values());
      console.log(`[useModels] Merged ${googleModels.length} Google models with ${vertexAIConfig.savedModels.length} Vertex AI models, result: ${mergedModels.length} models`);

      return mergedModels;
    } catch (error) {
      console.warn('[useModels] Failed to merge Vertex AI models, using Google models only:', error);
      // 如果合并失败，返回原始 Google 模型列表
      return googleModels;
    }
  }, [providerId]);

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

  // ✅ 同步更新 ref，供 useEffect 使用（避免将函数加入依赖数组）
  useEffect(() => {
      selectBestModelRef.current = internalSelectBestModel;
  }, [internalSelectBestModel]);

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
  // ✅ 移除 internalSelectBestModel 依赖，使用 ref 避免 appMode 变化触发重新获取
  useEffect(() => {
    if (!configReady) return;

    // ✅ 更新 refs
    if (providerChanged) {
      prevProviderIdRef.current = providerId;
      // ✅ 提供商切换时，重置用户选择标志并清空当前模型选择
      userSelectedModelRef.current = false;
      setCurrentModelId("");
      // ✅ 提供商切换时，清除 Vertex AI 配置缓存
      vertexAIConfigCacheRef.current = null;
    }

    // Inlined fetchModels logic
    const internalFetchModels = async (useCache: boolean) => {
      setIsLoadingModels(true);

      try {
        // ✅ 不传递 appMode 给后端，总是获取完整模型列表
        // 前端会根据 appMode 进行过滤，避免每次模式切换都调用 API
        let models = await llmService.getAvailableModels(useCache);

        // ✅ 如果是 Google 提供商，合并 Vertex AI 模型
        if (providerId === 'google' && models && models.length > 0) {
          models = await mergeVertexAIModels(models);
        }

        if (models && models.length > 0) {
          setAvailableModels(models);
          // ✅ 使用 ref 调用，避免将 internalSelectBestModel 加入依赖数组
          // 只有在提供商切换或首次加载（!useCache）时才强制重置
          selectBestModelRef.current?.(models, providerChanged || !useCache);
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
        // ✅ 如果是 Google 提供商，也需要合并 Vertex AI 模型（即使使用缓存）
        const processCachedModels = async () => {
          try {
            let models = cachedModels;
            if (providerId === 'google' && models && models.length > 0) {
              models = await mergeVertexAIModels(models);
            }
            setAvailableModels(models);
            setIsLoadingModels(false);
            // ✅ 使用 ref 调用，避免将 internalSelectBestModel 加入依赖数组
            selectBestModelRef.current?.(models, providerChanged);
          } catch (e) {
            console.error('[useModels] Failed to process cached models:', e);
            // 如果处理缓存失败，回退到从 API 获取
            setIsLoadingModels(false);
            internalFetchModels(true);
          }
        };
        processCachedModels();
    } else {
      if (cachedModels && cachedModels.length > 0) {
        console.warn('[useModels] Invalid cachedModels format detected, fetching from API instead:', cachedModels[0]);
      }
      internalFetchModels(true);
    }
    // ✅ 移除 internalSelectBestModel 依赖，改用 selectBestModelRef
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configReady, providerId, cachedModels, hiddenModelIds, providerChanged, mergeVertexAIModels]);

  /**
   * Forces a refresh of the model list from the provider, bypassing any cache.
   */
  const refreshModels = useCallback(async () => {
      setIsLoadingModels(true);
      // ✅ 刷新时重置用户选择标志，因为这是主动刷新操作
      userSelectedModelRef.current = false;

      try {
        // ✅ 不传递 appMode，获取完整模型列表
        let models = await llmService.getAvailableModels(false);
        
        // ✅ 如果是 Google 提供商，合并 Vertex AI 模型
        if (providerId === 'google' && models && models.length > 0) {
          models = await mergeVertexAIModels(models);
        }
        
        if (models && models.length > 0) {
          setAvailableModels(models);
          // ✅ 使用 ref 调用，避免将 internalSelectBestModel 加入依赖数组
          selectBestModelRef.current?.(models, true);
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
  // ✅ 移除 internalSelectBestModel 依赖，改用 selectBestModelRef
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providerId, mergeVertexAIModels]);

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

  // ✅ allVisibleModels: 完整模型列表（只排除隐藏模型，不按模式过滤）
  // 用于 ModeSelector 判断各模式的可用性
  const allVisibleModels = useMemo(() => {
    return availableModels.filter(m => !hiddenModelIds.includes(m.id));
  }, [availableModels, hiddenModelIds]);

  return {
    availableModels,
    visibleModels,
    allVisibleModels,  // ✅ 新增：用于 ModeSelector 判断模式可用性
    currentModelId,
    setCurrentModelId: setCurrentModelIdWithUserFlag,
    activeModelConfig,
    isLoadingModels,
    isModelMenuOpen,
    setIsModelMenuOpen,
    refreshModels
  };
};

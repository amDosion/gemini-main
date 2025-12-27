import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { ModelConfig } from '../types/types';
import { llmService } from '../services/llmService';

export const useModels = (
    configReady: boolean, 
    hiddenModelIds: string[], 
    providerId: string,
    cachedModels?: ModelConfig[],
    apiKey?: string
) => {
  const [availableModels, setAvailableModels] = useState<ModelConfig[]>([]);
  const [currentModelId, setCurrentModelId] = useState<string>("");
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [isModelMenuOpen, setIsModelMenuOpen] = useState(false);
  
  const prevApiKeyRef = useRef<string | undefined>(apiKey);

  // Main effect to handle model loading and updates
  useEffect(() => {
    if (!configReady) return;

    const apiKeyChanged = prevApiKeyRef.current !== apiKey;
    prevApiKeyRef.current = apiKey;

    // Inlined selectBestModel logic
    const internalSelectBestModel = (models: ModelConfig[], forceReset: boolean) => {
        if (!models || models.length === 0) {
            setCurrentModelId("");
            return;
        };
        const visible = models.filter(m => !hiddenModelIds.includes(m.id));
        if (visible.length === 0) {
            setCurrentModelId(""); // No visible models, clear selection
            return;
        };

        let candidate;
        if (providerId === 'google') {
            candidate = visible.find(m => m.capabilities.reasoning) 
                     || visible.find(m => m.capabilities.search) 
                     || visible.find(m => m.id.includes('flash')) 
                     || visible[0];
        } else if (providerId === 'openai') {
            candidate = visible.find(m => m.id.includes('gpt-4o')) || visible[0];
        } else if (providerId === 'deepseek') {
            candidate = visible.find(m => m.id.includes('chat')) || visible[0];
        } else {
            candidate = visible[0];
        }
        
        if (candidate) {
           setCurrentModelId(prev => {
               const isPrevModelVisible = prev && visible.find(m => m.id === prev);
               if (!forceReset && isPrevModelVisible) {
                   return prev;
               }
               return candidate.id;
           });
        }
    };

    // Inlined fetchModels logic
    const internalFetchModels = async (useCache: boolean) => {
      setIsLoadingModels(true);

      try {
        const models = await llmService.getAvailableModels(useCache);
        
        if (models && models.length > 0) {
          setAvailableModels(models);
          internalSelectBestModel(models, !useCache);
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

    if (cachedModels && cachedModels.length > 0) {
        setAvailableModels(cachedModels);
        setIsLoadingModels(false);
        internalSelectBestModel(cachedModels, apiKeyChanged);
    } else {
      internalFetchModels(true); // Use cache for standard fetching
    }
  }, [configReady, providerId, apiKey, cachedModels, hiddenModelIds]);

  /**
   * Forces a refresh of the model list from the provider, bypassing any cache.
   */
  const refreshModels = useCallback(async () => {
      setIsLoadingModels(true);

      try {
        const models = await llmService.getAvailableModels(false); // false = bypass cache
        
        if (models && models.length > 0) {
          setAvailableModels(models);
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
  }, []);

  const activeModelConfig = useMemo(() => {
    return availableModels.find(m => m.id === currentModelId) || availableModels[0];
  }, [availableModels, currentModelId]);

  const visibleModels = useMemo(() => {
    return availableModels.filter(m => !hiddenModelIds.includes(m.id));
  }, [availableModels, hiddenModelIds]);

  return {
    availableModels,
    visibleModels,
    currentModelId,
    setCurrentModelId,
    activeModelConfig,
    isLoadingModels,
    isModelMenuOpen,
    setIsModelMenuOpen,
    refreshModels
  };
};


import { useState, useEffect, useRef } from 'react';
import { ModelConfig } from '../../types';
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
  
  // Track previous key to detect actual profile switches
  const prevKeyRef = useRef<string | undefined>(apiKey);

  // Initialize with cached models if available (instant load)
  useEffect(() => {
      const hasKeyChanged = prevKeyRef.current !== apiKey;
      prevKeyRef.current = apiKey;

      if (cachedModels && cachedModels.length > 0) {
          setAvailableModels(cachedModels);
          setIsLoadingModels(false);
          // If key changed (profile switch), force reset selection. 
          // Otherwise, try to preserve current selection.
          selectBestModel(cachedModels, hasKeyChanged);
      } else if (!cachedModels && configReady) {
          // If we switched to a profile without cache, trigger fetch
          fetchModels(true);
      }
  }, [cachedModels, apiKey]); 

  const selectBestModel = (models: ModelConfig[], forceReset = false) => {
      if (!models || models.length === 0) return;
      const visible = models.filter(m => !hiddenModelIds.includes(m.id));
      if (visible.length === 0) return;

      // Smart Selection Logic
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
             // If we are NOT forcing a reset (same profile), and the previous model exists in the new list, keep it.
             if (!forceReset && prev && visible.find(m => m.id === prev)) {
                 return prev;
             }
             // Otherwise (Profile switch or invalid prev), switch to best candidate.
             return candidate.id;
         });
      }
  };

  const fetchModels = async (forceRefresh = false) => {
    if (!cachedModels || cachedModels.length === 0) {
        setIsLoadingModels(true);
    }

    try {
      const models = await llmService.getAvailableModels();
      
      if (models.length > 0) {
        setAvailableModels(models);
        // On explicit fetch, we usually want to verify/reset selection
        selectBestModel(models, true);
      } else {
         if (!cachedModels || cachedModels.length === 0) {
             setAvailableModels([]);
         }
      }
    } catch (e) {
      console.error("Failed to init models", e);
      if (!cachedModels || cachedModels.length === 0) {
          setAvailableModels([]);
      }
    } finally {
      setIsLoadingModels(false);
    }
  };

  // Re-fetch when config/provider changes
  useEffect(() => {
    if (configReady) {
      fetchModels(true); 
    }
  }, [configReady, providerId, apiKey]);

  const activeModelConfig = availableModels.find(m => m.id === currentModelId) || availableModels[0];
  const visibleModels = availableModels.filter(m => !hiddenModelIds.includes(m.id));

  return {
    availableModels,
    visibleModels,
    currentModelId,
    setCurrentModelId,
    activeModelConfig,
    isLoadingModels,
    isModelMenuOpen,
    setIsModelMenuOpen,
    refreshModels: () => fetchModels(true)
  };
};

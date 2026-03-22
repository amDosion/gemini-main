import { ModelConfig } from '../types/types';

type ModelTraitKey = keyof NonNullable<ModelConfig['traits']>;

const readTrait = (model: ModelConfig, key: ModelTraitKey): boolean | null => {
  const value = model.traits?.[key];
  return typeof value === 'boolean' ? value : null;
};

const isLegacyMultimodalUnderstandingFallback = (model: ModelConfig): boolean => {
  const lowerId = model.id.toLowerCase();
  if (!lowerId.includes('gemini')) {
    return false;
  }
  if (!model.capabilities?.vision) {
    return false;
  }

  // Minimal compatibility fallback for legacy backends without `traits`.
  return !lowerId.includes('imagen') && !lowerId.includes('veo') && !lowerId.includes('-image');
};

export const isMultimodalUnderstandingModel = (model: ModelConfig): boolean => {
  const trait = readTrait(model, 'multimodalUnderstanding');
  if (trait !== null) {
    return trait;
  }
  return isLegacyMultimodalUnderstandingFallback(model);
};

export const getEnhancePromptModelCandidates = (models: ModelConfig[]): ModelConfig[] => {
  return models.filter(isMultimodalUnderstandingModel);
};

export const isThinkingCapableModel = (model: ModelConfig): boolean => {
  const trait = readTrait(model, 'thinking');
  if (trait !== null) {
    return trait;
  }
  return Boolean(model.capabilities?.reasoning);
};

export const isDeepResearchModel = (model: ModelConfig): boolean => {
  const trait = readTrait(model, 'deepResearch');
  if (trait !== null) {
    return trait;
  }
  const id = model.id.toLowerCase();
  const name = model.name.toLowerCase();
  return id.includes('deep-research') || name.includes('deep research');
};

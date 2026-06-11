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

export const isOpenAITextPromptEnhancementModel = (model: ModelConfig): boolean => {
  const lowerId = model.id.toLowerCase().trim();
  if (!lowerId) {
    return false;
  }
  if (
    lowerId.startsWith('gpt-image') ||
    lowerId.startsWith('chatgpt-image') ||
    lowerId.startsWith('dall-e') ||
    lowerId.startsWith('dalle') ||
    lowerId.startsWith('sora') ||
    lowerId.startsWith('tts') ||
    lowerId.includes('whisper') ||
    lowerId.includes('audio') ||
    lowerId.includes('embedding') ||
    lowerId.includes('moderation')
  ) {
    return false;
  }
  return lowerId.startsWith('gpt-') || /^o\d/.test(lowerId);
};

export const isTongyiPromptEnhancementModel = (model: ModelConfig): boolean => {
  const lowerId = model.id.toLowerCase().trim();
  if (!lowerId) {
    return false;
  }
  if (
    lowerId.includes('qwen-image') ||
    lowerId.includes('wan') ||
    lowerId.includes('happyhorse') ||
    lowerId.includes('z-image') ||
    lowerId.includes('video') ||
    lowerId.includes('t2v') ||
    lowerId.includes('i2v') ||
    lowerId.includes('r2v') ||
    lowerId.includes('t2i') ||
    lowerId.includes('audio') ||
    lowerId.includes('speech') ||
    lowerId.includes('embedding') ||
    lowerId.includes('moderation')
  ) {
    return false;
  }
  return (
    lowerId.startsWith('qwen') ||
    lowerId.startsWith('qwq') ||
    lowerId.includes('/qwen') ||
    lowerId.includes('qwen-')
  );
};

export const isTongyiVisionPromptEnhancementModel = (model: ModelConfig): boolean => {
  if (!isTongyiPromptEnhancementModel(model)) {
    return false;
  }

  const lowerId = model.id.toLowerCase().trim();
  return (
    lowerId.includes('qwen-vl') ||
    lowerId.includes('qwen2-vl') ||
    lowerId.includes('qwen2.5-vl') ||
    lowerId.includes('qwen3-vl') ||
    lowerId.includes('-vl-') ||
    model.traits?.multimodalUnderstanding === true ||
    model.capabilities?.vision === true
  );
};

export interface EnhancePromptModelCandidateOptions {
  requiresVision?: boolean;
}

export const getEnhancePromptModelCandidates = (
  models: ModelConfig[],
  providerId?: string | null,
  options: EnhancePromptModelCandidateOptions = {}
): ModelConfig[] => {
  const provider = String(providerId || '').toLowerCase();
  if (provider === 'openai') {
    return models.filter(isOpenAITextPromptEnhancementModel);
  }
  if (provider === 'tongyi' || provider === 'qwen') {
    if (options.requiresVision) {
      return models.filter(isTongyiVisionPromptEnhancementModel);
    }
    return models.filter(isTongyiPromptEnhancementModel);
  }
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

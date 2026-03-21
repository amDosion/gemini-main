import type { AppMode, ModelConfig } from '../types/types';

type ResolveSendModelArgs = {
  mode: AppMode;
  currentModelId: string;
  visibleModels: ModelConfig[];
  allVisibleModels: ModelConfig[];
  activeModelConfig?: ModelConfig;
  forcedModelId?: string;
  isLoadingModels?: boolean;
};

type ResolveSendModelResult =
  | { model: ModelConfig; reason: 'resolved' }
  | { model?: undefined; reason: 'loading' | 'unavailable' };

export const resolveModelForModeSend = ({
  mode,
  currentModelId,
  visibleModels,
  allVisibleModels,
  activeModelConfig,
  forcedModelId,
  isLoadingModels = false,
}: ResolveSendModelArgs): ResolveSendModelResult => {
  const effectiveModelId = String(forcedModelId || currentModelId || '').trim();
  const visibleMatch = effectiveModelId
    ? visibleModels.find((model) => model.id === effectiveModelId)
    : undefined;

  if (visibleMatch) {
    return { model: visibleMatch, reason: 'resolved' };
  }

  if (forcedModelId) {
    const forcedFallback = allVisibleModels.find((model) => model.id === forcedModelId);
    if (forcedFallback) {
      return { model: forcedFallback, reason: 'resolved' };
    }
  }

  if (activeModelConfig && visibleModels.some((model) => model.id === activeModelConfig.id)) {
    return { model: activeModelConfig, reason: 'resolved' };
  }

  if (visibleModels.length > 0) {
    return { model: visibleModels[0], reason: 'resolved' };
  }

  if (isLoadingModels && mode !== 'chat') {
    return { reason: 'loading' };
  }

  return { reason: 'unavailable' };
};

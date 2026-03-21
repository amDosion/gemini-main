/**
 * Shared provider/model normalization for multi-agent UI.
 *
 * Contract:
 * - Backend response may be camelCase or snake_case.
 * - Frontend does not infer model tasks from modelId.
 */

export type AgentTaskType =
  | 'chat'
  | 'image-gen'
  | 'image-edit'
  | 'video-gen'
  | 'audio-gen'
  | 'vision-understand'
  | 'data-analysis';

export interface ModelOption {
  id: string;
  name: string;
  supportedTasks: AgentTaskType[];
}

export interface ProviderModels {
  providerId: string;
  providerName: string;
  models: ModelOption[];
  allModels: ModelOption[];
  defaultModelsByTask?: Partial<Record<AgentTaskType, string>>;
}

const SUPPORTED_TASKS = new Set<AgentTaskType>([
  'chat',
  'image-gen',
  'image-edit',
  'video-gen',
  'audio-gen',
  'vision-understand',
  'data-analysis',
]);

const TASK_ALIASES: Record<string, AgentTaskType> = {
  image_edit: 'image-edit',
  data_analysis: 'data-analysis',
  vision_understand: 'vision-understand',
  image_understand: 'vision-understand',
  vision_analyze: 'vision-understand',
  image_analyze: 'vision-understand',
  video: 'video-gen',
  video_generate: 'video-gen',
  video_generation: 'video-gen',
  audio: 'audio-gen',
  speech: 'audio-gen',
  tts: 'audio-gen',
  speech_gen: 'audio-gen',
  speech_generate: 'audio-gen',
  speech_generation: 'audio-gen',
  audio_generate: 'audio-gen',
  audio_generation: 'audio-gen',
};

const toTaskType = (value: unknown): AgentTaskType | null => {
  const token = String(value || '').trim().toLowerCase();
  if (!token) return null;
  const hyphenatedToken = token.replace(/_/g, '-');
  const normalized = (
    TASK_ALIASES[token]
    || TASK_ALIASES[token.replace(/-/g, '_')]
    || hyphenatedToken
  ) as AgentTaskType;
  return SUPPORTED_TASKS.has(normalized) ? normalized : null;
};

export const normalizeSupportedTasks = (raw: unknown): AgentTaskType[] => {
  if (!Array.isArray(raw)) return [];
  const normalized: AgentTaskType[] = [];
  for (const item of raw) {
    const task = toTaskType(item);
    if (task && !normalized.includes(task)) {
      normalized.push(task);
    }
  }
  return normalized;
};

const normalizeModelEntry = (rawModel: any): ModelOption | null => {
  const id = String(rawModel?.id || '').trim();
  if (!id) return null;
  const name = String(rawModel?.name || id).trim() || id;
  const supportedTasks = normalizeSupportedTasks(rawModel?.supportedTasks ?? rawModel?.supported_tasks);
  return {
    id,
    name,
    supportedTasks,
  };
};

const readProviderArray = (provider: any, ...keys: string[]): any[] => {
  for (const key of keys) {
    if (Array.isArray(provider?.[key])) {
      return provider[key];
    }
  }
  return [];
};

const readProviderString = (provider: any, ...keys: string[]): string => {
  for (const key of keys) {
    const value = String(provider?.[key] || '').trim();
    if (value) {
      return value;
    }
  }
  return '';
};

const dedupeModelsById = (models: ModelOption[]): ModelOption[] => {
  const merged = new Map<string, ModelOption>();
  for (const model of models) {
    const existing = merged.get(model.id);
    if (!existing) {
      merged.set(model.id, { ...model, supportedTasks: [...model.supportedTasks] });
      continue;
    }

    const mergedTasks = Array.from(
      new Set<AgentTaskType>([...existing.supportedTasks, ...model.supportedTasks])
    );
    merged.set(model.id, {
      ...existing,
      name: existing.name || model.name,
      supportedTasks: mergedTasks,
    });
  }
  return Array.from(merged.values());
};

const normalizeModelArray = (rawModels: unknown): ModelOption[] => {
  if (!Array.isArray(rawModels)) return [];
  const normalized = rawModels
    .map((model) => normalizeModelEntry(model))
    .filter((model): model is ModelOption => Boolean(model));
  return dedupeModelsById(normalized);
};

const normalizeDefaultModelsByTask = (rawValue: unknown): Partial<Record<AgentTaskType, string>> => {
  if (!rawValue || typeof rawValue !== 'object' || Array.isArray(rawValue)) {
    return {};
  }
  const output: Partial<Record<AgentTaskType, string>> = {};
  Object.entries(rawValue as Record<string, unknown>).forEach(([rawTask, rawModelId]) => {
    const taskType = toTaskType(rawTask);
    const modelId = String(rawModelId || '').trim();
    if (!taskType || !modelId) return;
    output[taskType] = modelId;
  });
  return output;
};

export const normalizeProviderModels = (payload: unknown): ProviderModels[] => {
  const providers = Array.isArray((payload as any)?.providers)
    ? (payload as any).providers
    : Array.isArray(payload)
      ? payload
      : [];
  return providers
    .map((provider: any) => {
      const providerId = readProviderString(provider, 'providerId', 'provider_id');
      if (!providerId) return null;

      const providerName = readProviderString(provider, 'providerName', 'provider_name') || providerId;
      const chatModels = normalizeModelArray(readProviderArray(provider, 'models'));
      const allModels = normalizeModelArray([
        ...readProviderArray(provider, 'allModels', 'all_models'),
        ...chatModels,
        ...readProviderArray(provider, 'imageGenerationModels', 'image_generation_models'),
        ...readProviderArray(provider, 'imageEditModels', 'image_edit_models'),
        ...readProviderArray(provider, 'videoGenerationModels', 'video_generation_models'),
        ...readProviderArray(provider, 'audioGenerationModels', 'audio_generation_models'),
      ]);
      const defaultModelsByTask = normalizeDefaultModelsByTask(
        provider?.defaultModelsByTask ?? provider?.default_models_by_task
      );

      return {
        providerId,
        providerName,
        models: chatModels,
        allModels: allModels.length > 0 ? allModels : chatModels,
        defaultModelsByTask,
      } as ProviderModels;
    })
    .filter((provider): provider is ProviderModels => Boolean(provider));
};

export const formatModelTaskHint = (tasks: AgentTaskType[]): string => {
  const labels: string[] = [];
  if (tasks.includes('chat')) labels.push('对话');
  if (tasks.includes('image-gen')) labels.push('文生图');
  if (tasks.includes('image-edit')) labels.push('图生图');
  if (tasks.includes('video-gen')) labels.push('视频');
  if (tasks.includes('audio-gen')) labels.push('语音');
  if (tasks.includes('vision-understand')) labels.push('视觉理解');
  if (tasks.includes('data-analysis')) labels.push('数据');
  return labels.join('/');
};

export const modelSupportsTask = (model: ModelOption | undefined, taskType: AgentTaskType): boolean => {
  if (!model) return false;
  return Array.isArray(model.supportedTasks) && model.supportedTasks.includes(taskType);
};

export const pickProviderDefaultModel = (
  provider: ProviderModels | undefined,
  taskType: AgentTaskType
): ModelOption | undefined => {
  if (!provider) return undefined;
  const modelPool = provider.allModels.length > 0 ? provider.allModels : provider.models;
  if (modelPool.length <= 0) return undefined;
  const preferredId = provider.defaultModelsByTask?.[taskType];
  if (preferredId) {
    const preferred = modelPool.find((model) => model.id === preferredId);
    if (modelSupportsTask(preferred, taskType)) return preferred;
  }
  return modelPool.find((model) => modelSupportsTask(model, taskType));
};

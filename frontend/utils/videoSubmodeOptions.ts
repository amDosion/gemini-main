import type { VideoContractInputStrategy } from '../hooks/useModeControlsSchema';
import type { ModelConfig } from '../types/types';

export interface VideoInputStrategyOption extends VideoContractInputStrategy {
  targetModelId?: string;
}

type TongyiVideoModelFamily = 't2v' | 'i2v' | 'r2v' | 'video-edit';

type TongyiSubmodeDefinition = VideoContractInputStrategy & {
  modelFamily: TongyiVideoModelFamily;
};

const VIDEO_INPUT_STRATEGY_LABELS: Record<string, string> = {
  text_to_video: '文生视频',
  image_to_video: '图生视频',
  first_frame_to_video: '图生视频',
  first_last_frame: '首尾帧生视频',
  first_last_frame_to_video: '首尾帧生视频',
  video_extension: '视频延长',
  video_continuation: '视频延长',
  video_continuation_to_last_frame: '延长到尾帧',
  reference_to_video: '参考生视频',
  video_edit: '视频编辑',
  masked_video_edit: '遮罩视频编辑',
};

const VIDEO_EXTENSION_STRATEGY_IDS = new Set([
  'video_extension',
  'video_continuation',
  'video_continuation_to_last_frame',
]);

const TONGYI_SUBMODE_DEFINITIONS: TongyiSubmodeDefinition[] = [
  {
    id: 'text_to_video',
    label: '文生视频',
    requires: [],
    allows: [],
    modelFamily: 't2v',
  },
  {
    id: 'first_frame_to_video',
    label: '图生视频',
    requires: ['source_image'],
    allows: ['driving_audio'],
    modelFamily: 'i2v',
  },
  {
    id: 'first_last_frame_to_video',
    label: '首尾帧生视频',
    requires: ['source_image', 'last_frame_image'],
    allows: ['driving_audio'],
    modelFamily: 'i2v',
  },
  {
    id: 'reference_to_video',
    label: '参考生视频',
    requires: [],
    allows: ['source_video', 'reference_video', 'reference_images'],
    modelFamily: 'r2v',
  },
  {
    id: 'video_edit',
    label: '视频编辑',
    requires: ['source_video'],
    allows: ['video_edit_reference_images'],
    modelFamily: 'video-edit',
  },
];

const isTongyiProvider = (providerId: string | undefined): boolean =>
  String(providerId || '').trim().toLowerCase() === 'tongyi';

const normalizedStrategyId = (id: string | undefined): string =>
  String(id || '').trim().toLowerCase();

export const isVideoExtensionStrategyId = (id: string | undefined): boolean =>
  VIDEO_EXTENSION_STRATEGY_IDS.has(normalizedStrategyId(id));

export const getVideoInputStrategyDisplayLabel = (
  strategy: Pick<VideoContractInputStrategy, 'id' | 'label'>
): string => {
  const id = normalizedStrategyId(strategy.id);
  return VIDEO_INPUT_STRATEGY_LABELS[id] ?? strategy.label ?? strategy.id;
};

const modelId = (model: ModelConfig | undefined): string =>
  String(model?.id || '').trim().toLowerCase();

const getTongyiModelFamily = (id: string): TongyiVideoModelFamily | null => {
  if (!id) return null;
  if (id.includes('videoedit') || id.includes('video-edit')) return 'video-edit';
  if (id.includes('-r2v')) return 'r2v';
  if (id.includes('-i2v')) return 'i2v';
  if (id.includes('-t2v')) return 't2v';
  return null;
};

const getTongyiModelLine = (id: string): 'happyhorse' | 'wan2.7' | 'other' => {
  if (id.includes('happyhorse')) return 'happyhorse';
  if (id.includes('wan2.7')) return 'wan2.7';
  return 'other';
};

const getPreferredTongyiModel = (
  models: ModelConfig[],
  currentModel: ModelConfig | undefined,
  family: TongyiVideoModelFamily
): ModelConfig | undefined => {
  const candidates = models.filter((model) => getTongyiModelFamily(modelId(model)) === family);
  if (candidates.length === 0) return undefined;

  const currentId = modelId(currentModel);
  const currentFamily = getTongyiModelFamily(currentId);
  if (currentFamily === family) {
    const currentCandidate = candidates.find((model) => modelId(model) === currentId);
    if (currentCandidate) return currentCandidate;
  }

  const currentLine = getTongyiModelLine(currentId);
  const lineCandidate = candidates.find((model) => getTongyiModelLine(modelId(model)) === currentLine);
  if (lineCandidate) return lineCandidate;

  return (
    candidates.find((model) => getTongyiModelLine(modelId(model)) === 'wan2.7') ??
    candidates.find((model) => getTongyiModelLine(modelId(model)) === 'happyhorse') ??
    candidates[0]
  );
};

export function buildVideoInputStrategyOptions({
  providerId,
  currentModel,
  availableModels = [],
  schemaStrategies,
}: {
  providerId?: string;
  currentModel?: ModelConfig;
  availableModels?: ModelConfig[];
  schemaStrategies: VideoContractInputStrategy[];
}): VideoInputStrategyOption[] {
  if (!isTongyiProvider(providerId)) {
    return schemaStrategies;
  }

  const modelCandidates = availableModels.length > 0
    ? availableModels
    : currentModel
      ? [currentModel]
      : [];
  if (modelCandidates.length === 0) {
    return schemaStrategies;
  }

  const options = TONGYI_SUBMODE_DEFINITIONS.flatMap((definition) => {
    const targetModel = getPreferredTongyiModel(modelCandidates, currentModel, definition.modelFamily);
    if (!targetModel) return [];
    return [{ ...definition, targetModelId: targetModel.id }];
  });

  return options.length > 0 ? options : schemaStrategies;
}

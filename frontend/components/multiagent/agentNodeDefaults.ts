import type { AgentDef, WorkflowNodeData } from './types';

const toSafeString = (value: unknown): string => String(value ?? '').trim();
const isBlank = (value: unknown): boolean => value === undefined || value === null || (typeof value === 'string' && value.trim().length === 0);
const shorten = (value: string, max = 36): string => (value.length <= max ? value : `${value.slice(0, max)}...`);

const AGENT_NODE_FIELD_LABELS: Record<string, string> = {
  agentTaskType: '任务类型',
  agentProviderId: '默认提供商',
  agentModelId: '默认模型',
  modelOverrideProfileId: '默认配置档',
  agentTemperature: '温度',
  agentMaxTokens: 'Max Tokens',
  agentPreferLatestModel: '最新模型优先',
  agentAspectRatio: '宽高比',
  agentResolutionTier: '分辨率',
  agentNumberOfImages: '图片数量',
  agentImageStyle: '图片风格',
  agentOutputMimeType: '输出类型',
  agentNegativePrompt: '反向提示词',
  agentPromptExtend: '提示词优化',
  agentAddMagicSuffix: '魔法后缀',
  agentVideoDurationSeconds: '视频时长',
  agentVideoExtensionCount: '延长次数',
  agentContinueFromPreviousVideo: '续接上一段视频',
  agentContinueFromPreviousLastFrame: '上一段尾帧作为首帧',
  agentGenerateAudio: '生成音频',
  agentPersonGeneration: '人物生成',
  agentSubtitleMode: '字幕模式',
  agentSubtitleLanguage: '字幕语言',
  agentSubtitleScript: '字幕脚本',
  agentStoryboardPrompt: '分镜提示词',
  agentVoice: '音色',
  agentAudioFormat: '音频格式',
  agentSpeechSpeed: '语速',
  agentOutputFormat: '输出格式',
};

const formatSummaryValue = (value: unknown): string => {
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return '';
    if (trimmed.startsWith('data:')) return '[data-url]';
    return shorten(trimmed);
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? `${value.length} 项` : '';
  }
  if (value && typeof value === 'object') {
    return `${Object.keys(value as Record<string, unknown>).length} 项`;
  }
  return String(value ?? '');
};

const areEquivalent = (left: unknown, right: unknown): boolean => {
  if (typeof left === 'number' || typeof right === 'number') {
    const leftNumber = Number(left);
    const rightNumber = Number(right);
    return Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber === rightNumber;
  }
  if (typeof left === 'boolean' || typeof right === 'boolean') {
    return Boolean(left) === Boolean(right);
  }
  if (Array.isArray(left) || Array.isArray(right)) {
    try {
      return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
    } catch {
      return false;
    }
  }
  return toSafeString(left) === toSafeString(right);
};

export interface AgentNodeDefaultFieldStatus {
  fieldKey: keyof WorkflowNodeData;
  label: string;
  agentValue: string;
  nodeValue: string;
  status: 'inherited' | 'duplicated' | 'overridden';
}

export interface AgentNodeDefaultAnalysis {
  inherited: AgentNodeDefaultFieldStatus[];
  duplicated: AgentNodeDefaultFieldStatus[];
  overridden: AgentNodeDefaultFieldStatus[];
}

export const buildAgentNodeDefaultsFromAgent = (agent?: AgentDef | null): Partial<WorkflowNodeData> => {
  const card = agent?.agentCard;
  if (!card || typeof card !== 'object') {
    return {};
  }
  const defaults = (card as any).defaults;
  if (!defaults || typeof defaults !== 'object') {
    return {};
  }

  const updates: Partial<WorkflowNodeData> = {};
  const defaultTaskType = toSafeString((defaults as any).defaultTaskType);
  if (defaultTaskType) {
    updates.agentTaskType = defaultTaskType;
  }

  const llmDefaults = (defaults as any).llm;
  if (llmDefaults && typeof llmDefaults === 'object') {
    const providerId = toSafeString((llmDefaults as any).providerId);
    const modelId = toSafeString((llmDefaults as any).modelId);
    const profileId = toSafeString((llmDefaults as any).profileId);
    if (providerId) updates.agentProviderId = providerId;
    if (modelId) updates.agentModelId = modelId;
    if (profileId) updates.modelOverrideProfileId = profileId;
    if (typeof (llmDefaults as any).temperature === 'number') {
      updates.agentTemperature = (llmDefaults as any).temperature;
    }
    if (typeof (llmDefaults as any).maxTokens === 'number') {
      updates.agentMaxTokens = (llmDefaults as any).maxTokens;
    }
    if (typeof (llmDefaults as any).preferLatestModel === 'boolean') {
      updates.agentPreferLatestModel = (llmDefaults as any).preferLatestModel;
    }
  }

  const imageGeneration = (defaults as any).imageGeneration;
  if (imageGeneration && typeof imageGeneration === 'object') {
    if (typeof imageGeneration.aspectRatio === 'string') updates.agentAspectRatio = imageGeneration.aspectRatio;
    if (typeof imageGeneration.resolutionTier === 'string') updates.agentResolutionTier = imageGeneration.resolutionTier;
    if (typeof imageGeneration.numberOfImages === 'number') updates.agentNumberOfImages = imageGeneration.numberOfImages;
    if (typeof imageGeneration.imageStyle === 'string') updates.agentImageStyle = imageGeneration.imageStyle;
    if (typeof imageGeneration.outputMimeType === 'string') updates.agentOutputMimeType = imageGeneration.outputMimeType;
    if (typeof imageGeneration.negativePrompt === 'string') updates.agentNegativePrompt = imageGeneration.negativePrompt;
    if (typeof imageGeneration.promptExtend === 'boolean') updates.agentPromptExtend = imageGeneration.promptExtend;
    if (typeof imageGeneration.addMagicSuffix === 'boolean') updates.agentAddMagicSuffix = imageGeneration.addMagicSuffix;
  }

  const imageEdit = (defaults as any).imageEdit;
  if (imageEdit && typeof imageEdit === 'object') {
    if (typeof imageEdit.aspectRatio === 'string' && imageEdit.aspectRatio) updates.agentAspectRatio = imageEdit.aspectRatio;
    if (typeof imageEdit.resolutionTier === 'string') updates.agentResolutionTier = imageEdit.resolutionTier;
    if (typeof imageEdit.numberOfImages === 'number') updates.agentNumberOfImages = imageEdit.numberOfImages;
    if (typeof imageEdit.outputMimeType === 'string') updates.agentOutputMimeType = imageEdit.outputMimeType;
    if (typeof imageEdit.promptExtend === 'boolean') updates.agentPromptExtend = imageEdit.promptExtend;
  }

  const videoGeneration = (defaults as any).videoGeneration;
  if (videoGeneration && typeof videoGeneration === 'object') {
    if (typeof videoGeneration.aspectRatio === 'string') updates.agentAspectRatio = videoGeneration.aspectRatio;
    if (typeof videoGeneration.resolution === 'string') updates.agentResolutionTier = videoGeneration.resolution;
    if (typeof videoGeneration.durationSeconds === 'number') updates.agentVideoDurationSeconds = videoGeneration.durationSeconds;
    if (typeof videoGeneration.videoExtensionCount === 'number') updates.agentVideoExtensionCount = videoGeneration.videoExtensionCount;
    if (typeof videoGeneration.continueFromPreviousVideo === 'boolean') {
      updates.agentContinueFromPreviousVideo = videoGeneration.continueFromPreviousVideo;
    }
    if (typeof videoGeneration.continueFromPreviousLastFrame === 'boolean') {
      updates.agentContinueFromPreviousLastFrame = videoGeneration.continueFromPreviousLastFrame;
    }
    if (typeof videoGeneration.generateAudio === 'boolean') updates.agentGenerateAudio = videoGeneration.generateAudio;
    if (typeof videoGeneration.personGeneration === 'string') updates.agentPersonGeneration = videoGeneration.personGeneration;
    if (typeof videoGeneration.subtitleMode === 'string') updates.agentSubtitleMode = videoGeneration.subtitleMode;
    if (typeof videoGeneration.subtitleLanguage === 'string') updates.agentSubtitleLanguage = videoGeneration.subtitleLanguage;
    if (typeof videoGeneration.subtitleScript === 'string') updates.agentSubtitleScript = videoGeneration.subtitleScript;
    if (typeof videoGeneration.storyboardPrompt === 'string') updates.agentStoryboardPrompt = videoGeneration.storyboardPrompt;
    if (typeof videoGeneration.negativePrompt === 'string') updates.agentNegativePrompt = videoGeneration.negativePrompt;
    if (typeof videoGeneration.seed === 'number') updates.agentSeed = videoGeneration.seed;
    if (typeof videoGeneration.promptExtend === 'boolean') updates.agentPromptExtend = videoGeneration.promptExtend;
  }

  const audioGeneration = (defaults as any).audioGeneration;
  if (audioGeneration && typeof audioGeneration === 'object') {
    if (typeof audioGeneration.voice === 'string') updates.agentVoice = audioGeneration.voice;
    if (typeof audioGeneration.responseFormat === 'string') updates.agentAudioFormat = audioGeneration.responseFormat;
    if (typeof audioGeneration.speed === 'number') updates.agentSpeechSpeed = audioGeneration.speed;
  }

  const dataAnalysis = (defaults as any).dataAnalysis;
  if (dataAnalysis && typeof dataAnalysis === 'object') {
    if (typeof dataAnalysis.outputFormat === 'string') updates.agentOutputFormat = dataAnalysis.outputFormat;
  }

  const visionUnderstand = (defaults as any).visionUnderstand;
  if (visionUnderstand && typeof visionUnderstand === 'object') {
    if (typeof visionUnderstand.outputFormat === 'string') updates.agentOutputFormat = visionUnderstand.outputFormat;
  }

  return updates;
};

export const analyzeAgentNodeDefaultUsage = (
  agent: AgentDef | null | undefined,
  nodeData: Partial<WorkflowNodeData> | null | undefined,
): AgentNodeDefaultAnalysis => {
  const defaults = buildAgentNodeDefaultsFromAgent(agent);
  const safeNodeData = nodeData || {};
  const analysis: AgentNodeDefaultAnalysis = {
    inherited: [],
    duplicated: [],
    overridden: [],
  };

  (Object.entries(defaults) as Array<[keyof WorkflowNodeData, WorkflowNodeData[keyof WorkflowNodeData]]>).forEach(([fieldKey, defaultValue]) => {
    if (isBlank(defaultValue)) {
      return;
    }

    const nodeValue = safeNodeData[fieldKey];
    const item: AgentNodeDefaultFieldStatus = {
      fieldKey,
      label: AGENT_NODE_FIELD_LABELS[String(fieldKey)] || String(fieldKey),
      agentValue: formatSummaryValue(defaultValue),
      nodeValue: formatSummaryValue(nodeValue),
      status: 'inherited',
    };

    if (isBlank(nodeValue)) {
      analysis.inherited.push(item);
      return;
    }

    if (areEquivalent(defaultValue, nodeValue)) {
      analysis.duplicated.push({
        ...item,
        status: 'duplicated',
        nodeValue: formatSummaryValue(nodeValue),
      });
      return;
    }

    analysis.overridden.push({
      ...item,
      status: 'overridden',
      nodeValue: formatSummaryValue(nodeValue),
    });
  });

  return analysis;
};

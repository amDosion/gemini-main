import type { AgentTaskType } from './providerModelUtils';
import { normalizeAgentTaskType } from './providerModelUtils';
import type { AgentDef, WorkflowNodeData } from './types';
import { buildAgentNodeDefaultsFromAgent } from './agentNodeDefaults';

type VisualMode = 'fill' | 'force';

interface BuildAgentNodeBindingPatchOptions {
  visualMode?: VisualMode;
}

const DEFAULT_AGENT_LABELS = new Set(['', '智能体', 'Agent']);
const DEFAULT_AGENT_DESCRIPTIONS = new Set([
  '',
  '核心执行单元：模型 + 指令 + 工具',
  'Core execution unit: model + instructions + tools',
]);

const GENERIC_AGENT_FIELD_DEFAULTS: Partial<WorkflowNodeData> = {
  agentAspectRatio: '',
  agentResolutionTier: '1K',
  agentImageSize: '',
  agentNumberOfImages: undefined,
  agentImageStyle: '',
  agentNegativePrompt: '',
  agentSeed: undefined,
  agentPromptExtend: false,
  agentAddMagicSuffix: true,
  agentVideoDurationSeconds: undefined,
  agentVideoExtensionCount: undefined,
  agentVideoInputStrategy: '',
  agentContinueFromPreviousVideo: false,
  agentContinueFromPreviousLastFrame: false,
  agentSourceVideoUrl: '',
  agentLastFrameImageUrl: '',
  agentVideoMaskImageUrl: '',
  agentVideoMaskMode: '',
  agentAudioUrl: '',
  agentGenerateAudio: false,
  agentSubtitleMode: '',
  agentSubtitleLanguage: '',
  agentSubtitleScript: '',
  agentStoryboardPrompt: '',
  agentSpeechSpeed: undefined,
  agentAudioFormat: '',
  agentVoice: '',
  agentOutputFormat: '',
  agentOutputMimeType: '',
  agentReferenceImageUrl: '',
  agentFileUrl: '',
  agentEditMode: '',
  agentEditPrompt: '',
  agentOutputLanguage: '',
  agentPreserveProductIdentity: undefined,
  agentImageEditMaxRetries: undefined,
  agentProductMatchThreshold: undefined,
  modelOverrideProfileId: '',
  agentTemperature: undefined,
  agentMaxTokens: undefined,
  agentPreferLatestModel: undefined,
};

const NODE_AGENT_DEFAULT_KEYS = new Set<keyof WorkflowNodeData>([
  'agentAspectRatio',
  'agentResolutionTier',
  'agentImageSize',
  'agentNumberOfImages',
  'agentImageStyle',
  'agentNegativePrompt',
  'agentSeed',
  'agentPromptExtend',
  'agentAddMagicSuffix',
  'agentVideoDurationSeconds',
  'agentVideoExtensionCount',
  'agentVideoInputStrategy',
  'agentContinueFromPreviousVideo',
  'agentContinueFromPreviousLastFrame',
  'agentSourceVideoUrl',
  'agentLastFrameImageUrl',
  'agentVideoMaskImageUrl',
  'agentVideoMaskMode',
  'agentAudioUrl',
  'agentGenerateAudio',
  'agentSubtitleMode',
  'agentSubtitleLanguage',
  'agentSubtitleScript',
  'agentStoryboardPrompt',
  'agentSpeechSpeed',
  'agentAudioFormat',
  'agentVoice',
  'agentOutputFormat',
  'agentOutputMimeType',
  'agentReferenceImageUrl',
  'agentFileUrl',
  'agentEditMode',
  'agentEditPrompt',
  'agentOutputLanguage',
  'agentPreserveProductIdentity',
  'agentImageEditMaxRetries',
  'agentProductMatchThreshold',
  'modelOverrideProfileId',
  'agentTemperature',
  'agentMaxTokens',
  'agentPreferLatestModel',
]);

const isBlank = (value: unknown): boolean =>
  value === undefined || value === null || (typeof value === 'string' && value.trim().length === 0);

const areEquivalent = (left: unknown, right: unknown): boolean => {
  if (left === right) return true;
  if (isBlank(left) && isBlank(right)) return true;
  if (typeof left === 'number' || typeof right === 'number') {
    const leftNumber = Number(left);
    const rightNumber = Number(right);
    return Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber === rightNumber;
  }
  if (typeof left === 'boolean' || typeof right === 'boolean') {
    return Boolean(left) === Boolean(right);
  }
  return String(left ?? '').trim() === String(right ?? '').trim();
};

const shouldFillText = (
  currentValue: unknown,
  defaultTokens: Set<string>,
  previousAgentName?: string
): boolean => {
  const text = String(currentValue || '').trim();
  if (defaultTokens.has(text)) return true;
  return Boolean(previousAgentName && text === previousAgentName);
};

const shouldFillVisualToken = (currentValue: unknown, fallbackToken: string): boolean => {
  const text = String(currentValue || '').trim();
  return !text || text === fallbackToken;
};

const shouldClearNodeAgentField = (
  fieldKey: keyof WorkflowNodeData,
  currentData: Partial<WorkflowNodeData>,
  agentDefaults: Partial<WorkflowNodeData>
): boolean => {
  const currentValue = currentData[fieldKey];
  const genericDefault = GENERIC_AGENT_FIELD_DEFAULTS[fieldKey];
  const agentDefault = agentDefaults[fieldKey];
  return (
    isBlank(currentValue) ||
    areEquivalent(currentValue, genericDefault) ||
    (!isBlank(agentDefault) && areEquivalent(currentValue, agentDefault))
  );
};

export const buildAgentNodeBindingPatch = (
  agent?: AgentDef | null,
  currentData: Partial<WorkflowNodeData> = {},
  options: BuildAgentNodeBindingPatchOptions = {}
): Partial<WorkflowNodeData> => {
  if (!agent) {
    return {};
  }

  const visualMode = options.visualMode || 'fill';
  const agentId = String(agent.id || '').trim();
  const agentName = String(agent.name || '').trim();
  const agentDescription = String(agent.description || '').trim();
  const agentIcon = String(agent.icon || '').trim();
  const agentColor = String(agent.color || '').trim();
  const previousAgentName = String(currentData.agentName || '').trim();
  const previousAgentId = String(currentData.agentId || '').trim();
  const agentDefaults = buildAgentNodeDefaultsFromAgent(agent);

  const patch: Partial<WorkflowNodeData> = {
    agentId,
    agentName,
    agentPresetKey: undefined,
    agentProviderId: String(agent.providerId || '').trim(),
    agentModelId: String(agent.modelId || '').trim(),
  };

  NODE_AGENT_DEFAULT_KEYS.forEach((fieldKey) => {
    if (shouldClearNodeAgentField(fieldKey, currentData, agentDefaults)) {
      patch[fieldKey] = undefined as never;
    }
  });

  const defaultTaskType = String(agentDefaults.agentTaskType || '').trim();
  const currentTaskType = String(currentData.agentTaskType || '').trim();
  const hasExistingAgentBinding = Boolean(previousAgentId || previousAgentName);
  if (
    defaultTaskType &&
    (
      isBlank(currentTaskType) ||
      (!hasExistingAgentBinding && areEquivalent(currentTaskType, 'chat'))
    )
  ) {
    patch.agentTaskType = defaultTaskType;
  }

  if (
    visualMode === 'force' ||
    shouldFillText(currentData.label, DEFAULT_AGENT_LABELS, previousAgentName)
  ) {
    patch.label = agentName || currentData.label || '智能体';
  }
  if (
    visualMode === 'force' ||
    shouldFillText(currentData.description, DEFAULT_AGENT_DESCRIPTIONS)
  ) {
    patch.description = agentDescription || currentData.description || '';
  }
  if (visualMode === 'force' || shouldFillVisualToken(currentData.icon, '🤖')) {
    patch.icon = agentIcon || currentData.icon || '🤖';
  }
  if (visualMode === 'force' || shouldFillVisualToken(currentData.iconColor, 'bg-teal-500')) {
    patch.iconColor = agentColor || currentData.iconColor || 'bg-teal-500';
  }

  return patch;
};

export const resolveAgentNodeEffectiveTaskType = (
  nodeData: Partial<WorkflowNodeData> = {},
  agent?: AgentDef | null
): AgentTaskType => {
  const explicitTaskType = normalizeAgentTaskType(nodeData.agentTaskType, null);
  if (explicitTaskType) {
    return explicitTaskType;
  }
  const defaultTaskType = normalizeAgentTaskType(
    agent?.agentCard?.defaults?.defaultTaskType,
    null
  );
  return defaultTaskType || 'chat';
};

export const buildAgentNodeDataForDisplay = (
  nodeData: Partial<WorkflowNodeData> = {},
  agent?: AgentDef | null
): Partial<WorkflowNodeData> => {
  const defaults = buildAgentNodeDefaultsFromAgent(agent);
  const displayData: Partial<WorkflowNodeData> = { ...nodeData };

  (Object.entries(defaults) as Array<[keyof WorkflowNodeData, WorkflowNodeData[keyof WorkflowNodeData]]>).forEach(
    ([fieldKey, defaultValue]) => {
      if (isBlank(defaultValue)) {
        return;
      }
      if (isBlank(displayData[fieldKey])) {
        displayData[fieldKey] = defaultValue as never;
      }
    }
  );
  displayData.agentTaskType = resolveAgentNodeEffectiveTaskType(nodeData, agent);
  return displayData;
};

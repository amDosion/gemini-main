import type { WorkflowNodeData } from './types';
import { resolveNodePortLayout } from './workflowPorts';

const toFiniteNumber = (value: any): number | null => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return parsed;
};

const isBlank = (value: any): boolean => {
  if (value === undefined || value === null) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  return false;
};

const withDefault = <K extends keyof WorkflowNodeData>(
  target: Partial<WorkflowNodeData>,
  key: K,
  value: WorkflowNodeData[K],
) => {
  if (isBlank(target[key])) {
    target[key] = value;
  }
};

const normalizeAgentTaskType = (value: any): 'chat' | 'image-gen' | 'image-edit' | 'video-gen' | 'audio-gen' | 'vision-understand' | 'data-analysis' => {
  const normalized = String(value || '').trim().toLowerCase().replace(/_/g, '-');
  const aliases: Record<string, 'video-gen' | 'audio-gen' | 'vision-understand' | 'data-analysis'> = {
    video: 'video-gen',
    'video-generate': 'video-gen',
    'video-generation': 'video-gen',
    audio: 'audio-gen',
    speech: 'audio-gen',
    tts: 'audio-gen',
    'speech-gen': 'audio-gen',
    'speech-generate': 'audio-gen',
    'speech-generation': 'audio-gen',
    'audio-generate': 'audio-gen',
    'audio-generation': 'audio-gen',
    'vision-analyze': 'vision-understand',
    'image-analyze': 'vision-understand',
    'image-understand': 'vision-understand',
    'table-analysis': 'data-analysis',
  };
  const safeTask = aliases[normalized] || normalized;
  if (
    safeTask === 'chat'
    || safeTask === 'image-gen'
    || safeTask === 'image-edit'
    || safeTask === 'video-gen'
    || safeTask === 'audio-gen'
    || safeTask === 'vision-understand'
    || safeTask === 'data-analysis'
  ) {
    return safeTask;
  }
  return 'chat';
};

const normalizeToolName = (value: any): string => String(value || '').trim().toLowerCase().replace(/-/g, '_');

const IMAGE_GEN_TOOL_NAMES = new Set([
  'image_generate',
  'generate_image',
  'image_gen',
]);

const IMAGE_EDIT_TOOL_NAMES = new Set([
  'image_edit',
  'edit_image',
  'image_chat_edit',
  'image_mask_edit',
  'image_inpainting',
  'image_background_edit',
  'image_recontext',
  'image_outpaint',
  'image_outpainting',
  'expand_image',
]);

const PROMPT_OPTIMIZE_TOOL_NAMES = new Set([
  'prompt_optimize',
  'prompt_optimizer',
  'optimize_prompt',
  'prompt_rewrite',
  'rewrite_prompt',
]);

const TABLE_ANALYZE_TOOL_NAMES = new Set([
  'table_analyze',
  'excel_analyze',
  'analyze_table',
  'sheet_analyze',
  'sheet_profile',
]);

const parseToolArgsObject = (rawValue: any): Record<string, any> | null => {
  if (rawValue && typeof rawValue === 'object' && !Array.isArray(rawValue)) {
    return { ...rawValue };
  }
  if (typeof rawValue !== 'string') {
    return null;
  }
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return {};
  }
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, any>;
    }
  } catch {
    return null;
  }
  return null;
};

export const buildEffectiveNodeData = (data: Partial<WorkflowNodeData>): Partial<WorkflowNodeData> => {
  const raw = data || {};
  const next: Partial<WorkflowNodeData> = { ...raw };
  const nodeType = String(next.type || '').toLowerCase();
  next.portLayout = resolveNodePortLayout(nodeType, next.portLayout);

  if (nodeType === 'agent') {
    const taskType = normalizeAgentTaskType(next.agentTaskType);
    next.agentTaskType = taskType;

    if (taskType === 'image-gen') {
      withDefault(next, 'agentAspectRatio', '1:1');
      withDefault(next, 'agentResolutionTier', '1K');
      withDefault(next, 'agentNumberOfImages', 1);
      withDefault(next, 'agentSeed', -1);
      if (next.agentAddMagicSuffix === undefined) {
        next.agentAddMagicSuffix = true;
      }
    } else if (taskType === 'image-edit') {
      withDefault(next, 'agentAspectRatio', '1:1');
      withDefault(next, 'agentResolutionTier', '1K');
      withDefault(next, 'agentNumberOfImages', 1);
    } else if (taskType === 'video-gen') {
      withDefault(next, 'agentAspectRatio', '16:9');
      withDefault(next, 'agentResolutionTier', '720p');
      withDefault(next, 'agentVideoDurationSeconds', 8);
      withDefault(next, 'agentVideoExtensionCount', 0);
      withDefault(next, 'agentContinueFromPreviousVideo', false);
      withDefault(next, 'agentContinueFromPreviousLastFrame', false);
    } else if (taskType === 'audio-gen') {
      withDefault(next, 'agentAudioFormat', 'mp3');
      withDefault(next, 'agentSpeechSpeed', 1);
    } else if (taskType === 'vision-understand') {
      withDefault(next, 'agentOutputFormat', 'json');
    }
  }

  if (nodeType === 'router') {
    withDefault(next, 'routerStrategy', 'intent');
  } else if (nodeType === 'parallel') {
    withDefault(next, 'joinMode', 'wait_all');
    withDefault(next, 'timeoutSeconds', 60);
  } else if (nodeType === 'merge') {
    withDefault(next, 'mergeStrategy', 'append');
  } else if (nodeType === 'loop') {
    withDefault(next, 'maxIterations', 3);
  }

  if (nodeType === 'tool') {
    const normalizedTool = normalizeToolName(next.toolName);
    if (normalizedTool) {
      next.toolName = normalizedTool;
    }

    if (IMAGE_GEN_TOOL_NAMES.has(normalizedTool)) {
      withDefault(next, 'toolAspectRatio', '1:1');
      withDefault(next, 'toolResolutionTier', next.toolImageSize || '1K');
      withDefault(next, 'toolNumberOfImages', 1);
      if (next.toolAddMagicSuffix === undefined) {
        next.toolAddMagicSuffix = true;
      }
    } else if (IMAGE_EDIT_TOOL_NAMES.has(normalizedTool)) {
      withDefault(next, 'toolNumberOfImages', 1);
    } else if (TABLE_ANALYZE_TOOL_NAMES.has(normalizedTool)) {
      withDefault(next, 'toolAnalysisType', 'comprehensive');
    } else if (PROMPT_OPTIMIZE_TOOL_NAMES.has(normalizedTool)) {
      const parsed = parseToolArgsObject(next.toolArgsTemplate);
      if (parsed) {
        if (isBlank(parsed.language)) {
          parsed.language = 'auto';
        }
        if (isBlank(parsed.length)) {
          parsed.length = 'medium';
        }
        next.toolArgsTemplate = JSON.stringify(parsed);
      }
    }
  }

  if (!isBlank(next.timeoutSeconds)) {
    const parsedTimeout = toFiniteNumber(next.timeoutSeconds);
    if (parsedTimeout !== null) {
      next.timeoutSeconds = parsedTimeout;
    }
  }
  if (!isBlank(next.maxIterations)) {
    const parsedMaxIterations = toFiniteNumber(next.maxIterations);
    if (parsedMaxIterations !== null) {
      next.maxIterations = Math.max(1, parsedMaxIterations);
    }
  }
  if (!isBlank(next.agentNumberOfImages)) {
    const parsedImages = toFiniteNumber(next.agentNumberOfImages);
    if (parsedImages !== null) {
      next.agentNumberOfImages = parsedImages;
    }
  }
  if (!isBlank(next.toolNumberOfImages)) {
    const parsedToolImages = toFiniteNumber(next.toolNumberOfImages);
    if (parsedToolImages !== null) {
      next.toolNumberOfImages = parsedToolImages;
    }
  }

  return next;
};

const shorten = (value: any, max = 28): string => {
  const text = String(value || '').trim();
  if (!text) return '';
  if (text.length <= max) return text;
  return `${text.slice(0, max)}...`;
};

const FIELD_LABELS: Record<string, string> = {
  agentId: '智能体ID',
  agentName: '智能体名称',
  agentid: '智能体ID',
  agentname: '智能体名称',
  continueOnError: '失败后继续',
  continue_on_error: '失败后继续',
  continueonerror: '失败后继续',
  agentTaskType: '任务',
  agentProviderId: '提供商',
  agentModelId: '模型',
  modelOverrideProviderId: '覆盖提供商',
  modelOverrideModelId: '覆盖模型',
  modelOverrideProfileId: '覆盖配置',
  agentTemperature: '温度',
  agentMaxTokens: '最大Token',
  agentPreferLatestModel: '最新优先',
  agentAspectRatio: '宽高比',
  agentResolutionTier: '分辨率',
  agentNumberOfImages: '出图数',
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
  agentSpeechSpeed: '语速',
  agentAudioFormat: '音频格式',
  agentVoice: '音色',
  agentEditMode: '编辑模式',
  agentPreserveProductIdentity: '保留主体',
  agentImageEditMaxRetries: '重试次数',
  agentProductMatchThreshold: '匹配阈值',
  agentOutputLanguage: '语言',
  agentImageStyle: '风格',
  agentNegativePrompt: '反向词',
  agentSeed: '随机种子',
  agentPromptExtend: '提示词优化',
  agentAddMagicSuffix: '魔法后缀',
  agentOutputFormat: '输出格式',
  agentOutputMimeType: '输出类型',
  agentReferenceImageUrl: '参考图',
  agentFileUrl: '输入文件',
  agentEditPrompt: '编辑指令',
  instructions: '节点指令',
  inputMapping: '输入映射',
  expression: '条件',
  routerStrategy: '路由策略',
  routerPrompt: '路由提示词',
  mergeStrategy: '合并策略',
  joinMode: '汇聚策略',
  timeoutSeconds: '超时(秒)',
  loopCondition: '循环条件',
  maxIterations: '最大迭代',
  toolName: '工具',
  toolArgsTemplate: '工具参数',
  toolProviderId: '工具提供商',
  toolModelId: '工具模型',
  toolNumberOfImages: '出图数',
  toolAspectRatio: '宽高比',
  toolResolutionTier: '分辨率',
  toolImageSize: '图片尺寸',
  toolImageStyle: '图片风格',
  toolOutputMimeType: '输出类型',
  toolNegativePrompt: '反向词',
  toolPromptExtend: '提示词优化',
  toolAddMagicSuffix: '魔法后缀',
  toolVideoDurationSeconds: '视频时长',
  toolVideoExtensionCount: '延长次数',
  toolGenerateAudio: '生成音频',
  toolPersonGeneration: '人物生成',
  toolSubtitleMode: '字幕模式',
  toolSubtitleLanguage: '字幕语言',
  toolSubtitleScript: '字幕脚本',
  toolStoryboardPrompt: '分镜提示词',
  toolEditMode: '编辑模式',
  toolEditPrompt: '编辑指令',
  toolReferenceImageUrl: '参考图',
  toolAnalysisType: '分析类型',
  approvalPrompt: '审核提示',
  startTask: '任务输入',
  startImageUrl: '图片输入',
  startImageUrls: '图片输入列表',
  startVideoUrl: '视频输入',
  startVideoUrls: '视频输入列表',
  startAudioUrl: '音频输入',
  startAudioUrls: '音频输入列表',
  startFileUrl: '文件输入',
  startFileUrls: '文件输入列表',
};

const FIELD_PRIORITY_BY_NODE_TYPE: Record<string, string[]> = {
  agent: [
    'agentId',
    'agentName',
    'agentTaskType',
    'agentProviderId',
    'agentModelId',
    'modelOverrideProviderId',
    'modelOverrideModelId',
    'modelOverrideProfileId',
    'agentTemperature',
    'agentMaxTokens',
    'agentPreferLatestModel',
    'agentReferenceImageUrl',
    'agentFileUrl',
    'agentVoice',
    'agentAudioFormat',
    'agentSpeechSpeed',
    'agentEditMode',
    'agentAspectRatio',
    'agentResolutionTier',
    'agentVideoDurationSeconds',
    'agentVideoExtensionCount',
    'agentContinueFromPreviousVideo',
    'agentContinueFromPreviousLastFrame',
    'agentGenerateAudio',
    'agentPersonGeneration',
    'agentSubtitleMode',
    'agentSubtitleLanguage',
    'agentSubtitleScript',
    'agentStoryboardPrompt',
    'agentNumberOfImages',
    'agentPreserveProductIdentity',
    'agentImageEditMaxRetries',
    'agentProductMatchThreshold',
    'agentOutputLanguage',
    'agentImageStyle',
    'agentOutputMimeType',
    'agentOutputFormat',
    'agentEditPrompt',
    'agentNegativePrompt',
    'agentSeed',
    'agentPromptExtend',
    'agentAddMagicSuffix',
    'continueOnError',
    'inputMapping',
    'instructions',
  ],
  tool: [
    'toolName',
    'toolProviderId',
    'toolModelId',
    'toolArgsTemplate',
    'toolAspectRatio',
    'toolNumberOfImages',
    'toolResolutionTier',
    'toolVideoDurationSeconds',
    'toolVideoExtensionCount',
    'toolGenerateAudio',
    'toolPersonGeneration',
    'toolSubtitleMode',
    'toolSubtitleLanguage',
    'toolSubtitleScript',
    'toolStoryboardPrompt',
    'toolImageSize',
    'toolImageStyle',
    'toolOutputMimeType',
    'toolNegativePrompt',
    'toolPromptExtend',
    'toolAddMagicSuffix',
    'toolEditMode',
    'toolEditPrompt',
    'toolReferenceImageUrl',
    'toolAnalysisType',
  ],
  start: ['startTask', 'startImageUrls', 'startImageUrl', 'startVideoUrls', 'startVideoUrl', 'startAudioUrls', 'startAudioUrl', 'startFileUrls', 'startFileUrl'],
  input_text: ['startTask'],
  input_image: ['startImageUrls', 'startImageUrl'],
  input_video: ['startVideoUrls', 'startVideoUrl'],
  input_audio: ['startAudioUrls', 'startAudioUrl'],
  input_file: ['startFileUrls', 'startFileUrl'],
  condition: ['expression', 'continueOnError'],
  router: ['routerStrategy', 'routerPrompt'],
  parallel: ['joinMode', 'timeoutSeconds'],
  merge: ['mergeStrategy'],
  loop: ['loopCondition', 'maxIterations', 'continueOnError'],
  human: ['approvalPrompt'],
};

const EXCLUDED_KEYS = new Set([
  'label',
  'description',
  'icon',
  'iconColor',
  'type',
  'status',
  'progress',
  'result',
  'error',
  'runtime',
  'startTime',
  'endTime',
  'nodeWidth',
  'nodeHeight',
  'portLayout',
]);

const isConfiguredValue = (value: any): boolean => {
  if (value === undefined || value === null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value === 'boolean') return true;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;
  return true;
};

const formatValue = (key: string, value: any): string => {
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  if (typeof value === 'number') {
    const parsed = toFiniteNumber(value);
    if (parsed === null) return '';
    if (Number.isInteger(parsed)) return String(parsed);
    return String(Number(parsed.toFixed(4)));
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return '';
    if (key.toLowerCase().includes('url')) {
      if (trimmed.startsWith('data:')) return '[data-url]';
      return shorten(trimmed, 42);
    }
    return shorten(trimmed, 36);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '';
    const primitive = value.every((item) => ['string', 'number', 'boolean'].includes(typeof item));
    if (primitive && value.length <= 4) {
      return value.map((item) => shorten(item, 12)).join('|');
    }
    return `${value.length} items`;
  }
  if (typeof value === 'object' && value !== null) {
    return `${Object.keys(value).length} keys`;
  }
  return shorten(String(value || ''), 36);
};

export interface NodeParamChipItem {
  fieldKey: string;
  label: string;
  value: string;
  text: string;
}

const buildToolArgsChipItems = (rawValue: any): NodeParamChipItem[] => {
  if (!isConfiguredValue(rawValue)) return [];
  const parsed = (() => {
    if (typeof rawValue === 'string') {
      const trimmed = rawValue.trim();
      if (!trimmed) return null;
      try {
        return JSON.parse(trimmed);
      } catch {
        return trimmed;
      }
    }
    return rawValue;
  })();

  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const chips: NodeParamChipItem[] = [];
    Object.entries(parsed).forEach(([subKey, subValue]) => {
      if (!isConfiguredValue(subValue)) return;
      const formatted = formatValue(`toolArgs.${subKey}`, subValue);
      if (!formatted) return;
      const label = `参数.${subKey}`;
      chips.push({
        fieldKey: 'toolArgsTemplate',
        label,
        value: formatted,
        text: `${label}: ${formatted}`,
      });
    });
    return chips;
  }

  const formatted = formatValue('toolArgsTemplate', parsed);
  if (!formatted) return [];
  return [{
    fieldKey: 'toolArgsTemplate',
    label: 'toolArgs',
    value: formatted,
    text: `toolArgs: ${formatted}`,
  }];
};

export const buildNodeParamChipItems = (data: Partial<WorkflowNodeData>): NodeParamChipItem[] => {
  const safeData = buildEffectiveNodeData(data || {});
  const nodeType = String(safeData.type || '').toLowerCase();
  const keys = Object.keys(safeData).filter((key) => !EXCLUDED_KEYS.has(key));
  const priority = FIELD_PRIORITY_BY_NODE_TYPE[nodeType] || [];
  const orderedKeys = [
    ...priority.filter((key) => keys.includes(key)),
    ...keys.filter((key) => !priority.includes(key)).sort(),
  ];

  const chips: NodeParamChipItem[] = [];
  const seen = new Set<string>();
  const pushChip = (item: NodeParamChipItem) => {
    const normalized = String(item?.text || '').trim();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    chips.push(item);
  };

  orderedKeys.forEach((key) => {
    const value = (safeData as any)[key];
    if (!isConfiguredValue(value)) return;

    if (key === 'toolArgsTemplate') {
      buildToolArgsChipItems(value).forEach((chip) => pushChip(chip));
      return;
    }
    const formatted = formatValue(key, value);
    if (!formatted) return;
    const label = FIELD_LABELS[key] || key;
    pushChip({
      fieldKey: key,
      label,
      value: formatted,
      text: `${label}: ${formatted}`,
    });
  });

  return chips;
};

export const buildNodeParamChips = (data: Partial<WorkflowNodeData>): string[] => {
  return buildNodeParamChipItems(data).map((item) => item.text);
};

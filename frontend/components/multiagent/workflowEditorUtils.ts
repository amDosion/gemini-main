import type { Node, Edge } from 'reactflow';
import { CustomNode } from './CustomNode';
import { NodeType } from './nodeTypeConfigs';
import type { AgentDef, WorkflowNodeData } from './types';
import { isPlainObject } from './workflowResultUtils';
import { getDefaultNodePortLayout, resolveNodePortLayout } from './workflowPorts';

export interface DisconnectHandleEventDetail {
  editorScopeId: string;
  nodeId: string;
  direction: 'source' | 'target';
  handleId?: string | null;
}

export interface WorkflowNodeActionEventDetail {
  editorScopeId: string;
  nodeId: string;
}

export interface WorkflowRemoveEdgeRequestDetail {
  editorScopeId: string;
  edgeId: string;
}

export interface WorkflowNodeFieldFocusEventDetail {
  editorScopeId: string;
  nodeId: string;
  fieldKey?: string;
}

export interface WorkflowNodeFieldFocusRequest {
  nodeId: string;
  fieldKey: string;
  token: string;
}

export const FLOW_NODE_TYPES = {
  start: CustomNode,
  end: CustomNode,
  input_text: CustomNode,
  input_image: CustomNode,
  input_video: CustomNode,
  input_audio: CustomNode,
  input_file: CustomNode,
  agent: CustomNode,
  tool: CustomNode,
  human: CustomNode,
  router: CustomNode,
  parallel: CustomNode,
  condition: CustomNode,
  merge: CustomNode,
  loop: CustomNode,
} as const;

export const getDefaultNodeConfig = (type: NodeType): Partial<WorkflowNodeData> => {
  let baseConfig: Partial<WorkflowNodeData> = {};

  if (type === 'start') {
    baseConfig = {
      startTask: '',
      startImageUrl: '',
      startImageUrls: [],
      startVideoUrl: '',
      startVideoUrls: [],
      startAudioUrl: '',
      startAudioUrls: [],
      startFileUrl: '',
      startFileUrls: [],
    };
  }
  if (type === 'input_text') {
    baseConfig = {
      startTask: '',
    };
  }
  if (type === 'input_image') {
    baseConfig = {
      startImageUrl: '',
      startImageUrls: [],
    };
  }
  if (type === 'input_video') {
    baseConfig = {
      startVideoUrl: '',
      startVideoUrls: [],
    };
  }
  if (type === 'input_audio') {
    baseConfig = {
      startAudioUrl: '',
      startAudioUrls: [],
    };
  }
  if (type === 'input_file') {
    baseConfig = {
      startFileUrl: '',
      startFileUrls: [],
    };
  }
  if (type === 'agent') {
    baseConfig = {
      instructions: '',
      inputMapping: '',
      agentTaskType: 'chat',
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
      agentContinueFromPreviousVideo: false,
      agentContinueFromPreviousLastFrame: false,
      agentSourceVideoUrl: '',
      agentLastFrameImageUrl: '',
      agentVideoMaskImageUrl: '',
      agentVideoMaskMode: '',
      agentGenerateAudio: false,
      agentPersonGeneration: '',
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
      agentEditPrompt: '',
    };
  }
  if (type === 'condition') {
    baseConfig = {
      expression: '{{prev.output.text}}.includes("通过")',
    };
  }
  if (type === 'router') {
    baseConfig = {
      routerStrategy: 'intent',
      routerPrompt: '',
    };
  }
  if (type === 'parallel') {
    baseConfig = {
      joinMode: 'wait_all',
      timeoutSeconds: 60,
    };
  }
  if (type === 'merge') {
    baseConfig = {
      mergeStrategy: 'append',
    };
  }
  if (type === 'loop') {
    baseConfig = {
      loopCondition: '{{prev.output.retry}} < 3',
      maxIterations: 3,
    };
  }
  if (type === 'tool') {
    baseConfig = {
      toolName: '',
      toolArgsTemplate: '',
      toolProviderId: '',
      toolModelId: '',
      toolNumberOfImages: undefined,
      toolAspectRatio: '',
      toolResolutionTier: '',
      toolImageSize: '',
      toolImageStyle: '',
      toolOutputMimeType: '',
      toolNegativePrompt: '',
      toolPromptExtend: false,
      toolAddMagicSuffix: true,
      toolVideoDurationSeconds: undefined,
      toolVideoExtensionCount: undefined,
      toolSourceVideoUrl: '',
      toolLastFrameImageUrl: '',
      toolVideoMaskImageUrl: '',
      toolVideoMaskMode: '',
      toolGenerateAudio: false,
      toolPersonGeneration: '',
      toolSubtitleMode: '',
      toolSubtitleLanguage: '',
      toolSubtitleScript: '',
      toolStoryboardPrompt: '',
      toolEditMode: '',
      toolEditPrompt: '',
      toolReferenceImageUrl: '',
      toolAnalysisType: '',
    };
  }
  if (type === 'human') {
    baseConfig = {
      approvalPrompt: '',
    };
  }

  return {
    ...baseConfig,
    portLayout: getDefaultNodePortLayout(type),
  };
};

export const NODE_DEFAULT_FOCUS_FIELD_BY_TYPE: Partial<Record<NodeType, string>> = {
  start: 'startTask',
  input_text: 'startTask',
  input_image: 'startImageUrls',
  input_video: 'startVideoUrls',
  input_audio: 'startAudioUrls',
  input_file: 'startFileUrls',
  agent: 'agentTaskType',
  tool: 'toolName',
  condition: 'expression',
  router: 'routerPrompt',
  parallel: 'joinMode',
  merge: 'mergeStrategy',
  loop: 'loopCondition',
  human: 'approvalPrompt',
};

const normalizeSelectionId = (value: unknown): string | null => {
  const normalized = String(value || '').trim();
  return normalized || null;
};

export const applySingleNodeSelection = <TData,>(
  inputNodes: Array<Node<TData>>,
  selectedNodeId: unknown,
): Array<Node<TData>> => {
  const targetId = normalizeSelectionId(selectedNodeId);
  if (!Array.isArray(inputNodes) || inputNodes.length === 0) {
    return inputNodes;
  }
  return inputNodes.map((node) => {
    const isSelected = Boolean(targetId && String(node.id) === targetId);
    return node.selected === isSelected ? node : { ...node, selected: isSelected };
  });
};

export const applySingleEdgeSelection = (
  inputEdges: Array<Edge>,
  selectedEdgeId: unknown,
): Array<Edge> => {
  const targetId = normalizeSelectionId(selectedEdgeId);
  if (!Array.isArray(inputEdges) || inputEdges.length === 0) {
    return inputEdges;
  }
  return inputEdges.map((edge) => {
    const isSelected = Boolean(targetId && String(edge.id) === targetId);
    return edge.selected === isSelected ? edge : { ...edge, selected: isSelected };
  });
};

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON']);
const EDITABLE_ROLES = new Set(['combobox', 'textbox', 'spinbutton', 'searchbox']);
const EDITABLE_CONTEXT_SELECTOR = '[contenteditable]:not([contenteditable="false"]), [data-workflow-editor-editable="true"]';
export const WORKFLOW_EDITOR_SCOPE_ATTRIBUTE = 'data-workflow-editor-scope';
const WORKFLOW_EDITOR_SCOPE_SELECTOR = `[${WORKFLOW_EDITOR_SCOPE_ATTRIBUTE}]`;
let workflowEditorScopeCounter = 0;

const toElement = (target: EventTarget | null): Element | null => {
  if (typeof Element === 'undefined') {
    return null;
  }
  return target instanceof Element ? target : null;
};

export const createWorkflowEditorScopeId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `workflow-editor-${crypto.randomUUID()}`;
  }
  workflowEditorScopeCounter += 1;
  return `workflow-editor-${Date.now()}-${workflowEditorScopeCounter}`;
};

export const resolveWorkflowEditorScopeIdFromTarget = (target: EventTarget | null): string | null => {
  const element = toElement(target);
  if (!element) {
    return null;
  }
  const scopeRoot = element.closest(WORKFLOW_EDITOR_SCOPE_SELECTOR);
  const scopeId = String(scopeRoot?.getAttribute(WORKFLOW_EDITOR_SCOPE_ATTRIBUTE) || '').trim();
  return scopeId || null;
};

export const isWorkflowEventForEditorScope = (
  eventScopeId: unknown,
  expectedEditorScopeId: string,
): boolean => {
  const expected = String(expectedEditorScopeId || '').trim();
  const received = String(eventScopeId || '').trim();
  return Boolean(expected && received && expected === received);
};

export const dispatchScopedWorkflowEvent = <TDetail extends Record<string, unknown>>(
  eventName: string,
  target: EventTarget | null,
  detail: TDetail,
): boolean => {
  if (typeof window === 'undefined') {
    return false;
  }
  const editorScopeId = resolveWorkflowEditorScopeIdFromTarget(target);
  if (!editorScopeId) {
    return false;
  }
  window.dispatchEvent(new CustomEvent(eventName, {
    detail: {
      ...detail,
      editorScopeId,
    },
  }));
  return true;
};

export const isEventTargetWithinEditableContext = (target: EventTarget | null): boolean => {
  const element = toElement(target);
  if (!element) {
    return false;
  }

  const tagName = String(element.tagName || '').toUpperCase();
  if (EDITABLE_TAGS.has(tagName)) {
    return true;
  }

  const role = String(element.getAttribute('role') || '').trim().toLowerCase();
  if (EDITABLE_ROLES.has(role)) {
    return true;
  }

  if (typeof HTMLElement !== 'undefined' && element instanceof HTMLElement && element.isContentEditable) {
    return true;
  }

  return Boolean(element.closest(EDITABLE_CONTEXT_SELECTOR));
};

export const isKeyboardEventWithinEditableContext = (
  event: Pick<KeyboardEvent, 'target' | 'composedPath'>,
): boolean => {
  if (isEventTargetWithinEditableContext(event.target ?? null)) {
    return true;
  }
  if (typeof event.composedPath !== 'function') {
    return false;
  }
  return event.composedPath().some((target) => isEventTargetWithinEditableContext(target));
};

const hasValidPosition = (position: Record<string, unknown>): position is { x: number; y: number } => {
  return Boolean(
    position &&
    typeof position.x === 'number' &&
    Number.isFinite(position.x) &&
    typeof position.y === 'number' &&
    Number.isFinite(position.y)
  );
};

const getFallbackNodePosition = (index: number) => {
  const col = index % 4;
  const row = Math.floor(index / 4);
  return {
    x: 120 + col * 240,
    y: 120 + row * 170,
  };
};

export const normalizeLoadedNode = (node: unknown, index: number): Node<WorkflowNodeData> => {
  const safeType = node?.data?.type || node?.type || 'agent';
  const safePosition = hasValidPosition(node?.position)
    ? node.position
    : hasValidPosition(node?.positionAbsolute)
      ? node.positionAbsolute
      : getFallbackNodePosition(index);
  const rawData = { ...(node?.data || {}) };
  const rawPortLayout = rawData?.portLayout;
  const normalizedPortLayout = rawPortLayout && typeof rawPortLayout === 'object' && !Array.isArray(rawPortLayout)
    ? resolveNodePortLayout(safeType, rawPortLayout)
    : undefined;
  const normalizedData: WorkflowNodeData = {
    ...(rawData as WorkflowNodeData),
    type: safeType,
    label: node?.data?.label || node?.label || `节点 ${index + 1}`,
    description: node?.data?.description || '',
    icon: node?.data?.icon || '🔧',
    iconColor: node?.data?.iconColor || 'bg-slate-500',
  };
  if (normalizedPortLayout) {
    normalizedData.portLayout = normalizedPortLayout;
  }

  return {
    ...(node || {}),
    id: String(node?.id || `node-loaded-${index}-${Date.now()}`),
    type: node?.type || safeType,
    position: safePosition,
    data: normalizedData,
  };
};

export const buildPresetPromptValue = (preset: Record<string, unknown>): string => {
  if (!preset) return '';

  const promptExample = preset?.promptExample;
  if (typeof promptExample === 'string') {
    return promptExample;
  }
  if (promptExample && typeof promptExample === 'object' && !Array.isArray(promptExample)) {
    try {
      return JSON.stringify(promptExample);
    } catch {
      return '';
    }
  }

  const promptHint = preset?.promptHint;
  return typeof promptHint === 'string' ? promptHint : '';
};

export interface TemplateSampleInput {
  task: string;
  imageUrl: string;
  imageUrls: string[];
  videoUrl: string;
  videoUrls: string[];
  audioUrl: string;
  audioUrls: string[];
  prompts: string[];
  fileUrl: string;
  fileUrls: string[];
}

export const normalizeTemplateSampleInput = (value: unknown): TemplateSampleInput => {
  const safeValue = isPlainObject(value) ? value : {};
  const imageUrls = Array.from(new Set([
    ...(Array.isArray(safeValue.imageUrls)
      ? safeValue.imageUrls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : []),
    ...(Array.isArray(safeValue.image_urls)
      ? safeValue.image_urls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : []),
  ]));
  const prompts = Array.isArray(safeValue.prompts)
    ? safeValue.prompts.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
    : [];
  const task = String(safeValue.task || safeValue.prompt || safeValue.text || '').trim();
  const imageUrlRaw = String(safeValue.imageUrl || safeValue.image_url || '').trim();
  const imageUrl = imageUrlRaw || imageUrls[0] || '';
  const videoUrls = Array.from(new Set([
    ...(Array.isArray(safeValue.videoUrls)
      ? safeValue.videoUrls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : []),
    ...(Array.isArray(safeValue.video_urls)
      ? safeValue.video_urls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : []),
  ]));
  const videoUrlRaw = String(safeValue.videoUrl || safeValue.video_url || '').trim();
  const videoUrl = videoUrlRaw || videoUrls[0] || '';
  const audioUrls = Array.from(new Set([
    ...(Array.isArray(safeValue.audioUrls)
      ? safeValue.audioUrls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : []),
    ...(Array.isArray(safeValue.audio_urls)
      ? safeValue.audio_urls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : []),
  ]));
  const audioUrlRaw = String(safeValue.audioUrl || safeValue.audio_url || '').trim();
  const audioUrl = audioUrlRaw || audioUrls[0] || '';
  const fileUrls = Array.from(new Set([
    ...(Array.isArray(safeValue.fileUrls)
      ? safeValue.fileUrls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : []),
    ...(Array.isArray(safeValue.file_urls)
      ? safeValue.file_urls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : []),
  ]));
  const fileUrlRaw = String(safeValue.fileUrl || safeValue.file_url || '').trim();
  const fileUrl = fileUrlRaw || fileUrls[0] || '';
  return {
    task,
    imageUrl,
    imageUrls,
    videoUrl,
    videoUrls,
    audioUrl,
    audioUrls,
    prompts,
    fileUrl,
    fileUrls,
  };
};

const WORKFLOW_ALLOWED_AGENT_TASK_TYPES = new Set([
  'chat',
  'image-gen',
  'image-edit',
  'video-gen',
  'audio-gen',
  'vision-understand',
  'data-analysis',
]);

const WORKFLOW_ALLOWED_ANALYSIS_TYPES = new Set([
  'comprehensive',
  'statistics',
  'correlation',
  'trends',
  'distribution',
]);

const WORKFLOW_ALLOWED_IMAGE_EDIT_MODES = new Set([
  'image-chat-edit',
  'image-mask-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext',
  'image-outpainting',
  'virtual-try-on',
]);

const WORKFLOW_ALLOWED_IMAGE_OUTPUT_MIME_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/webp',
]);

const WORKFLOW_ALLOWED_AUDIO_OUTPUT_FORMATS = new Set([
  'mp3',
  'wav',
  'opus',
  'aac',
  'flac',
  'pcm',
]);

const WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS = new Set([
  '16:9',
  '9:16',
]);

const WORKFLOW_ALLOWED_VIDEO_RESOLUTIONS = new Set([
  '720p',
  '1080p',
  '4k',
]);

const WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES = new Set([
  'none',
  'vtt',
  'srt',
  'both',
]);

const WORKFLOW_ALLOWED_VIDEO_PERSON_GENERATION = new Set([
  'dont_allow',
  'allow_adult',
  'allow_all',
]);

const WORKFLOW_ALLOWED_OUTPUT_FORMATS = new Set([
  'text',
  'json',
  'markdown',
]);

const normalizeWorkflowStringList = (value: unknown, maxItems = 12): string[] => {
  if (!Array.isArray(value)) return [];
  const deduped = new Set<string>();
  const normalized: string[] = [];
  for (const item of value) {
    const text = String(item || '').trim();
    if (!text || deduped.has(text)) continue;
    deduped.add(text);
    normalized.push(text);
    if (normalized.length >= maxItems) break;
  }
  return normalized;
};

const clampOptionalInt = (value: unknown, minimum: number, maximum: number): number | null => {
  if (value === undefined || value === null || value === '') return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  const integer = Math.trunc(parsed);
  return Math.max(minimum, Math.min(maximum, integer));
};

const clampOptionalFloat = (value: unknown, minimum: number, maximum: number): number | null => {
  if (value === undefined || value === null || value === '') return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.max(minimum, Math.min(maximum, parsed));
};

const normalizeOptionalChoice = (value: unknown, allowed: Set<string>): string | null => {
  const text = String(value || '').trim().toLowerCase();
  if (!text) return null;
  return allowed.has(text) ? text : null;
};

const normalizeOptionalString = (value: unknown, maxLength = 128): string | null => {
  const text = String(value || '').trim();
  if (!text) return null;
  return text.length > maxLength ? text.slice(0, maxLength) : text;
};

const normalizeVideoResolutionForExecute = (value: unknown): string | null => {
  const raw = String(value || '').trim();
  if (!raw) return null;

  const normalized = raw.toLowerCase().replace(/\s+/g, '').replace(/\*/g, 'x').replace(/×/g, 'x');
  const aliases: Record<string, string> = {
    '1k': '720p',
    '720p': '720p',
    '1280': '720p',
    '1280x720': '720p',
    '720x1280': '720p',
    '2k': '1080p',
    '1080p': '1080p',
    '1920': '1080p',
    '1920x1080': '1080p',
    '1080x1920': '1080p',
    '4k': '4k',
    '2160p': '4k',
    '3840x2160': '4k',
    '2160x3840': '4k',
  };

  if (normalized in aliases) {
    return aliases[normalized];
  }
  if (WORKFLOW_ALLOWED_VIDEO_RESOLUTIONS.has(normalized)) {
    return normalized;
  }
  return null;
};

const normalizeAgentTaskTypeForExecute = (value: unknown): string => {
  const raw = String(value || '').trim().toLowerCase().replace(/_/g, '-');
  const aliases: Record<string, string> = {
    'vision-analyze': 'vision-understand',
    'image-analyze': 'vision-understand',
    'image-understand': 'vision-understand',
    'table-analysis': 'data-analysis',
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
  };
  const normalized = aliases[raw] || raw;
  return WORKFLOW_ALLOWED_AGENT_TASK_TYPES.has(normalized) ? normalized : 'chat';
};

const normalizeAnalysisTypeForExecute = (value: unknown): string => {
  const raw = String(value || '').trim().toLowerCase();
  const aliases: Record<string, string> = {
    summary: 'statistics',
    stats: 'statistics',
    statistic: 'statistics',
    trend: 'trends',
    anomaly: 'distribution',
    anomalies: 'distribution',
    all: 'comprehensive',
  };
  const normalized = aliases[raw] || raw;
  return WORKFLOW_ALLOWED_ANALYSIS_TYPES.has(normalized) ? normalized : 'comprehensive';
};

const normalizeImageEditModeForExecute = (value: unknown): string | null => {
  const normalized = String(value || '').trim().toLowerCase().replace(/_/g, '-');
  if (!normalized) return null;
  return WORKFLOW_ALLOWED_IMAGE_EDIT_MODES.has(normalized) ? normalized : null;
};

const normalizeNodeSizeForExecute = (value: unknown, minimum: number, maximum: number): number | undefined => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return undefined;
  return Math.max(minimum, Math.min(maximum, Math.round(parsed)));
};

export const normalizeWorkflowInputForExecute = (
  rawInput: unknown,
  fallbackTask: string,
): Record<string, unknown> => {
  const payload = isPlainObject(rawInput) ? { ...rawInput } : {};
  const task = String(
    payload.task
    || payload.prompt
    || payload.text
    || fallbackTask
    || ''
  ).trim();
  payload.task = task || String(fallbackTask || '').trim();

  let imageUrls = normalizeWorkflowStringList(payload.imageUrls);
  if (imageUrls.length === 0) {
    imageUrls = normalizeWorkflowStringList(payload.image_urls);
  }
  const singleImageUrl = String(payload.imageUrl || payload.image_url || '').trim();
  if (singleImageUrl) {
    imageUrls = normalizeWorkflowStringList([singleImageUrl, ...imageUrls]);
  }
  if (imageUrls.length > 0) {
    payload.imageUrls = imageUrls;
    payload.imageUrl = imageUrls[0];
  } else {
    delete payload.imageUrls;
    delete payload.imageUrl;
    delete payload.image_url;
  }

  let videoUrls = normalizeWorkflowStringList(payload.videoUrls);
  if (videoUrls.length === 0) {
    videoUrls = normalizeWorkflowStringList(payload.video_urls);
  }
  const singleVideoUrl = String(payload.videoUrl || payload.video_url || '').trim();
  if (singleVideoUrl) {
    videoUrls = normalizeWorkflowStringList([singleVideoUrl, ...videoUrls]);
  }
  if (videoUrls.length > 0) {
    payload.videoUrls = videoUrls;
    payload.videoUrl = videoUrls[0];
  } else {
    delete payload.videoUrls;
    delete payload.videoUrl;
    delete payload.video_url;
  }

  let audioUrls = normalizeWorkflowStringList(payload.audioUrls);
  if (audioUrls.length === 0) {
    audioUrls = normalizeWorkflowStringList(payload.audio_urls);
  }
  const singleAudioUrl = String(payload.audioUrl || payload.audio_url || '').trim();
  if (singleAudioUrl) {
    audioUrls = normalizeWorkflowStringList([singleAudioUrl, ...audioUrls]);
  }
  if (audioUrls.length > 0) {
    payload.audioUrls = audioUrls;
    payload.audioUrl = audioUrls[0];
  } else {
    delete payload.audioUrls;
    delete payload.audioUrl;
    delete payload.audio_url;
  }

  let fileUrls = normalizeWorkflowStringList(payload.fileUrls);
  if (fileUrls.length === 0) {
    fileUrls = normalizeWorkflowStringList(payload.file_urls);
  }
  const singleFileUrl = String(payload.fileUrl || payload.file_url || '').trim();
  if (singleFileUrl) {
    fileUrls = normalizeWorkflowStringList([singleFileUrl, ...fileUrls]);
  }
  if (fileUrls.length > 0) {
    payload.fileUrls = fileUrls;
    payload.fileUrl = fileUrls[0];
  } else {
    delete payload.fileUrls;
    delete payload.fileUrl;
    delete payload.file_url;
  }

  if (payload.analysisType !== undefined) {
    payload.analysisType = normalizeAnalysisTypeForExecute(payload.analysisType);
  }
  if (payload.analysis_type !== undefined) {
    payload.analysis_type = normalizeAnalysisTypeForExecute(payload.analysis_type);
  }

  return payload;
};

export const normalizeWorkflowNodeDataForExecute = (
  rawData: Partial<WorkflowNodeData> & Record<string, unknown>,
): Record<string, unknown> => {
  const data: Record<string, unknown> = isPlainObject(rawData) ? { ...rawData } : {};

  const taskType = data.agentTaskType ?? data.agent_task_type;
  let normalizedTaskType = '';
  if (taskType !== undefined) {
    normalizedTaskType = normalizeAgentTaskTypeForExecute(taskType);
    data.agentTaskType = normalizedTaskType;
    data.agent_task_type = normalizedTaskType;
  }

  const analysisTypeCandidates = [
    'toolAnalysisType',
    'tool_analysis_type',
    'analysisType',
    'analysis_type',
  ];
  for (const fieldName of analysisTypeCandidates) {
    if (data[fieldName] !== undefined) {
      data[fieldName] = normalizeAnalysisTypeForExecute(data[fieldName]);
    }
  }

  for (const fieldName of ['agentNumberOfImages', 'toolNumberOfImages', 'numberOfImages', 'number_of_images']) {
    if (data[fieldName] === undefined) continue;
    const normalized = clampOptionalInt(data[fieldName], 1, 8);
    if (normalized === null) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }

  if (data.agentImageEditMaxRetries !== undefined) {
    const retries = clampOptionalInt(data.agentImageEditMaxRetries, 0, 3);
    data.agentImageEditMaxRetries = retries === null ? 1 : retries;
  }
  if (data.agent_image_edit_max_retries !== undefined) {
    const retries = clampOptionalInt(data.agent_image_edit_max_retries, 0, 3);
    data.agent_image_edit_max_retries = retries === null ? 1 : retries;
  }

  if (data.agentProductMatchThreshold !== undefined) {
    const threshold = clampOptionalInt(data.agentProductMatchThreshold, 50, 95);
    data.agentProductMatchThreshold = threshold === null ? 70 : threshold;
  }
  if (data.agent_product_match_threshold !== undefined) {
    const threshold = clampOptionalInt(data.agent_product_match_threshold, 50, 95);
    data.agent_product_match_threshold = threshold === null ? 70 : threshold;
  }

  for (const fieldName of ['agentOutputMimeType', 'toolOutputMimeType']) {
    if (data[fieldName] === undefined) continue;
    const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_IMAGE_OUTPUT_MIME_TYPES);
    if (!normalized) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }

  for (const fieldName of ['agentOutputFormat', 'outputFormat']) {
    if (data[fieldName] === undefined) continue;
    const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_OUTPUT_FORMATS);
    if (!normalized) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }

  for (const fieldName of ['toolEditMode', 'agentEditMode']) {
    if (data[fieldName] === undefined) continue;
    const normalized = normalizeImageEditModeForExecute(data[fieldName]);
    if (!normalized) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }

  for (const [listField, singleField] of [
    ['startImageUrls', 'startImageUrl'],
    ['startVideoUrls', 'startVideoUrl'],
    ['startAudioUrls', 'startAudioUrl'],
    ['startFileUrls', 'startFileUrl'],
  ]) {
    let listValues = normalizeWorkflowStringList(data[listField]);
    const singleValue = String(data[singleField] || '').trim();
    if (singleValue) {
      listValues = normalizeWorkflowStringList([singleValue, ...listValues]);
    }
    if (listValues.length > 0) {
      data[listField] = listValues;
      data[singleField] = listValues[0];
    } else {
      delete data[listField];
      delete data[singleField];
    }
  }

  if (normalizedTaskType === 'video-gen') {
    for (const fieldName of [
      'agentVideoDurationSeconds',
      'agent_video_duration_seconds',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalInt(data[fieldName], 1, 20);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentVideoExtensionCount',
      'agent_video_extension_count',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalInt(data[fieldName], 0, 20);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentVideoAspectRatio',
      'agent_video_aspect_ratio',
      'videoAspectRatio',
      'video_aspect_ratio',
      'agentAspectRatio',
      'agent_aspect_ratio',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentVideoResolution',
      'agent_video_resolution',
      'videoResolution',
      'video_resolution',
      'agentResolutionTier',
      'agent_resolution_tier',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeVideoResolutionForExecute(data[fieldName]);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentContinueFromPreviousVideo',
      'agent_continue_from_previous_video',
      'agentContinueFromPreviousLastFrame',
      'agent_continue_from_previous_last_frame',
      'agentGenerateAudio',
      'agent_generate_audio',
      'generateAudio',
      'generate_audio',
    ]) {
      if (data[fieldName] === undefined) continue;
      data[fieldName] = Boolean(data[fieldName]);
    }

    for (const fieldName of [
      'agentPersonGeneration',
      'agent_person_generation',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_VIDEO_PERSON_GENERATION);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentSubtitleMode',
      'agent_subtitle_mode',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentSubtitleLanguage',
      'agent_subtitle_language',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 32);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentSubtitleScript',
      'agent_subtitle_script',
      'agentStoryboardPrompt',
      'agent_storyboard_prompt',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 4000);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentSourceVideoUrl',
      'agent_source_video_url',
      'agentLastFrameImageUrl',
      'agent_last_frame_image_url',
      'agentVideoMaskImageUrl',
      'agent_video_mask_image_url',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 2048);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentVideoMaskMode',
      'agent_video_mask_mode',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 64);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }
  }

  const normalizedToolName = String(data.toolName || data.tool_name || '').trim().toLowerCase().replace(/-/g, '_');
  if (normalizedToolName === 'video_generate' || normalizedToolName === 'generate_video' || normalizedToolName === 'video_gen') {
    for (const fieldName of [
      'toolVideoDurationSeconds',
      'tool_video_duration_seconds',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalInt(data[fieldName], 1, 20);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolVideoExtensionCount',
      'tool_video_extension_count',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalInt(data[fieldName], 0, 20);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolAspectRatio',
      'tool_aspect_ratio',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolResolutionTier',
      'tool_resolution_tier',
      'toolVideoResolution',
      'tool_video_resolution',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeVideoResolutionForExecute(data[fieldName]);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolGenerateAudio',
      'tool_generate_audio',
    ]) {
      if (data[fieldName] === undefined) continue;
      data[fieldName] = Boolean(data[fieldName]);
    }

    for (const fieldName of [
      'toolPersonGeneration',
      'tool_person_generation',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_VIDEO_PERSON_GENERATION);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolSubtitleMode',
      'tool_subtitle_mode',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolSubtitleLanguage',
      'tool_subtitle_language',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 32);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolSubtitleScript',
      'tool_subtitle_script',
      'toolStoryboardPrompt',
      'tool_storyboard_prompt',
      'toolSourceVideoUrl',
      'tool_source_video_url',
      'toolLastFrameImageUrl',
      'tool_last_frame_image_url',
      'toolVideoMaskImageUrl',
      'tool_video_mask_image_url',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 4000);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolVideoMaskMode',
      'tool_video_mask_mode',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 64);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }
  }

  if (normalizedTaskType === 'audio-gen') {
    for (const fieldName of [
      'agentSpeechSpeed',
      'agent_speech_speed',
      'agentAudioSpeed',
      'agent_audio_speed',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalFloat(data[fieldName], 0.25, 4.0);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentAudioFormat',
      'agent_audio_format',
      'agentSpeechFormat',
      'agent_speech_format',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_AUDIO_OUTPUT_FORMATS);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['agentVoice', 'agent_voice']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 64);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }
  }

  const nodeWidth = normalizeNodeSizeForExecute(data.nodeWidth, 135, 720);
  if (nodeWidth !== undefined) {
    data.nodeWidth = nodeWidth;
  } else if (data.nodeWidth !== undefined) {
    delete data.nodeWidth;
  }

  const nodeHeight = normalizeNodeSizeForExecute(data.nodeHeight, 1, 1200);
  if (nodeHeight !== undefined) {
    data.nodeHeight = nodeHeight;
  } else if (data.nodeHeight !== undefined) {
    delete data.nodeHeight;
  }

  return data;
};

export const resolveTemplateInputPlaceholder = (
  rawValue: unknown,
  sampleInput: TemplateSampleInput,
  fallbackValue = '',
) => {
  const text = String(rawValue || '').trim();
  if (!text) {
    return String(fallbackValue || '').trim();
  }

  const replaceByIndex = (sourceText: string, pattern: RegExp, source: string[]) =>
    sourceText.replace(pattern, (_, indexText: string) => {
      const index = Number(indexText);
      if (!Number.isFinite(index) || index < 0) return '';
      return source[index] || '';
    });

  let resolved = text;
  resolved = replaceByIndex(resolved, /\{\{\s*input\.imageUrls\[(\d+)\]\s*\}\}/g, sampleInput.imageUrls);
  resolved = replaceByIndex(resolved, /\{\{\s*input\.videoUrls\[(\d+)\]\s*\}\}/g, sampleInput.videoUrls);
  resolved = replaceByIndex(resolved, /\{\{\s*input\.audioUrls\[(\d+)\]\s*\}\}/g, sampleInput.audioUrls);
  resolved = replaceByIndex(resolved, /\{\{\s*input\.fileUrls\[(\d+)\]\s*\}\}/g, sampleInput.fileUrls);
  resolved = replaceByIndex(resolved, /\{\{\s*input\.prompts\[(\d+)\]\s*\}\}/g, sampleInput.prompts);
  resolved = resolved
    .replace(/\{\{\s*input\.(?:task|prompt|text)\s*\}\}/g, sampleInput.task)
    .replace(/\{\{\s*input\.imageUrl\s*\}\}/g, sampleInput.imageUrl)
    .replace(/\{\{\s*input\.videoUrl\s*\}\}/g, sampleInput.videoUrl)
    .replace(/\{\{\s*input\.audioUrl\s*\}\}/g, sampleInput.audioUrl)
    .replace(/\{\{\s*input\.fileUrl\s*\}\}/g, sampleInput.fileUrl)
    .trim();

  if (resolved.includes('{{') || resolved.includes('}}')) {
    const fallback = String(fallbackValue || '').trim();
    return fallback || text;
  }
  return resolved || String(fallbackValue || '').trim();
};

const normalizeAgentName = (value: string) => String(value || '').trim().toLowerCase();

export const isTerminalExecutionStatus = (status: string) => (
  status === 'completed'
  || status === 'failed'
  || status === 'cancelled'
);

export const applyAgentBindingsToNodes = (
  inputNodes: Node<WorkflowNodeData>[],
  agents: AgentDef[],
): Node<WorkflowNodeData>[] => {
  if (!Array.isArray(inputNodes) || inputNodes.length === 0 || !Array.isArray(agents) || agents.length === 0) {
    return inputNodes;
  }

  const byId = new Map<string, AgentDef>();
  const byName = new Map<string, AgentDef>();
  agents.forEach((agent) => {
    const id = String(agent?.id || '').trim();
    const name = String(agent?.name || '').trim();
    if (id) byId.set(id, agent);
    if (name) byName.set(normalizeAgentName(name), agent);
  });

  return inputNodes.map((node) => {
    const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
    if (nodeType !== 'agent') {
      return node;
    }
    const data = (node.data || {}) as WorkflowNodeData;
    const currentAgentId = String(data.agentId || '').trim();
    const currentAgentName = String(data.agentName || '').trim();

    let matched: AgentDef | undefined;
    if (currentAgentId) {
      matched = byId.get(currentAgentId);
    }
    if (!matched && currentAgentName) {
      matched = byName.get(normalizeAgentName(currentAgentName));
    }
    if (!matched) {
      return node;
    }

    const matchedId = String(matched.id || '').trim();
    const matchedName = String(matched.name || '').trim();
    const matchedProviderId = String(matched.providerId || '').trim();
    const matchedModelId = String(matched.modelId || '').trim();

    return {
      ...node,
      data: {
        ...data,
        agentId: currentAgentId || matchedId,
        agentName: currentAgentName || matchedName,
        agentProviderId: String(data.agentProviderId || '').trim() || matchedProviderId,
        agentModelId: String(data.agentModelId || '').trim() || matchedModelId,
      } as WorkflowNodeData,
    };
  });
};

export const buildWorkflowStructureFingerprint = (
  workflowNodes: Array<Node<WorkflowNodeData>>,
  workflowEdges: Array<Edge>,
): string => {
  const nodeTokens = workflowNodes
    .map((node) => `${String(node?.id || '').trim()}::${String(node?.data?.type || node?.type || '').trim().toLowerCase()}`)
    .sort()
    .join('|');
  const edgeTokens = workflowEdges
    .map((edge) => `${String(edge?.source || '').trim()}->${String(edge?.target || '').trim()}`)
    .sort()
    .join('|');
  return `${workflowNodes.length}:${workflowEdges.length}:${nodeTokens}::${edgeTokens}`;
};

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

export const applySingleNodeSelection = <TData>(
  inputNodes: Array<Node<TData>>,
  selectedNodeId: unknown
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
  selectedEdgeId: unknown
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
const EDITABLE_CONTEXT_SELECTOR =
  '[contenteditable]:not([contenteditable="false"]), [data-workflow-editor-editable="true"]';
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

export const resolveWorkflowEditorScopeIdFromTarget = (
  target: EventTarget | null
): string | null => {
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
  expectedEditorScopeId: string
): boolean => {
  const expected = String(expectedEditorScopeId || '').trim();
  const received = String(eventScopeId || '').trim();
  return Boolean(expected && received && expected === received);
};

export const dispatchScopedWorkflowEvent = <TDetail extends Record<string, unknown>>(
  eventName: string,
  target: EventTarget | null,
  detail: TDetail
): boolean => {
  if (typeof window === 'undefined') {
    return false;
  }
  const editorScopeId = resolveWorkflowEditorScopeIdFromTarget(target);
  if (!editorScopeId) {
    return false;
  }
  window.dispatchEvent(
    new CustomEvent(eventName, {
      detail: {
        ...detail,
        editorScopeId,
      },
    })
  );
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

  const role = String(element.getAttribute('role') || '')
    .trim()
    .toLowerCase();
  if (EDITABLE_ROLES.has(role)) {
    return true;
  }

  if (
    typeof HTMLElement !== 'undefined' &&
    element instanceof HTMLElement &&
    element.isContentEditable
  ) {
    return true;
  }

  return Boolean(element.closest(EDITABLE_CONTEXT_SELECTOR));
};

export const isKeyboardEventWithinEditableContext = (
  event: Pick<KeyboardEvent, 'target' | 'composedPath'>
): boolean => {
  if (isEventTargetWithinEditableContext(event.target ?? null)) {
    return true;
  }
  if (typeof event.composedPath !== 'function') {
    return false;
  }
  return event.composedPath().some((target) => isEventTargetWithinEditableContext(target));
};

const hasValidPosition = (position: unknown): position is { x: number; y: number } => {
  if (!position || typeof position !== 'object') return false;
  const p = position as Record<string, unknown>;
  return (
    typeof p.x === 'number' &&
    Number.isFinite(p.x) &&
    typeof p.y === 'number' &&
    Number.isFinite(p.y)
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
  const n = (node && typeof node === 'object' ? node : {}) as Record<string, unknown>;
  const nData = (n.data && typeof n.data === 'object' ? n.data : {}) as Record<string, unknown>;
  const safeType = (nData.type as string) || (n.type as string) || 'agent';
  const safePosition = hasValidPosition(n.position)
    ? (n.position as { x: number; y: number })
    : hasValidPosition(n.positionAbsolute)
      ? (n.positionAbsolute as { x: number; y: number })
      : getFallbackNodePosition(index);
  const rawData = { ...nData };
  const rawPortLayout = rawData.portLayout;
  const normalizedPortLayout =
    rawPortLayout && typeof rawPortLayout === 'object' && !Array.isArray(rawPortLayout)
      ? resolveNodePortLayout(safeType, rawPortLayout as Record<string, unknown>)
      : undefined;
  const normalizedData: WorkflowNodeData = {
    // rawData 是后端模板节点 data 字段（未类型化），通过 unknown 中转避免 TS 拒绝
    ...(rawData as unknown as WorkflowNodeData),
    type: safeType,
    label: (nData.label as string) || (n.label as string) || `节点 ${index + 1}`,
    description: (nData.description as string) || '',
    icon: (nData.icon as string) || '🔧',
    iconColor: (nData.iconColor as string) || 'bg-slate-500',
  };
  if (normalizedPortLayout) {
    normalizedData.portLayout = normalizedPortLayout;
  }

  return {
    ...(n as object),
    id: String(n.id || `node-loaded-${index}-${Date.now()}`),
    type: (n.type as string) || safeType,
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
  const imageUrls = Array.from(
    new Set([
      ...(Array.isArray(safeValue.imageUrls)
        ? safeValue.imageUrls
            .map((item: Record<string, unknown>) => String(item || '').trim())
            .filter(Boolean)
        : []),
      ...(Array.isArray(safeValue.image_urls)
        ? safeValue.image_urls
            .map((item: Record<string, unknown>) => String(item || '').trim())
            .filter(Boolean)
        : []),
    ])
  );
  const prompts = Array.isArray(safeValue.prompts)
    ? safeValue.prompts
        .map((item: Record<string, unknown>) => String(item || '').trim())
        .filter(Boolean)
    : [];
  const task = String(safeValue.task || safeValue.prompt || safeValue.text || '').trim();
  const imageUrlRaw = String(safeValue.imageUrl || safeValue.image_url || '').trim();
  const imageUrl = imageUrlRaw || imageUrls[0] || '';
  const videoUrls = Array.from(
    new Set([
      ...(Array.isArray(safeValue.videoUrls)
        ? safeValue.videoUrls
            .map((item: Record<string, unknown>) => String(item || '').trim())
            .filter(Boolean)
        : []),
      ...(Array.isArray(safeValue.video_urls)
        ? safeValue.video_urls
            .map((item: Record<string, unknown>) => String(item || '').trim())
            .filter(Boolean)
        : []),
    ])
  );
  const videoUrlRaw = String(safeValue.videoUrl || safeValue.video_url || '').trim();
  const videoUrl = videoUrlRaw || videoUrls[0] || '';
  const audioUrls = Array.from(
    new Set([
      ...(Array.isArray(safeValue.audioUrls)
        ? safeValue.audioUrls
            .map((item: Record<string, unknown>) => String(item || '').trim())
            .filter(Boolean)
        : []),
      ...(Array.isArray(safeValue.audio_urls)
        ? safeValue.audio_urls
            .map((item: Record<string, unknown>) => String(item || '').trim())
            .filter(Boolean)
        : []),
    ])
  );
  const audioUrlRaw = String(safeValue.audioUrl || safeValue.audio_url || '').trim();
  const audioUrl = audioUrlRaw || audioUrls[0] || '';
  const fileUrls = Array.from(
    new Set([
      ...(Array.isArray(safeValue.fileUrls)
        ? safeValue.fileUrls
            .map((item: Record<string, unknown>) => String(item || '').trim())
            .filter(Boolean)
        : []),
      ...(Array.isArray(safeValue.file_urls)
        ? safeValue.file_urls
            .map((item: Record<string, unknown>) => String(item || '').trim())
            .filter(Boolean)
        : []),
    ])
  );
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


export const resolveTemplateInputPlaceholder = (
  rawValue: unknown,
  sampleInput: TemplateSampleInput,
  fallbackValue = ''
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
  resolved = replaceByIndex(
    resolved,
    /\{\{\s*input\.imageUrls\[(\d+)\]\s*\}\}/g,
    sampleInput.imageUrls
  );
  resolved = replaceByIndex(
    resolved,
    /\{\{\s*input\.videoUrls\[(\d+)\]\s*\}\}/g,
    sampleInput.videoUrls
  );
  resolved = replaceByIndex(
    resolved,
    /\{\{\s*input\.audioUrls\[(\d+)\]\s*\}\}/g,
    sampleInput.audioUrls
  );
  resolved = replaceByIndex(
    resolved,
    /\{\{\s*input\.fileUrls\[(\d+)\]\s*\}\}/g,
    sampleInput.fileUrls
  );
  resolved = replaceByIndex(
    resolved,
    /\{\{\s*input\.prompts\[(\d+)\]\s*\}\}/g,
    sampleInput.prompts
  );
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

const normalizeAgentName = (value: string) =>
  String(value || '')
    .trim()
    .toLowerCase();

export const isTerminalExecutionStatus = (status: string) =>
  status === 'completed' || status === 'failed' || status === 'cancelled';

export const applyAgentBindingsToNodes = (
  inputNodes: Node<WorkflowNodeData>[],
  agents: AgentDef[]
): Node<WorkflowNodeData>[] => {
  if (
    !Array.isArray(inputNodes) ||
    inputNodes.length === 0 ||
    !Array.isArray(agents) ||
    agents.length === 0
  ) {
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
  workflowEdges: Array<Edge>
): string => {
  const nodeTokens = workflowNodes
    .map(
      (node) =>
        `${String(node?.id || '').trim()}::${String(node?.data?.type || node?.type || '')
          .trim()
          .toLowerCase()}`
    )
    .sort()
    .join('|');
  const edgeTokens = workflowEdges
    .map((edge) => `${String(edge?.source || '').trim()}->${String(edge?.target || '').trim()}`)
    .sort()
    .join('|');
  return `${workflowNodes.length}:${workflowEdges.length}:${nodeTokens}::${edgeTokens}`;
};

// Re-export normalize functions for backwards compat (抽离至 ./workflowExecuteNormalizer)
export {
  normalizeWorkflowInputForExecute,
  normalizeWorkflowNodeDataForExecute,
} from './workflowExecuteNormalizer';

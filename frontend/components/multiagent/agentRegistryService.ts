import { requestJson } from '../../services/http';
import type { AgentDef } from './types';
import type { AgentTaskType } from './providerModelUtils';

export const AGENT_REGISTRY_UPDATED_EVENT = 'multiagent:agent-registry-updated';

export type AgentTaskFilter = AgentTaskType | 'all';

export const AGENT_TASK_FILTER_OPTIONS: AgentTaskFilter[] = [
  'all',
  'chat',
  'image-gen',
  'image-edit',
  'video-gen',
  'audio-gen',
  'vision-understand',
  'data-analysis',
];

export const AGENT_TASK_FILTER_LABELS: Record<AgentTaskFilter, string> = {
  all: '全部',
  chat: '💬 对话',
  'image-gen': '🖼️ 图片生成',
  'image-edit': '🪄 图片编辑',
  'video-gen': '🎬 视频生成',
  'audio-gen': '🎧 音频生成',
  'vision-understand': '🧠 图片理解',
  'data-analysis': '📊 数据分析',
};

export interface AgentListFetchOptions {
  includeInactive?: boolean;
  search?: string;
  status?: 'active' | 'inactive';
  taskType?: AgentTaskFilter;
  signal?: AbortSignal;
}

export interface AgentListFetchResult {
  agents: AgentDef[];
  count: number;
  activeCount: number;
  inactiveCount: number;
  taskCounts: Record<AgentTaskFilter, number>;
}

const toSafeString = (value: unknown): string => String(value ?? '').trim();

const normalizeAgentTaskFilter = (value: unknown): AgentTaskFilter => {
  const normalized = toSafeString(value).toLowerCase().replace(/_/g, '-');
  return AGENT_TASK_FILTER_OPTIONS.includes(normalized as AgentTaskFilter)
    ? (normalized as AgentTaskFilter)
    : 'all';
};

const parseAgentTaskFilterKey = (value: unknown): AgentTaskFilter | null => {
  const normalized = toSafeString(value).toLowerCase().replace(/_/g, '-');
  return AGENT_TASK_FILTER_OPTIONS.includes(normalized as AgentTaskFilter)
    ? (normalized as AgentTaskFilter)
    : null;
};

const inferLegacyRuntimeSupport = (agent: Record<string, unknown>): boolean => {
  const normalizedAgentType = toSafeString(agent?.agentType).toLowerCase();
  const normalizedProviderId = toSafeString(agent?.providerId).toLowerCase();
  return (
    ['adk', 'google-adk'].includes(normalizedAgentType) && normalizedProviderId.startsWith('google')
  );
};

const normalizeAgentRuntime = (agent: Record<string, unknown>): AgentDef['runtime'] => {
  const runtime = agent?.runtime;
  if (!runtime || typeof runtime !== 'object') {
    const fallbackSupportsSessions = inferLegacyRuntimeSupport(agent);
    return {
      kind: fallbackSupportsSessions ? 'google-adk' : '',
      label: fallbackSupportsSessions ? 'Google ADK' : '',
      supportsRun: fallbackSupportsSessions,
      supportsLiveRun: fallbackSupportsSessions,
      supportsSessions: fallbackSupportsSessions,
      supportsMemory: fallbackSupportsSessions,
      supportsOfficialOrchestration: fallbackSupportsSessions,
    };
  }

  const r = runtime as Record<string, unknown>;
  return {
    kind: toSafeString(r.kind),
    label: toSafeString(r.label),
    supportsRun: Boolean(r.supportsRun),
    supportsLiveRun: Boolean(r.supportsLiveRun),
    supportsSessions: Boolean(r.supportsSessions),
    supportsMemory: Boolean(r.supportsMemory),
    supportsOfficialOrchestration: Boolean(r.supportsOfficialOrchestration),
  };
};

const normalizeAgentSource = (agent: unknown, runtime: AgentDef['runtime']): AgentDef['source'] => {
  const a = (agent && typeof agent === 'object' ? agent : {}) as Record<string, unknown>;
  const source = a.source;
  if (source && typeof source === 'object') {
    const s = source as Record<string, unknown>;
    return {
      kind: toSafeString(s.kind),
      label: toSafeString(s.label),
      isSystem: Boolean(s.isSystem),
    };
  }

  const normalizedAgentType = toSafeString(a.agentType).toLowerCase();
  const normalizedProviderId = toSafeString(a.providerId).toLowerCase();
  if (normalizedAgentType === 'seed') {
    return {
      kind: 'seed',
      label: '官方 Seed',
      isSystem: true,
    };
  }
  if (
    runtime?.kind === 'google-adk' ||
    (['adk', 'google-adk'].includes(normalizedAgentType) &&
      normalizedProviderId.startsWith('google'))
  ) {
    return {
      kind: 'google-runtime',
      label: 'Google runtime',
      isSystem: false,
    };
  }
  if (normalizedAgentType === 'interactions') {
    return {
      kind: 'vertex-interactions',
      label: 'Vertex Interactions',
      isSystem: false,
    };
  }
  return {
    kind: 'user',
    label: '用户创建',
    isSystem: false,
  };
};

export const createEmptyAgentTaskCounts = (): Record<AgentTaskFilter, number> => ({
  all: 0,
  chat: 0,
  'image-gen': 0,
  'image-edit': 0,
  'video-gen': 0,
  'audio-gen': 0,
  'vision-understand': 0,
  'data-analysis': 0,
});

const normalizeAgentTaskCounts = (
  payload: Record<string, unknown>
): Record<AgentTaskFilter, number> => {
  const base = createEmptyAgentTaskCounts();
  const rawCounts = payload?.taskCounts;
  if (!rawCounts || typeof rawCounts !== 'object') {
    return base;
  }

  for (const [key, value] of Object.entries(rawCounts as Record<string, unknown>)) {
    const taskType = parseAgentTaskFilterKey(key);
    if (taskType && typeof value === 'number' && Number.isFinite(value)) {
      base[taskType] = value;
    }
  }
  return base;
};

export const createDefaultAgentCard = () => ({
  defaults: {
    defaultTaskType: 'chat' as const,
    imageGeneration: {
      aspectRatio: '1:1',
      resolutionTier: '1K',
      numberOfImages: 1,
      imageStyle: '',
      outputMimeType: 'image/png',
      negativePrompt: '',
      promptExtend: false,
      addMagicSuffix: true,
    },
    imageEdit: {
      editMode: 'image-chat-edit',
      aspectRatio: '',
      imageSize: '1K',
      resolutionTier: '1K',
      numberOfImages: 1,
      outputMimeType: 'image/png',
      promptExtend: false,
      addMagicSuffix: true,
      preserveProductIdentity: true,
      productMatchThreshold: 72,
      maxRetries: 2,
      outputLanguage: 'en',
    },
    videoGeneration: {
      aspectRatio: '16:9',
      resolution: '1080p',
      durationSeconds: 5,
      videoExtensionCount: 0,
      continueFromPreviousVideo: false,
      continueFromPreviousLastFrame: false,
      generateAudio: true,
      subtitleMode: 'none',
      subtitleLanguage: '',
      subtitleScript: '',
      storyboardPrompt: '',
      negativePrompt: '',
      seed: -1,
      promptExtend: false,
    },
    audioGeneration: {
      voice: '',
      responseFormat: 'mp3',
      speed: 1,
    },
    visionUnderstand: {
      outputFormat: 'json',
    },
    dataAnalysis: {
      outputFormat: 'markdown',
    },
  },
});

const normalizeAgentItem = (agentUnknown: unknown): AgentDef | null => {
  const agent = agentUnknown as Record<string, unknown>;
  const id = toSafeString(agent?.id);
  if (!id) return null;
  const runtime = normalizeAgentRuntime(agent);
  const source = normalizeAgentSource(agent, runtime);
  return {
    id,
    name: toSafeString(agent?.name) || '未命名 Agent',
    description: toSafeString(agent?.description),
    agentType: toSafeString(agent?.agentType || 'custom') || 'custom',
    providerId: toSafeString(agent?.providerId),
    modelId: toSafeString(agent?.modelId),
    systemPrompt: toSafeString(agent?.systemPrompt),
    temperature: typeof agent?.temperature === 'number' ? agent.temperature : 0.7,
    maxTokens: typeof agent?.maxTokens === 'number' ? agent.maxTokens : 4096,
    icon: toSafeString(agent?.icon) || '🤖',
    color: toSafeString(agent?.color) || '#14b8a6',
    status: toSafeString(agent?.status) || 'active',
    runtime,
    source,
    supportsRuntimeSessions: Boolean(agent?.supportsRuntimeSessions ?? runtime?.supportsSessions),
    supportsRuntimeLiveRun: Boolean(agent?.supportsRuntimeLiveRun ?? runtime?.supportsLiveRun),
    supportsRuntimeMemory: Boolean(agent?.supportsRuntimeMemory ?? runtime?.supportsMemory),
    supportsOfficialOrchestration: Boolean(
      agent?.supportsOfficialOrchestration ?? runtime?.supportsOfficialOrchestration
    ),
    agentCard: agent?.agentCard || createDefaultAgentCard(),
  };
};

const extractAgentArray = (payload: Record<string, unknown>): unknown[] => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.agents)) return payload.agents;
  return [];
};

export const normalizeAgentListPayload = (payload: Record<string, unknown>): AgentDef[] => {
  return extractAgentArray(payload)
    .map(normalizeAgentItem)
    .filter((agent): agent is AgentDef => Boolean(agent));
};

export const fetchAgentList = async (
  options: AgentListFetchOptions = {}
): Promise<AgentListFetchResult> => {
  const params = new URLSearchParams();
  if (options.includeInactive) params.set('includeInactive', 'true');
  if (toSafeString(options.search)) params.set('search', toSafeString(options.search));
  if (options.status) params.set('status', options.status);
  if (options.taskType) params.set('taskType', options.taskType);
  const query = params.toString();
  const url = query ? `/api/agents?${query}` : '/api/agents';

  const payload = await requestJson<Record<string, unknown>>(url, {
    withAuth: true,
    signal: options.signal,
    timeoutMs: 0,
    errorMessage: 'Failed to fetch agents',
  });
  const agents = normalizeAgentListPayload(payload);
  const count = typeof payload?.count === 'number' ? payload.count : agents.length;
  const activeCount =
    typeof payload?.activeCount === 'number'
      ? payload.activeCount
      : agents.filter((agent) => agent.status === 'active').length;
  const inactiveCount =
    typeof payload?.inactiveCount === 'number'
      ? payload.inactiveCount
      : agents.filter((agent) => agent.status === 'inactive').length;
  const taskCounts = normalizeAgentTaskCounts(payload);

  return {
    agents,
    count,
    activeCount,
    inactiveCount,
    taskCounts,
  };
};

export const emitAgentRegistryUpdated = (): void => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(AGENT_REGISTRY_UPDATED_EVENT));
};

export const subscribeAgentRegistryUpdated = (listener: () => void): (() => void) => {
  if (typeof window === 'undefined') return () => {};
  const handler = () => listener();
  window.addEventListener(AGENT_REGISTRY_UPDATED_EVENT, handler as EventListener);
  return () => {
    window.removeEventListener(AGENT_REGISTRY_UPDATED_EVENT, handler as EventListener);
  };
};

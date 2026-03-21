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

const inferLegacyRuntimeSupport = (agent: any): boolean => {
  const normalizedAgentType = toSafeString(agent?.agentType || agent?.agent_type).toLowerCase();
  const normalizedProviderId = toSafeString(agent?.providerId || agent?.provider_id).toLowerCase();
  return ['adk', 'google-adk'].includes(normalizedAgentType) && normalizedProviderId.startsWith('google');
};

const normalizeAgentRuntime = (agent: any): AgentDef['runtime'] => {
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

  return {
    kind: toSafeString(runtime?.kind),
    label: toSafeString(runtime?.label),
    supportsRun: Boolean(runtime?.supportsRun ?? runtime?.supports_run),
    supportsLiveRun: Boolean(runtime?.supportsLiveRun ?? runtime?.supports_live_run),
    supportsSessions: Boolean(runtime?.supportsSessions ?? runtime?.supports_sessions),
    supportsMemory: Boolean(runtime?.supportsMemory ?? runtime?.supports_memory),
    supportsOfficialOrchestration: Boolean(
      runtime?.supportsOfficialOrchestration ?? runtime?.supports_official_orchestration
    ),
  };
};

const normalizeAgentSource = (agent: any, runtime: AgentDef['runtime']): AgentDef['source'] => {
  const source = agent?.source;
  if (source && typeof source === 'object') {
    return {
      kind: toSafeString(source?.kind),
      label: toSafeString(source?.label),
      isSystem: Boolean(source?.isSystem ?? source?.is_system),
    };
  }

  const normalizedAgentType = toSafeString(agent?.agentType || agent?.agent_type).toLowerCase();
  const normalizedProviderId = toSafeString(agent?.providerId || agent?.provider_id).toLowerCase();
  if (normalizedAgentType === 'seed') {
    return {
      kind: 'seed',
      label: '官方 Seed',
      isSystem: true,
    };
  }
  if (runtime?.kind === 'google-adk' || (['adk', 'google-adk'].includes(normalizedAgentType) && normalizedProviderId.startsWith('google'))) {
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

const normalizeAgentTaskCounts = (payload: any): Record<AgentTaskFilter, number> => {
  const base = createEmptyAgentTaskCounts();
  const rawCounts = payload?.taskCounts ?? payload?.task_counts;
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
      resolutionTier: '1K',
      numberOfImages: 1,
      outputMimeType: 'image/png',
      promptExtend: false,
    },
    videoGeneration: {
      aspectRatio: '16:9',
      resolution: '2K',
      durationSeconds: 5,
      continueFromPreviousVideo: false,
      continueFromPreviousLastFrame: false,
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

const normalizeAgentItem = (agent: any): AgentDef | null => {
  const id = toSafeString(agent?.id);
  if (!id) return null;
  const runtime = normalizeAgentRuntime(agent);
  const source = normalizeAgentSource(agent, runtime);
  return {
    id,
    name: toSafeString(agent?.name) || '未命名 Agent',
    description: toSafeString(agent?.description),
    agentType: toSafeString(agent?.agentType || agent?.agent_type || 'custom') || 'custom',
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
    supportsRuntimeSessions: Boolean(
      agent?.supportsRuntimeSessions ?? agent?.supports_runtime_sessions ?? runtime?.supportsSessions
    ),
    supportsRuntimeLiveRun: Boolean(
      agent?.supportsRuntimeLiveRun ?? agent?.supports_runtime_live_run ?? runtime?.supportsLiveRun
    ),
    supportsRuntimeMemory: Boolean(
      agent?.supportsRuntimeMemory ?? agent?.supports_runtime_memory ?? runtime?.supportsMemory
    ),
    supportsOfficialOrchestration: Boolean(
      agent?.supportsOfficialOrchestration
      ?? agent?.supports_official_orchestration
      ?? runtime?.supportsOfficialOrchestration
    ),
    agentCard: agent?.agentCard || createDefaultAgentCard(),
  };
};

const extractAgentArray = (payload: any): any[] => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.agents)) return payload.agents;
  return [];
};

export const normalizeAgentListPayload = (payload: any): AgentDef[] => {
  return extractAgentArray(payload)
    .map(normalizeAgentItem)
    .filter((agent): agent is AgentDef => Boolean(agent));
};

export const fetchAgentList = async (options: AgentListFetchOptions = {}): Promise<AgentListFetchResult> => {
  const params = new URLSearchParams();
  if (options.includeInactive) params.set('include_inactive', 'true');
  if (toSafeString(options.search)) params.set('search', toSafeString(options.search));
  if (options.status) params.set('status', options.status);
  if (options.taskType) params.set('task_type', options.taskType);
  const query = params.toString();
  const url = query ? `/api/agents?${query}` : '/api/agents';

  const payload = await requestJson<any>(url, {
    withAuth: true,
    credentials: 'include',
    signal: options.signal,
    timeoutMs: 0,
    errorMessage: 'Failed to fetch agents',
  });
  const agents = normalizeAgentListPayload(payload);
  const count = typeof payload?.count === 'number' ? payload.count : agents.length;
  const activeCount = typeof payload?.activeCount === 'number'
    ? payload.activeCount
    : typeof payload?.active_count === 'number'
      ? payload.active_count
      : agents.filter((agent) => agent.status === 'active').length;
  const inactiveCount = typeof payload?.inactiveCount === 'number'
    ? payload.inactiveCount
    : typeof payload?.inactive_count === 'number'
      ? payload.inactive_count
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

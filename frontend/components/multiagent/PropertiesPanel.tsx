/**
 * Properties Panel Component (Dark Theme)
 */

import { reportError } from '../../utils/globalErrorHandler';
import React from 'react';
import { Node } from 'reactflow';
import { X, RefreshCw, CheckCircle2, XCircle, Clock, Loader2, Info, Trash2, Upload, Image as ImageIcon, FileSpreadsheet, Video, Mic } from 'lucide-react';
import { CustomNodeData } from './CustomNode';
import { nodeTypeConfigs, NodeType } from './nodeTypeConfigs';
import { AgentSelector } from './AgentSelector';
import type { NodeStatus } from './types';
import type { AgentDef } from './types';
import { getAuthHeaders } from '../../services/apiClient';
import {
  AgentTaskType,
  ModelOption,
  ProviderModels,
  formatModelTaskHint,
  modelSupportsTask,
  normalizeProviderModels,
  pickProviderDefaultModel,
} from './providerModelUtils';
import {
  extractAudioUrls,
  extractImageUrls,
  extractTextContent,
  extractVideoUrls,
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
  normalizeImageValue,
} from './workflowResultUtils';
import { analyzeAgentNodeDefaultUsage, buildAgentNodeDefaultsFromAgent } from './agentNodeDefaults';
import { isFixedPortLayoutNodeType, resolveNodePortLayout, type WorkflowNodePortSide } from './workflowPorts';
import { AdkExportPanel } from './AdkExportPanel';
import { dispatchScopedWorkflowEvent } from './workflowEditorUtils';
import {
  extractSheetStageProtocolState,
  type SheetStageName,
  type SheetStageProtocolState,
  type SheetStageStatus,
} from './sheetStageService';
import {
  getPixelResolutionFromSchema,
  useModeControlsSchema,
} from '../../hooks/useModeControlsSchema';
import {
  buildVideoControlContract,
  getVideoExtensionOptions,
} from '../../utils/videoControlSchema';

/**
 * 通用分辨率映射（工作流编辑器使用，不区分具体模型）
 * 合并 Google 和通义的常见比例，取最大公约数
 */
const WORKFLOW_RESOLUTION_MAP: Record<string, Record<string, string>> = {
  '1K': {
    '1:1': '1024×1024', '2:3': '682×1024', '3:2': '1024×682',
    '3:4': '768×1024', '4:3': '1024×768', '4:5': '819×1024', '5:4': '1024×819',
    '9:16': '576×1024', '16:9': '1024×576', '21:9': '1024×438',
  },
  '1.5K': {
    '1:1': '1536×1536', '2:3': '1248×1872', '3:2': '1872×1248',
    '3:4': '1152×1536', '4:3': '1536×1152', '4:5': '1228×1536', '5:4': '1536×1228',
    '9:16': '864×1536', '16:9': '1536×864', '21:9': '1536×658',
  },
  '2K': {
    '1:1': '2048×2048', '2:3': '1365×2048', '3:2': '2048×1365',
    '3:4': '1536×2048', '4:3': '2048×1536', '4:5': '1638×2048', '5:4': '2048×1638',
    '9:16': '1152×2048', '16:9': '2048×1152', '21:9': '2048×877',
  },
  '4K': {
    '1:1': '4096×4096', '2:3': '2730×4096', '3:2': '4096×2730',
    '3:4': '3072×4096', '4:3': '4096×3072', '4:5': '3276×4096', '5:4': '4096×3276',
    '9:16': '2304×4096', '16:9': '4096×2304', '21:9': '4096×1755',
  },
};

function getResolutionLabel(tier: string, ratio: string): string {
  const map = WORKFLOW_RESOLUTION_MAP[tier];
  if (!map) return tier;
  return map[ratio] || map['1:1'] || tier;
}

const WORKFLOW_LEGACY_VIDEO_RESOLUTION_ALIASES: Record<string, string> = {
  '1k': '720p',
  '720p': '720p',
  '2k': '1080p',
  '1080p': '1080p',
  '4k': '4k',
  '2160p': '4k',
};

function normalizeWorkflowVideoResolutionSelection(
  value: unknown,
  validValues: string[],
  fallbackValue: string
): string {
  const raw = String(value || '').trim();
  if (!raw) {
    return fallbackValue;
  }
  if (validValues.includes(raw)) {
    return raw;
  }
  const alias = WORKFLOW_LEGACY_VIDEO_RESOLUTION_ALIASES[raw.toLowerCase()];
  if (alias && validValues.includes(alias)) {
    return alias;
  }
  return fallbackValue;
}

function normalizeWorkflowVideoSecondsSelection(
  value: unknown,
  validValues: string[],
  fallbackValue: string
): string {
  const raw = String(value ?? '').trim();
  if (!raw) {
    return fallbackValue;
  }
  if (validValues.length === 0 || validValues.includes(raw)) {
    return raw;
  }
  return fallbackValue;
}

function normalizeWorkflowVideoExtensionSelection(
  value: unknown,
  validValues: number[],
  fallbackValue: number
): number {
  const parsed = Number(value);
  if (Number.isFinite(parsed) && validValues.includes(parsed)) {
    return parsed;
  }
  if (validValues.includes(fallbackValue)) {
    return fallbackValue;
  }
  return validValues[0] ?? fallbackValue;
}

function getWorkflowVideoResolutionLabel(
  aspectRatio: string,
  resolution: string,
  schema: ReturnType<typeof useModeControlsSchema>['schema']
): string {
  const schemaLabel = schema?.resolutionTiers?.find((item) => item.value === resolution)?.label || resolution;
  const pixels = getPixelResolutionFromSchema(schema, aspectRatio, resolution);
  if (pixels) {
    return `${schemaLabel} (${pixels})`;
  }
  return schemaLabel || getResolutionLabel(resolution, aspectRatio);
}

const INLINE_UPLOAD_MAX_BYTES = 8 * 1024 * 1024;
const INLINE_UPLOAD_MAX_BYTES_LABEL = '8MB';

/** 将文件转为 base64 data URL */
function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = (e) => reject(e);
    reader.readAsDataURL(file);
  });
}

function reportInlineUploadError(fallbackMessage: string, error: unknown): void {
  const message = error instanceof Error && error.message
    ? error.message
    : fallbackMessage;
  if (typeof window !== 'undefined' && typeof window.alert === 'function') {
    window.alert(message);
  }
}

async function readInlineFilesAsDataUrls(files: File[], uploadLabel: string): Promise<string[]> {
  for (const file of files) {
    if (file.size > INLINE_UPLOAD_MAX_BYTES) {
      throw new Error(`${uploadLabel} 超过 ${INLINE_UPLOAD_MAX_BYTES_LABEL} 内联上传上限，请改用可访问的 URL。`);
    }
  }
  return Promise.all(files.map((file) => fileToDataUrl(file)));
}

interface PropertiesPanelProps {
  selectedNode: Node<CustomNodeData> | null;
  onClose: () => void;
  onUpdateNode: (nodeId: string, updates: Partial<CustomNodeData>) => void;
  onRetry?: (nodeId: string) => void;
  onDeleteNode?: (nodeId: string) => void;
  onConsumeFocusRequest?: (token: string) => void;
  focusRequest?: {
    nodeId: string;
    fieldKey: string;
    token: string;
  } | null;
}

const statusDisplayConfig: Record<NodeStatus, {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  color: string;
  bgColor: string;
}> = {
  pending: { icon: Clock, label: '等待执行', color: 'text-slate-400', bgColor: 'bg-slate-800' },
  running: { icon: Loader2, label: '执行中', color: 'text-blue-400', bgColor: 'bg-blue-500/10' },
  completed: { icon: CheckCircle2, label: '已完成', color: 'text-emerald-400', bgColor: 'bg-emerald-500/10' },
  skipped: { icon: Clock, label: '已跳过', color: 'text-amber-300', bgColor: 'bg-amber-500/10' },
  failed: { icon: XCircle, label: '执行失败', color: 'text-red-400', bgColor: 'bg-red-500/10' },
};

function usePropertiesPanelFocus(
  focusRequest: PropertiesPanelProps['focusRequest'],
  selectedNode: Node<CustomNodeData> | null,
  onConsumeFocusRequest?: (token: string) => void,
) {
  const panelRootRef = React.useRef<HTMLDivElement | null>(null);
  const panelContentRef = React.useRef<HTMLDivElement | null>(null);

  const focusFieldByKey = React.useCallback((fieldKey: string): boolean => {
    const normalized = String(fieldKey || '').trim();
    if (!normalized) return false;
    const root = panelRootRef.current;
    if (!root) return false;

    const queryCandidates = [
      `[data-field-key="${normalized}"]`,
      `[data-field-key="${normalized.toLowerCase()}"]`,
    ];
    const target = queryCandidates
      .map((selector) => root.querySelector(selector))
      .find((element): element is HTMLElement => element instanceof HTMLElement);
    if (!target) {
      return false;
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (typeof (target as HTMLInputElement).focus === 'function') {
      window.setTimeout(() => {
        (target as HTMLInputElement).focus();
      }, 20);
    }
    return true;
  }, []);

  React.useEffect(() => {
    if (!focusRequest || !selectedNode) {
      return;
    }
    if (String(focusRequest.nodeId) !== String(selectedNode.id)) {
      return;
    }
    const timer = window.setTimeout(() => {
      const focused = focusFieldByKey(focusRequest.fieldKey);
      if (!focused) {
        const fallback = panelContentRef.current?.querySelector('input, textarea, select, button') as HTMLElement | null;
        if (fallback) {
          fallback.focus();
          fallback.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
      onConsumeFocusRequest?.(focusRequest.token);
    }, 40);
    return () => window.clearTimeout(timer);
  }, [focusFieldByKey, focusRequest, onConsumeFocusRequest, selectedNode]);

  return {
    panelRootRef,
    panelContentRef,
  };
}

function useProviderModels(selectedNode: Node<CustomNodeData> | null, nodeType: NodeType) {
  const [providers, setProviders] = React.useState<ProviderModels[]>([]);
  const [providersLoading, setProvidersLoading] = React.useState(false);

  React.useEffect(() => {
    if (!selectedNode || (nodeType !== 'agent' && nodeType !== 'tool')) {
      return;
    }
    let cancelled = false;

    const fetchProviders = async () => {
      setProvidersLoading(true);
      try {
        const res = await fetch('/api/agents/available-models', {
          headers: getAuthHeaders(),
          credentials: 'include',
        });
        if (!res.ok || cancelled) return;
        const data = await res.json();
        setProviders(normalizeProviderModels(data));
      } catch (error) {
        if (!cancelled) {
        }
      } finally {
        if (!cancelled) {
          setProvidersLoading(false);
        }
      }
    };

    fetchProviders();
    return () => {
      cancelled = true;
    };
  }, [nodeType, selectedNode?.id]);

  return {
    providers,
    providersLoading,
  };
}

interface PropertiesPanelResultSectionProps {
  nodeData: CustomNodeData;
  selectedNodeId: string;
  sourcePreviewUrl: string;
  resultPreviewUrls: string[];
  resultPreviewAudioUrls: string[];
  resultPreviewVideoUrls: string[];
  resultPreviewText: string;
  status: NodeStatus;
}

const PropertiesPanelResultSection: React.FC<PropertiesPanelResultSectionProps> = ({
  nodeData,
  selectedNodeId,
  sourcePreviewUrl,
  resultPreviewUrls,
  resultPreviewAudioUrls,
  resultPreviewVideoUrls,
  resultPreviewText,
  status,
}) => {
  if (status === 'pending' || !nodeData.result) {
    return null;
  }

  return (
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">执行结果</label>
      <div className={`p-3 rounded-lg border ${
        status === 'failed'
          ? 'bg-red-500/5 border-red-500/20'
          : 'bg-emerald-500/5 border-emerald-500/20'
      }`}>
        {(sourcePreviewUrl || resultPreviewUrls.length > 0) && (
          <div className="mb-3 grid grid-cols-2 gap-2">
            {sourcePreviewUrl && (
              <div>
                <div className="text-[10px] text-slate-400 mb-1">输入参考图</div>
                <img
                  src={sourcePreviewUrl}
                  alt="source-preview"
                  className="w-full h-24 object-contain rounded border border-slate-700 bg-slate-900"
                />
              </div>
            )}
            {resultPreviewUrls.length > 0 && (
              <div>
                <div className="text-[10px] text-slate-400 mb-1">输出结果图（{resultPreviewUrls.length}）</div>
                <div className="grid grid-cols-2 gap-1 max-h-44 overflow-y-auto pr-0.5">
                  {resultPreviewUrls.map((imageUrl, index) => (
                    <img
                      key={`${selectedNodeId}-result-preview-${index}`}
                      src={imageUrl}
                      alt={`result-preview-${index + 1}`}
                      className="w-full h-24 object-cover rounded border border-slate-700 bg-slate-900"
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {(resultPreviewVideoUrls.length > 0 || resultPreviewAudioUrls.length > 0) && (
          <div className="mb-3 space-y-2">
            {resultPreviewVideoUrls.length > 0 && (
              <div>
                <div className="text-[10px] text-slate-400 mb-1">输出视频（{resultPreviewVideoUrls.length}）</div>
                <div className="space-y-2 max-h-52 overflow-y-auto pr-0.5">
                  {resultPreviewVideoUrls.map((videoUrl, index) => (
                    <video
                      key={`${selectedNodeId}-result-video-${index}`}
                      src={videoUrl}
                      controls
                      className="w-full rounded border border-slate-700 bg-slate-900"
                    />
                  ))}
                </div>
              </div>
            )}
            {resultPreviewAudioUrls.length > 0 && (
              <div>
                <div className="text-[10px] text-slate-400 mb-1">输出音频（{resultPreviewAudioUrls.length}）</div>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-0.5">
                  {resultPreviewAudioUrls.map((audioUrl, index) => (
                    <audio
                      key={`${selectedNodeId}-result-audio-${index}`}
                      src={audioUrl}
                      controls
                      className="w-full"
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words max-h-[220px] overflow-y-auto">
          {resultPreviewText || '（无可读文本结果）'}
        </pre>
        {typeof nodeData.result !== 'string' && (
          <details className="mt-2">
            <summary className="text-[10px] text-slate-500 cursor-pointer hover:text-slate-400">
              查看原始结构化结果
            </summary>
            <pre className="mt-1 text-[10px] text-slate-400 whitespace-pre-wrap break-words max-h-[180px] overflow-y-auto">
              {JSON.stringify(nodeData.result, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
};

const SHEET_STAGE_LABELS: Record<SheetStageName, string> = {
  ingest: 'Ingest',
  profile: 'Profile',
  query: 'Query',
  export: 'Export',
};

const SHEET_STAGE_RELATION_LABELS: Record<'input' | 'output' | 'history', string> = {
  input: '输入',
  output: '输出',
  history: '历史',
};

const getSheetStageStatusLabel = (status: SheetStageStatus): string =>
  status === 'completed' ? '完成' : '失败';

const getSheetStageStatusClassName = (status: SheetStageStatus): string =>
  status === 'completed'
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
    : 'border-red-500/30 bg-red-500/10 text-red-300';

const formatSheetStageTime = (timestampMs: number): string => {
  if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
    return '时间未知';
  }
  try {
    return new Date(timestampMs).toLocaleString();
  } catch {
    return String(timestampMs);
  }
};

interface PropertiesPanelSheetStageSectionProps {
  stageState: SheetStageProtocolState;
}

const PropertiesPanelSheetStageSection: React.FC<PropertiesPanelSheetStageSectionProps> = ({
  stageState,
}) => {
  if (!stageState.found) {
    return null;
  }

  if (!stageState.valid || !stageState.envelope) {
    return (
      <div className="pt-1 border-t border-slate-800 space-y-1.5">
        <label className="block text-xs text-slate-500">Sheet Stage 协议</label>
        <div className="rounded border border-red-500/30 bg-red-500/10 p-2 text-[11px] text-red-200 space-y-1">
          <div className="font-medium">检测到协议响应，但结构无效</div>
          {stageState.parseErrors.length > 0 ? (
            <ul className="space-y-0.5 list-disc pl-4">
              {stageState.parseErrors.slice(0, 5).map((item) => (
                <li key={`${item.sourcePath}-${item.message}`}>
                  {item.message} <span className="text-red-300/70">({item.sourcePath})</span>
                </li>
              ))}
            </ul>
          ) : (
            <div>请检查后端响应是否符合 `sheet-stage/v1` 合同。</div>
          )}
        </div>
      </div>
    );
  }

  const { envelope } = stageState;
  return (
    <div className="pt-1 border-t border-slate-800 space-y-2.5">
      <label className="block text-xs text-slate-500">Sheet Stage 协议</label>
      <div className="rounded-lg border border-cyan-500/25 bg-cyan-500/5 p-2.5 space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[11px] text-cyan-200">
            协议版本: {envelope.protocolVersion}
          </div>
          <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] ${getSheetStageStatusClassName(envelope.status)}`}>
            {getSheetStageStatusLabel(envelope.status)}
          </span>
        </div>
        <div className="text-[11px] text-slate-300">
          当前阶段: {SHEET_STAGE_LABELS[envelope.stage]} · Session: {envelope.sessionId}
        </div>
        {envelope.nextStage && (
          <div className="text-[10px] text-slate-400">
            下一阶段: {SHEET_STAGE_LABELS[envelope.nextStage]}
          </div>
        )}
        {envelope.error?.message && (
          <div className="text-[10px] text-red-300">
            错误: {envelope.error.code ? `${envelope.error.code} - ` : ''}{envelope.error.message}
          </div>
        )}
      </div>

      {stageState.timeline.length > 0 && (
        <div className="rounded border border-slate-800 bg-slate-900/40 p-2.5">
          <div className="text-[11px] text-slate-300 font-medium mb-1.5">阶段时间线</div>
          <ol className="space-y-1.5" aria-label="Sheet stage timeline">
            {stageState.timeline.map((entry, index) => (
              <li key={entry.id} className="rounded border border-slate-800 bg-slate-900/50 px-2 py-1.5 text-[10px] text-slate-300 space-y-0.5">
                <div className="flex items-center justify-between gap-2">
                  <span>{index + 1}. {SHEET_STAGE_LABELS[entry.stage]}</span>
                  <span className={`inline-flex items-center rounded border px-1.5 py-0.5 ${getSheetStageStatusClassName(entry.status)}`}>
                    {getSheetStageStatusLabel(entry.status)}
                  </span>
                </div>
                <div className="text-slate-500">时间: {formatSheetStageTime(entry.timestampMs)}</div>
                {entry.artifact && (
                  <div className="font-mono text-slate-400 break-all">
                    {entry.artifact.artifactKey}@{entry.artifact.artifactVersion} ({entry.artifact.artifactSessionId})
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {stageState.playbackRefs.length > 0 && (
        <div className="rounded border border-slate-800 bg-slate-900/40 p-2.5">
          <div className="text-[11px] text-slate-300 font-medium mb-1.5">Artifact 回放引用</div>
          <ul className="space-y-1.5" aria-label="Sheet stage artifact playback references">
            {stageState.playbackRefs.map((entry) => (
              <li key={entry.id} className="rounded border border-slate-800 bg-slate-900/50 px-2 py-1.5 text-[10px] text-slate-300 space-y-0.5">
                <div className="flex items-center justify-between gap-2">
                  <span>{SHEET_STAGE_RELATION_LABELS[entry.relation]} · {SHEET_STAGE_LABELS[entry.stage]}</span>
                  {entry.timestampMs > 0 && (
                    <span className="text-slate-500">{formatSheetStageTime(entry.timestampMs)}</span>
                  )}
                </div>
                <div className="font-mono text-slate-400 break-all">
                  {entry.artifact.artifactKey}@{entry.artifact.artifactVersion} ({entry.artifact.artifactSessionId})
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {stageState.precheckIssues.length > 0 && (
        <AdkExportPanel issues={stageState.precheckIssues} />
      )}

      {stageState.parseErrors.length > 0 && (
        <div className="rounded border border-amber-500/30 bg-amber-500/10 p-2 text-[10px] text-amber-200 space-y-0.5">
          <div className="font-medium">解析告警</div>
          {stageState.parseErrors.slice(0, 4).map((item) => (
            <div key={`${item.sourcePath}-${item.message}`}>
              {item.message} <span className="text-amber-300/70">({item.sourcePath})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  selectedNode, onClose, onUpdateNode, onRetry, onDeleteNode, focusRequest, onConsumeFocusRequest
}) => {
  const { panelRootRef, panelContentRef } = usePropertiesPanelFocus(focusRequest, selectedNode, onConsumeFocusRequest);
  const nodeType = (selectedNode?.data.type || selectedNode?.type || 'agent') as NodeType;
  const { providers, providersLoading } = useProviderModels(selectedNode, nodeType);
  const config = nodeTypeConfigs[nodeType] || nodeTypeConfigs.agent;
  const status = ((selectedNode?.data.status || 'pending') as NodeStatus);
  const statusDisplay = statusDisplayConfig[status];
  const StatusIcon = statusDisplay.icon;
  const nodeData = selectedNode?.data;
  const resolvedPortLayout = resolveNodePortLayout(nodeType, nodeData?.portLayout);
  const normalizedToolName = String(nodeData?.toolName || '').trim().toLowerCase().replace(/-/g, '_');
  const shouldLoadWorkflowVideoSchema = nodeType === 'agent' || nodeType === 'tool';
  const workflowVideoSchemaProviderId = shouldLoadWorkflowVideoSchema
    ? (
      nodeType === 'agent'
        ? String(nodeData?.modelOverrideProviderId || nodeData?.agentProviderId || '').trim()
        : String(nodeData?.toolProviderId || '').trim()
    )
    : '';
  const workflowVideoSchemaModelId = shouldLoadWorkflowVideoSchema
    ? (
      nodeType === 'agent'
        ? String(nodeData?.modelOverrideModelId || nodeData?.agentModelId || '').trim()
        : String(nodeData?.toolModelId || '').trim()
    )
    : '';
  const {
    schema: workflowVideoSchema,
  } = useModeControlsSchema(
    workflowVideoSchemaProviderId || undefined,
    'video-gen',
    workflowVideoSchemaModelId || undefined,
  );
  const workflowVideoControlContract = React.useMemo(
    () => buildVideoControlContract(workflowVideoSchema),
    [workflowVideoSchema],
  );
  const isFixedPortLayout = isFixedPortLayoutNodeType(nodeType);
  const sourcePreviewUrl = normalizeImageValue(
    String(nodeData?.agentReferenceImageUrl || nodeData?.toolReferenceImageUrl || '')
  );
  const resultPreviewUrls = extractImageUrls(nodeData?.result)
    .filter((imageUrl) => isDirectlyRenderableImageUrl(imageUrl));
  const resultPreviewAudioUrls = extractAudioUrls(nodeData?.result)
    .filter((audioUrl) => isDirectlyRenderableAudioUrl(audioUrl));
  const resultPreviewVideoUrls = extractVideoUrls(nodeData?.result)
    .filter((videoUrl) => isDirectlyRenderableVideoUrl(videoUrl));
  const readableResultText = extractTextContent(nodeData?.result).trim();
  const resultPreviewText = readableResultText || (
    nodeData?.result == null
      ? ''
      : (typeof nodeData.result === 'string' ? nodeData.result : JSON.stringify(nodeData.result, null, 2))
  );
  const [resolvedAgent, setResolvedAgent] = React.useState<AgentDef | null>(null);
  const sheetStageState = React.useMemo(
    () => extractSheetStageProtocolState(nodeData?.result),
    [nodeData?.result]
  );
  const agentDefaultAnalysis = React.useMemo(
    () => analyzeAgentNodeDefaultUsage(resolvedAgent, nodeData),
    [resolvedAgent, nodeData]
  );

  const updateNodeData = (updates: Partial<CustomNodeData>) => {
    if (!selectedNode) {
      return;
    }
    onUpdateNode(selectedNode.id, updates);
  };

  React.useEffect(() => {
    if (nodeType !== 'agent') {
      setResolvedAgent(null);
      return;
    }
    if (!String(nodeData.agentId || '').trim()) {
      setResolvedAgent(null);
    }
  }, [nodeData.agentId, nodeType]);

  const updatePortLayoutCount = (side: WorkflowNodePortSide, rawValue: string) => {
    if (isFixedPortLayout) {
      return;
    }
    const parsed = Number(rawValue);
    const normalized = Number.isFinite(parsed) ? Math.max(0, Math.floor(parsed)) : 0;
    updateNodeData({
      portLayout: resolveNodePortLayout(nodeType, {
        ...resolvedPortLayout,
        [side]: normalized,
      }),
    });
  };

  if (!selectedNode || !nodeData) return null;

  const renderStartInputNodeConfig = () => {
    if (['start', 'input_text', 'input_image', 'input_video', 'input_audio', 'input_file'].includes(nodeType)) {
      const isStartNode = nodeType === 'start';
      const isTextInputNode = nodeType === 'input_text';
      const isImageInputNode = nodeType === 'input_image';
      const isVideoInputNode = nodeType === 'input_video';
      const isAudioInputNode = nodeType === 'input_audio';
      const isFileInputNode = nodeType === 'input_file';
      const normalizeUrlList = (value: unknown): string[] => {
        if (!Array.isArray(value)) return [];
        return value
          .map((item) => String(item || '').trim())
          .filter(Boolean);
      };
      const dedupeUrlList = (...sources: string[][]): string[] => {
        const deduped = new Set<string>();
        const result: string[] = [];
        sources.forEach((source) => {
          source.forEach((item) => {
            if (!deduped.has(item)) {
              deduped.add(item);
              result.push(item);
            }
          });
        });
        return result;
      };
      const parseUrlTextareaValue = (rawValue: string): string[] => {
        return Array.from(new Set(
          String(rawValue || '')
            .split(/\r?\n/)
            .map((item) => item.trim())
            .filter(Boolean)
        ));
      };

      const startImageValues = dedupeUrlList(
        normalizeUrlList(nodeData.startImageUrls),
        nodeData.startImageUrl ? [String(nodeData.startImageUrl).trim()] : [],
      );
      const startVideoValues = dedupeUrlList(
        normalizeUrlList(nodeData.startVideoUrls),
        nodeData.startVideoUrl ? [String(nodeData.startVideoUrl).trim()] : [],
      );
      const startAudioValues = dedupeUrlList(
        normalizeUrlList(nodeData.startAudioUrls),
        nodeData.startAudioUrl ? [String(nodeData.startAudioUrl).trim()] : [],
      );
      const startFileValues = dedupeUrlList(
        normalizeUrlList(nodeData.startFileUrls),
        nodeData.startFileUrl ? [String(nodeData.startFileUrl).trim()] : [],
      );
      const hasStartImage = startImageValues.length > 0;
      const hasStartVideo = startVideoValues.length > 0;
      const hasStartAudio = startAudioValues.length > 0;
      const hasStartFile = startFileValues.length > 0;
      const renderableStartImageValues = startImageValues.filter((value) =>
        value.startsWith('data:') || isDirectlyRenderableImageUrl(value)
      );
      const startImageTextAreaValue = startImageValues
        .filter((value) => !value.startsWith('data:'))
        .join('\n');
      const startVideoTextAreaValue = startVideoValues
        .filter((value) => !value.startsWith('data:'))
        .join('\n');
      const startAudioTextAreaValue = startAudioValues
        .filter((value) => !value.startsWith('data:'))
        .join('\n');
      const startFileTextAreaValue = startFileValues
        .filter((value) => !value.startsWith('data:'))
        .join('\n');
      const title = isStartNode
        ? '开始入口配置'
        : isTextInputNode
          ? '文本输入组件'
          : isImageInputNode
            ? '图片输入组件'
            : isVideoInputNode
              ? '视频输入组件'
              : isAudioInputNode
                ? '音频输入组件'
            : '文件输入组件';
      const desc = isStartNode
        ? '开始节点按钮将从此处读取任务输入和媒体附件并启动工作流。'
        : isTextInputNode
          ? '注入任务文本到下游节点（覆盖 input.task）。'
          : isImageInputNode
            ? '注入图片地址到下游节点（input.imageUrl）。'
            : isVideoInputNode
              ? '注入视频地址到下游节点（input.videoUrl）。'
              : isAudioInputNode
                ? '注入音频地址到下游节点（input.audioUrl）。'
            : '注入文件地址到下游节点（input.fileUrl）。';

      return (
        <div className="space-y-4">
          <div className="p-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5">
            <div className="text-xs text-emerald-300 font-medium">{title}</div>
            <div className="mt-1 text-[10px] text-slate-500">{desc}</div>
          </div>

          {(isStartNode || isTextInputNode) && (
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">任务输入（input.task）</label>
              <textarea
                value={nodeData.startTask || ''}
                onChange={(e) => updateNodeData({ startTask: e.target.value })}
                rows={3}
                data-field-key="startTask"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 resize-none"
                placeholder="输入提示词，或 JSON（例如包含 imageUrl / fileUrl）"
              />
            </div>
          )}

          {(isStartNode || isImageInputNode) && (
            <div className="space-y-2">
              <label className="block text-xs text-slate-500">输入图片（input.imageUrl / input.imageUrls）</label>
              {renderableStartImageValues.length > 0 && (
                <div className="grid grid-cols-4 gap-2 max-h-56 overflow-y-auto pr-1">
                  {renderableStartImageValues.map((imageUrl, index) => (
                    <div key={`${selectedNode.id}-input-image-${index}`} className="relative group">
                      <img
                        src={imageUrl}
                        alt={`输入图片-${index + 1}`}
                        className="w-full h-16 object-cover rounded border border-emerald-500/30"
                      />
                      <button
                        onClick={() => {
                          const removeIndex = startImageValues.findIndex((value) => value === imageUrl);
                          const nextValues = startImageValues.filter((_, sourceIndex) => sourceIndex !== removeIndex);
                          updateNodeData({
                            startImageUrl: nextValues[0] || '',
                            startImageUrls: nextValues,
                          });
                        }}
                        className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {hasStartImage && (
                <button
                  type="button"
                  onClick={() => updateNodeData({ startImageUrl: '', startImageUrls: [] })}
                  className="w-full px-2 py-1 text-[11px] rounded border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                >
                  清空全部图片
                </button>
              )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-emerald-500/40 rounded-lg cursor-pointer hover:border-emerald-500/60 transition-colors">
                <Upload size={12} className="text-emerald-400" />
                <ImageIcon size={12} className="text-emerald-400" />
                <span className="text-xs text-emerald-300">{hasStartImage ? '继续上传图片' : '上传图片'}</span>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length === 0) return;
                    try {
                      const encoded = await readInlineFilesAsDataUrls(files, '输入节点图片');
                      const nextValues = dedupeUrlList(startImageValues, encoded);
                      updateNodeData({
                        startImageUrl: nextValues[0] || '',
                        startImageUrls: nextValues,
                      });
                    } catch (err) {
                      reportInlineUploadError('输入节点图片读取失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <textarea
                value={startImageTextAreaValue}
                onChange={(e) => {
                  const dataUrls = startImageValues.filter((value) => value.startsWith('data:'));
                  const textUrls = parseUrlTextareaValue(e.target.value);
                  const nextValues = dedupeUrlList(dataUrls, textUrls);
                  updateNodeData({
                    startImageUrl: nextValues[0] || '',
                    startImageUrls: nextValues,
                  });
                }}
                rows={3}
                data-field-key="startImageUrls"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 font-mono focus:outline-none focus:border-emerald-500/50 resize-y"
                placeholder={'每行一个图片URL\nhttps://... \n{{prev.output.imageUrl}}'}
              />
              <input type="hidden" data-field-key="startImageUrl" value="" readOnly />
            </div>
          )}

          {(isStartNode || isVideoInputNode) && (
            <div className="space-y-2">
              <label className="block text-xs text-slate-500">输入视频（input.videoUrl / input.videoUrls）</label>
              {hasStartVideo && (
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {startVideoValues.map((videoUrl, index) => (
                    <div
                      key={`${selectedNode.id}-input-video-${index}`}
                      className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-indigo-500/30"
                    >
                      <Video size={14} className="text-indigo-400 flex-shrink-0" />
                      <span className="text-[10px] text-slate-300 truncate flex-1">
                        {videoUrl.startsWith('data:') ? `已上传视频 ${index + 1}` : videoUrl}
                      </span>
                      <button
                        onClick={() => {
                          const nextValues = startVideoValues.filter((_, sourceIndex) => sourceIndex !== index);
                          updateNodeData({
                            startVideoUrl: nextValues[0] || '',
                            startVideoUrls: nextValues,
                          });
                        }}
                        className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {hasStartVideo && (
                <button
                  type="button"
                  onClick={() => updateNodeData({ startVideoUrl: '', startVideoUrls: [] })}
                  className="w-full px-2 py-1 text-[11px] rounded border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                >
                  清空全部视频
                </button>
              )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-indigo-500/40 rounded-lg cursor-pointer hover:border-indigo-500/60 transition-colors">
                <Upload size={12} className="text-indigo-400" />
                <Video size={12} className="text-indigo-400" />
                <span className="text-xs text-indigo-300">{hasStartVideo ? '继续上传视频' : '上传视频'}</span>
                <input
                  type="file"
                  accept="video/*,.mp4,.mov,.webm,.avi,.mkv"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length === 0) return;
                    try {
                      const encoded = await readInlineFilesAsDataUrls(files, '输入节点视频');
                      const nextValues = dedupeUrlList(startVideoValues, encoded);
                      updateNodeData({
                        startVideoUrl: nextValues[0] || '',
                        startVideoUrls: nextValues,
                      });
                    } catch (err) {
                      reportInlineUploadError('输入节点视频读取失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <textarea
                value={startVideoTextAreaValue}
                onChange={(e) => {
                  const dataUrls = startVideoValues.filter((value) => value.startsWith('data:'));
                  const textUrls = parseUrlTextareaValue(e.target.value);
                  const nextValues = dedupeUrlList(dataUrls, textUrls);
                  updateNodeData({
                    startVideoUrl: nextValues[0] || '',
                    startVideoUrls: nextValues,
                  });
                }}
                rows={3}
                data-field-key="startVideoUrls"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 font-mono focus:outline-none focus:border-indigo-500/50 resize-y"
                placeholder={'每行一个视频URL\nhttps://... \n{{prev.output.videoUrl}}'}
              />
              <input type="hidden" data-field-key="startVideoUrl" value="" readOnly />
            </div>
          )}

          {(isStartNode || isAudioInputNode) && (
            <div className="space-y-2">
              <label className="block text-xs text-slate-500">输入音频（input.audioUrl / input.audioUrls）</label>
              {hasStartAudio && (
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {startAudioValues.map((audioUrl, index) => (
                    <div
                      key={`${selectedNode.id}-input-audio-${index}`}
                      className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-sky-500/30"
                    >
                      <Mic size={14} className="text-sky-400 flex-shrink-0" />
                      <span className="text-[10px] text-slate-300 truncate flex-1">
                        {audioUrl.startsWith('data:') ? `已上传音频 ${index + 1}` : audioUrl}
                      </span>
                      <button
                        onClick={() => {
                          const nextValues = startAudioValues.filter((_, sourceIndex) => sourceIndex !== index);
                          updateNodeData({
                            startAudioUrl: nextValues[0] || '',
                            startAudioUrls: nextValues,
                          });
                        }}
                        className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {hasStartAudio && (
                <button
                  type="button"
                  onClick={() => updateNodeData({ startAudioUrl: '', startAudioUrls: [] })}
                  className="w-full px-2 py-1 text-[11px] rounded border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                >
                  清空全部音频
                </button>
              )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-sky-500/40 rounded-lg cursor-pointer hover:border-sky-500/60 transition-colors">
                <Upload size={12} className="text-sky-400" />
                <Mic size={12} className="text-sky-400" />
                <span className="text-xs text-sky-300">{hasStartAudio ? '继续上传音频' : '上传音频'}</span>
                <input
                  type="file"
                  accept="audio/*,.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length === 0) return;
                    try {
                      const encoded = await readInlineFilesAsDataUrls(files, '输入节点音频');
                      const nextValues = dedupeUrlList(startAudioValues, encoded);
                      updateNodeData({
                        startAudioUrl: nextValues[0] || '',
                        startAudioUrls: nextValues,
                      });
                    } catch (err) {
                      reportInlineUploadError('输入节点音频读取失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <textarea
                value={startAudioTextAreaValue}
                onChange={(e) => {
                  const dataUrls = startAudioValues.filter((value) => value.startsWith('data:'));
                  const textUrls = parseUrlTextareaValue(e.target.value);
                  const nextValues = dedupeUrlList(dataUrls, textUrls);
                  updateNodeData({
                    startAudioUrl: nextValues[0] || '',
                    startAudioUrls: nextValues,
                  });
                }}
                rows={3}
                data-field-key="startAudioUrls"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 font-mono focus:outline-none focus:border-sky-500/50 resize-y"
                placeholder={'每行一个音频URL\nhttps://... \n{{prev.output.audioUrl}}'}
              />
              <input type="hidden" data-field-key="startAudioUrl" value="" readOnly />
            </div>
          )}

          {(isStartNode || isFileInputNode) && (
            <div className="space-y-2">
              <label className="block text-xs text-slate-500">输入文件（input.fileUrl / input.fileUrls）</label>
              {hasStartFile && (
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {startFileValues.map((fileUrl, index) => (
                    <div
                      key={`${selectedNode.id}-input-file-${index}`}
                      className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-cyan-500/30"
                    >
                      <FileSpreadsheet size={14} className="text-cyan-400 flex-shrink-0" />
                      <span className="text-[10px] text-slate-300 truncate flex-1">
                        {fileUrl.startsWith('data:') ? `已上传文件 ${index + 1}` : fileUrl}
                      </span>
                      <button
                        onClick={() => {
                          const nextValues = startFileValues.filter((_, sourceIndex) => sourceIndex !== index);
                          updateNodeData({
                            startFileUrl: nextValues[0] || '',
                            startFileUrls: nextValues,
                          });
                        }}
                        className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {hasStartFile && (
                <button
                  type="button"
                  onClick={() => updateNodeData({ startFileUrl: '', startFileUrls: [] })}
                  className="w-full px-2 py-1 text-[11px] rounded border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                >
                  清空全部文件
                </button>
              )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-cyan-500/40 rounded-lg cursor-pointer hover:border-cyan-500/60 transition-colors">
                <Upload size={12} className="text-cyan-400" />
                <FileSpreadsheet size={12} className="text-cyan-400" />
                <span className="text-xs text-cyan-300">{hasStartFile ? '继续上传文件' : '上传文件'}</span>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.json,.tsv,.txt,.pdf"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length === 0) return;
                    try {
                      const encoded = await readInlineFilesAsDataUrls(files, '输入节点文件');
                      const nextValues = dedupeUrlList(startFileValues, encoded);
                      updateNodeData({
                        startFileUrl: nextValues[0] || '',
                        startFileUrls: nextValues,
                      });
                    } catch (err) {
                      reportInlineUploadError('输入节点文件读取失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <textarea
                value={startFileTextAreaValue}
                onChange={(e) => {
                  const dataUrls = startFileValues.filter((value) => value.startsWith('data:'));
                  const textUrls = parseUrlTextareaValue(e.target.value);
                  const nextValues = dedupeUrlList(dataUrls, textUrls);
                  updateNodeData({
                    startFileUrl: nextValues[0] || '',
                    startFileUrls: nextValues,
                  });
                }}
                rows={3}
                data-field-key="startFileUrls"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 font-mono focus:outline-none focus:border-cyan-500/50 resize-y"
                placeholder={'每行一个文件URL\nhttps://... \n{{prev.output.fileUrl}}'}
              />
              <input type="hidden" data-field-key="startFileUrl" value="" readOnly />
            </div>
          )}

          {isStartNode && (
            <button
              onClick={(event) => {
                dispatchScopedWorkflowEvent('workflow:execute-request', event.currentTarget, {
                  nodeId: String(selectedNode.id),
                });
              }}
              className="w-full px-3 py-2 text-xs rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 transition-colors"
            >
              使用开始按钮执行工作流
            </button>
          )}
        </div>
      );
    }

    return null;
  };

  const renderAgentNodeConfig = () => {
    if (nodeType === 'agent') {
      const selectedProviderId = nodeData.modelOverrideProviderId || '';
      const selectedProvider = providers.find((provider) => provider.providerId === selectedProviderId);
      const selectedTaskType: AgentTaskType = (
        ['chat', 'image-gen', 'image-edit', 'video-gen', 'audio-gen', 'vision-understand', 'data-analysis'].includes(String(nodeData.agentTaskType || 'chat'))
          ? String(nodeData.agentTaskType || 'chat')
          : 'chat'
      ) as AgentTaskType;
      const hasAgentReferenceImage = Boolean(String(nodeData.agentReferenceImageUrl || '').trim());
      const taskSupportsReferenceImage = selectedTaskType === 'image-edit' || selectedTaskType === 'vision-understand';
      const providerModels = selectedProvider?.allModels || selectedProvider?.models || [];
      const compatibleModels = providerModels.filter((model) => modelSupportsTask(model, selectedTaskType));
      const selectedModels = compatibleModels;
      const providerHasNoCompatibleModels = selectedProviderId !== '' && providerModels.length > 0 && compatibleModels.length === 0;
      const selectedOverrideModel = providerModels.find((model) => model.id === (nodeData.modelOverrideModelId || ''));
      const effectiveProvider = nodeData.modelOverrideProviderId || nodeData.agentProviderId || '';
      const effectiveModel = nodeData.modelOverrideModelId || nodeData.agentModelId || '';
      const effectiveModelPool = providers.find((provider) => provider.providerId === effectiveProvider)?.allModels
        || providers.find((provider) => provider.providerId === effectiveProvider)?.models
        || [];
      const effectiveModelOption = effectiveModelPool.find((model) => model.id === effectiveModel);
      const effectiveSupportedTasks = Array.isArray(effectiveModelOption?.supportedTasks)
        ? effectiveModelOption.supportedTasks
        : [];
      const hasEffectiveTaskConstraint = effectiveSupportedTasks.length > 0;
      const taskOptions: Array<{ value: AgentTaskType; label: string }> = [
        { value: 'chat', label: '💬 对话（文本生成）' },
        { value: 'image-gen', label: '🖼️ 图片生成（文生图）' },
        { value: 'image-edit', label: '🪄 图片编辑（图生图）' },
        { value: 'video-gen', label: '🎬 视频生成（文生视频）' },
        { value: 'audio-gen', label: '🎧 音频生成（语音/旁白）' },
        { value: 'vision-understand', label: '🧠 图片理解（多模态）' },
        { value: 'data-analysis', label: '📊 数据分析' },
      ];
      const isTaskCompatible = (model: ModelOption | undefined, taskType: AgentTaskType) => {
        return modelSupportsTask(model, taskType);
      };
      const findProvider = (providerId: string): ProviderModels | undefined => {
        return providers.find((item) => item.providerId === providerId);
      };
      const findProviderModels = (providerId: string): ModelOption[] => {
        const provider = findProvider(providerId);
        return provider?.allModels || provider?.models || [];
      };
      const findModelById = (providerId: string, modelId: string): ModelOption | undefined => {
        if (!providerId || !modelId) return undefined;
        return findProviderModels(providerId).find((model) => model.id === modelId);
      };
      const pickCompatibleModel = (providerId: string, taskType: AgentTaskType): ModelOption | undefined => {
        const provider = findProvider(providerId);
        return pickProviderDefaultModel(provider, taskType);
      };
      const handleAgentTaskTypeChange = (nextTaskType: AgentTaskType) => {
        const updates: Partial<CustomNodeData> = { agentTaskType: nextTaskType };
        if (nextTaskType === 'video-gen') {
          if (!String(nodeData.agentAspectRatio || '').trim()) {
            updates.agentAspectRatio = workflowVideoControlContract.defaultAspectRatio;
          }
          if (!String(nodeData.agentResolutionTier || '').trim()) {
            updates.agentResolutionTier = workflowVideoControlContract.defaultResolution;
          }
          if (!Number.isFinite(Number(nodeData.agentVideoDurationSeconds))) {
            updates.agentVideoDurationSeconds = Number(workflowVideoControlContract.defaultVideoSeconds || '8');
          }
          if (!Number.isFinite(Number(nodeData.agentVideoExtensionCount))) {
            updates.agentVideoExtensionCount = workflowVideoControlContract.defaultVideoExtensionCount;
          }
          if (typeof nodeData.agentContinueFromPreviousVideo !== 'boolean') {
            updates.agentContinueFromPreviousVideo = false;
          }
          if (typeof nodeData.agentContinueFromPreviousLastFrame !== 'boolean') {
            updates.agentContinueFromPreviousLastFrame = false;
          }
          if (typeof nodeData.agentGenerateAudio !== 'boolean') {
            updates.agentGenerateAudio = workflowVideoControlContract.defaultGenerateAudio;
          }
          if (!String(nodeData.agentPersonGeneration || '').trim() && workflowVideoControlContract.defaultPersonGeneration) {
            updates.agentPersonGeneration = workflowVideoControlContract.defaultPersonGeneration;
          }
          if (!String(nodeData.agentSubtitleMode || '').trim()) {
            updates.agentSubtitleMode = workflowVideoControlContract.defaultSubtitleMode;
          }
          if (!String(nodeData.agentSubtitleLanguage || '').trim() && workflowVideoControlContract.defaultSubtitleLanguage) {
            updates.agentSubtitleLanguage = workflowVideoControlContract.defaultSubtitleLanguage;
          }
          if (!String(nodeData.agentSubtitleScript || '').trim() && workflowVideoControlContract.defaultSubtitleScript) {
            updates.agentSubtitleScript = workflowVideoControlContract.defaultSubtitleScript;
          }
          if (!String(nodeData.agentStoryboardPrompt || '').trim() && workflowVideoControlContract.defaultStoryboardPrompt) {
            updates.agentStoryboardPrompt = workflowVideoControlContract.defaultStoryboardPrompt;
          }
          if (!String(nodeData.agentNegativePrompt || '').trim() && workflowVideoControlContract.defaultNegativePrompt) {
            updates.agentNegativePrompt = workflowVideoControlContract.defaultNegativePrompt;
          }
          if (!Number.isFinite(Number(nodeData.agentSeed))) {
            updates.agentSeed = workflowVideoControlContract.defaultSeed;
          }
          if (typeof nodeData.agentPromptExtend !== 'boolean') {
            updates.agentPromptExtend = workflowVideoControlContract.defaultEnhancePrompt;
          }
        }
        if (nextTaskType === 'audio-gen') {
          if (!String(nodeData.agentAudioFormat || '').trim()) {
            updates.agentAudioFormat = 'mp3';
          }
          if (!Number.isFinite(Number(nodeData.agentSpeechSpeed))) {
            updates.agentSpeechSpeed = 1;
          }
        }
        if (nextTaskType === 'vision-understand' && !String(nodeData.agentOutputFormat || '').trim()) {
          updates.agentOutputFormat = 'json';
        }
        if (nextTaskType === 'data-analysis' && !String(nodeData.agentOutputFormat || '').trim()) {
          updates.agentOutputFormat = 'markdown';
        }
        const overrideProviderId = String(nodeData.modelOverrideProviderId || '').trim();
        const overrideModelId = String(nodeData.modelOverrideModelId || '').trim();

        if (overrideProviderId) {
          const overrideModel = findModelById(overrideProviderId, overrideModelId);
          if (!isTaskCompatible(overrideModel, nextTaskType)) {
            const fallback = pickCompatibleModel(overrideProviderId, nextTaskType);
            updates.modelOverrideModelId = fallback?.id || '';
          }
          updateNodeData(updates);
          return;
        }

        const baseProviderId = String(nodeData.agentProviderId || '').trim();
        const baseModelId = String(nodeData.agentModelId || '').trim();
        if (!baseProviderId) {
          updateNodeData(updates);
          return;
        }
        const baseModel = findModelById(baseProviderId, baseModelId);
        if (!isTaskCompatible(baseModel, nextTaskType)) {
          const fallback = pickCompatibleModel(baseProviderId, nextTaskType);
          if (fallback?.id) {
            updates.modelOverrideProviderId = baseProviderId;
            updates.modelOverrideModelId = fallback.id;
          }
        }
        updateNodeData(updates);
      };
      const duplicateFieldKeys = agentDefaultAnalysis.duplicated.map((item) => item.fieldKey);
      const clearDuplicatedAgentDefaults = () => {
        if (duplicateFieldKeys.length === 0) {
          return;
        }
        const updates: Partial<CustomNodeData> = {};
        duplicateFieldKeys.forEach((fieldKey) => {
          (updates as Record<string, undefined>)[String(fieldKey)] = undefined;
        });
        updateNodeData(updates);
      };
      const renderAgentDefaultFieldList = (
        title: string,
        items: typeof agentDefaultAnalysis.inherited,
        toneClassName: string,
        emptyText: string,
      ) => (
        <div>
          <div className="text-[11px] text-slate-400 mb-1">{title}</div>
          {items.length === 0 ? (
            <div className="text-[10px] text-slate-500">{emptyText}</div>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {items.map((item) => (
                <div
                  key={`${item.status}-${item.fieldKey}`}
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] ${toneClassName}`}
                >
                  <span className="font-medium">{item.label}</span>
                  <span className="opacity-80">
                    {item.status === 'overridden'
                      ? `${item.agentValue || '默认'} → ${item.nodeValue || '空'}`
                      : (item.agentValue || item.nodeValue || '已配置')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      );

      return (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">选择智能体</label>
            <AgentSelector
              value={nodeData.agentId || ''}
              agentName={nodeData.agentName || ''}
              onResolvedAgent={setResolvedAgent}
              onChange={(agentId, agentName, agent) => {
                updateNodeData({
                  agentId,
                  agentName,
                  agentProviderId: agent?.providerId || '',
                  agentModelId: agent?.modelId || '',
                  modelOverrideProviderId: '',
                  modelOverrideModelId: '',
                  ...buildAgentNodeDefaultsFromAgent(agent),
                });
              }}
            />
          </div>

          {resolvedAgent && (
            <div className="p-2.5 rounded-lg border border-teal-500/20 bg-teal-500/5 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs text-teal-300 font-medium">Agent 默认值继承分析</div>
                  <div className="mt-1 text-[10px] text-slate-500">
                    节点会继承 Agent 默认值；只有与默认不同的字段才值得保留在节点上。
                  </div>
                </div>
                {agentDefaultAnalysis.duplicated.length > 0 && (
                  <button
                    type="button"
                    onClick={clearDuplicatedAgentDefaults}
                    className="px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 text-[10px] text-amber-200 hover:bg-amber-500/20 transition-colors"
                  >
                    清理重复字段 {agentDefaultAnalysis.duplicated.length}
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5 text-[10px]">
                {resolvedAgent.source?.label && (
                  <div className="inline-flex px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200">
                    来源: {resolvedAgent.source.label}
                  </div>
                )}
                {resolvedAgent.runtime?.label && (
                  <div className="inline-flex px-1.5 py-0.5 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">
                    Runtime: {resolvedAgent.runtime.label}
                  </div>
                )}
                <div className="inline-flex px-1.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
                  继承 {agentDefaultAnalysis.inherited.length}
                </div>
                <div className="inline-flex px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200">
                  重复 {agentDefaultAnalysis.duplicated.length}
                </div>
                <div className="inline-flex px-1.5 py-0.5 rounded border border-indigo-500/30 bg-indigo-500/10 text-indigo-200">
                  覆盖 {agentDefaultAnalysis.overridden.length}
                </div>
              </div>
              {renderAgentDefaultFieldList(
                '继承中的默认值',
                agentDefaultAnalysis.inherited.slice(0, 8),
                'border border-emerald-500/20 bg-emerald-500/10 text-emerald-200',
                '当前没有可继承的 Agent 默认值。',
              )}
              {renderAgentDefaultFieldList(
                '与 Agent 默认重复的节点字段',
                agentDefaultAnalysis.duplicated,
                'border border-amber-500/20 bg-amber-500/10 text-amber-200',
                '当前没有重复字段。',
              )}
              {renderAgentDefaultFieldList(
                '节点级覆盖',
                agentDefaultAnalysis.overridden,
                'border border-indigo-500/20 bg-indigo-500/10 text-indigo-200',
                '当前没有节点级覆盖。',
              )}
            </div>
          )}

          <div className="p-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5">
            <div className="text-xs text-indigo-300 font-medium mb-2">节点级模型覆盖（可选）</div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1.5">覆盖提供商</label>
                <select
                  value={selectedProviderId}
                  onChange={(e) => {
                    const providerId = e.target.value;
                    const provider = providers.find((item) => item.providerId === providerId);
                    const firstModel = pickProviderDefaultModel(provider, selectedTaskType);
                    updateNodeData({
                      modelOverrideProviderId: providerId,
                      modelOverrideModelId: providerId ? (firstModel?.id || '') : '',
                    });
                  }}
                  data-field-key="modelOverrideProviderId"
                  disabled={providersLoading}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 disabled:opacity-50"
                >
                  <option value="">跟随智能体默认</option>
                  {providers.map((provider) => (
                    <option key={provider.providerId} value={provider.providerId}>
                      {provider.providerName}
                    </option>
                  ))}
                </select>
              </div>
              {selectedProviderId && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1.5">覆盖模型</label>
                  <select
                    value={nodeData.modelOverrideModelId || ''}
                    onChange={(e) => updateNodeData({ modelOverrideModelId: e.target.value })}
                    data-field-key="modelOverrideModelId"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
                  >
                    <option value="">请选择模型</option>
                    {selectedModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name} · {formatModelTaskHint(model.supportedTasks)}
                      </option>
                    ))}
                  </select>
                  {providerHasNoCompatibleModels && (
                    <div className="mt-1 text-[10px] text-amber-300">
                      当前提供商没有可用于该任务的兼容模型，已阻止回退到不兼容模型。
                    </div>
                  )}
                  {selectedOverrideModel && !modelSupportsTask(selectedOverrideModel, selectedTaskType) && (
                    <div className="mt-1 text-[10px] text-amber-300">
                      当前覆盖模型与任务类型不匹配，建议清空或切换到兼容模型。
                    </div>
                  )}
                </div>
              )}
              <div className="text-[10px] text-slate-500">
                当前生效模型：{effectiveProvider && effectiveModel ? `${effectiveProvider} / ${effectiveModel}` : '未配置'}
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1.5">覆盖 Profile ID（可选）</label>
                <input
                  type="text"
                  value={nodeData.modelOverrideProfileId || ''}
                  onChange={(e) => updateNodeData({ modelOverrideProfileId: e.target.value })}
                  data-field-key="modelOverrideProfileId"
                  placeholder="例如 profile-google-prod"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
                />
                <div className="mt-1 text-[10px] text-slate-500">
                  仅在同 Provider 多配置档并存时使用；留空则按当前活动配置。
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1.5">温度（可选）</label>
                  <input
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={nodeData.agentTemperature ?? ''}
                    onChange={(e) => {
                      const raw = e.target.value.trim();
                      updateNodeData({ agentTemperature: raw === '' ? undefined : Number(raw) });
                    }}
                    data-field-key="agentTemperature"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
                    placeholder="默认"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1.5">Max Tokens（可选）</label>
                  <input
                    type="number"
                    min={1}
                    max={65536}
                    step={1}
                    value={nodeData.agentMaxTokens ?? ''}
                    onChange={(e) => {
                      const raw = e.target.value.trim();
                      updateNodeData({ agentMaxTokens: raw === '' ? undefined : Number(raw) });
                    }}
                    data-field-key="agentMaxTokens"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
                    placeholder="默认"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(nodeData.agentPreferLatestModel)}
                  onChange={(e) => updateNodeData({ agentPreferLatestModel: e.target.checked })}
                  data-field-key="agentPreferLatestModel"
                  className="accent-indigo-500"
                />
                优先自动选择当前任务可用的最新模型
              </label>
            </div>
          </div>

          {/* 任务类型选择 */}
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">任务类型</label>
            <select
              value={nodeData.agentTaskType || 'chat'}
              onChange={(e) => {
                const nextTaskType = (
                  ['chat', 'image-gen', 'image-edit', 'video-gen', 'audio-gen', 'vision-understand', 'data-analysis'].includes(e.target.value)
                    ? e.target.value
                    : 'chat'
                ) as AgentTaskType;
                handleAgentTaskTypeChange(nextTaskType);
              }}
              data-field-key="agentTaskType"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
            >
              {taskOptions.map((option) => {
                const unsupported = hasEffectiveTaskConstraint && !effectiveSupportedTasks.includes(option.value);
                return (
                  <option
                    key={`agent-task-${option.value}`}
                    value={option.value}
                    disabled={unsupported && option.value !== selectedTaskType}
                  >
                    {option.label}{unsupported ? '（当前模型不支持）' : ''}
                  </option>
                );
              })}
            </select>
            {hasEffectiveTaskConstraint && (
              <div className="mt-1 text-[10px] text-slate-500">
                当前模型支持：{effectiveSupportedTasks.join(' / ')}
              </div>
            )}
            {hasEffectiveTaskConstraint && !effectiveSupportedTasks.includes(selectedTaskType) && (
              <div className="mt-1 text-[10px] text-amber-300">
                当前任务类型与生效模型不匹配，建议切换任务类型或模型。
              </div>
            )}
            {hasAgentReferenceImage && !taskSupportsReferenceImage && (
              <div className="mt-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-2">
                <div className="text-[11px] text-rose-300">
                  当前节点已配置参考图，但任务类型是 `{selectedTaskType}`。请改为 `vision-understand` 或 `image-edit`。
                </div>
                <button
                  type="button"
                  onClick={() => handleAgentTaskTypeChange('vision-understand')}
                  className="mt-2 px-2 py-1 text-[11px] rounded border border-indigo-500/40 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20"
                >
                  一键改为图片理解
                </button>
              </div>
            )}
          </div>

          {/* ========== 图片生成参数 ========== */}
          {(nodeData.agentTaskType === 'image-gen') && (() => {
            const _tier = nodeData.agentResolutionTier || '1K';
            const _ratio = nodeData.agentAspectRatio || '1:1';
            const _ratios = ['1:1','2:3','3:2','3:4','4:3','4:5','5:4','9:16','16:9','21:9'];
            const _tiers = [
              { v: '1K', l: '1K 标准' }, { v: '1.5K', l: '1.5K' },
              { v: '2K', l: '2K 高清' }, { v: '4K', l: '4K 超清' },
            ];
            return (
            <div className="space-y-3 p-2.5 rounded-lg border border-pink-500/20 bg-pink-500/5">
              <div className="text-xs text-pink-300 font-medium">图片生成参数</div>
              {/* 宽高比（联动显示像素） */}
              <div>
                <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                <select
                  value={_ratio}
                  onChange={(e) => updateNodeData({ agentAspectRatio: e.target.value })}
                  data-field-key="agentAspectRatio"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                >
                  {_ratios.map(r => <option key={r} value={r}>{r} ({getResolutionLabel(_tier, r)})</option>)}
                </select>
              </div>
              {/* 分辨率档位（联动显示像素） */}
              <div>
                <label className="block text-xs text-slate-500 mb-1">分辨率</label>
                <select
                  value={_tier}
                  onChange={(e) => updateNodeData({ agentResolutionTier: e.target.value })}
                  data-field-key="agentResolutionTier"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                >
                  {_tiers.map(t => <option key={t.v} value={t.v}>{t.l} ({getResolutionLabel(t.v, _ratio)})</option>)}
                </select>
              </div>
              {/* 数量 + 风格 */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">数量</label>
                  <select
                    value={nodeData.agentNumberOfImages ?? ''}
                    onChange={(e) => updateNodeData({ agentNumberOfImages: e.target.value ? Number(e.target.value) : undefined })}
                    data-field-key="agentNumberOfImages"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">默认(1)</option>
                    <option value="1">1 张</option>
                    <option value="2">2 张</option>
                    <option value="3">3 张</option>
                    <option value="4">4 张</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">风格</label>
                  <select
                    value={nodeData.agentImageStyle || ''}
                    onChange={(e) => updateNodeData({ agentImageStyle: e.target.value })}
                    data-field-key="agentImageStyle"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">无风格</option>
                    <option value="Photorealistic">写实</option>
                    <option value="Anime">动漫</option>
                    <option value="Digital Art">数字艺术</option>
                    <option value="Oil Painting">油画</option>
                    <option value="Cyberpunk">赛博朋克</option>
                    <option value="Watercolor">水彩</option>
                  </select>
                </div>
              </div>
              {/* 输出格式 + Seed */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                  <select
                    value={nodeData.agentOutputMimeType || ''}
                    onChange={(e) => updateNodeData({ agentOutputMimeType: e.target.value })}
                    data-field-key="agentOutputMimeType"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">默认(PNG)</option>
                    <option value="image/png">PNG</option>
                    <option value="image/jpeg">JPEG</option>
                    <option value="image/webp">WebP</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Seed</label>
                  <div className="flex gap-1">
                    <input
                      type="number"
                      value={nodeData.agentSeed ?? -1}
                      onChange={(e) => updateNodeData({ agentSeed: parseInt(e.target.value) || -1 })}
                      data-field-key="agentSeed"
                      className="flex-1 px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono focus:outline-none focus:border-teal-500/50"
                      placeholder="-1 随机"
                    />
                    <button
                      onClick={() => updateNodeData({ agentSeed: -1 })}
                      className="px-1.5 bg-slate-800 border border-slate-700 rounded hover:bg-slate-700 text-slate-400 text-xs"
                      title="随机"
                    >🎲</button>
                  </div>
                </div>
              </div>
              {/* 反向提示词 */}
              <div>
                <label className="block text-xs text-slate-500 mb-1">反向提示词</label>
                <input
                  type="text"
                  value={nodeData.agentNegativePrompt || ''}
                  onChange={(e) => updateNodeData({ agentNegativePrompt: e.target.value })}
                  data-field-key="agentNegativePrompt"
                  className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  placeholder="blurry, bad quality, distorted..."
                />
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(nodeData.agentPromptExtend)}
                  onChange={(e) => updateNodeData({ agentPromptExtend: e.target.checked })}
                  data-field-key="agentPromptExtend"
                  className="accent-teal-500"
                />
                启用提示词优化（provider 支持时生效）
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={nodeData.agentAddMagicSuffix !== false}
                  onChange={(e) => updateNodeData({ agentAddMagicSuffix: e.target.checked })}
                  data-field-key="agentAddMagicSuffix"
                  className="accent-teal-500"
                />
                启用提示词增强后缀（provider 支持时生效）
              </label>
            </div>
            );
          })()}

          {/* ========== 图片理解参数 ========== */}
          {(nodeData.agentTaskType === 'vision-understand') && (() => {
            const hasRef = !!(nodeData.agentReferenceImageUrl);
            return (
            <div className="space-y-3 p-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5">
              <div className="text-xs text-indigo-300 font-medium">图片理解参数</div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">参考图片 <span className="text-red-400">*</span></label>
                {hasRef && nodeData.agentReferenceImageUrl?.startsWith('data:') && (
                  <div className="mb-2 relative group">
                    <img
                      src={nodeData.agentReferenceImageUrl}
                      alt="参考图片"
                      className="w-full h-24 object-cover rounded border border-indigo-500/30"
                    />
                    <button
                      onClick={() => updateNodeData({ agentReferenceImageUrl: '' })}
                      className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X size={10} />
                    </button>
                  </div>
                )}
                <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-indigo-500/40 rounded-lg cursor-pointer hover:border-indigo-500/60 transition-colors">
                  <Upload size={12} className="text-indigo-300" />
                  <span className="text-xs text-indigo-200">{hasRef ? '更换图片' : '上传参考图片'}</span>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      try {
                        const [encoded] = await readInlineFilesAsDataUrls([file], '参考图片');
                        updateNodeData({ agentReferenceImageUrl: encoded || '' });
                      } catch (error) {
                        reportInlineUploadError('参考图片读取失败', error);
                      }
                      e.target.value = '';
                    }}
                  />
                </label>
                <input
                  type="text"
                  value={(!nodeData.agentReferenceImageUrl?.startsWith('data:')) ? (nodeData.agentReferenceImageUrl || '') : ''}
                  onChange={(e) => updateNodeData({ agentReferenceImageUrl: e.target.value })}
                  data-field-key="agentReferenceImageUrl"
                  className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-indigo-500/50"
                  placeholder="或输入 URL / {{prev.output.imageUrl}}"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                <select
                  value={nodeData.agentOutputFormat || 'json'}
                  onChange={(e) => updateNodeData({ agentOutputFormat: e.target.value })}
                  data-field-key="agentOutputFormat"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                >
                  <option value="json">JSON（推荐）</option>
                  <option value="markdown">Markdown</option>
                  <option value="text">Text</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">理解任务说明</label>
                <textarea
                  value={nodeData.inputMapping || ''}
                  onChange={(e) => updateNodeData({ inputMapping: e.target.value })}
                  rows={2}
                  data-field-key="inputMapping"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-indigo-500/50 resize-none"
                  placeholder="例如：识别主体、颜色、材质，并给出可保留/需规避元素"
                />
              </div>
            </div>
            );
          })()}

          {/* ========== 图片编辑参数 ========== */}
          {(nodeData.agentTaskType === 'image-edit') && (() => {
            const _tier = nodeData.agentResolutionTier || '1K';
            const _ratio = nodeData.agentAspectRatio || '1:1';
            const _ratios = ['1:1','2:3','3:2','3:4','4:3','9:16','16:9','21:9'];
            const _tiers = [
              { v: '1K', l: '1K 标准' }, { v: '2K', l: '2K 高清' }, { v: '4K', l: '4K 超清' },
            ];
            const _hasRef = !!(nodeData.agentReferenceImageUrl);
            return (
            <div className="space-y-3 p-2.5 rounded-lg border border-purple-500/20 bg-purple-500/5">
              <div className="text-xs text-purple-300 font-medium">图片编辑参数</div>
              {/* 参考图片上传 */}
              <div>
                <label className="block text-xs text-slate-500 mb-1">参考图片 <span className="text-red-400">*</span></label>
                {_hasRef && nodeData.agentReferenceImageUrl?.startsWith('data:') && (
                  <div className="mb-2 relative group">
                    <img src={nodeData.agentReferenceImageUrl} alt="参考图片"
                      className="w-full h-24 object-cover rounded border border-purple-500/30" />
                    <button onClick={() => updateNodeData({ agentReferenceImageUrl: '' })}
                      className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity">
                      <X size={10} />
                    </button>
                  </div>
                )}
                <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-purple-500/40 rounded-lg cursor-pointer hover:border-purple-500/60 transition-colors">
                  <Upload size={12} className="text-purple-400" />
                  <span className="text-xs text-purple-300">{_hasRef ? '更换图片' : '上传参考图片'}</span>
                  <input type="file" accept="image/*" className="hidden"
                    onChange={async (e) => {
                      const f = e.target.files?.[0]; if (!f) return;
                      try {
                        const [encoded] = await readInlineFilesAsDataUrls([f], '参考图片');
                        updateNodeData({ agentReferenceImageUrl: encoded || '' });
                      }
                      catch (err) { reportInlineUploadError('参考图片读取失败', err); }
                      e.target.value = '';
                    }} />
                </label>
                <input type="text"
                  value={(!nodeData.agentReferenceImageUrl?.startsWith('data:')) ? (nodeData.agentReferenceImageUrl || '') : ''}
                  onChange={(e) => updateNodeData({ agentReferenceImageUrl: e.target.value })}
                  data-field-key="agentReferenceImageUrl"
                  className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-purple-500/50"
                  placeholder="或输入 URL / {{prev.output.imageUrl}}" />
              </div>
              {/* 编辑指令 */}
              <div>
                <label className="block text-xs text-slate-500 mb-1">编辑指令</label>
                <textarea
                  value={nodeData.agentEditPrompt || ''}
                  onChange={(e) => updateNodeData({ agentEditPrompt: e.target.value })}
                  rows={2}
                  data-field-key="agentEditPrompt"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-purple-500/50 resize-none"
                  placeholder="描述你想要的编辑效果..."
                />
              </div>
              {/* 宽高比 + 分辨率（联动） */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                  <select value={_ratio}
                    onChange={(e) => updateNodeData({ agentAspectRatio: e.target.value })}
                    data-field-key="agentAspectRatio"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50">
                    <option value="">保持原比例</option>
                    {_ratios.map(r => <option key={r} value={r}>{r} ({getResolutionLabel(_tier, r)})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">分辨率</label>
                  <select value={_tier}
                    onChange={(e) => updateNodeData({ agentResolutionTier: e.target.value })}
                    data-field-key="agentResolutionTier"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50">
                    {_tiers.map(t => <option key={t.v} value={t.v}>{t.l} ({getResolutionLabel(t.v, _ratio || '1:1')})</option>)}
                  </select>
                </div>
              </div>
              {/* 数量 + 输出格式 */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">数量</label>
                  <select
                    value={nodeData.agentNumberOfImages ?? ''}
                    onChange={(e) => updateNodeData({ agentNumberOfImages: e.target.value ? Number(e.target.value) : undefined })}
                    data-field-key="agentNumberOfImages"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">默认(1)</option>
                    <option value="1">1 张</option>
                    <option value="2">2 张</option>
                    <option value="3">3 张</option>
                    <option value="4">4 张</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                  <select
                    value={nodeData.agentOutputMimeType || ''}
                    onChange={(e) => updateNodeData({ agentOutputMimeType: e.target.value })}
                    data-field-key="agentOutputMimeType"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">默认(PNG)</option>
                    <option value="image/png">PNG</option>
                    <option value="image/jpeg">JPEG</option>
                    <option value="image/webp">WebP</option>
                  </select>
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(nodeData.agentPromptExtend)}
                  onChange={(e) => updateNodeData({ agentPromptExtend: e.target.checked })}
                  data-field-key="agentPromptExtend"
                  className="accent-teal-500"
                />
                启用编辑提示词优化（provider 支持时生效）
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={nodeData.agentPreserveProductIdentity !== false}
                    onChange={(e) => updateNodeData({ agentPreserveProductIdentity: e.target.checked })}
                    data-field-key="agentPreserveProductIdentity"
                    className="accent-purple-500"
                  />
                  保留主体
                </label>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">重试次数</label>
                  <select
                    value={nodeData.agentImageEditMaxRetries ?? 1}
                    onChange={(e) => updateNodeData({ agentImageEditMaxRetries: Number(e.target.value) })}
                    data-field-key="agentImageEditMaxRetries"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-purple-500/50"
                  >
                    <option value="0">0</option>
                    <option value="1">1</option>
                    <option value="2">2</option>
                    <option value="3">3</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">匹配阈值（50-95）</label>
                <input
                  type="number"
                  min={50}
                  max={95}
                  step={1}
                  value={nodeData.agentProductMatchThreshold ?? 70}
                  onChange={(e) => {
                    const raw = Number(e.target.value);
                    const safe = Number.isFinite(raw) ? Math.max(50, Math.min(95, Math.round(raw))) : 70;
                    updateNodeData({ agentProductMatchThreshold: safe });
                  }}
                  data-field-key="agentProductMatchThreshold"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-purple-500/50"
                />
              </div>
            </div>
            );
          })()}

          {/* ========== 视频生成参数 ========== */}
          {(nodeData.agentTaskType === 'video-gen') && (() => {
            const aspectRatioOptions = workflowVideoControlContract.validAspectRatios.length > 0
              ? workflowVideoControlContract.validAspectRatios
              : ['16:9', '9:16'];
            const videoAspectRatio = aspectRatioOptions.includes(String(nodeData.agentAspectRatio || '').trim())
              ? String(nodeData.agentAspectRatio || '').trim()
              : workflowVideoControlContract.defaultAspectRatio;
            const resolutionOptions = workflowVideoSchema?.resolutionTiers?.length
              ? workflowVideoSchema.resolutionTiers
              : [
                { value: '720p', label: '720p', baseResolution: '1280×720' },
                { value: '1080p', label: '1080p', baseResolution: '1920×1080' },
                { value: '4k', label: '4k', baseResolution: '3840×2160' },
              ];
            const resolutionValues = resolutionOptions.map((item) => item.value);
            const videoResolution = normalizeWorkflowVideoResolutionSelection(
              nodeData.agentResolutionTier,
              resolutionValues,
              workflowVideoControlContract.defaultResolution,
            );
            const durationOptions = workflowVideoControlContract.validSeconds.length > 0
              ? workflowVideoControlContract.validSeconds
              : [workflowVideoControlContract.defaultVideoSeconds];
            const videoDuration = normalizeWorkflowVideoSecondsSelection(
              nodeData.agentVideoDurationSeconds,
              durationOptions,
              workflowVideoControlContract.defaultVideoSeconds,
            );
            const extensionOptions = getVideoExtensionOptions(workflowVideoControlContract, videoDuration);
            const validExtensionCounts = extensionOptions.map((item) => item.count);
            const videoExtensionCount = normalizeWorkflowVideoExtensionSelection(
              nodeData.agentVideoExtensionCount,
              validExtensionCounts.length > 0 ? validExtensionCounts : [0],
              workflowVideoControlContract.defaultVideoExtensionCount,
            );
            const continueFromPreviousVideo = Boolean(nodeData.agentContinueFromPreviousVideo);
            const continueFromPreviousLastFrame = Boolean(nodeData.agentContinueFromPreviousLastFrame);
            const promptExtendMandatory = workflowVideoControlContract.fieldPolicies.enhancePromptMandatory;
            const promptExtendValue = promptExtendMandatory
              ? true
              : Boolean(nodeData.agentPromptExtend ?? workflowVideoControlContract.defaultEnhancePrompt);
            const generateAudioForcedValue = workflowVideoControlContract.fieldPolicies.generateAudioForcedValue;
            const generateAudioValue = typeof generateAudioForcedValue === 'boolean'
              ? generateAudioForcedValue
              : Boolean(nodeData.agentGenerateAudio ?? workflowVideoControlContract.defaultGenerateAudio);
            const personGenerationOptions = workflowVideoControlContract.validPersonGenerationValues;
            const personGenerationValue = personGenerationOptions.includes(String(nodeData.agentPersonGeneration || '').trim())
              ? String(nodeData.agentPersonGeneration || '').trim()
              : workflowVideoControlContract.defaultPersonGeneration;
            const subtitleModeOptions = workflowVideoControlContract.validSubtitleModes.length > 0
              ? workflowVideoControlContract.validSubtitleModes
              : ['none'];
            const subtitleModeValue = subtitleModeOptions.includes(String(nodeData.agentSubtitleMode || '').trim())
              ? String(nodeData.agentSubtitleMode || '').trim()
              : workflowVideoControlContract.defaultSubtitleMode;
            const subtitleLanguageOptions = workflowVideoControlContract.validSubtitleLanguages;
            const subtitleLanguageValue = subtitleLanguageOptions.includes(String(nodeData.agentSubtitleLanguage || '').trim())
              ? String(nodeData.agentSubtitleLanguage || '').trim()
              : workflowVideoControlContract.defaultSubtitleLanguage;
            const extensionSummary = extensionOptions.find((item) => item.count === videoExtensionCount);
            return (
            <div className="space-y-3 p-2.5 rounded-lg border border-fuchsia-500/20 bg-fuchsia-500/5">
              <div className="text-xs text-fuchsia-300 font-medium">视频生成参数</div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                  <select
                    value={videoAspectRatio}
                    onChange={(e) => updateNodeData({ agentAspectRatio: e.target.value })}
                    data-field-key="agentAspectRatio"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  >
                    {aspectRatioOptions.map((item) => (
                      <option key={item} value={item}>
                        {item} {item === '16:9' ? '横屏' : item === '9:16' ? '竖屏' : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">分辨率</label>
                  <select
                    value={videoResolution}
                    onChange={(e) => updateNodeData({
                      agentResolutionTier: e.target.value,
                      ...(videoExtensionCount > 0
                        && workflowVideoControlContract.extensionConstraints.requireResolutionValues.length > 0
                        && !workflowVideoControlContract.extensionConstraints.requireResolutionValues.includes(e.target.value)
                        ? { agentVideoExtensionCount: 0 }
                        : {}),
                    })}
                    data-field-key="agentResolutionTier"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  >
                    {resolutionOptions.map((item) => (
                      <option key={item.value} value={item.value}>
                        {getWorkflowVideoResolutionLabel(videoAspectRatio, item.value, workflowVideoSchema)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">时长（秒）</label>
                  <select
                    value={videoDuration}
                    onChange={(e) => {
                      const nextSeconds = e.target.value;
                      const nextExtensionOptions = getVideoExtensionOptions(workflowVideoControlContract, nextSeconds);
                      updateNodeData({
                        agentVideoDurationSeconds: Number(nextSeconds),
                        agentVideoExtensionCount: normalizeWorkflowVideoExtensionSelection(
                          nodeData.agentVideoExtensionCount,
                          nextExtensionOptions.map((item) => item.count),
                          workflowVideoControlContract.defaultVideoExtensionCount,
                        ),
                      });
                    }}
                    data-field-key="agentVideoDurationSeconds"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  >
                    {durationOptions.map((item) => (
                      <option key={item} value={item}>
                        {item}s
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {extensionOptions.length > 0 && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">官方延长次数</label>
                    <select
                      value={String(videoExtensionCount)}
                      onChange={(e) => updateNodeData({ agentVideoExtensionCount: Number(e.target.value) })}
                      data-field-key="agentVideoExtensionCount"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      {extensionOptions.map((item) => (
                        <option key={item.count} value={item.count}>
                          {item.count === 0 ? '不延长' : `延长 ${item.count} 次`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="rounded border border-fuchsia-500/20 bg-slate-900/40 px-2.5 py-1.5">
                    <div className="text-[10px] text-slate-500">预计总时长</div>
                    <div className="text-xs text-slate-200">
                      {extensionSummary ? `${extensionSummary.totalSeconds}s` : `${videoDuration}s`}
                    </div>
                  </div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2">
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={promptExtendValue}
                    disabled={promptExtendMandatory}
                    onChange={(e) => updateNodeData({ agentPromptExtend: e.target.checked })}
                    data-field-key="agentPromptExtend"
                    className="accent-fuchsia-500 disabled:opacity-60"
                  />
                  AI 增强提示词
                </label>
                {workflowVideoControlContract.fieldPolicies.generateAudioAvailable && (
                  <label className="flex items-center gap-2 text-xs text-slate-300">
                    <input
                      type="checkbox"
                      checked={generateAudioValue}
                      disabled={typeof generateAudioForcedValue === 'boolean'}
                      onChange={(e) => updateNodeData({ agentGenerateAudio: e.target.checked })}
                      data-field-key="agentGenerateAudio"
                      className="accent-fuchsia-500 disabled:opacity-60"
                    />
                    生成音频
                  </label>
                )}
              </div>
              {personGenerationOptions.length > 0 && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1">人物生成</label>
                  <select
                    value={personGenerationValue}
                    onChange={(e) => updateNodeData({ agentPersonGeneration: e.target.value })}
                    data-field-key="agentPersonGeneration"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  >
                    <option value="">默认</option>
                    {personGenerationOptions.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-xs text-slate-500 mb-1">分镜提示词（可选）</label>
                <textarea
                  value={nodeData.agentStoryboardPrompt || ''}
                  onChange={(e) => updateNodeData({ agentStoryboardPrompt: e.target.value })}
                  data-field-key="agentStoryboardPrompt"
                  rows={4}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50 resize-y"
                  placeholder="Shot 1: macro lace cuff... Shot 2: styling reveal..."
                />
              </div>
              {subtitleModeOptions.length > 0 && (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">字幕模式</label>
                      <select
                        value={subtitleModeValue}
                        onChange={(e) => updateNodeData({ agentSubtitleMode: e.target.value })}
                        data-field-key="agentSubtitleMode"
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                      >
                        {subtitleModeOptions.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    </div>
                    {subtitleLanguageOptions.length > 0 && subtitleModeValue !== 'none' && (
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">字幕语言</label>
                        <select
                          value={subtitleLanguageValue}
                          onChange={(e) => updateNodeData({ agentSubtitleLanguage: e.target.value })}
                          data-field-key="agentSubtitleLanguage"
                          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                        >
                          {subtitleLanguageOptions.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                  {subtitleModeValue !== 'none' && (
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">字幕脚本（可选）</label>
                      <textarea
                        value={nodeData.agentSubtitleScript || ''}
                        onChange={(e) => updateNodeData({ agentSubtitleScript: e.target.value })}
                        data-field-key="agentSubtitleScript"
                        rows={3}
                        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50 resize-y"
                        placeholder="每行一句字幕，或留空让模型按分镜生成。"
                      />
                    </div>
                  )}
                </>
              )}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Seed</label>
                  <input
                    type="number"
                    value={nodeData.agentSeed ?? workflowVideoControlContract.defaultSeed}
                    onChange={(e) => updateNodeData({ agentSeed: Number(e.target.value) || 0 })}
                    data-field-key="agentSeed"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono focus:outline-none focus:border-fuchsia-500/50"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">反向提示词</label>
                  <input
                    type="text"
                    value={nodeData.agentNegativePrompt || ''}
                    onChange={(e) => updateNodeData({ agentNegativePrompt: e.target.value })}
                    data-field-key="agentNegativePrompt"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="避免出现的画面元素..."
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={continueFromPreviousVideo}
                  onChange={(e) => updateNodeData({
                    agentContinueFromPreviousVideo: e.target.checked,
                    ...(e.target.checked ? { agentContinueFromPreviousLastFrame: false } : {}),
                  })}
                  data-field-key="agentContinueFromPreviousVideo"
                  className="accent-fuchsia-500"
                />
                续接上一段视频结果
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={continueFromPreviousLastFrame}
                  onChange={(e) => updateNodeData({
                    agentContinueFromPreviousLastFrame: e.target.checked,
                    ...(e.target.checked ? { agentContinueFromPreviousVideo: false } : {}),
                  })}
                  data-field-key="agentContinueFromPreviousLastFrame"
                  className="accent-fuchsia-500"
                />
                以上一段最后一帧作为首帧
              </label>
              <div className="text-[10px] text-slate-500">
                直接续接会优先走 SDK 的视频扩展；尾帧桥接会提取上一段最后一帧，作为下一段视频的首帧输入。
              </div>
              <div className="text-[10px] text-slate-500">
                {workflowVideoControlContract.extensionConstraints.requireResolutionValues.length > 0
                  ? `官方延长当前要求分辨率：${workflowVideoControlContract.extensionConstraints.requireResolutionValues.join(', ')}`
                  : '不填源视频时是文生视频；只填参考图时是图生视频。'}
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">源视频 URL（可选）</label>
                <input
                  type="text"
                  value={nodeData.agentSourceVideoUrl || ''}
                  onChange={(e) => updateNodeData({ agentSourceVideoUrl: e.target.value })}
                  data-field-key="agentSourceVideoUrl"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  placeholder="https://... 或 {{prev.output.videoUrl}}"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">首帧参考图 / 图生视频（可选）</label>
                <input
                  type="text"
                  value={nodeData.agentReferenceImageUrl || ''}
                  onChange={(e) => updateNodeData({ agentReferenceImageUrl: e.target.value })}
                  data-field-key="agentReferenceImageUrl"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  placeholder="https://... 或 {{input-image.output.imageUrl}}"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">末帧图片（可选）</label>
                <input
                  type="text"
                  value={nodeData.agentLastFrameImageUrl || ''}
                  onChange={(e) => updateNodeData({ agentLastFrameImageUrl: e.target.value })}
                  data-field-key="agentLastFrameImageUrl"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  placeholder="https://... 或 {{input-last-frame.output.imageUrl}}"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">视频编辑掩码图（可选）</label>
                  <input
                    type="text"
                    value={nodeData.agentVideoMaskImageUrl || ''}
                    onChange={(e) => updateNodeData({ agentVideoMaskImageUrl: e.target.value })}
                    data-field-key="agentVideoMaskImageUrl"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="https://... 或 {{input-mask.output.imageUrl}}"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">掩码模式</label>
                  <select
                    value={nodeData.agentVideoMaskMode || ''}
                    onChange={(e) => updateNodeData({ agentVideoMaskMode: e.target.value })}
                    data-field-key="agentVideoMaskMode"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  >
                    <option value="">无</option>
                    <option value="REMOVE">REMOVE · 替换遮罩区域</option>
                    <option value="INSERT">INSERT · 插入新内容</option>
                    <option value="REMOVE_STATIC">REMOVE_STATIC · 清除静态区域</option>
                    <option value="OUTPAINT">OUTPAINT · 向外扩展</option>
                  </select>
                </div>
              </div>
            </div>
            );
          })()}

          {/* ========== 音频生成参数 ========== */}
          {(nodeData.agentTaskType === 'audio-gen') && (() => {
            const audioFormat = nodeData.agentAudioFormat || 'mp3';
            const audioSpeed = nodeData.agentSpeechSpeed ?? 1;
            return (
            <div className="space-y-3 p-2.5 rounded-lg border border-sky-500/20 bg-sky-500/5">
              <div className="text-xs text-sky-300 font-medium">音频生成参数</div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">音色</label>
                <input
                  type="text"
                  value={nodeData.agentVoice || ''}
                  onChange={(e) => updateNodeData({ agentVoice: e.target.value })}
                  data-field-key="agentVoice"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                  placeholder="留空时使用 provider 默认音色"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                  <select
                    value={audioFormat}
                    onChange={(e) => updateNodeData({ agentAudioFormat: e.target.value })}
                    data-field-key="agentAudioFormat"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                  >
                    <option value="mp3">MP3</option>
                    <option value="wav">WAV</option>
                    <option value="opus">OPUS</option>
                    <option value="aac">AAC</option>
                    <option value="flac">FLAC</option>
                    <option value="pcm">PCM</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">语速</label>
                  <input
                    type="number"
                    min={0.25}
                    max={4}
                    step={0.25}
                    value={audioSpeed}
                    onChange={(e) => {
                      const raw = Number(e.target.value);
                      const safe = Number.isFinite(raw) ? Math.max(0.25, Math.min(4, raw)) : 1;
                      updateNodeData({ agentSpeechSpeed: safe });
                    }}
                    data-field-key="agentSpeechSpeed"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
                  />
                </div>
              </div>
            </div>
            );
          })()}

          {/* ========== 数据分析参数 ========== */}
          {(nodeData.agentTaskType === 'data-analysis') && (() => {
            const _hasFile = !!(nodeData.agentFileUrl);
            const _fileName = nodeData.agentFileUrl?.startsWith('data:') ? '已上传文件' : (nodeData.agentFileUrl || '');
            return (
            <div className="space-y-3 p-2.5 rounded-lg border border-cyan-500/20 bg-cyan-500/5">
              <div className="text-xs text-cyan-300 font-medium">数据分析参数</div>
              {/* 文件上传 */}
              <div>
                <label className="block text-xs text-slate-500 mb-1">数据文件 <span className="text-red-400">*</span></label>
                {_hasFile && (
                  <div className="mb-2 flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-cyan-500/30">
                    <FileSpreadsheet size={14} className="text-cyan-400 flex-shrink-0" />
                    <span className="text-[10px] text-slate-300 truncate flex-1">{_fileName}</span>
                    <button onClick={() => updateNodeData({ agentFileUrl: '' })}
                      className="p-0.5 hover:bg-red-500/20 rounded text-red-400"><X size={10} /></button>
                  </div>
                )}
                <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-cyan-500/40 rounded-lg cursor-pointer hover:border-cyan-500/60 transition-colors">
                  <Upload size={12} className="text-cyan-400" />
                  <span className="text-xs text-cyan-300">{_hasFile ? '更换文件' : '上传文件'}</span>
                  <input type="file" accept=".csv,.xlsx,.xls,.json,.tsv,.txt" className="hidden"
                    onChange={async (e) => {
                      const f = e.target.files?.[0]; if (!f) return;
                      try { updateNodeData({ agentFileUrl: await fileToDataUrl(f) }); } catch { /* ignore */ }
                      e.target.value = '';
                    }} />
                </label>
                <input type="text"
                  value={(!nodeData.agentFileUrl?.startsWith('data:')) ? (nodeData.agentFileUrl || '') : ''}
                  onChange={(e) => updateNodeData({ agentFileUrl: e.target.value })}
                  data-field-key="agentFileUrl"
                  className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-cyan-500/50"
                  placeholder="或输入 URL / {{prev.output.fileUrl}}" />
                <div className="mt-1 text-[10px] text-slate-600">支持 Excel / CSV / JSON / TSV 文件</div>
              </div>
              {/* 输出格式 */}
              <div>
                <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                <select
                  value={nodeData.agentOutputFormat || ''}
                  onChange={(e) => updateNodeData({ agentOutputFormat: e.target.value })}
                  data-field-key="agentOutputFormat"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                >
                  <option value="">默认（文本）</option>
                  <option value="text">纯文本</option>
                  <option value="json">JSON</option>
                  <option value="markdown">Markdown 表格</option>
                </select>
              </div>
            </div>
            );
          })()}

          {/* 输出格式（对话模式） */}
          {(!nodeData.agentTaskType || nodeData.agentTaskType === 'chat') && (
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">输出格式</label>
              <select
                value={nodeData.agentOutputFormat || ''}
                onChange={(e) => updateNodeData({ agentOutputFormat: e.target.value })}
                data-field-key="agentOutputFormat"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
              >
                <option value="">默认（文本）</option>
                <option value="text">纯文本</option>
                <option value="json">JSON</option>
                <option value="markdown">Markdown</option>
              </select>
            </div>
          )}

          <div>
            <label className="block text-xs text-slate-500 mb-1">节点指令</label>
            <div className="flex items-start gap-1 mb-1.5">
              <Info size={10} className="text-slate-600 mt-0.5 flex-shrink-0" />
              <span className="text-[10px] text-slate-600">追加到 Agent System Prompt</span>
            </div>
            <textarea
              value={nodeData.instructions || ''}
              onChange={(e) => updateNodeData({ instructions: e.target.value })}
              rows={4}
              data-field-key="instructions"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
              placeholder="例如：请用中文回答，输出 JSON 格式..."
            />
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">输入映射</label>
            <div className="flex items-start gap-1 mb-1.5">
              <Info size={10} className="text-slate-600 mt-0.5 flex-shrink-0" />
              <span className="text-[10px] text-slate-600">留空默认使用上一节点输出</span>
            </div>
            <textarea
              value={nodeData.inputMapping || ''}
              onChange={(e) => updateNodeData({ inputMapping: e.target.value })}
              rows={2}
              data-field-key="inputMapping"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
              placeholder="{{prev.output.text}}"
            />
          </div>
        </div>
      );
    }

    return null;
  };

  const renderToolNodeConfig = () => {
    if (nodeType === 'tool') {
      const toolName = (nodeData.toolName || '').trim().toLowerCase().replace(/-/g, '_');
      const isImageGen = ['image_generate', 'generate_image', 'image_gen'].includes(toolName);
      const isImageEdit = ['image_edit', 'edit_image', 'image_chat_edit', 'image_mask_edit', 'image_inpainting', 'image_background_edit', 'image_recontext', 'image_outpaint', 'image_outpainting', 'expand_image'].includes(toolName);
      const isVideoGenerate = ['video_generate', 'generate_video', 'video_gen'].includes(toolName);
      const isVideoUnderstand = ['video_understand', 'understand_video'].includes(toolName);
      const isVideoDelete = ['video_delete', 'delete_video'].includes(toolName);
      const isPromptOptimize = ['prompt_optimize', 'prompt_optimizer', 'optimize_prompt', 'prompt_rewrite', 'rewrite_prompt'].includes(toolName);
      const isTableAnalyze = ['table_analyze', 'excel_analyze', 'analyze_table', 'sheet_analyze', 'sheet_profile'].includes(toolName);
      const isAmazonAdsOptimize = ['amazon_ads_keyword_optimize', 'amazon_ads_optimize', 'ads_keyword_optimize', 'amazon_ppc_optimize', 'amazon_search_term_optimize'].includes(toolName);
      const toolTaskType: AgentTaskType = isImageEdit
        ? 'image-edit'
        : isImageGen
          ? 'image-gen'
          : isVideoGenerate
            ? 'video-gen'
            : isVideoUnderstand
              ? 'vision-understand'
              : 'chat';
      const shouldShowToolModelOverride = isImageGen || isImageEdit || isPromptOptimize || isVideoGenerate || isVideoUnderstand;
      const shouldShowToolProviderOverride = shouldShowToolModelOverride || isVideoDelete;
      const selectedProviderId = nodeData.toolProviderId || '';
      const selectedProvider = providers.find((provider) => provider.providerId === selectedProviderId);
      const providerModels = selectedProvider?.allModels || selectedProvider?.models || [];
      const compatibleModels = providerModels.filter((model) => modelSupportsTask(model, toolTaskType));
      const selectedModels = compatibleModels;
      const providerHasNoCompatibleModels = selectedProviderId !== '' && providerModels.length > 0 && compatibleModels.length === 0;
      const selectedToolModel = providerModels.find((model) => model.id === (nodeData.toolModelId || ''));
      const isToolTaskCompatible = (model: ModelOption | undefined, taskType: AgentTaskType) => {
        return modelSupportsTask(model, taskType);
      };
      const findProviderModels = (providerId: string): ModelOption[] => {
        const provider = providers.find((item) => item.providerId === providerId);
        return provider?.allModels || provider?.models || [];
      };
      const pickCompatibleToolModel = (providerId: string, taskType: AgentTaskType): ModelOption | undefined => {
        const provider = providers.find((item) => item.providerId === providerId);
        return pickProviderDefaultModel(provider, taskType);
      };
      const handleToolNameChange = (nextToolName: string) => {
        const normalized = nextToolName.trim().toLowerCase().replace(/-/g, '_');
        const nextIsImageGen = ['image_generate', 'generate_image', 'image_gen'].includes(normalized);
        const nextIsImageEdit = [
          'image_edit', 'edit_image', 'image_chat_edit', 'image_mask_edit',
          'image_inpainting', 'image_background_edit', 'image_recontext',
          'image_outpaint', 'image_outpainting', 'expand_image',
        ].includes(normalized);
        const nextIsVideoGenerate = ['video_generate', 'generate_video', 'video_gen'].includes(normalized);
        const nextIsVideoUnderstand = ['video_understand', 'understand_video'].includes(normalized);
        const nextIsVideoDelete = ['video_delete', 'delete_video'].includes(normalized);
        const nextIsPromptOptimize = ['prompt_optimize', 'prompt_optimizer', 'optimize_prompt', 'prompt_rewrite', 'rewrite_prompt'].includes(normalized);
        const updates: Partial<CustomNodeData> = { toolName: nextToolName };

        if (nextIsVideoGenerate) {
          if (!String(nodeData.toolAspectRatio || '').trim()) {
            updates.toolAspectRatio = workflowVideoControlContract.defaultAspectRatio || '16:9';
          }
          if (!String(nodeData.toolResolutionTier || '').trim()) {
            updates.toolResolutionTier = workflowVideoControlContract.defaultResolution || '720p';
          }
          if (!Number.isFinite(Number(nodeData.toolVideoDurationSeconds))) {
            updates.toolVideoDurationSeconds = Number(workflowVideoControlContract.defaultVideoSeconds || '8');
          }
          if (!Number.isFinite(Number(nodeData.toolVideoExtensionCount))) {
            updates.toolVideoExtensionCount = workflowVideoControlContract.defaultVideoExtensionCount;
          }
          if (typeof nodeData.toolGenerateAudio !== 'boolean') {
            updates.toolGenerateAudio = workflowVideoControlContract.defaultGenerateAudio;
          }
          if (!String(nodeData.toolPersonGeneration || '').trim() && workflowVideoControlContract.defaultPersonGeneration) {
            updates.toolPersonGeneration = workflowVideoControlContract.defaultPersonGeneration;
          }
          if (!String(nodeData.toolSubtitleMode || '').trim()) {
            updates.toolSubtitleMode = workflowVideoControlContract.defaultSubtitleMode;
          }
          if (!String(nodeData.toolSubtitleLanguage || '').trim() && workflowVideoControlContract.defaultSubtitleLanguage) {
            updates.toolSubtitleLanguage = workflowVideoControlContract.defaultSubtitleLanguage;
          }
        }

        if (nextIsImageGen || nextIsImageEdit || nextIsPromptOptimize || nextIsVideoGenerate || nextIsVideoUnderstand) {
          const targetTask: AgentTaskType = nextIsImageEdit
            ? 'image-edit'
            : nextIsImageGen
              ? 'image-gen'
              : nextIsVideoGenerate
                ? 'video-gen'
                : nextIsVideoUnderstand
                  ? 'vision-understand'
                  : 'chat';
          const currentProviderId = String(nodeData.toolProviderId || '').trim();
          const currentModelId = String(nodeData.toolModelId || '').trim();

          if (currentProviderId) {
            const currentModel = findProviderModels(currentProviderId).find((model) => model.id === currentModelId);
            if (!isToolTaskCompatible(currentModel, targetTask)) {
              const fallback = pickCompatibleToolModel(currentProviderId, targetTask);
              updates.toolModelId = fallback?.id || '';
            }
          } else {
            const providerWithModel = providers.find((provider) => {
              const modelPool = provider.allModels || provider.models || [];
              return modelPool.some((model) => isToolTaskCompatible(model, targetTask));
            });

            if (providerWithModel?.providerId) {
              const fallback = pickCompatibleToolModel(providerWithModel.providerId, targetTask);
              updates.toolProviderId = providerWithModel.providerId;
              updates.toolModelId = fallback?.id || '';
            }
          }
        } else if (nextIsVideoDelete && !String(nodeData.toolProviderId || '').trim()) {
          const googleProvider = providers.find((provider) => provider.providerId === 'google');
          if (googleProvider?.providerId) {
            updates.toolProviderId = googleProvider.providerId;
            updates.toolModelId = '';
          }
        }

        updateNodeData(updates);
      };

      const parseToolArgs = () => {
        try {
          const parsed = JSON.parse(nodeData.toolArgsTemplate || '{}');
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            return parsed as Record<string, any>;
          }
        } catch {
          // ignore parse error
        }
        return {} as Record<string, any>;
      };

      const updateToolArgs = (patch: Record<string, any>) => {
        const current = parseToolArgs();
        updateNodeData({ toolArgsTemplate: JSON.stringify({ ...current, ...patch }) });
      };

      const amazonArgs = parseToolArgs();
      const amazonTargetAcosRaw = amazonArgs.targetAcos ?? '';
      const amazonTargetAcosValue = typeof amazonTargetAcosRaw === 'number'
        ? String(amazonTargetAcosRaw > 1 ? amazonTargetAcosRaw : amazonTargetAcosRaw * 100)
        : String(amazonTargetAcosRaw || '').replace('%', '');
      const promptOptimizeArgs = parseToolArgs();
      const promptOptimizePromptValue = String(promptOptimizeArgs.prompt ?? '');
      const promptOptimizeGoalValue = String(promptOptimizeArgs.goal ?? '');
      const promptOptimizeStyleValue = String(promptOptimizeArgs.style ?? '');
      const promptOptimizeLanguageValue = String(promptOptimizeArgs.language ?? 'auto');
      const promptOptimizeLengthValue = String(promptOptimizeArgs.length ?? 'medium');
      const promptOptimizeMustKeepValue = Array.isArray(promptOptimizeArgs.must_keep)
        ? promptOptimizeArgs.must_keep.join(', ')
        : String(promptOptimizeArgs.must_keep ?? '');
      const promptOptimizeAvoidValue = Array.isArray(promptOptimizeArgs.avoid)
        ? promptOptimizeArgs.avoid.join(', ')
        : String(promptOptimizeArgs.avoid ?? '');
      const promptOptimizeRequirementsValue = String(promptOptimizeArgs.requirements ?? '');
      const videoPromptValue = String(parseToolArgs().prompt ?? '');
      const videoUnderstandOutputFormatValue = String(parseToolArgs().output_format ?? 'markdown');
      const videoDeleteProviderFileNameValue = String(parseToolArgs().provider_file_name ?? '');
      const videoDeleteProviderFileUriValue = String(parseToolArgs().provider_file_uri ?? '');
      const videoDeleteGcsUriValue = String(parseToolArgs().gcs_uri ?? '');

      return (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">工具类型</label>
            <select
              value={nodeData.toolName || ''}
              onChange={(e) => handleToolNameChange(e.target.value)}
              data-field-key="toolName"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            >
              <option value="">请选择工具</option>
              <optgroup label="图片生成">
                <option value="image_generate">🖼️ 图片生成</option>
              </optgroup>
              <optgroup label="图片编辑">
                <option value="image_chat_edit">🪄 图片编辑（对话式）</option>
                <option value="image_mask_edit">🎭 蒙版编辑</option>
                <option value="image_inpainting">🖌️ 局部重绘</option>
                <option value="image_background_edit">🏞️ 背景替换</option>
                <option value="image_recontext">🔄 场景重构</option>
                <option value="image_outpaint">📐 图片扩展</option>
              </optgroup>
              <optgroup label="视频">
                <option value="video_generate">🎬 视频生成 / 图生视频</option>
                <option value="video_understand">🧠 视频理解</option>
                <option value="video_delete">🗑️ 视频删除</option>
              </optgroup>
              <optgroup label="数据分析">
                <option value="table_analyze">📊 表格分析</option>
                <option value="sheet_analyze">🧾 全量表格剖析</option>
                <option value="sheet_stage_ingest">🧱 Sheet Stage · Ingest</option>
                <option value="sheet_stage_profile">📐 Sheet Stage · Profile</option>
                <option value="sheet_stage_query">🔎 Sheet Stage · Query</option>
                <option value="sheet_stage_export">📤 Sheet Stage · Export</option>
                <option value="amazon_ads_keyword_optimize">🛒 Amazon 广告关键词优化</option>
              </optgroup>
              <optgroup label="搜索">
                <option value="web_search">🔍 网页搜索</option>
                <option value="google_search">🔍 网页搜索（兼容别名）</option>
                <option value="read_webpage">📖 网页读取</option>
                <option value="selenium_browse">🧭 浏览器抓取</option>
              </optgroup>
              <optgroup label="MCP">
                <option value="mcp_tool_call">🧩 MCP 工具调用</option>
              </optgroup>
              <optgroup label="数据处理">
                <option value="json_extract">📋 JSON 提取</option>
                <option value="text_length">📏 文本长度</option>
              </optgroup>
              <optgroup label="提示词">
                <option value="prompt_optimize">✨ 提示词优化</option>
              </optgroup>
            </select>
          </div>

          {shouldShowToolProviderOverride && (
            <div className="p-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5 space-y-3">
              <div className="text-xs text-indigo-300 font-medium">
                {isPromptOptimize
                  ? '文本模型覆盖（可选）'
                  : isVideoGenerate
                    ? '视频生成模型覆盖（可选）'
                    : isVideoUnderstand
                      ? '视频理解模型覆盖（可选）'
                      : isVideoDelete
                        ? '视频删除 Provider（必填）'
                        : '图片模型覆盖（可选）'}
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1.5">提供商</label>
                <select
                  value={selectedProviderId}
                  onChange={(e) => {
                    const providerId = e.target.value;
                    const provider = providers.find((item) => item.providerId === providerId);
                    const fallbackModel = pickProviderDefaultModel(provider, toolTaskType);
                    updateNodeData({
                      toolProviderId: providerId,
                      toolModelId: shouldShowToolModelOverride && providerId ? (fallbackModel?.id || '') : '',
                    });
                  }}
                  data-field-key="toolProviderId"
                  disabled={providersLoading}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 disabled:opacity-50"
                >
                  <option value="">自动选择（按已配置 provider 回退）</option>
                  {providers.map((provider) => (
                    <option key={provider.providerId} value={provider.providerId}>
                      {provider.providerName}
                    </option>
                  ))}
                </select>
              </div>
              {selectedProviderId && shouldShowToolModelOverride && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1.5">模型</label>
                  <select
                    value={nodeData.toolModelId || ''}
                    onChange={(e) => updateNodeData({ toolModelId: e.target.value })}
                    data-field-key="toolModelId"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20"
                  >
                    <option value="">请选择模型</option>
                    {selectedModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name} · {formatModelTaskHint(model.supportedTasks)}
                      </option>
                    ))}
                  </select>
                  {providerHasNoCompatibleModels && (
                    <div className="mt-1 text-[10px] text-amber-300">
                      当前提供商没有可用于该工具任务的兼容模型，已阻止回退到不兼容模型。
                    </div>
                  )}
                  {selectedToolModel && !modelSupportsTask(selectedToolModel, toolTaskType) && (
                    <div className="mt-1 text-[10px] text-amber-300">
                      当前覆盖模型与工具任务类型不匹配，建议清空或切换到兼容模型。
                    </div>
                  )}
                </div>
              )}
              <div className="text-[10px] text-slate-500">
                当前生效：{selectedProviderId
                  ? (nodeData.toolModelId || !shouldShowToolModelOverride
                      ? `${selectedProviderId}${nodeData.toolModelId ? ` / ${nodeData.toolModelId}` : ''}`
                      : `${selectedProviderId} / 自动回退`)
                  : '自动回退选择'}
              </div>
            </div>
          )}

          {/* 图片生成参数 */}
          {isImageGen && (() => {
            const parsedArgs = parseToolArgs();
            const promptValue = String(parsedArgs.prompt ?? '');
            const tier = nodeData.toolResolutionTier || nodeData.toolImageSize || '1K';
            const ratio = nodeData.toolAspectRatio || '1:1';
            const ratios = ['1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'];
            const tiers = [
              { value: '1K', label: '1K 标准' },
              { value: '1.25K', label: '1.25K' },
              { value: '1.5K', label: '1.5K' },
              { value: '2K', label: '2K 高清' },
            ];
            return (
              <div className="space-y-3 p-2.5 rounded-lg border border-pink-500/20 bg-pink-500/5">
                <div className="text-xs text-pink-300 font-medium">图片生成参数</div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">提示词</label>
                  <textarea
                    value={promptValue}
                    onChange={(e) => updateToolArgs({ prompt: e.target.value || '{{input.task}}' })}
                    rows={2}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
                    placeholder="{{input.task}}"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                    <select
                      value={ratio}
                      onChange={(e) => updateNodeData({ toolAspectRatio: e.target.value })}
                      data-field-key="toolAspectRatio"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                    >
                      {ratios.map((item) => (
                        <option key={item} value={item}>
                          {item} ({getResolutionLabel(tier, item)})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">分辨率</label>
                    <select
                      value={tier}
                      onChange={(e) => updateNodeData({ toolResolutionTier: e.target.value })}
                      data-field-key="toolResolutionTier"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                    >
                      {tiers.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label} ({getResolutionLabel(item.value, ratio)})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">数量</label>
                    <select
                      value={nodeData.toolNumberOfImages ?? ''}
                      onChange={(e) => updateNodeData({ toolNumberOfImages: e.target.value ? Number(e.target.value) : undefined })}
                      data-field-key="toolNumberOfImages"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                    >
                      <option value="">默认(1)</option>
                      <option value="1">1 张</option>
                      <option value="2">2 张</option>
                      <option value="3">3 张</option>
                      <option value="4">4 张</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">风格</label>
                    <select
                      value={nodeData.toolImageStyle || ''}
                      onChange={(e) => updateNodeData({ toolImageStyle: e.target.value })}
                      data-field-key="toolImageStyle"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                    >
                      <option value="">默认</option>
                      <option value="photorealistic">写实</option>
                      <option value="digital_art">数字艺术</option>
                      <option value="anime">动漫</option>
                      <option value="watercolor">水彩</option>
                      <option value="oil_painting">油画</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                  <select
                    value={nodeData.toolOutputMimeType || ''}
                    onChange={(e) => updateNodeData({ toolOutputMimeType: e.target.value })}
                    data-field-key="toolOutputMimeType"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">默认(PNG)</option>
                    <option value="image/png">PNG</option>
                    <option value="image/jpeg">JPEG</option>
                    <option value="image/webp">WebP</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">反向提示词</label>
                  <input
                    type="text"
                    value={nodeData.toolNegativePrompt || ''}
                    onChange={(e) => updateNodeData({ toolNegativePrompt: e.target.value })}
                    data-field-key="toolNegativePrompt"
                    className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                    placeholder="不希望出现的内容..."
                  />
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={Boolean(nodeData.toolPromptExtend)}
                    onChange={(e) => updateNodeData({ toolPromptExtend: e.target.checked })}
                    data-field-key="toolPromptExtend"
                    className="accent-teal-500"
                  />
                  启用提示词优化（provider 支持时生效）
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={nodeData.toolAddMagicSuffix !== false}
                    onChange={(e) => updateNodeData({ toolAddMagicSuffix: e.target.checked })}
                    data-field-key="toolAddMagicSuffix"
                    className="accent-teal-500"
                  />
                  启用提示词增强后缀（provider 支持时生效）
                </label>
              </div>
            );
          })()}

          {isVideoGenerate && (() => {
            const aspectRatioOptions = workflowVideoControlContract.validAspectRatios.length > 0
              ? workflowVideoControlContract.validAspectRatios
              : ['16:9', '9:16'];
            const aspectRatio = aspectRatioOptions.includes(String(nodeData.toolAspectRatio || '').trim())
              ? String(nodeData.toolAspectRatio || '').trim()
              : workflowVideoControlContract.defaultAspectRatio;
            const resolutionOptions = workflowVideoSchema?.resolutionTiers?.length
              ? workflowVideoSchema.resolutionTiers
              : [
                { value: '720p', label: '720p', baseResolution: '1280×720' },
                { value: '1080p', label: '1080p', baseResolution: '1920×1080' },
                { value: '4k', label: '4k', baseResolution: '3840×2160' },
              ];
            const resolution = normalizeWorkflowVideoResolutionSelection(
              nodeData.toolResolutionTier,
              resolutionOptions.map((item) => item.value),
              workflowVideoControlContract.defaultResolution,
            );
            const durationOptions = workflowVideoControlContract.validSeconds.length > 0
              ? workflowVideoControlContract.validSeconds
              : [workflowVideoControlContract.defaultVideoSeconds];
            const duration = normalizeWorkflowVideoSecondsSelection(
              nodeData.toolVideoDurationSeconds,
              durationOptions,
              workflowVideoControlContract.defaultVideoSeconds,
            );
            const extensionOptions = getVideoExtensionOptions(workflowVideoControlContract, duration);
            const toolVideoExtensionCount = normalizeWorkflowVideoExtensionSelection(
              nodeData.toolVideoExtensionCount,
              extensionOptions.map((item) => item.count),
              workflowVideoControlContract.defaultVideoExtensionCount,
            );
            return (
              <div className="space-y-3 p-2.5 rounded-lg border border-fuchsia-500/20 bg-fuchsia-500/5">
                <div className="text-xs text-fuchsia-300 font-medium">视频生成参数</div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">提示词</label>
                  <textarea
                    value={videoPromptValue}
                    onChange={(e) => updateToolArgs({ prompt: e.target.value || '{{input.task}}' })}
                    rows={3}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 focus:ring-1 focus:ring-fuchsia-500/20 resize-none"
                    placeholder="{{input.task}}"
                  />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                    <select
                      value={aspectRatio}
                      onChange={(e) => updateNodeData({ toolAspectRatio: e.target.value })}
                      data-field-key="toolAspectRatio"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      {aspectRatioOptions.map((item) => (
                        <option key={item} value={item}>
                          {item} {item === '16:9' ? '横屏' : item === '9:16' ? '竖屏' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">分辨率</label>
                    <select
                      value={resolution}
                      onChange={(e) => updateNodeData({
                        toolResolutionTier: e.target.value,
                        ...(toolVideoExtensionCount > 0
                          && workflowVideoControlContract.extensionConstraints.requireResolutionValues.length > 0
                          && !workflowVideoControlContract.extensionConstraints.requireResolutionValues.includes(e.target.value)
                          ? { toolVideoExtensionCount: 0 }
                          : {}),
                      })}
                      data-field-key="toolResolutionTier"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      {resolutionOptions.map((item) => (
                        <option key={item.value} value={item.value}>
                          {getWorkflowVideoResolutionLabel(aspectRatio, item.value, workflowVideoSchema)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">时长（秒）</label>
                    <select
                      value={duration}
                      onChange={(e) => {
                        const nextSeconds = e.target.value;
                        const nextExtensionOptions = getVideoExtensionOptions(workflowVideoControlContract, nextSeconds);
                        updateNodeData({
                          toolVideoDurationSeconds: Number(nextSeconds),
                          toolVideoExtensionCount: normalizeWorkflowVideoExtensionSelection(
                            nodeData.toolVideoExtensionCount,
                            nextExtensionOptions.map((item) => item.count),
                            workflowVideoControlContract.defaultVideoExtensionCount,
                          ),
                        });
                      }}
                      data-field-key="toolVideoDurationSeconds"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      {durationOptions.map((item) => (
                        <option key={item} value={item}>
                          {item}s
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {extensionOptions.length > 0 && (
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">官方延长次数</label>
                      <select
                        value={String(toolVideoExtensionCount)}
                        onChange={(e) => updateNodeData({ toolVideoExtensionCount: Number(e.target.value) })}
                        data-field-key="toolVideoExtensionCount"
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                      >
                        {extensionOptions.map((item) => (
                          <option key={item.count} value={item.count}>
                            {item.count === 0 ? '不延长' : `延长 ${item.count} 次`}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="rounded border border-fuchsia-500/20 bg-slate-900/40 px-2.5 py-1.5">
                      <div className="text-[10px] text-slate-500">预计总时长</div>
                      <div className="text-xs text-slate-200">
                        {extensionOptions.find((item) => item.count === toolVideoExtensionCount)?.totalSeconds ?? duration}s
                      </div>
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <label className="flex items-center gap-2 text-xs text-slate-300">
                    <input
                      type="checkbox"
                      checked={Boolean(nodeData.toolPromptExtend ?? workflowVideoControlContract.defaultEnhancePrompt)}
                      onChange={(e) => updateNodeData({ toolPromptExtend: e.target.checked })}
                      data-field-key="toolPromptExtend"
                      className="accent-fuchsia-500"
                    />
                    AI 增强提示词
                  </label>
                  {workflowVideoControlContract.fieldPolicies.generateAudioAvailable && (
                    <label className="flex items-center gap-2 text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={Boolean(nodeData.toolGenerateAudio ?? workflowVideoControlContract.defaultGenerateAudio)}
                        onChange={(e) => updateNodeData({ toolGenerateAudio: e.target.checked })}
                        data-field-key="toolGenerateAudio"
                        className="accent-fuchsia-500"
                      />
                      生成音频
                    </label>
                  )}
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">分镜提示词（可选）</label>
                  <textarea
                    value={nodeData.toolStoryboardPrompt || ''}
                    onChange={(e) => updateNodeData({ toolStoryboardPrompt: e.target.value })}
                    data-field-key="toolStoryboardPrompt"
                    rows={3}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 resize-none"
                    placeholder="Shot 1: product hero... Shot 2: tracking close-up..."
                  />
                </div>
                {workflowVideoControlContract.validPersonGenerationValues.length > 0 && (
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">人物生成</label>
                    <select
                      value={String(nodeData.toolPersonGeneration || workflowVideoControlContract.defaultPersonGeneration || '')}
                      onChange={(e) => updateNodeData({ toolPersonGeneration: e.target.value })}
                      data-field-key="toolPersonGeneration"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      <option value="">默认</option>
                      {workflowVideoControlContract.validPersonGenerationValues.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {workflowVideoControlContract.validSubtitleModes.length > 0 && (
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">字幕模式</label>
                        <select
                          value={String(nodeData.toolSubtitleMode || workflowVideoControlContract.defaultSubtitleMode || 'none')}
                          onChange={(e) => updateNodeData({ toolSubtitleMode: e.target.value })}
                          data-field-key="toolSubtitleMode"
                          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                        >
                          {workflowVideoControlContract.validSubtitleModes.map((item) => (
                            <option key={item} value={item}>
                              {item}
                            </option>
                          ))}
                        </select>
                      </div>
                      {workflowVideoControlContract.validSubtitleLanguages.length > 0
                        && String(nodeData.toolSubtitleMode || workflowVideoControlContract.defaultSubtitleMode || 'none') !== 'none' && (
                        <div>
                          <label className="block text-xs text-slate-500 mb-1">字幕语言</label>
                          <select
                            value={String(nodeData.toolSubtitleLanguage || workflowVideoControlContract.defaultSubtitleLanguage || '')}
                            onChange={(e) => updateNodeData({ toolSubtitleLanguage: e.target.value })}
                            data-field-key="toolSubtitleLanguage"
                            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                          >
                            {workflowVideoControlContract.validSubtitleLanguages.map((item) => (
                              <option key={item} value={item}>
                                {item}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                    {String(nodeData.toolSubtitleMode || workflowVideoControlContract.defaultSubtitleMode || 'none') !== 'none' && (
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">字幕脚本（可选）</label>
                        <textarea
                          value={nodeData.toolSubtitleScript || ''}
                          onChange={(e) => updateNodeData({ toolSubtitleScript: e.target.value })}
                          data-field-key="toolSubtitleScript"
                          rows={3}
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 resize-none"
                          placeholder="每行一句字幕，或留空让模型按分镜生成。"
                        />
                      </div>
                    )}
                  </>
                )}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">源视频 URL（可选，视频续接 / 视频编辑）</label>
                  <input
                    type="text"
                    value={nodeData.toolSourceVideoUrl || ''}
                    onChange={(e) => updateNodeData({ toolSourceVideoUrl: e.target.value })}
                    data-field-key="toolSourceVideoUrl"
                    className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="https://... 或 {{prev.output.videoUrl}}"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">首帧参考图 / 图生视频（可选）</label>
                  <input
                    type="text"
                    value={nodeData.toolReferenceImageUrl || ''}
                    onChange={(e) => updateNodeData({ toolReferenceImageUrl: e.target.value })}
                    data-field-key="toolReferenceImageUrl"
                    className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="https://... 或 {{input-image.output.imageUrl}}"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">末帧图片（可选）</label>
                  <input
                    type="text"
                    value={nodeData.toolLastFrameImageUrl || ''}
                    onChange={(e) => updateNodeData({ toolLastFrameImageUrl: e.target.value })}
                    data-field-key="toolLastFrameImageUrl"
                    className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="https://... 或 {{prev.output.lastFrameImageUrl}}"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">视频编辑掩码图（可选）</label>
                    <input
                      type="text"
                      value={nodeData.toolVideoMaskImageUrl || ''}
                      onChange={(e) => updateNodeData({ toolVideoMaskImageUrl: e.target.value })}
                      data-field-key="toolVideoMaskImageUrl"
                      className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                      placeholder="https://... 或 {{input-mask.output.imageUrl}}"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">掩码模式</label>
                    <select
                      value={nodeData.toolVideoMaskMode || ''}
                      onChange={(e) => updateNodeData({ toolVideoMaskMode: e.target.value })}
                      data-field-key="toolVideoMaskMode"
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    >
                      <option value="">无</option>
                      <option value="REMOVE">REMOVE · 替换遮罩区域</option>
                      <option value="INSERT">INSERT · 插入新内容</option>
                      <option value="REMOVE_STATIC">REMOVE_STATIC · 清除静态区域</option>
                      <option value="OUTPAINT">OUTPAINT · 向外扩展</option>
                    </select>
                  </div>
                </div>
                <div className="text-[10px] text-slate-500">
                  不填源视频时是文生视频；只填参考图时是图生视频；同时填源视频 + 掩码时走视频编辑。
                </div>
              </div>
            );
          })()}

          {isVideoUnderstand && (
            <div className="space-y-3 p-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/5">
              <div className="text-xs text-indigo-300 font-medium">视频理解参数</div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">分析提示词</label>
                <textarea
                  value={videoPromptValue}
                  onChange={(e) => updateToolArgs({ prompt: e.target.value || '请分析该视频的主要场景、动作、镜头变化和关键信息。' })}
                  rows={3}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 resize-none"
                  placeholder="请分析该视频的主要场景、动作、镜头变化和关键信息。"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">源视频 URL</label>
                <input
                  type="text"
                  value={nodeData.toolSourceVideoUrl || ''}
                  onChange={(e) => updateNodeData({ toolSourceVideoUrl: e.target.value })}
                  data-field-key="toolSourceVideoUrl"
                  className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                  placeholder="https://... 或 {{prev.output.videoUrl}}"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                <select
                  value={videoUnderstandOutputFormatValue}
                  onChange={(e) => updateToolArgs({ output_format: e.target.value || 'markdown' })}
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                >
                  <option value="markdown">Markdown</option>
                  <option value="json">JSON</option>
                  <option value="text">文本</option>
                </select>
              </div>
            </div>
          )}

          {isVideoDelete && (
            <div className="space-y-3 p-2.5 rounded-lg border border-rose-500/20 bg-rose-500/5">
              <div className="text-xs text-rose-300 font-medium">视频删除参数</div>
              <div className="text-[10px] text-slate-500">
                如果当前节点接在视频生成节点后面，留空即可自动读取上一节点的 provider 资产信息。
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Provider File Name（Gemini Files）</label>
                <input
                  type="text"
                  value={videoDeleteProviderFileNameValue}
                  onChange={(e) => updateToolArgs({ provider_file_name: e.target.value || undefined })}
                  className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-rose-500/50"
                  placeholder="files/..."
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Provider File URI（可选）</label>
                <input
                  type="text"
                  value={videoDeleteProviderFileUriValue}
                  onChange={(e) => updateToolArgs({ provider_file_uri: e.target.value || undefined })}
                  className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-rose-500/50"
                  placeholder="files/... 或 gs://..."
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">GCS URI（Vertex）</label>
                <input
                  type="text"
                  value={videoDeleteGcsUriValue}
                  onChange={(e) => updateToolArgs({ gcs_uri: e.target.value || undefined })}
                  className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-rose-500/50"
                  placeholder="gs://bucket/path/video.mp4"
                />
              </div>
            </div>
          )}

          {/* 提示词优化参数 */}
          {isPromptOptimize && (
            <div className="space-y-3 p-2.5 rounded-lg border border-fuchsia-500/20 bg-fuchsia-500/5">
              <div className="text-xs text-fuchsia-300 font-medium">提示词优化参数</div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">原始提示词</label>
                <textarea
                  value={promptOptimizePromptValue}
                  onChange={(e) => updateToolArgs({ prompt: e.target.value || '{{input.task}}' })}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 focus:ring-1 focus:ring-fuchsia-500/20 resize-none"
                  placeholder="{{input.task}}"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">优化目标</label>
                <input
                  type="text"
                  value={promptOptimizeGoalValue}
                  onChange={(e) => updateToolArgs({ goal: e.target.value || undefined })}
                  className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  placeholder="如：电商主图生成，强调主体和构图"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">风格</label>
                  <input
                    type="text"
                    value={promptOptimizeStyleValue}
                    onChange={(e) => updateToolArgs({ style: e.target.value || undefined })}
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                    placeholder="专业 / 创意 / 营销"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">长度</label>
                  <select
                    value={promptOptimizeLengthValue}
                    onChange={(e) => updateToolArgs({ length: e.target.value || 'medium' })}
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  >
                    <option value="short">短</option>
                    <option value="medium">中</option>
                    <option value="long">长</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">输出语言</label>
                <select
                  value={promptOptimizeLanguageValue}
                  onChange={(e) => updateToolArgs({ language: e.target.value || 'auto' })}
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                >
                  <option value="auto">自动</option>
                  <option value="zh-CN">中文</option>
                  <option value="en-US">English</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">必须保留关键词（逗号分隔）</label>
                <input
                  type="text"
                  value={promptOptimizeMustKeepValue}
                  onChange={(e) => {
                    const keywords = e.target.value
                      .split(/[,，;\n]+/)
                      .map((item) => item.trim())
                      .filter(Boolean);
                    updateToolArgs({ must_keep: keywords.length > 0 ? keywords : undefined });
                  }}
                  className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  placeholder="主体名称, 材质, 品牌元素"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">禁止元素（逗号分隔）</label>
                <input
                  type="text"
                  value={promptOptimizeAvoidValue}
                  onChange={(e) => {
                    const keywords = e.target.value
                      .split(/[,，;\n]+/)
                      .map((item) => item.trim())
                      .filter(Boolean);
                    updateToolArgs({ avoid: keywords.length > 0 ? keywords : undefined });
                  }}
                  className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-fuchsia-500/50"
                  placeholder="水印, 低质量, 变形"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">附加约束</label>
                <textarea
                  value={promptOptimizeRequirementsValue}
                  onChange={(e) => updateToolArgs({ requirements: e.target.value || undefined })}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-fuchsia-500/50 focus:ring-1 focus:ring-fuchsia-500/20 resize-none"
                  placeholder="如：必须可直接用于 image generation API，不要解释文本"
                />
              </div>
            </div>
          )}

          {/* 图片编辑参数 */}
          {isImageEdit && (
            <div className="space-y-3 p-2.5 rounded-lg border border-purple-500/20 bg-purple-500/5">
              <div className="text-xs text-purple-300 font-medium">图片编辑参数</div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">参考图片 <span className="text-red-400">*</span></label>
                {!!nodeData.toolReferenceImageUrl && nodeData.toolReferenceImageUrl.startsWith('data:') && (
                  <div className="mb-2 relative group">
                    <img
                      src={nodeData.toolReferenceImageUrl}
                      alt="参考图片"
                      className="w-full h-24 object-cover rounded border border-purple-500/30"
                    />
                    <button
                      onClick={() => updateNodeData({ toolReferenceImageUrl: '' })}
                      className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X size={10} />
                    </button>
                  </div>
                )}
                <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-purple-500/40 rounded-lg cursor-pointer hover:border-purple-500/60 transition-colors">
                  <Upload size={12} className="text-purple-400" />
                  <span className="text-xs text-purple-300">{nodeData.toolReferenceImageUrl ? '更换图片' : '上传参考图片'}</span>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      try {
                        updateNodeData({ toolReferenceImageUrl: await fileToDataUrl(file) });
                      } catch (err) {
                        reportError('文件转换失败', err);
                      }
                      e.target.value = '';
                    }}
                  />
                </label>
                <input
                  type="text"
                  value={(!nodeData.toolReferenceImageUrl?.startsWith('data:')) ? (nodeData.toolReferenceImageUrl || '') : ''}
                  onChange={(e) => updateNodeData({ toolReferenceImageUrl: e.target.value })}
                  data-field-key="toolReferenceImageUrl"
                  className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-purple-500/50"
                  placeholder="或输入 URL / {{prev.output.imageUrl}}"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">编辑指令</label>
                <textarea
                  value={nodeData.toolEditPrompt || ''}
                  onChange={(e) => updateNodeData({ toolEditPrompt: e.target.value })}
                  rows={2}
                  data-field-key="toolEditPrompt"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
                  placeholder="描述你想要的编辑效果..."
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">宽高比</label>
                  <select
                    value={nodeData.toolAspectRatio || ''}
                    onChange={(e) => updateNodeData({ toolAspectRatio: e.target.value })}
                    data-field-key="toolAspectRatio"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">保持原比例</option>
                    <option value="1:1">1:1</option>
                    <option value="16:9">16:9</option>
                    <option value="9:16">9:16</option>
                    <option value="4:3">4:3</option>
                    <option value="3:4">3:4</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">数量</label>
                  <select
                    value={nodeData.toolNumberOfImages ?? ''}
                    onChange={(e) => updateNodeData({ toolNumberOfImages: e.target.value ? Number(e.target.value) : undefined })}
                    data-field-key="toolNumberOfImages"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">默认(1)</option>
                    <option value="1">1 张</option>
                    <option value="2">2 张</option>
                    <option value="3">3 张</option>
                    <option value="4">4 张</option>
                  </select>
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={Boolean(nodeData.toolPromptExtend)}
                  onChange={(e) => updateNodeData({ toolPromptExtend: e.target.checked })}
                  data-field-key="toolPromptExtend"
                  className="accent-teal-500"
                />
                启用编辑提示词优化（provider 支持时生效）
              </label>
            </div>
          )}

          {/* 表格分析参数 */}
          {isTableAnalyze && (
            <div className="space-y-3 p-2.5 rounded-lg border border-cyan-500/20 bg-cyan-500/5">
              <div className="text-xs text-cyan-300 font-medium">表格分析参数</div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">分析类型</label>
                <select
                  value={nodeData.toolAnalysisType || 'comprehensive'}
                  onChange={(e) => updateNodeData({ toolAnalysisType: e.target.value })}
                  data-field-key="toolAnalysisType"
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                >
                  <option value="comprehensive">综合分析</option>
                  <option value="statistics">描述统计</option>
                  <option value="correlation">相关性分析</option>
                  <option value="trends">趋势分析</option>
                  <option value="distribution">分布与异常</option>
                </select>
              </div>
            </div>
          )}

          {/* Amazon 广告优化参数 */}
          {isAmazonAdsOptimize && (
            <div className="space-y-3 p-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5">
              <div className="text-xs text-amber-300 font-medium">Amazon 广告优化参数</div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">目标 ACoS（%）</label>
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={amazonTargetAcosValue}
                  onChange={(e) => {
                    const nextValue = e.target.value.trim();
                    if (!nextValue) {
                      updateToolArgs({ targetAcos: undefined });
                      return;
                    }
                    const numeric = Number(nextValue);
                    if (Number.isFinite(numeric) && numeric > 0) {
                      updateToolArgs({ targetAcos: numeric });
                    }
                  }}
                  className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-amber-500/50"
                  placeholder="例如 30"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">优化目标说明</label>
                <textarea
                  value={String(amazonArgs.query || '')}
                  onChange={(e) => updateToolArgs({ query: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/20 resize-none"
                  placeholder="例如：控 ACOS 到 30% 以内，并扩大高转化词流量"
                />
              </div>
              <div className="text-[10px] text-slate-500">
                文件请通过“文件输入组件”传入，工具会自动识别表头并输出否定词/加投词建议。
              </div>
            </div>
          )}

          {/* 高级：原始参数模板（所有工具通用） */}
          <details className="group">
            <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400 flex items-center gap-1">
              <span className="group-open:rotate-90 transition-transform">▶</span>
              高级：自定义参数 JSON
            </summary>
            <div className="mt-2">
              <textarea
                value={nodeData.toolArgsTemplate || ''}
                onChange={(e) => updateNodeData({ toolArgsTemplate: e.target.value })}
                rows={3}
                data-field-key="toolArgsTemplate"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
                placeholder={'{"query":"{{prev.output.text}}"}'}
              />
              <div className="mt-1 text-[10px] text-slate-600">
                支持模板变量：{'{{input.task}}'}, {'{{prev.output.text}}'}
              </div>
            </div>
          </details>
        </div>
      );
    }

    return null;
  };

  const renderResultNodeConfig = () => {
    if (nodeType === 'end') {
      const hasInlineResult = nodeData.result !== undefined && nodeData.result !== null;
      return (
        <div className="space-y-4">
          <div className="p-2.5 rounded-lg border border-rose-500/20 bg-rose-500/5">
            <div className="text-xs text-rose-300 font-medium">结束出口配置</div>
            <div className="mt-1 text-[10px] text-slate-500">结束节点内置最终结果预览，并可打开独立结果面板查看完整输出。</div>
          </div>
          {hasInlineResult ? (
            <div className="p-2.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 space-y-2">
              <div className="text-xs text-indigo-200 font-medium">结束结果预览</div>
              {resultPreviewUrls.length > 0 && (
                <div>
                  <div className="text-[11px] text-slate-400 mb-1">结果图片共 {resultPreviewUrls.length} 张</div>
                  <div className="grid grid-cols-4 gap-2 max-h-56 overflow-y-auto pr-1">
                    {resultPreviewUrls.map((imageUrl, index) => (
                      <img
                        key={`${selectedNode.id}-end-result-${index}`}
                        src={imageUrl}
                        alt={`end-result-${index + 1}`}
                        className="w-full h-16 object-cover rounded border border-slate-700 bg-slate-900"
                      />
                    ))}
                  </div>
                </div>
              )}
              {resultPreviewVideoUrls.length > 0 && (
                <div>
                  <div className="text-[11px] text-slate-400 mb-1">结果视频共 {resultPreviewVideoUrls.length} 条</div>
                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                    {resultPreviewVideoUrls.map((videoUrl, index) => (
                      <video
                        key={`${selectedNode.id}-end-video-${index}`}
                        src={videoUrl}
                        controls
                        className="w-full rounded border border-slate-700 bg-slate-900"
                      />
                    ))}
                  </div>
                </div>
              )}
              {resultPreviewAudioUrls.length > 0 && (
                <div>
                  <div className="text-[11px] text-slate-400 mb-1">结果音频共 {resultPreviewAudioUrls.length} 条</div>
                  <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                    {resultPreviewAudioUrls.map((audioUrl, index) => (
                      <audio
                        key={`${selectedNode.id}-end-audio-${index}`}
                        src={audioUrl}
                        controls
                        className="w-full"
                      />
                    ))}
                  </div>
                </div>
              )}
              {resultPreviewText && (
                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words max-h-[160px] overflow-y-auto">
                  {resultPreviewText}
                </pre>
              )}
            </div>
          ) : (
            <div className="p-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-[11px] text-slate-400">
              当前还没有结束结果，执行工作流后会自动显示。
            </div>
          )}
          {status === 'failed' && nodeData.error && (
            <div className="p-2.5 rounded-lg border border-red-500/30 bg-red-500/10 text-[11px] text-red-300 whitespace-pre-wrap break-words">
              {nodeData.error}
            </div>
          )}
          <button
            onClick={(event) => {
              dispatchScopedWorkflowEvent('workflow:end-request', event.currentTarget, {
                nodeId: String(selectedNode.id),
              });
            }}
            className="w-full px-3 py-2 text-xs rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 transition-colors"
          >
            打开结束结果
          </button>
        </div>
      );
    }

    return null;
  };


  const renderNodeConfigEditor = () => {
    const startInputNodeConfig = renderStartInputNodeConfig();
    if (startInputNodeConfig) {
      return startInputNodeConfig;
    }
    const resultNodeConfig = renderResultNodeConfig();
    if (resultNodeConfig) {
      return resultNodeConfig;
    }

    const agentNodeConfig = renderAgentNodeConfig();
    if (agentNodeConfig) {
      return agentNodeConfig;
    }
    if (nodeType === 'condition') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">条件表达式</label>
            <div className="flex items-start gap-1 mb-1.5">
              <Info size={10} className="text-slate-600 mt-0.5 flex-shrink-0" />
              <span className="text-[10px] text-slate-600">支持模板变量，例如 {'{{prev.output.text}}'}</span>
            </div>
            <textarea
              value={nodeData.expression || ''}
              onChange={(e) => updateNodeData({ expression: e.target.value })}
              rows={3}
              data-field-key="expression"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
              placeholder="{{prev.output.text}}.includes('通过')"
            />
          </div>
          <div className="p-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-[11px] text-slate-400">
            True 分支使用上方输出口，False 分支使用下方输出口。
          </div>
        </div>
      );
    }

    if (nodeType === 'router') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">路由策略</label>
            <select
              value={nodeData.routerStrategy || 'intent'}
              onChange={(e) => updateNodeData({ routerStrategy: e.target.value as CustomNodeData['routerStrategy'] })}
              data-field-key="routerStrategy"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            >
              <option value="intent">Intent（推荐）</option>
              <option value="keyword">Keyword</option>
              <option value="llm">LLM 分类</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">路由提示词</label>
            <textarea
              value={nodeData.routerPrompt || ''}
              onChange={(e) => updateNodeData({ routerPrompt: e.target.value })}
              rows={3}
              data-field-key="routerPrompt"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
              placeholder="根据任务意图将输入分发到最合适的分支..."
            />
          </div>
        </div>
      );
    }

    if (nodeType === 'parallel') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">汇聚模式</label>
            <select
              value={nodeData.joinMode || 'wait_all'}
              onChange={(e) => updateNodeData({ joinMode: e.target.value as CustomNodeData['joinMode'] })}
              data-field-key="joinMode"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            >
              <option value="wait_all">等待全部分支完成</option>
              <option value="race_first">任一分支先完成即返回</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">超时（秒）</label>
            <input
              type="number"
              min={5}
              value={nodeData.timeoutSeconds ?? 60}
              onChange={(e) => updateNodeData({ timeoutSeconds: Math.max(5, Number(e.target.value) || 60) })}
              data-field-key="timeoutSeconds"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            />
          </div>
        </div>
      );
    }

    if (nodeType === 'merge') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">结果合并策略</label>
            <select
              value={nodeData.mergeStrategy || 'append'}
              onChange={(e) => updateNodeData({ mergeStrategy: e.target.value as CustomNodeData['mergeStrategy'] })}
              data-field-key="mergeStrategy"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            >
              <option value="append">顺序拼接</option>
              <option value="json_merge">JSON 合并</option>
              <option value="latest">选择最新结果</option>
            </select>
          </div>
        </div>
      );
    }

    if (nodeType === 'loop') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">循环条件</label>
            <textarea
              value={nodeData.loopCondition || ''}
              onChange={(e) => updateNodeData({ loopCondition: e.target.value })}
              rows={2}
              data-field-key="loopCondition"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
              placeholder="{{prev.output.retry}} < 3"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">最大迭代次数</label>
            <input
              type="number"
              min={1}
              value={nodeData.maxIterations ?? 3}
              onChange={(e) => updateNodeData({ maxIterations: Math.max(1, Number(e.target.value) || 1) })}
              data-field-key="maxIterations"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            />
          </div>
        </div>
      );
    }

    const toolNodeConfig = renderToolNodeConfig();
    if (toolNodeConfig) {
      return toolNodeConfig;
    }
    if (nodeType === 'human') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">人工审核提示</label>
            <textarea
              value={nodeData.approvalPrompt || ''}
              onChange={(e) => updateNodeData({ approvalPrompt: e.target.value })}
              rows={3}
              data-field-key="approvalPrompt"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
              placeholder="请确认输出是否满足业务规则..."
            />
          </div>
        </div>
      );
    }

    return (
      <div className="p-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-[11px] text-slate-400">
        当前节点暂无额外可配置项。
      </div>
    );
  };

  return (
    <div ref={panelRootRef} className="w-[340px] bg-slate-900 border-l border-slate-800 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className={`w-6 h-6 ${config.iconColor} rounded flex items-center justify-center text-white text-xs`}>
            {config.icon}
          </span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-200 truncate">{nodeData.label || config.label}</div>
            <div className="text-[10px] text-slate-500">{config.label} · {config.category}</div>
          </div>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded transition-colors flex-shrink-0">
          <X size={16} className="text-slate-500" />
        </button>
      </div>

      {/* Content */}
      <div ref={panelContentRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Label */}
        <div>
          <label className="block text-xs text-slate-500 mb-1.5">节点名称</label>
          <input type="text" value={nodeData.label || ''}
            onChange={(e) => updateNodeData({ label: e.target.value })}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            placeholder="节点名称" />
        </div>

        {/* Description */}
        <div>
          <label className="block text-xs text-slate-500 mb-1.5">描述</label>
          <textarea value={nodeData.description || ''}
            onChange={(e) => updateNodeData({ description: e.target.value })}
            rows={2}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
            placeholder="节点描述" />
        </div>

        <div className="pt-1 border-t border-slate-800">
          <div className="text-xs text-slate-400 mb-2 font-medium">连接端口</div>
          {isFixedPortLayout ? (
            <div className="p-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-[11px] text-slate-400">
              该节点端口固定：左 {resolvedPortLayout.left} · 右 {resolvedPortLayout.right} · 上 {resolvedPortLayout.top} · 下 {resolvedPortLayout.bottom}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">左侧</label>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={resolvedPortLayout.left}
                  onChange={(e) => updatePortLayoutCount('left', e.target.value)}
                  data-field-key="portLayout.left"
                  className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">右侧</label>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={resolvedPortLayout.right}
                  onChange={(e) => updatePortLayoutCount('right', e.target.value)}
                  data-field-key="portLayout.right"
                  className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">上侧</label>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={resolvedPortLayout.top}
                  onChange={(e) => updatePortLayoutCount('top', e.target.value)}
                  data-field-key="portLayout.top"
                  className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">下侧</label>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={resolvedPortLayout.bottom}
                  onChange={(e) => updatePortLayoutCount('bottom', e.target.value)}
                  data-field-key="portLayout.bottom"
                  className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                />
              </div>
            </div>
          )}
        </div>

        <div className="pt-1 border-t border-slate-800">
          <div className="text-xs text-slate-400 mb-2 font-medium">节点配置</div>
          {renderNodeConfigEditor()}
        </div>

        <div className="pt-1 border-t border-slate-800">
          <div className="text-xs text-slate-400 mb-2 font-medium">容错策略</div>
          <label className="flex items-center gap-2 text-xs text-slate-300">
            <input
              type="checkbox"
              checked={Boolean(nodeData.continueOnError)}
              onChange={(e) => updateNodeData({ continueOnError: e.target.checked })}
              data-field-key="continueOnError"
              className="accent-amber-500"
            />
            失败后继续执行
          </label>
        </div>

        {/* Execution Status */}
        <div className="pt-1 border-t border-slate-800">
          <label className="block text-xs text-slate-500 mb-1.5">执行状态</label>
          <div className={`flex items-center gap-2 px-3 py-2 ${statusDisplay.bgColor} rounded-lg border border-slate-700/50`}>
            <StatusIcon size={14} className={`${statusDisplay.color} ${status === 'running' ? 'animate-spin' : ''}`} />
            <span className={`text-xs font-medium ${statusDisplay.color}`}>{statusDisplay.label}</span>
          </div>

          {typeof nodeData.progress === 'number' && status !== 'pending' && (
            <div className="mt-2">
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-teal-500 transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, nodeData.progress))}%` }}
                />
              </div>
            </div>
          )}

          {/* Timing */}
          {(nodeData.startTime || nodeData.endTime) && (
            <div className="mt-2 text-[10px] text-slate-600 space-y-0.5">
              {nodeData.startTime && nodeData.endTime && (
                <div className="text-slate-400">
                  耗时: {((nodeData.endTime - nodeData.startTime) / 1000).toFixed(2)}s
                </div>
              )}
            </div>
          )}
        </div>

        <PropertiesPanelResultSection
          nodeData={nodeData}
          selectedNodeId={selectedNode.id}
          sourcePreviewUrl={sourcePreviewUrl}
          resultPreviewUrls={resultPreviewUrls}
          resultPreviewAudioUrls={resultPreviewAudioUrls}
          resultPreviewVideoUrls={resultPreviewVideoUrls}
          resultPreviewText={resultPreviewText}
          status={status}
        />

        <PropertiesPanelSheetStageSection stageState={sheetStageState} />

        {/* Error */}
        {status === 'failed' && nodeData.error && (
          <div>
            <label className="block text-xs text-slate-500 mb-1.5">错误信息</label>
            <div className="p-3 bg-red-500/5 border border-red-500/20 rounded-lg">
              <pre className="text-[11px] text-red-400 whitespace-pre-wrap break-words">{nodeData.error}</pre>
            </div>
            {onRetry && (
              <button onClick={() => onRetry(selectedNode.id)}
                className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors text-xs">
                <RefreshCw size={13} /> 重试
              </button>
            )}
          </div>
        )}

        {/* Node ID */}
        <div className="pt-3 border-t border-slate-800">
          <div className="text-[10px] text-slate-600 font-mono">ID: {selectedNode.id}</div>
        </div>

        {/* Delete Node */}
        {onDeleteNode && (
          <div className="pt-1">
            <button
              onClick={() => onDeleteNode(selectedNode.id)}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors text-xs"
            >
              <Trash2 size={13} />
              删除该节点
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

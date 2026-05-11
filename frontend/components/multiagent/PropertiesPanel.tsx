/**
 * Properties Panel Component (Dark Theme)
 */

import { reportError } from '../../utils/globalErrorHandler';
import React from 'react';
import { Node } from 'reactflow';
import {
  X,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Info,
  Trash2,
  Upload,
  Image as ImageIcon,
  FileSpreadsheet,
  Video,
  Mic,
} from 'lucide-react';
import { CustomNodeData } from './CustomNode';
import { nodeTypeConfigs, NodeType } from './nodeTypeConfigs';
import { AgentSelector } from './AgentSelector';
import type { NodeStatus } from './types';
import type { AgentDef } from './types';
import { getAuthHeaders } from '../../services/apiClient';
import { fileToBase64 } from '../../hooks/handlers/attachmentUtils';
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
import {
  isFixedPortLayoutNodeType,
  resolveNodePortLayout,
  type WorkflowNodePortSide,
} from './workflowPorts';
import { dispatchScopedWorkflowEvent } from './workflowEditorUtils';
import {
  WORKFLOW_RESOLUTION_MAP,
  WORKFLOW_LEGACY_VIDEO_RESOLUTION_ALIASES,
  getResolutionLabel,
  normalizeWorkflowVideoResolutionSelection,
  normalizeWorkflowVideoSecondsSelection,
  normalizeWorkflowVideoExtensionSelection,
  getWorkflowVideoResolutionLabel,
} from './workflowResolution';
import { useProviderModels } from '../../hooks/useProviderModels';
import {
  INLINE_UPLOAD_MAX_BYTES_LABEL,
  reportInlineUploadError,
  readInlineFilesAsDataUrls,
} from './uploadHandlers';
import { PropertiesPanelResultSection } from './panels/ResultSection';
import { PropertiesPanelSheetStageSection } from './panels/SheetStagePanel';
import { classifyToolNode } from './toolClassification';
import {
  ConditionNodePanel,
  RouterNodePanel,
  ParallelNodePanel,
  MergeNodePanel,
  LoopNodePanel,
  HumanNodePanel,
} from './panels/SimpleNodeTypePanels';
import { EndNodeResultPanel } from './panels/EndNodeResultPanel';
import { ToolNodeConfigPanel } from './panels/ToolNodeConfigPanel';
import { AgentNodeConfigPanel } from './panels/AgentNodeConfigPanel';
import { extractSheetStageProtocolState } from './sheetStageService';
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
// WORKFLOW_RESOLUTION_MAP + 6 resolution helper 抽离至 ./workflowResolution
// （JIRA-frontend-view-decomposition.md P0 #1 Step 1）

// INLINE_UPLOAD_MAX_BYTES + 3 上传辅助函数抽离至 ./uploadHandlers
// （JIRA-frontend-view-decomposition.md P0 #1 Step 3）

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

const statusDisplayConfig: Record<
  NodeStatus,
  {
    icon: React.ComponentType<{ size?: number; className?: string }>;
    label: string;
    color: string;
    bgColor: string;
  }
> = {
  pending: { icon: Clock, label: '等待执行', color: 'text-slate-400', bgColor: 'bg-slate-800' },
  running: { icon: Loader2, label: '执行中', color: 'text-blue-400', bgColor: 'bg-blue-500/10' },
  completed: {
    icon: CheckCircle2,
    label: '已完成',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
  },
  skipped: { icon: Clock, label: '已跳过', color: 'text-amber-300', bgColor: 'bg-amber-500/10' },
  failed: { icon: XCircle, label: '执行失败', color: 'text-red-400', bgColor: 'bg-red-500/10' },
};

function usePropertiesPanelFocus(
  focusRequest: PropertiesPanelProps['focusRequest'],
  selectedNode: Node<CustomNodeData> | null,
  onConsumeFocusRequest?: (token: string) => void
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
        const fallback = panelContentRef.current?.querySelector(
          'input, textarea, select, button'
        ) as HTMLElement | null;
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

// useProviderModels 抽离至 ../../hooks/useProviderModels
// （JIRA-frontend-view-decomposition.md P0 #1 Step 2）

// PropertiesPanelResultSection 抽离至 ./panels/ResultSection
// （JIRA-frontend-view-decomposition.md P0 #1 Step 4）

// PropertiesPanelSheetStageSection（含 SHEET_STAGE_* 常量 + 3 helper）抽离至 ./panels/SheetStagePanel
// （JIRA-frontend-view-decomposition.md P0 #1 Step 5）

export const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  selectedNode,
  onClose,
  onUpdateNode,
  onRetry,
  onDeleteNode,
  focusRequest,
  onConsumeFocusRequest,
}) => {
  const { panelRootRef, panelContentRef } = usePropertiesPanelFocus(
    focusRequest,
    selectedNode,
    onConsumeFocusRequest
  );
  const nodeType = (selectedNode?.data.type || selectedNode?.type || 'agent') as NodeType;
  const { providers, providersLoading } = useProviderModels(selectedNode, nodeType);
  const config = nodeTypeConfigs[nodeType] || nodeTypeConfigs.agent;
  const status = (selectedNode?.data.status || 'pending') as NodeStatus;
  const statusDisplay = statusDisplayConfig[status];
  const StatusIcon = statusDisplay.icon;
  const nodeData = selectedNode?.data;
  const resolvedPortLayout = resolveNodePortLayout(nodeType, nodeData?.portLayout);
  const normalizedToolName = String(nodeData?.toolName || '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_');
  const shouldLoadWorkflowVideoSchema = nodeType === 'agent' || nodeType === 'tool';
  const workflowVideoSchemaProviderId = shouldLoadWorkflowVideoSchema
    ? nodeType === 'agent'
      ? String(nodeData?.modelOverrideProviderId || nodeData?.agentProviderId || '').trim()
      : String(nodeData?.toolProviderId || '').trim()
    : '';
  const workflowVideoSchemaModelId = shouldLoadWorkflowVideoSchema
    ? nodeType === 'agent'
      ? String(nodeData?.modelOverrideModelId || nodeData?.agentModelId || '').trim()
      : String(nodeData?.toolModelId || '').trim()
    : '';
  const { schema: workflowVideoSchema } = useModeControlsSchema(
    workflowVideoSchemaProviderId || undefined,
    'video-gen',
    workflowVideoSchemaModelId || undefined
  );
  const workflowVideoControlContract = React.useMemo(
    () => buildVideoControlContract(workflowVideoSchema),
    [workflowVideoSchema]
  );
  const isFixedPortLayout = isFixedPortLayoutNodeType(nodeType);
  const sourcePreviewUrl = normalizeImageValue(
    String(nodeData?.agentReferenceImageUrl || nodeData?.toolReferenceImageUrl || '')
  );
  const resultPreviewUrls = extractImageUrls(nodeData?.result).filter((imageUrl) =>
    isDirectlyRenderableImageUrl(imageUrl)
  );
  const resultPreviewAudioUrls = extractAudioUrls(nodeData?.result).filter((audioUrl) =>
    isDirectlyRenderableAudioUrl(audioUrl)
  );
  const resultPreviewVideoUrls = extractVideoUrls(nodeData?.result).filter((videoUrl) =>
    isDirectlyRenderableVideoUrl(videoUrl)
  );
  const readableResultText = extractTextContent(nodeData?.result).trim();
  const resultPreviewText =
    readableResultText ||
    (nodeData?.result == null
      ? ''
      : typeof nodeData.result === 'string'
        ? nodeData.result
        : JSON.stringify(nodeData.result, null, 2));
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
    if (!String(nodeData?.agentId || '').trim()) {
      setResolvedAgent(null);
    }
  }, [nodeData?.agentId, nodeType]);

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
    if (
      ['start', 'input_text', 'input_image', 'input_video', 'input_audio', 'input_file'].includes(
        nodeType
      )
    ) {
      const isStartNode = nodeType === 'start';
      const isTextInputNode = nodeType === 'input_text';
      const isImageInputNode = nodeType === 'input_image';
      const isVideoInputNode = nodeType === 'input_video';
      const isAudioInputNode = nodeType === 'input_audio';
      const isFileInputNode = nodeType === 'input_file';
      const normalizeUrlList = (value: unknown): string[] => {
        if (!Array.isArray(value)) return [];
        return value.map((item) => String(item || '').trim()).filter(Boolean);
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
        return Array.from(
          new Set(
            String(rawValue || '')
              .split(/\r?\n/)
              .map((item) => item.trim())
              .filter(Boolean)
          )
        );
      };

      const startImageValues = dedupeUrlList(
        normalizeUrlList(nodeData.startImageUrls),
        nodeData.startImageUrl ? [String(nodeData.startImageUrl).trim()] : []
      );
      const startVideoValues = dedupeUrlList(
        normalizeUrlList(nodeData.startVideoUrls),
        nodeData.startVideoUrl ? [String(nodeData.startVideoUrl).trim()] : []
      );
      const startAudioValues = dedupeUrlList(
        normalizeUrlList(nodeData.startAudioUrls),
        nodeData.startAudioUrl ? [String(nodeData.startAudioUrl).trim()] : []
      );
      const startFileValues = dedupeUrlList(
        normalizeUrlList(nodeData.startFileUrls),
        nodeData.startFileUrl ? [String(nodeData.startFileUrl).trim()] : []
      );
      const hasStartImage = startImageValues.length > 0;
      const hasStartVideo = startVideoValues.length > 0;
      const hasStartAudio = startAudioValues.length > 0;
      const hasStartFile = startFileValues.length > 0;
      const renderableStartImageValues = startImageValues.filter(
        (value) => value.startsWith('data:') || isDirectlyRenderableImageUrl(value)
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
              <label className="block text-xs text-slate-500">
                输入图片（input.imageUrl / input.imageUrls）
              </label>
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
                          const removeIndex = startImageValues.findIndex(
                            (value) => value === imageUrl
                          );
                          const nextValues = startImageValues.filter(
                            (_, sourceIndex) => sourceIndex !== removeIndex
                          );
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
                <span className="text-xs text-emerald-300">
                  {hasStartImage ? '继续上传图片' : '上传图片'}
                </span>
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
              <label className="block text-xs text-slate-500">
                输入视频（input.videoUrl / input.videoUrls）
              </label>
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
                          const nextValues = startVideoValues.filter(
                            (_, sourceIndex) => sourceIndex !== index
                          );
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
                <span className="text-xs text-indigo-300">
                  {hasStartVideo ? '继续上传视频' : '上传视频'}
                </span>
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
              <label className="block text-xs text-slate-500">
                输入音频（input.audioUrl / input.audioUrls）
              </label>
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
                          const nextValues = startAudioValues.filter(
                            (_, sourceIndex) => sourceIndex !== index
                          );
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
                <span className="text-xs text-sky-300">
                  {hasStartAudio ? '继续上传音频' : '上传音频'}
                </span>
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
              <label className="block text-xs text-slate-500">
                输入文件（input.fileUrl / input.fileUrls）
              </label>
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
                          const nextValues = startFileValues.filter(
                            (_, sourceIndex) => sourceIndex !== index
                          );
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
                <span className="text-xs text-cyan-300">
                  {hasStartFile ? '继续上传文件' : '上传文件'}
                </span>
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


  const renderResultNodeConfig = () => {
    if (nodeType === 'end') {
      return (
        <EndNodeResultPanel
          nodeData={nodeData}
          selectedNodeId={String(selectedNode.id)}
          status={status}
          resultPreviewUrls={resultPreviewUrls}
          resultPreviewVideoUrls={resultPreviewVideoUrls}
          resultPreviewAudioUrls={resultPreviewAudioUrls}
          resultPreviewText={resultPreviewText}
        />
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

    if (nodeType === 'agent') {
      return (
        <AgentNodeConfigPanel
          nodeData={nodeData}
          nodeType={nodeType}
          updateNodeData={updateNodeData}
          providers={providers}
          providersLoading={providersLoading}
          workflowVideoSchema={workflowVideoSchema}
          workflowVideoControlContract={workflowVideoControlContract}
          status={status}
          resolvedAgent={resolvedAgent}
          setResolvedAgent={setResolvedAgent}
          agentDefaultAnalysis={agentDefaultAnalysis}
        />
      );
    }
    // 6 个简单节点类型面板抽离至 ./panels/SimpleNodeTypePanels（业务下沉 + 主组件瘦身）
    if (nodeType === 'condition') {
      return <ConditionNodePanel nodeData={nodeData} updateNodeData={updateNodeData} />;
    }
    if (nodeType === 'router') {
      return <RouterNodePanel nodeData={nodeData} updateNodeData={updateNodeData} />;
    }
    if (nodeType === 'parallel') {
      return <ParallelNodePanel nodeData={nodeData} updateNodeData={updateNodeData} />;
    }
    if (nodeType === 'merge') {
      return <MergeNodePanel nodeData={nodeData} updateNodeData={updateNodeData} />;
    }
    if (nodeType === 'loop') {
      return <LoopNodePanel nodeData={nodeData} updateNodeData={updateNodeData} />;
    }

    if (nodeType === 'tool') {
      return (
        <ToolNodeConfigPanel
          nodeData={nodeData}
          nodeType={nodeType}
          updateNodeData={updateNodeData}
          providers={providers}
          providersLoading={providersLoading}
          workflowVideoSchema={workflowVideoSchema}
          workflowVideoControlContract={workflowVideoControlContract}
        />
      );
    }
    if (nodeType === 'human') {
      return <HumanNodePanel nodeData={nodeData} updateNodeData={updateNodeData} />;
    }

    return (
      <div className="p-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-[11px] text-slate-400">
        当前节点暂无额外可配置项。
      </div>
    );
  };

  return (
    <div
      ref={panelRootRef}
      className="w-[340px] bg-slate-900 border-l border-slate-800 flex flex-col h-full overflow-hidden"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className={`w-6 h-6 ${config.iconColor} rounded flex items-center justify-center text-white text-xs`}
          >
            {config.icon}
          </span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-200 truncate">
              {nodeData.label || config.label}
            </div>
            <div className="text-[10px] text-slate-500">
              {config.label} · {config.category}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-slate-800 rounded transition-colors flex-shrink-0"
        >
          <X size={16} className="text-slate-500" />
        </button>
      </div>

      {/* Content */}
      <div ref={panelContentRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Label */}
        <div>
          <label className="block text-xs text-slate-500 mb-1.5">节点名称</label>
          <input
            type="text"
            value={nodeData.label || ''}
            onChange={(e) => updateNodeData({ label: e.target.value })}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20"
            placeholder="节点名称"
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-xs text-slate-500 mb-1.5">描述</label>
          <textarea
            value={nodeData.description || ''}
            onChange={(e) => updateNodeData({ description: e.target.value })}
            rows={2}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 resize-none"
            placeholder="节点描述"
          />
        </div>

        <div className="pt-1 border-t border-slate-800">
          <div className="text-xs text-slate-400 mb-2 font-medium">连接端口</div>
          {isFixedPortLayout ? (
            <div className="p-2.5 rounded-lg border border-slate-700 bg-slate-800/50 text-[11px] text-slate-400">
              该节点端口固定：左 {resolvedPortLayout.left} · 右 {resolvedPortLayout.right} · 上{' '}
              {resolvedPortLayout.top} · 下 {resolvedPortLayout.bottom}
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
          <div
            className={`flex items-center gap-2 px-3 py-2 ${statusDisplay.bgColor} rounded-lg border border-slate-700/50`}
          >
            <StatusIcon
              size={14}
              className={`${statusDisplay.color} ${status === 'running' ? 'animate-spin' : ''}`}
            />
            <span className={`text-xs font-medium ${statusDisplay.color}`}>
              {statusDisplay.label}
            </span>
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
              <pre className="text-[11px] text-red-400 whitespace-pre-wrap break-words">
                {nodeData.error}
              </pre>
            </div>
            {onRetry && (
              <button
                onClick={() => onRetry(selectedNode.id)}
                className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors text-xs"
              >
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

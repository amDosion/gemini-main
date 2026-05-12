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
import { StartInputNodeConfigPanel } from './panels/StartInputNodeConfigPanel';
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
    if (
      ['start', 'input_text', 'input_image', 'input_video', 'input_audio', 'input_file'].includes(
        nodeType
      )
    ) {
      return (
        <StartInputNodeConfigPanel
          nodeData={nodeData}
          nodeType={nodeType}
          selectedNode={selectedNode}
          updateNodeData={updateNodeData}
        />
      );
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

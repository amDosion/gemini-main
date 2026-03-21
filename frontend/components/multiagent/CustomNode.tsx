/**
 * Custom Node Component for React Flow (Dark Theme)
 */

import React, { memo, useMemo } from 'react';
import { Handle, Position, NodeProps, NodeResizeControl } from 'reactflow';
import { Clock, Loader2, CheckCircle2, XCircle, Image as ImageIcon, Video, Mic } from 'lucide-react';
import { nodeTypeConfigs } from './nodeTypeConfigs';
import type { NodeStatus, WorkflowNodeData } from './types';
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
import { buildNodeParamChipItems } from './nodeParamSummaryUtils';
import { buildHandlesForSide, resolveNodePortLayout, type WorkflowNodePortSide } from './workflowPorts';
import '@reactflow/node-resizer/dist/style.css';

export type CustomNodeData = WorkflowNodeData;

const statusConfig: Record<NodeStatus, {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  color: string;
  border: string;
  animate?: string;
}> = {
  pending: { icon: Clock, color: 'text-slate-500', border: 'border-slate-700' },
  running: { icon: Loader2, color: 'text-blue-400', border: 'border-blue-500/50', animate: 'animate-spin' },
  completed: { icon: CheckCircle2, color: 'text-emerald-400', border: 'border-emerald-500/50' },
  skipped: { icon: Clock, color: 'text-amber-300', border: 'border-amber-500/50' },
  failed: { icon: XCircle, color: 'text-red-400', border: 'border-red-500/50' },
};

const toFiniteNumber = (value: any): number | null => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return parsed;
};

const getRelativeOffset = (index: number, count: number): string => {
  if (count <= 1) return '50%';
  return `${((index + 1) / (count + 1)) * 100}%`;
};

const getHandleClassName = (nodeType: string, side: WorkflowNodePortSide, index: number): string => {
  if (side === 'right' && (nodeType === 'condition' || nodeType === 'loop')) {
    if (index === 0) return '!w-2.5 !h-2.5 !bg-emerald-500 !border-2 !border-slate-800';
    if (index === 1) return '!w-2.5 !h-2.5 !bg-red-500 !border-2 !border-slate-800';
  }
  if (side === 'top' || side === 'bottom') {
    return '!w-2.5 !h-2.5 !bg-cyan-400 !border-2 !border-slate-800';
  }
  return '!w-2.5 !h-2.5 !bg-teal-500 !border-2 !border-slate-800';
};

const toStringList = (value: any): string[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item || '').trim())
    .filter(Boolean);
};

const mergeUniqueValues = (...sources: Array<any>): string[] => {
  const deduped = new Set<string>();
  const result: string[] = [];
  sources.forEach((source) => {
    toStringList(source).forEach((item) => {
      if (!deduped.has(item)) {
        deduped.add(item);
        result.push(item);
      }
    });
  });
  return result;
};

const MANUAL_NODE_MIN_WIDTH = 135;
const MANUAL_NODE_MAX_WIDTH = 360;
const MANUAL_NODE_MIN_HEIGHT = 1;
const FOUR_WAY_CURSOR = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='%2314b8a6' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='12' y1='4' x2='12' y2='20'/%3E%3Cline x1='4' y1='12' x2='20' y2='12'/%3E%3Cpolyline points='9 7 12 4 15 7'/%3E%3Cpolyline points='9 17 12 20 15 17'/%3E%3Cpolyline points='7 9 4 12 7 15'/%3E%3Cpolyline points='17 9 20 12 17 15'/%3E%3Ccircle cx='12' cy='12' r='1.3' fill='%2314b8a6' stroke='none'/%3E%3C/svg%3E") 10 10, move`;
const RESIZE_CONTROL_STYLE = {
  background: 'transparent',
  border: 'none',
  width: 20,
  height: 20,
  cursor: FOUR_WAY_CURSOR,
} as const;
const WORKFLOW_EDITOR_SCOPE_ATTRIBUTE = 'data-workflow-editor-scope';
const WORKFLOW_EDITOR_SCOPE_SELECTOR = `[${WORKFLOW_EDITOR_SCOPE_ATTRIBUTE}]`;

const dispatchScopedWorkflowEvent = <TDetail extends Record<string, unknown>>(
  eventName: string,
  target: EventTarget | null,
  detail: TDetail,
): boolean => {
  if (typeof window === 'undefined' || typeof Element === 'undefined') {
    return false;
  }
  const element = target instanceof Element ? target : null;
  const scopeRoot = element?.closest(WORKFLOW_EDITOR_SCOPE_SELECTOR);
  const editorScopeId = String(scopeRoot?.getAttribute(WORKFLOW_EDITOR_SCOPE_ATTRIBUTE) || '').trim();
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

const CustomNodeComponent: React.FC<NodeProps<CustomNodeData>> = (props) => {
  const { id, data, selected } = props;
  const config = nodeTypeConfigs[data.type] || nodeTypeConfigs.agent;
  const status = data.status || 'pending';
  const statusInfo = statusConfig[status];
  const StatusIcon = statusInfo.icon;
  const progressValueRaw = toFiniteNumber(data.progress);
  const progressValue = status === 'completed'
    ? 100
    : Math.max(0, Math.min(100, Math.round(progressValueRaw ?? 0)));
  const nodeType = String(data.type || '').toLowerCase();
  const portLayout = useMemo(
    () => resolveNodePortLayout(nodeType, data.portLayout),
    [nodeType, data.portLayout]
  );
  const leftHandles = useMemo(
    () => buildHandlesForSide(nodeType, 'left', portLayout),
    [nodeType, portLayout]
  );
  const rightHandles = useMemo(
    () => buildHandlesForSide(nodeType, 'right', portLayout),
    [nodeType, portLayout]
  );
  const topHandles = useMemo(
    () => buildHandlesForSide(nodeType, 'top', portLayout),
    [nodeType, portLayout]
  );
  const bottomHandles = useMemo(
    () => buildHandlesForSide(nodeType, 'bottom', portLayout),
    [nodeType, portLayout]
  );
  const inputImagePreviewUrls = useMemo(() => {
    const startNodeCandidates = mergeUniqueValues(
      data.startImageUrls,
      data.startImageUrl ? [data.startImageUrl] : [],
    )
      .map((item) => normalizeImageValue(item))
      .filter((item): item is string => Boolean(item && isDirectlyRenderableImageUrl(item)));
    if (startNodeCandidates.length > 0) {
      return startNodeCandidates;
    }

    const fallbackCandidate = normalizeImageValue(
      String(nodeType === 'agent' ? data.agentReferenceImageUrl || '' : nodeType === 'tool' ? data.toolReferenceImageUrl || '' : '')
    );
    if (fallbackCandidate && isDirectlyRenderableImageUrl(fallbackCandidate)) {
      return [fallbackCandidate];
    }
    return [];
  }, [data.startImageUrls, data.startImageUrl, data.agentReferenceImageUrl, data.toolReferenceImageUrl, nodeType]);
  const resultImageUrls = useMemo(
    () => extractImageUrls(data.result).filter((imageUrl) => isDirectlyRenderableImageUrl(imageUrl)),
    [data.result]
  );
  const resultAudioUrls = useMemo(
    () => extractAudioUrls(data.result).filter((audioUrl) => isDirectlyRenderableAudioUrl(audioUrl)),
    [data.result]
  );
  const resultVideoUrls = useMemo(
    () => extractVideoUrls(data.result).filter((videoUrl) => isDirectlyRenderableVideoUrl(videoUrl)),
    [data.result]
  );
  const rawResultText = useMemo(
    () => extractTextContent(data.result).trim(),
    [data.result]
  );
  const resultPreviewLimit = nodeType === 'end' ? 150 : 90;
  const resultTextPreview = rawResultText.length > resultPreviewLimit
    ? `${rawResultText.slice(0, resultPreviewLimit)}...`
    : rawResultText;
  const paramChipItems = useMemo(
    () => buildNodeParamChipItems(data),
    [data]
  );
  const hasResultPreview = useMemo(
    () => resultImageUrls.length > 0 || resultAudioUrls.length > 0 || resultVideoUrls.length > 0 || resultTextPreview.length > 0,
    [resultAudioUrls.length, resultImageUrls.length, resultTextPreview.length, resultVideoUrls.length]
  );
  const shouldRenderInputImage = inputImagePreviewUrls.length > 0;
  const resultPreviewTitle = nodeType === 'end' ? '最终结果预览' : '输出预览';
  const isEndNode = nodeType === 'end';
  const resultImageGridColsClass = isEndNode
    ? (
      resultImageUrls.length >= 4
        ? 'grid-cols-4'
        : resultImageUrls.length === 3
          ? 'grid-cols-3'
          : resultImageUrls.length === 2
            ? 'grid-cols-2'
            : 'grid-cols-1'
    )
    : (resultImageUrls.length > 1 ? 'grid-cols-2' : 'grid-cols-1');
  const inputImageGridColsClass = inputImagePreviewUrls.length >= 4
    ? 'grid-cols-4'
    : inputImagePreviewUrls.length === 3
      ? 'grid-cols-3'
      : inputImagePreviewUrls.length === 2
        ? 'grid-cols-2'
        : 'grid-cols-1';
  const inputImageCellHeightClass = inputImagePreviewUrls.length <= 1 ? 'h-28' : 'h-14';
  const resultThumbnailHeightClass = isEndNode
    ? (resultImageUrls.length <= 1 ? 'h-36' : 'h-16')
    : 'h-28';
  const resultGalleryMaxHeightClass = isEndNode ? 'max-h-96' : 'max-h-56';

  const emitDisconnectHandleEvent = (direction: 'source' | 'target', handleId?: string) =>
    (event: React.MouseEvent) => {
      event.preventDefault();
      event.stopPropagation();

      dispatchScopedWorkflowEvent('workflow:disconnect-handle', event.currentTarget, {
        nodeId: id,
        direction,
        handleId: handleId || null,
      });
    };

  const emitWorkflowActionEvent = (eventName: 'workflow:execute-request' | 'workflow:end-request') =>
    (event: React.MouseEvent) => {
      event.preventDefault();
      event.stopPropagation();
      dispatchScopedWorkflowEvent(eventName, event.currentTarget, {
        nodeId: String(id),
      });
    };

  const emitFocusNodeFieldEvent = (fieldKey: string) =>
    (event: React.MouseEvent) => {
      event.preventDefault();
      event.stopPropagation();
      dispatchScopedWorkflowEvent('workflow:focus-node-field', event.currentTarget, {
        nodeId: String(id),
        fieldKey: String(fieldKey || '').trim(),
      });
    };

  const getMetaText = () => {
    if (data.type === 'agent') {
      const effectiveProvider = data.modelOverrideProviderId || data.agentProviderId;
      const effectiveModel = data.modelOverrideModelId || data.agentModelId;
      const modelText = effectiveProvider && effectiveModel
        ? `${effectiveProvider}/${effectiveModel}`
        : '';
      if (data.agentName && modelText) {
        return `${data.agentName} · ${modelText}`;
      }
      return data.agentName || modelText || data.description || '';
    }
    if (data.type === 'condition') {
      return data.expression || data.description || '';
    }
    if (data.type === 'router') {
      return data.routerPrompt || data.description || '';
    }
    if (data.type === 'tool') {
      const modelText = data.toolProviderId && data.toolModelId
        ? `${data.toolProviderId}/${data.toolModelId}`
        : '';
      if (data.toolName && modelText) {
        return `${data.toolName} · ${modelText}`;
      }
      return data.toolName || modelText || data.description || '';
    }
    if (data.type === 'human') {
      return data.approvalPrompt || data.description || '';
    }
    if (data.type === 'loop') {
      return data.loopCondition || data.description || '';
    }
    if (data.type === 'input_text') {
      return (data.startTask || '').trim() || '未配置文本输入';
    }
    if (data.type === 'input_image') {
      const sourceList = mergeUniqueValues(data.startImageUrls, data.startImageUrl ? [data.startImageUrl] : []);
      if (sourceList.length === 0) return '未配置图片输入';
      if (sourceList.length > 1) {
        return `已配置 ${sourceList.length} 张图片`;
      }
      const source = sourceList[0];
      return source.startsWith('data:') ? '已上传图片' : source;
    }
    if (data.type === 'input_file') {
      const sourceList = mergeUniqueValues(data.startFileUrls, data.startFileUrl ? [data.startFileUrl] : []);
      if (sourceList.length === 0) return '未配置文件输入';
      if (sourceList.length > 1) {
        return `已配置 ${sourceList.length} 个文件`;
      }
      const source = sourceList[0];
      return source.startsWith('data:') ? '已上传文件' : source;
    }
    return data.description || '';
  };

  const metaText = getMetaText();

  return (
    <div className={`
      relative w-full h-full min-w-[135px] min-h-0 overflow-visible bg-slate-800/90 backdrop-blur-sm rounded-md border shadow-lg
      ${selected ? 'border-teal-500 shadow-teal-500/20' : statusInfo.border}
      transition-all hover:shadow-xl
    `}>
      {selected && (
        <NodeResizeControl
          className="nodrag nopan"
          style={RESIZE_CONTROL_STYLE}
          minWidth={MANUAL_NODE_MIN_WIDTH}
          maxWidth={MANUAL_NODE_MAX_WIDTH}
          minHeight={MANUAL_NODE_MIN_HEIGHT}
        />
      )}

      <div
        className="h-full min-h-0 overflow-y-auto overflow-x-hidden [scrollbar-width:thin] [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-600/70 [&::-webkit-scrollbar-track]:bg-transparent"
      >
      {/* Header */}
      <div className="px-3 py-2.5 flex items-center gap-2.5">
        <span className={`w-8 h-8 ${config.iconColor} rounded-lg flex items-center justify-center text-white text-base flex-shrink-0`}>
          {config.icon}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-slate-200 truncate">{data.label}</div>
          {metaText && (
            <div className={`text-[10px] truncate ${data.type === 'agent' ? 'text-teal-400/80' : 'text-slate-500'}`}>
              {metaText}
            </div>
          )}
        </div>
        <StatusIcon size={14} className={`${statusInfo.color} ${statusInfo.animate || ''} flex-shrink-0`} />
      </div>

      {/* Progress */}
      {(status !== 'pending' || progressValue > 0) && (
        <div className="px-3 pb-2 space-y-1">
          <div className="flex items-center justify-between text-[9px] text-slate-400">
            <span>执行进度</span>
            <span>{progressValue}%</span>
          </div>
          <div className="h-1 bg-slate-700 rounded-full overflow-hidden">
            <div className={`h-full transition-all duration-500 rounded-full ${status === 'completed' ? 'bg-emerald-500' : 'bg-blue-500'}`}
              style={{ width: `${progressValue}%` }} />
          </div>
        </div>
      )}

      {data.runtime && (
        <div className="mx-3 mb-2 px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 text-[9px] text-amber-200 break-all">
          runtime: {data.runtime}
        </div>
      )}

      {paramChipItems.length > 0 && (
        <div className="mx-3 mb-2">
          <div className="grid grid-cols-2 gap-1">
            {paramChipItems.map((chip, index) => (
              <button
                type="button"
                key={`${id}-chip-${index}`}
                className="px-1.5 py-1 rounded border border-slate-600 bg-slate-700/60 text-left hover:border-teal-500/50 hover:bg-slate-700 transition-colors"
                title={`点击定位参数：${chip.text}`}
                onClick={emitFocusNodeFieldEvent(chip.fieldKey)}
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-[8px] uppercase tracking-wide text-slate-400 shrink-0">{chip.label}</span>
                  <span className="text-[10px] text-slate-200 truncate min-w-0 flex-1 text-right">{chip.value}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {status === 'failed' && data.error && (
        <div className="mx-3 mb-2 px-2 py-1 bg-red-500/10 rounded text-[9px] text-red-400 break-words">
          {data.error.substring(0, 80)}...
        </div>
      )}

      {/* Instructions indicator */}
      {data.instructions && (
        <div className="mx-3 mb-2 px-2 py-0.5 bg-teal-500/10 rounded text-[9px] text-teal-400 truncate">
          📝 {data.instructions.substring(0, 30)}...
        </div>
      )}

      {shouldRenderInputImage && (
        <div className="mx-3 mb-2 p-2 rounded border border-slate-700 bg-slate-900/60">
          <div className="mb-1 text-[9px] text-slate-400 flex items-center gap-1">
            <ImageIcon size={10} />
            输入图片 ({inputImagePreviewUrls.length})
          </div>
          <div className={`grid gap-1.5 pr-0.5 overflow-y-auto max-h-56 ${inputImageGridColsClass}`}>
            {inputImagePreviewUrls.map((imageUrl, index) => (
              <div
                key={`${id}-input-image-${index}`}
                className={`w-full rounded border border-slate-700 bg-slate-900 p-1 flex items-center justify-center ${inputImageCellHeightClass}`}
              >
                <img
                  src={imageUrl}
                  alt={`node-input-image-${id}-${index + 1}`}
                  className="max-w-full max-h-full h-auto w-auto rounded object-contain"
                  loading="lazy"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {hasResultPreview && (status === 'running' || status === 'completed' || status === 'failed') && (
        <div className="mx-3 mb-2 p-2 rounded border border-slate-700 bg-slate-900/60 space-y-1">
          <div className="text-[9px] text-slate-400">{resultPreviewTitle}</div>
          {resultImageUrls.length > 0 && (
            <div>
              <div className="mb-1 text-[9px] text-slate-500">共 {resultImageUrls.length} 张</div>
              <div className={`grid gap-1.5 pr-0.5 overflow-y-auto ${resultImageGridColsClass} ${resultGalleryMaxHeightClass}`}>
                {resultImageUrls.map((imageUrl, index) => (
                  <div
                    key={`${id}-result-image-${index}`}
                    className={`w-full rounded border border-slate-700 bg-slate-900 p-1 flex items-center justify-center ${resultThumbnailHeightClass}`}
                  >
                    <img
                      src={imageUrl}
                      alt={`node-result-image-${id}-${index + 1}`}
                      className="max-w-full max-h-full h-auto w-auto rounded object-contain"
                      loading="lazy"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
          {resultVideoUrls.length > 0 && (
            <div>
              <div className="mb-1 text-[9px] text-slate-500 flex items-center gap-1">
                <Video size={10} />
                视频 {resultVideoUrls.length} 条
              </div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-0.5">
                {resultVideoUrls.map((videoUrl, index) => (
                  <video
                    key={`${id}-result-video-${index}`}
                    src={videoUrl}
                    controls
                    className="w-full rounded border border-slate-700 bg-slate-900"
                  />
                ))}
              </div>
            </div>
          )}
          {resultAudioUrls.length > 0 && (
            <div>
              <div className="mb-1 text-[9px] text-slate-500 flex items-center gap-1">
                <Mic size={10} />
                音频 {resultAudioUrls.length} 条
              </div>
              <div className="space-y-1.5 max-h-40 overflow-y-auto pr-0.5">
                {resultAudioUrls.map((audioUrl, index) => (
                  <audio
                    key={`${id}-result-audio-${index}`}
                    src={audioUrl}
                    controls
                    className="w-full"
                  />
                ))}
              </div>
            </div>
          )}
          {resultTextPreview && (
            <div className="text-[9px] text-slate-300 break-words leading-relaxed">
              {resultTextPreview}
            </div>
          )}
        </div>
      )}

      {data.type === 'start' && (
        <div className="mx-3 mb-2">
          <button
            onClick={emitWorkflowActionEvent('workflow:execute-request')}
            className="w-full px-2 py-1 text-[10px] rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 transition-colors"
            title="从该开始节点启动工作流"
          >
            开始按钮
          </button>
        </div>
      )}

      {data.type === 'end' && (
        <div className="mx-3 mb-2">
          <button
            onClick={emitWorkflowActionEvent('workflow:end-request')}
            className="w-full px-2 py-1 text-[10px] rounded border border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 transition-colors"
            title="查看结束节点输出结果"
          >
            结束按钮
          </button>
        </div>
      )}
      </div>

      {/* Handles */}
      {leftHandles.map((handle) => (
        <Handle
          key={handle.key}
          type={handle.direction}
          position={Position.Left}
          id={handle.id}
          className={getHandleClassName(nodeType, 'left', handle.index)}
          style={{
            left: '-5px',
            top: getRelativeOffset(handle.index, handle.count),
            transform: handle.count <= 1 ? 'translateY(-50%)' : undefined,
          }}
          title="右键断开该端口连接"
          onContextMenu={emitDisconnectHandleEvent(handle.direction, handle.id)}
        />
      ))}
      {rightHandles.map((handle) => (
        <Handle
          key={handle.key}
          type={handle.direction}
          position={Position.Right}
          id={handle.id}
          className={getHandleClassName(nodeType, 'right', handle.index)}
          style={{
            right: '-5px',
            top: getRelativeOffset(handle.index, handle.count),
            transform: handle.count <= 1 ? 'translateY(-50%)' : undefined,
          }}
          title="右键断开该端口连接"
          onContextMenu={emitDisconnectHandleEvent(handle.direction, handle.id)}
        />
      ))}
      {topHandles.map((handle) => (
        <Handle
          key={handle.key}
          type={handle.direction}
          position={Position.Top}
          id={handle.id}
          className={getHandleClassName(nodeType, 'top', handle.index)}
          style={{
            top: '-5px',
            left: getRelativeOffset(handle.index, handle.count),
            transform: handle.count <= 1 ? 'translateX(-50%)' : undefined,
          }}
          title="右键断开该端口连接"
          onContextMenu={emitDisconnectHandleEvent(handle.direction, handle.id)}
        />
      ))}
      {bottomHandles.map((handle) => (
        <Handle
          key={handle.key}
          type={handle.direction}
          position={Position.Bottom}
          id={handle.id}
          className={getHandleClassName(nodeType, 'bottom', handle.index)}
          style={{
            bottom: '-5px',
            left: getRelativeOffset(handle.index, handle.count),
            transform: handle.count <= 1 ? 'translateX(-50%)' : undefined,
          }}
          title="右键断开该端口连接"
          onContextMenu={emitDisconnectHandleEvent(handle.direction, handle.id)}
        />
      ))}
    </div>
  );
};

export const CustomNode = memo(CustomNodeComponent);

export default CustomNode;

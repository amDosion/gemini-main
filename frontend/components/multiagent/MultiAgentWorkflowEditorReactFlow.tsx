/**
 * Multi-Agent Workflow Editor - React Flow Implementation (Redesigned)
 * 
 * Dark-themed visual workflow editor with:
 * - Start/End entry buttons in flow-control nodes
 * - Drag-and-drop node composition
 * - Properties panel with per-node instructions
 * - Execution log panel
 * - Template management
 */

import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  ReactFlowInstance,
  ReactFlowProvider,
  getNodesBounds,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { toPng, toSvg } from 'html-to-image';

import { nodeTypeConfigs, NodeType } from './nodeTypeConfigs';
import { ExecutionLogPanel } from './ExecutionLogPanel';
import { WorkflowResultPanel } from './WorkflowResultPanel';
import { WorkflowTemplateSelector, type WorkflowTemplate } from './WorkflowTemplateSelector';
import {
  WorkflowTemplateSaveDialog,
  type WorkflowTemplateSaveTarget,
} from './WorkflowTemplateSaveDialog';
import { WorkflowEditorTopBar } from './WorkflowEditorTopBar';
import { WorkflowEditorCanvasPane } from './WorkflowEditorCanvasPane';
import { useExecutionLogs } from './WorkflowExecutionHooks';
import { useUndoRedo } from './useUndoRedo';
import { autoLayoutWorkflow, validateWorkflow } from './workflowUtils';
import type { AgentDef, ExecutionStatus, WorkflowNode, WorkflowEdge, WorkflowNodeData } from './types';
import {
  extractAudioUrls,
  extractImageUrls,
  extractTextContent,
  extractThoughtContent,
  extractUrlContent,
  extractVideoUrls,
  hasUsableImageInput,
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
  isPlainObject,
  mergePreviewImagesIntoResult,
  mergePreviewMediaIntoResult,
  normalizeImageValue,
} from './workflowResultUtils';
import { useAgentRegistry } from './useAgentRegistry';
import { buildAgentNodeDefaultsFromAgent } from './agentNodeDefaults';
import { loadTemplateIntoEditor } from './workflowTemplateLoader';
import { useResultPanelPreviewState } from './useResultPanelPreviewState';
import {
  applySingleEdgeSelection,
  applySingleNodeSelection,
  createWorkflowEditorScopeId,
  NODE_DEFAULT_FOCUS_FIELD_BY_TYPE,
  applyAgentBindingsToNodes,
  buildWorkflowStructureFingerprint,
  DisconnectHandleEventDetail,
  getDefaultNodeConfig,
  isKeyboardEventWithinEditableContext,
  isWorkflowEventForEditorScope,
  isTerminalExecutionStatus,
  normalizeLoadedNode,
  WORKFLOW_EDITOR_SCOPE_ATTRIBUTE,
  WorkflowNodeActionEventDetail,
  WorkflowNodeFieldFocusEventDetail,
  WorkflowNodeFieldFocusRequest,
  WorkflowRemoveEdgeRequestDetail,
} from './workflowEditorUtils';
import {
  filterEdgesByNodePortLayouts,
  hydrateNodePortLayoutsFromEdges,
  resolveNodePortLayout,
} from './workflowPorts';
import { DEFAULT_WORKFLOW_EDGE_TYPE } from './workflowEdgeTypes';

const TEMP_IMAGE_PATH_SEGMENT = '/api/temp-images/';
const EXPORT_NODE_PADDING = 280;
const EXPORT_MIN_WIDTH = 1920;
const EXPORT_MIN_HEIGHT = 1080;
const EXPORT_PNG_MAX_SIDE = 8192;
const EXPORT_PNG_MAX_PIXELS = 85_000_000;
const EXPORT_PNG_TARGET_PIXELS = 140_000_000;
const NON_RESULT_WORKFLOW_NODE_TYPES = new Set([
  'start',
  'input_text',
  'input_image',
  'input_video',
  'input_audio',
  'input_file',
]);

const clampNumber = (value: number, min: number, max: number): number => {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
};

const formatWorkflowExportError = (error: unknown): string => {
  if (error instanceof Error && typeof error.message === 'string' && error.message.trim()) {
    return error.message.trim();
  }
  if (error instanceof Event) {
    return error.type ? `浏览器事件: ${error.type}` : '浏览器事件';
  }
  if (typeof error === 'string') {
    return error.trim() || '未知错误';
  }
  if (error && typeof error === 'object') {
    const maybeMessage = (error as { message?: unknown }).message;
    if (typeof maybeMessage === 'string' && maybeMessage.trim()) {
      return maybeMessage.trim();
    }
    try {
      const serialized = JSON.stringify(error);
      if (serialized && serialized !== '{}') {
        return serialized;
      }
    } catch {
      // ignore JSON stringify errors
    }
  }
  return String(error || '未知错误');
};

const ensureTempImageNoRedirect = (rawUrl: string): string => {
  const value = String(rawUrl || '').trim();
  if (!value) return value;
  try {
    const parsed = new URL(value, window.location.origin);
    if (!parsed.pathname.startsWith(TEMP_IMAGE_PATH_SEGMENT)) {
      return value;
    }
    parsed.searchParams.set('no_redirect', '1');
    parsed.searchParams.set('export', '1');
    return `${parsed.pathname}?${parsed.searchParams.toString()}`;
  } catch {
    return value;
  }
};

const isNonResultWorkflowOutputNode = (nodeId: string, nodeType: string): boolean => {
  const normalizedNodeType = String(nodeType || '').trim().toLowerCase();
  if (NON_RESULT_WORKFLOW_NODE_TYPES.has(normalizedNodeType)) {
    return true;
  }
  const normalizedNodeId = String(nodeId || '').trim().toLowerCase();
  return (
    normalizedNodeId.startsWith('start')
    || normalizedNodeId.startsWith('input-')
    || normalizedNodeId.startsWith('input_')
  );
};

const normalizeStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => String(item || '').trim())
    .filter(Boolean);
};

const mergeUniqueStringList = (...sources: string[][]): string[] => {
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

const waitForClonedImages = async (container: HTMLElement, timeoutMs = 10000): Promise<void> => {
  const images = Array.from(container.querySelectorAll('img[src]')) as HTMLImageElement[];
  if (images.length === 0) {
    return;
  }

  await Promise.all(images.map((img) => new Promise<void>((resolve) => {
    if (img.complete) {
      resolve();
      return;
    }

    const cleanup = () => {
      window.clearTimeout(timer);
      img.removeEventListener('load', onComplete);
      img.removeEventListener('error', onComplete);
    };
    const onComplete = () => {
      cleanup();
      resolve();
    };
    const timer = window.setTimeout(onComplete, timeoutMs);
    img.addEventListener('load', onComplete);
    img.addEventListener('error', onComplete);
  })));
};

interface MultiAgentWorkflowEditorReactFlowProps {
  onExecute?: (workflow: {
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    prompt: string;
    input?: Record<string, any>;
    meta?: {
      source: 'editor' | 'template';
      templateId?: string;
      templateName?: string;
    };
  }) => void | Promise<void>;
  onSave?: (workflow: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }) => void;
  executionStatus?: ExecutionStatus;
  loadedWorkflow?: {
    token: string;
    name?: string;
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    prompt?: string;
    input?: Record<string, any>;
  } | null;
  onExit?: () => void;
}

interface ActiveTemplateMeta extends WorkflowTemplateSaveTarget {
  templateId: string;
  templateName?: string;
}

const MultiAgentWorkflowEditorReactFlowInner: React.FC<MultiAgentWorkflowEditorReactFlowProps> = ({
  onExecute,
  onSave,
  executionStatus,
  loadedWorkflow,
  onExit,
}) => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const editorRootRef = useRef<HTMLDivElement>(null);
  const editorScopeIdRef = useRef(createWorkflowEditorScopeId());
  const editorScopeId = editorScopeIdRef.current;
  const pendingFitTokenRef = useRef<string | null>(null);
  const importedExecutionLogCountRef = useRef(0);
  const lastResultSignatureRef = useRef<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<WorkflowNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  // UI state
  const [showLogs, setShowLogs] = useState(false);
  const [showResultPanel, setShowResultPanel] = useState(() => {
    const initialFinalStatus = String(executionStatus?.finalStatus || '').trim().toLowerCase();
    return isTerminalExecutionStatus(initialFinalStatus);
  });
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [showTemplateSave, setShowTemplateSave] = useState(false);
  const [workflowPrompt, setWorkflowPrompt] = useState('');
  const [workflowInputImageUrl, setWorkflowInputImageUrl] = useState('');
  const [workflowInputFileUrl, setWorkflowInputFileUrl] = useState('');
  const [activeTemplateMeta, setActiveTemplateMeta] = useState<ActiveTemplateMeta | null>(null);
  const [activeTemplateFingerprint, setActiveTemplateFingerprint] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executeErrorBanner, setExecuteErrorBanner] = useState<string | null>(null);
  const [finalResult, setFinalResult] = useState<any>(null);
  const [finalError, setFinalError] = useState<string | null>(null);
  const [finalCompletedAt, setFinalCompletedAt] = useState<number | null>(null);
  const [finalRuntime, setFinalRuntime] = useState<string>('');
  const [finalRuntimeHints, setFinalRuntimeHints] = useState<string[]>([]);
  const [pendingNodeFieldFocusRequest, setPendingNodeFieldFocusRequest] = useState<WorkflowNodeFieldFocusRequest | null>(null);
  const [isMainWorkspaceFullscreen, setIsMainWorkspaceFullscreen] = useState(false);
  const [isExportingWorkflowImage, setIsExportingWorkflowImage] = useState(false);

  const { logs, addLog } = useExecutionLogs();
  const { undo, redo, canUndo, canRedo, takeSnapshot } = useUndoRedo();
  const { agents: registryAgents, refreshAgents } = useAgentRegistry();
  const selectedNode = useMemo(() => {
    const selected = nodes.find((node) => Boolean(node.selected));
    return (selected as Node<WorkflowNodeData>) || null;
  }, [nodes]);
  const selectedEdgeId = useMemo(() => {
    const selected = edges.find((edge) => Boolean(edge.selected));
    return selected ? String(selected.id) : null;
  }, [edges]);

  const hydrateAgentBindingsFromRegistry = useCallback(async (
    inputNodes: Node<WorkflowNodeData>[]
  ): Promise<Node<WorkflowNodeData>[]> => {
    if (!Array.isArray(inputNodes) || inputNodes.length === 0) {
      return inputNodes;
    }

    try {
      if (registryAgents.length > 0) {
        return applyAgentBindingsToNodes(inputNodes, registryAgents);
      }
      const fetchedAgents = await refreshAgents();
      return applyAgentBindingsToNodes(inputNodes, fetchedAgents);
    } catch {
      return inputNodes;
    }
  }, [registryAgents, refreshAgents]);

  const handleUndo = useCallback(() => {
    const state = undo();
    if (state) { setNodes(state.nodes); setEdges(state.edges); }
  }, [undo, setNodes, setEdges]);

  const handleRedo = useCallback(() => {
    const state = redo();
    if (state) { setNodes(state.nodes); setEdges(state.edges); }
  }, [redo, setNodes, setEdges]);

  const handleToggleMainWorkspaceFullscreen = useCallback(async () => {
    const target = editorRootRef.current;
    if (!target || typeof document === 'undefined') {
      return;
    }

    const currentFullscreenElement = document.fullscreenElement;
    if (!currentFullscreenElement) {
      if (typeof target.requestFullscreen === 'function') {
        await target.requestFullscreen();
      }
      return;
    }

    if (currentFullscreenElement === target) {
      if (typeof document.exitFullscreen === 'function') {
        await document.exitFullscreen();
      }
      return;
    }

    if (typeof target.requestFullscreen === 'function') {
      await target.requestFullscreen();
    }
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const syncFullscreenState = () => {
      setIsMainWorkspaceFullscreen(document.fullscreenElement === editorRootRef.current);
    };

    syncFullscreenState();
    document.addEventListener('fullscreenchange', syncFullscreenState);
    return () => {
      document.removeEventListener('fullscreenchange', syncFullscreenState);
    };
  }, []);

  const isValidConnection = useCallback((connection: Connection) => {
    const { source, target } = connection;
    if (!source || !target || source === target) return false;
    const sourceNode = nodes.find(n => n.id === source);
    const targetNode = nodes.find(n => n.id === target);
    if (!sourceNode || !targetNode) return false;
    if (targetNode.data.type === 'start') return false;
    if (sourceNode.data.type === 'end') return false;
    if (edges.find(e => e.source === source && e.target === target)) return false;
    return true;
  }, [nodes, edges]);

  const onConnect = useCallback((params: Connection) => {
    takeSnapshot(nodes, edges);
    setEdges((eds) => addEdge({
      ...params,
      type: DEFAULT_WORKFLOW_EDGE_TYPE,
      animated: true,
      style: { stroke: '#14b8a6', strokeWidth: 2 },
    }, eds));
  }, [setEdges, takeSnapshot, nodes, edges]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setNodes((nds) => applySingleNodeSelection(nds as Node<WorkflowNodeData>[], node.id));
    setEdges((eds) => applySingleEdgeSelection(eds, null));
  }, [setEdges, setNodes]);

  const onEdgeClick = useCallback((_event: React.MouseEvent, edge: Edge) => {
    setEdges((eds) => applySingleEdgeSelection(eds, edge.id));
    setNodes((nds) => applySingleNodeSelection(nds as Node<WorkflowNodeData>[], null));
  }, [setEdges, setNodes]);

  const onPaneClick = useCallback(() => {
    setNodes((nds) => applySingleNodeSelection(nds as Node<WorkflowNodeData>[], null));
    setEdges((eds) => applySingleEdgeSelection(eds, null));
  }, [setEdges, setNodes]);

  const handleCloseSelectedNode = useCallback(() => {
    onPaneClick();
  }, [onPaneClick]);

  const handleRemoveSelectedEdge = useCallback(() => {
    if (!selectedEdgeId) {
      return;
    }
    takeSnapshot(nodes, edges);
    setEdges((eds) => eds.filter((edge) => edge.id !== selectedEdgeId));
    addLog('system', '系统', 'info', '已断开 1 条连接');
  }, [selectedEdgeId, takeSnapshot, nodes, edges, setEdges, addLog]);

  const handleRemoveEdgeById = useCallback((edgeId: string) => {
    const normalizedId = String(edgeId || '').trim();
    if (!normalizedId || !edges.some((edge) => edge.id === normalizedId)) {
      return;
    }
    takeSnapshot(nodes, edges);
    setEdges((eds) => eds.filter((edge) => edge.id !== normalizedId));
    addLog('system', '系统', 'info', '已移除连接线');
  }, [edges, takeSnapshot, nodes, setEdges, addLog]);

  const handleDisconnectByHandle = useCallback((detail: DisconnectHandleEventDetail) => {
    const normalizeHandleId = (value?: string | null) => value ?? '__default__';

    const matchedEdges = edges.filter((edge) => {
      if (detail.direction === 'source') {
        if (edge.source !== detail.nodeId) return false;
        return normalizeHandleId(edge.sourceHandle) === normalizeHandleId(detail.handleId);
      }
      if (edge.target !== detail.nodeId) return false;
      return normalizeHandleId(edge.targetHandle) === normalizeHandleId(detail.handleId);
    });

    if (matchedEdges.length === 0) {
      addLog('system', '系统', 'warn', '该端口当前没有连接可断开');
      return;
    }

    const matchedIds = new Set(matchedEdges.map((edge) => edge.id));
    takeSnapshot(nodes, edges);
    setEdges((eds) => eds.filter((edge) => !matchedIds.has(edge.id)));
    addLog('system', '系统', 'info', `端口已断开 ${matchedEdges.length} 条连接`);
  }, [edges, addLog, takeSnapshot, nodes, setEdges]);

  const handleRemoveNodeById = useCallback((nodeId: string) => {
    const node = nodes.find((item) => item.id === nodeId);
    if (!node) {
      return;
    }
    takeSnapshot(nodes, edges);
    setNodes((nds) => nds.filter((item) => item.id !== nodeId));
    setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
    addLog('system', '系统', 'info', `已移除节点：${node.data.label}`);
  }, [nodes, edges, takeSnapshot, setNodes, setEdges, addLog]);

  const handleRemoveSelectedNode = useCallback(() => {
    if (!selectedNode) {
      return;
    }
    handleRemoveNodeById(selectedNode.id);
  }, [selectedNode, handleRemoveNodeById]);

  const handleAutoLayout = useCallback(() => {
    if (nodes.length === 0) {
      return;
    }
    takeSnapshot(nodes, edges);
    setNodes(autoLayoutWorkflow(nodes as Node<WorkflowNodeData>[], edges) as Node<WorkflowNodeData>[]);
    requestAnimationFrame(() => {
      reactFlowInstance?.fitView({ padding: 0.25, duration: 450 });
    });
    addLog('system', '系统', 'info', '已完成自动排版');
  }, [nodes, edges, takeSnapshot, setNodes, reactFlowInstance, addLog]);

  const handleDownloadWorkflowImage = useCallback(async () => {
    if (isExportingWorkflowImage) {
      return;
    }

    if (!reactFlowInstance) {
      addLog('system', '系统', 'warn', '画布尚未初始化，暂时无法下载');
      setExecuteErrorBanner('下载失败：画布尚未初始化，请稍后重试。');
      return;
    }

    const workflowNodes = reactFlowInstance.getNodes();
    if (!Array.isArray(workflowNodes) || workflowNodes.length === 0) {
      addLog('system', '系统', 'warn', '当前画布没有节点可下载');
      setExecuteErrorBanner('下载失败：当前画布没有可导出的节点。');
      return;
    }

    const flowElement = reactFlowWrapper.current?.querySelector('.react-flow') as HTMLElement | null;
    if (!flowElement) {
      addLog('system', '系统', 'warn', '未找到 React Flow 根容器，下载失败');
      setExecuteErrorBanner('下载失败：未找到画布容器。');
      return;
    }

    const nodeBounds = getNodesBounds(workflowNodes);
    const expandedBounds = {
      x: nodeBounds.x - EXPORT_NODE_PADDING,
      y: nodeBounds.y - EXPORT_NODE_PADDING,
      width: nodeBounds.width + EXPORT_NODE_PADDING * 2,
      height: nodeBounds.height + EXPORT_NODE_PADDING * 2,
    };

    const imageWidth = Math.max(Math.ceil(expandedBounds.width), EXPORT_MIN_WIDTH);
    const imageHeight = Math.max(Math.ceil(expandedBounds.height), EXPORT_MIN_HEIGHT);
    const exportArea = imageWidth * imageHeight;
    const shouldExportAsSvg = (
      imageWidth > EXPORT_PNG_MAX_SIDE
      || imageHeight > EXPORT_PNG_MAX_SIDE
      || exportArea > EXPORT_PNG_MAX_PIXELS
    );
    const exportPixelRatio = clampNumber(
      Math.sqrt(EXPORT_PNG_TARGET_PIXELS / Math.max(1, exportArea)),
      1.35,
      3.5
    );
    const offscreenWrapper = document.createElement('div');
    offscreenWrapper.style.position = 'fixed';
    offscreenWrapper.style.left = '-99999px';
    offscreenWrapper.style.top = '-99999px';
    offscreenWrapper.style.width = `${imageWidth}px`;
    offscreenWrapper.style.height = `${imageHeight}px`;
    offscreenWrapper.style.pointerEvents = 'none';
    offscreenWrapper.style.opacity = '0';
    offscreenWrapper.style.zIndex = '-1';

    const flowClone = flowElement.cloneNode(true) as HTMLElement;
    flowClone.style.width = `${imageWidth}px`;
    flowClone.style.height = `${imageHeight}px`;
    flowClone.style.background = '#0f172a';
    flowClone.style.overflow = 'hidden';

    flowClone.querySelectorAll('.react-flow__controls, .react-flow__minimap, .react-flow__attribution, .react-flow__panel')
      .forEach((element) => element.remove());

    const viewportClone = flowClone.querySelector('.react-flow__viewport') as HTMLElement | null;
    if (!viewportClone) {
      addLog('system', '系统', 'warn', '未找到导出视口，下载失败');
      setExecuteErrorBanner('下载失败：未找到导出视口。');
      return;
    }
    viewportClone.style.transform = `translate(${-expandedBounds.x}px, ${-expandedBounds.y}px) scale(1)`;
    viewportClone.style.transformOrigin = '0 0';

    const clonedImages = Array.from(flowClone.querySelectorAll('img[src]')) as HTMLImageElement[];
    clonedImages.forEach((img) => {
      const currentSrc = img.getAttribute('src') || '';
      const nextSrc = ensureTempImageNoRedirect(currentSrc);
      if (nextSrc !== currentSrc) {
        img.setAttribute('src', nextSrc);
      }
      img.setAttribute('crossorigin', 'anonymous');
      img.removeAttribute('srcset');
    });
    offscreenWrapper.appendChild(flowClone);

    setExecuteErrorBanner(null);
    setIsExportingWorkflowImage(true);

    try {
      document.body.appendChild(offscreenWrapper);
      await waitForClonedImages(flowClone);

      let dataUrl: string;
      let fileExtension: 'png' | 'svg' = shouldExportAsSvg ? 'svg' : 'png';
      try {
        if (shouldExportAsSvg) {
          dataUrl = await toSvg(flowClone, {
            backgroundColor: '#0f172a',
            cacheBust: true,
            width: imageWidth,
            height: imageHeight,
            style: {
              width: `${imageWidth}px`,
              height: `${imageHeight}px`,
            },
          });
          setExecuteErrorBanner('流程较大，已自动导出为 SVG 无损格式以保证清晰度。');
        } else {
          dataUrl = await toPng(flowClone, {
            backgroundColor: '#0f172a',
            cacheBust: true,
            pixelRatio: exportPixelRatio,
            width: imageWidth,
            height: imageHeight,
            style: {
              width: `${imageWidth}px`,
              height: `${imageHeight}px`,
            },
          });
        }
      } catch {
        if (shouldExportAsSvg) {
          dataUrl = await toSvg(flowClone, {
            backgroundColor: '#0f172a',
            cacheBust: true,
            width: imageWidth,
            height: imageHeight,
            style: {
              width: `${imageWidth}px`,
              height: `${imageHeight}px`,
            },
            filter: (domNode: HTMLElement) => {
              if (domNode instanceof HTMLImageElement) {
                const source = String(domNode.getAttribute('src') || domNode.src || '').trim();
                if (!source) return false;
                if (source.startsWith('data:') || source.startsWith('blob:')) return true;
                if (source.startsWith('/') || source.startsWith(window.location.origin)) return true;
                return false;
              }
              return true;
            },
          });
          fileExtension = 'svg';
        } else {
          dataUrl = await toPng(flowClone, {
            backgroundColor: '#0f172a',
            cacheBust: true,
            pixelRatio: exportPixelRatio,
            width: imageWidth,
            height: imageHeight,
            style: {
              width: `${imageWidth}px`,
              height: `${imageHeight}px`,
            },
            filter: (domNode: HTMLElement) => {
              if (domNode instanceof HTMLImageElement) {
                const source = String(domNode.getAttribute('src') || domNode.src || '').trim();
                if (!source) return false;
                if (source.startsWith('data:') || source.startsWith('blob:')) return true;
                if (source.startsWith('/') || source.startsWith(window.location.origin)) return true;
                return false;
              }
              return true;
            },
          });
          fileExtension = 'png';
        }
        setExecuteErrorBanner('已导出图片，但已自动跳过无法跨域加载的图片资源。');
      }

      const timestamp = `${Date.now()}`;
      const anchor = document.createElement('a');
      anchor.href = dataUrl;
      anchor.download = `workflow-${timestamp}.${fileExtension}`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      addLog('system', '系统', 'info', `已下载工作流画布图片（${fileExtension.toUpperCase()}，${imageWidth}×${imageHeight}${fileExtension === 'png' ? `，倍率 ${exportPixelRatio.toFixed(2)}` : ''}）`);
    } catch (error) {
      const rawMessage = formatWorkflowExportError(error);
      const lower = rawMessage.toLowerCase();
      const message = (
        lower.includes('tainted')
        || lower.includes('cross')
        || lower.includes('cors')
        || lower.includes('security')
        || lower.includes('failed to fetch')
      )
        ? '下载失败：检测到跨域图片资源无法导出，请确认图片可经 /api/temp-images/*?no_redirect=1 访问。'
        : `下载失败：${rawMessage}`;
      addLog('system', '系统', 'error', `下载工作流图片失败: ${rawMessage}`);
      setExecuteErrorBanner(message);
    } finally {
      if (offscreenWrapper.parentNode) {
        offscreenWrapper.parentNode.removeChild(offscreenWrapper);
      }
      setIsExportingWorkflowImage(false);
    }
  }, [addLog, isExportingWorkflowImage, reactFlowInstance]);

  const handleUpdateNode = useCallback((nodeId: string, updates: Partial<WorkflowNodeData>) => {
    const includesPortLayoutUpdate = Object.prototype.hasOwnProperty.call(updates, 'portLayout');
    const mergeNodeData = (node: Node<WorkflowNodeData>): Node<WorkflowNodeData> => {
      if (node.id !== nodeId) {
        return node;
      }
      const nodeType = node.data?.type || node.type || 'agent';
      const nextData: WorkflowNodeData = {
        ...node.data,
        ...updates,
      };
      if (includesPortLayoutUpdate) {
        nextData.portLayout = resolveNodePortLayout(nodeType, updates.portLayout ?? node.data?.portLayout);
      }
      return {
        ...node,
        data: nextData,
      };
    };

    if (includesPortLayoutUpdate) {
      takeSnapshot(nodes, edges);
    }

    setNodes((nds) => nds.map((node) => mergeNodeData(node as Node<WorkflowNodeData>)));

    if (includesPortLayoutUpdate) {
      setEdges((eds) => {
        // Read latest nodes from setNodes updater to avoid stale closure
        let currentNodes: Node<WorkflowNodeData>[] = [];
        setNodes((nds) => { currentNodes = nds.map((n) => mergeNodeData(n as Node<WorkflowNodeData>)); return nds; });
        const updatedNodes = currentNodes.length > 0 ? currentNodes : nodes.map((node) => mergeNodeData(node as Node<WorkflowNodeData>));
        const filteredEdges = filterEdgesByNodePortLayouts(updatedNodes, eds);
        const removedCount = eds.length - filteredEdges.length;
        if (removedCount > 0) {
          addLog('system', '系统', 'warn', `端口配置变更后，已移除 ${removedCount} 条不匹配连接`);
        }
        return filteredEdges;
      });
    }
  }, [addLog, edges, nodes, setEdges, setNodes, takeSnapshot]);

  useEffect(() => {
    if (!executionStatus) {
      return;
    }

    const previewImages = Array.isArray(executionStatus.resultPreviewImageUrls)
      ? executionStatus.resultPreviewImageUrls
      : [];
    const previewAudioUrls = Array.isArray(executionStatus.resultPreviewAudioUrls)
      ? executionStatus.resultPreviewAudioUrls
      : [];
    const previewVideoUrls = Array.isArray(executionStatus.resultPreviewVideoUrls)
      ? executionStatus.resultPreviewVideoUrls
      : [];
    const finalResult = executionStatus.finalResult;
    const mergeNodeResult = (rawResult: unknown, nodeType: string, existingResult: unknown) => {
      const normalizedNodeType = String(nodeType || '').toLowerCase();
      if (normalizedNodeType !== 'end') {
        return rawResult;
      }
      const mergedFinalResult = finalResult !== undefined && finalResult !== null
        ? mergePreviewImagesIntoResult(finalResult, extractImageUrls(rawResult))
        : rawResult;
      let mergedWithPreview = mergePreviewImagesIntoResult(mergedFinalResult, previewImages);
      if (previewAudioUrls.length > 0) {
        mergedWithPreview = mergePreviewMediaIntoResult(mergedWithPreview, 'audio', previewAudioUrls);
      }
      if (previewVideoUrls.length > 0) {
        mergedWithPreview = mergePreviewMediaIntoResult(mergedWithPreview, 'video', previewVideoUrls);
      }
      const existingImages = extractImageUrls(existingResult);
      const existingAudioUrls = extractAudioUrls(existingResult);
      const existingVideoUrls = extractVideoUrls(existingResult);
      if (existingImages.length === 0 && existingAudioUrls.length === 0 && existingVideoUrls.length === 0) {
        return mergedWithPreview;
      }
      let mergedExistingResult = mergePreviewImagesIntoResult(mergedWithPreview, existingImages);
      if (existingAudioUrls.length > 0) {
        mergedExistingResult = mergePreviewMediaIntoResult(mergedExistingResult, 'audio', existingAudioUrls);
      }
      if (existingVideoUrls.length > 0) {
        mergedExistingResult = mergePreviewMediaIntoResult(mergedExistingResult, 'video', existingVideoUrls);
      }
      return mergedExistingResult;
    };

    setNodes((nds) =>
      nds.map((node) => {
        const status = executionStatus.nodeStatuses[node.id];
        if (!status) {
          return node;
        }
        const nodeType = String(node?.data?.type || node?.type || '').trim().toLowerCase();
        const rawResult = executionStatus.nodeResults[node.id] ?? node.data.result;
        return {
          ...node,
          data: {
            ...node.data,
            status,
            progress: executionStatus.nodeProgress[node.id] ?? node.data.progress,
            result: mergeNodeResult(rawResult, nodeType, node.data.result),
            error: executionStatus.nodeErrors[node.id] ?? node.data.error,
            runtime: executionStatus.nodeRuntimes?.[node.id] ?? node.data.runtime,
          },
        };
      })
    );
  }, [executionStatus, setNodes]);

  useEffect(() => {
    if (!executionStatus) {
      importedExecutionLogCountRef.current = 0;
      return;
    }

    const sourceLogs = Array.isArray(executionStatus.logs) ? executionStatus.logs : [];
    if (sourceLogs.length < importedExecutionLogCountRef.current) {
      importedExecutionLogCountRef.current = 0;
    }

    const pendingLogs = sourceLogs.slice(importedExecutionLogCountRef.current);
    if (pendingLogs.length === 0) {
      return;
    }

    const nodeNameMap = new Map(nodes.map((node) => [node.id, node.data.label]));
    for (const log of pendingLogs) {
      const nodeName = log.nodeId === 'system'
        ? '系统'
        : nodeNameMap.get(log.nodeId) || log.nodeId || '节点';
      addLog(log.nodeId || 'system', nodeName, log.level, log.message, log.timestamp);
    }
    importedExecutionLogCountRef.current = sourceLogs.length;
  }, [executionStatus?.logs, nodes, addLog]);

  useEffect(() => {
    const status = String(executionStatus?.finalStatus || '').trim().toLowerCase();
    if (status === 'running' || status === 'pending') {
      setExecuteErrorBanner(null);
      setFinalResult(null);
      setFinalError(null);
      setFinalCompletedAt(null);
      setFinalRuntime('');
      setFinalRuntimeHints([]);
      return;
    }
    if (!isTerminalExecutionStatus(status)) {
      return;
    }

    const signature = `${executionStatus?.executionId || ''}:${executionStatus?.completedAt || ''}:${status}`;
    if (signature === lastResultSignatureRef.current) {
      return;
    }
    lastResultSignatureRef.current = signature;

    const statusPreviewImages = Array.isArray(executionStatus?.resultPreviewImageUrls)
      ? executionStatus.resultPreviewImageUrls.map((item) => String(item || '').trim()).filter(Boolean)
      : [];
    const statusPreviewAudioUrls = Array.isArray(executionStatus?.resultPreviewAudioUrls)
      ? executionStatus.resultPreviewAudioUrls.map((item) => String(item || '').trim()).filter(Boolean)
      : [];
    const statusPreviewVideoUrls = Array.isArray(executionStatus?.resultPreviewVideoUrls)
      ? executionStatus.resultPreviewVideoUrls.map((item) => String(item || '').trim()).filter(Boolean)
      : [];
    let mergedFinalResult = mergePreviewImagesIntoResult(executionStatus?.finalResult ?? null, statusPreviewImages);
    if (statusPreviewAudioUrls.length > 0) {
      mergedFinalResult = mergePreviewMediaIntoResult(mergedFinalResult, 'audio', statusPreviewAudioUrls);
    }
    if (statusPreviewVideoUrls.length > 0) {
      mergedFinalResult = mergePreviewMediaIntoResult(mergedFinalResult, 'video', statusPreviewVideoUrls);
    }
    setFinalResult(mergedFinalResult);
    setFinalError(executionStatus?.finalError || null);
    setFinalCompletedAt(executionStatus?.completedAt || Date.now());
    setFinalRuntime(String(executionStatus?.finalRuntime || '').trim());
    setFinalRuntimeHints(
      Array.isArray(executionStatus?.runtimeHints)
        ? executionStatus.runtimeHints.map((hint) => String(hint || '').trim()).filter(Boolean)
        : []
    );
    setShowResultPanel(true);
  }, [
    executionStatus?.executionId,
    executionStatus?.completedAt,
    executionStatus?.finalStatus,
    executionStatus?.finalResult,
    executionStatus?.resultPreviewImageUrls,
    executionStatus?.resultPreviewAudioUrls,
    executionStatus?.resultPreviewVideoUrls,
    executionStatus?.finalError,
    executionStatus?.finalRuntime,
    executionStatus?.runtimeHints,
  ]);

  useEffect(() => {
    if (!loadedWorkflow?.token) {
      return;
    }

    const normalizedNodes = (loadedWorkflow.nodes || []).map((node, index) => normalizeLoadedNode(node, index));
    const nodeIdSet = new Set(normalizedNodes.map((node) => node.id));
    const normalizedEdges = (loadedWorkflow.edges || [])
      .map((edge: Record<string, unknown>, index: number) => ({
        ...edge,
        id: String(edge?.id || `edge-loaded-${index}-${Date.now()}`),
        type: String(edge?.type || DEFAULT_WORKFLOW_EDGE_TYPE),
      }))
      .filter((edge: Record<string, unknown>) => nodeIdSet.has(String(edge?.source || '')) && nodeIdSet.has(String(edge?.target || '')));
    const normalizedNodesWithPortLayout = hydrateNodePortLayoutsFromEdges(
      normalizedNodes as Node<WorkflowNodeData>[],
      normalizedEdges as Edge[],
    );

    const loadedInput = loadedWorkflow.input && typeof loadedWorkflow.input === 'object' && !Array.isArray(loadedWorkflow.input)
      ? loadedWorkflow.input
      : {};
    const loadedPrompt = String(
      loadedInput.task || loadedInput.prompt || loadedInput.text || loadedWorkflow.prompt || ''
    );
    const loadedImageUrls = mergeUniqueStringList(
      normalizeStringList(loadedInput.imageUrls),
      normalizeStringList(loadedInput.image_urls),
      typeof loadedInput.imageUrl === 'string' ? [loadedInput.imageUrl.trim()] : [],
    );
    const loadedImageUrl = loadedImageUrls[0] || '';
    const loadedFileUrls = mergeUniqueStringList(
      normalizeStringList(loadedInput.fileUrls),
      normalizeStringList(loadedInput.file_urls),
      typeof loadedInput.fileUrl === 'string' ? [loadedInput.fileUrl.trim()] : [],
    );
    const loadedFileUrl = loadedFileUrls[0] || '';
    const hydratedNodes = normalizedNodesWithPortLayout.map((node) => {
      const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
      if (!['start', 'input_text', 'input_image', 'input_file'].includes(nodeType)) {
        return node;
      }
      const nextData: Record<string, any> = { ...node.data };
      if (nodeType === 'start' || nodeType === 'input_text') {
        nextData.startTask = String(node.data?.startTask || loadedPrompt || '');
      }
      if (nodeType === 'start' || nodeType === 'input_image') {
        const nodeImageUrls = mergeUniqueStringList(
          normalizeStringList(node.data?.startImageUrls),
          node.data?.startImageUrl ? [String(node.data.startImageUrl).trim()] : [],
          loadedImageUrls,
        );
        nextData.startImageUrl = nodeImageUrls[0] || '';
        nextData.startImageUrls = nodeImageUrls;
      }
      if (nodeType === 'start' || nodeType === 'input_file') {
        const nodeFileUrls = mergeUniqueStringList(
          normalizeStringList(node.data?.startFileUrls),
          node.data?.startFileUrl ? [String(node.data.startFileUrl).trim()] : [],
          loadedFileUrls,
        );
        nextData.startFileUrl = nodeFileUrls[0] || '';
        nextData.startFileUrls = nodeFileUrls;
      }
      return {
        ...node,
        data: nextData,
      };
    });

    let cancelled = false;
    void (async () => {
      const nodesWithAgentBinding = await hydrateAgentBindingsFromRegistry(hydratedNodes as Node<WorkflowNodeData>[]);
      if (cancelled) return;
      setNodes(applySingleNodeSelection(nodesWithAgentBinding as Node<WorkflowNodeData>[], null));
      setEdges(applySingleEdgeSelection(normalizedEdges as Edge[], null));
      setWorkflowPrompt(loadedPrompt);
      setWorkflowInputImageUrl(loadedImageUrl);
      setWorkflowInputFileUrl(loadedFileUrl);
      setActiveTemplateMeta(null);
      setActiveTemplateFingerprint(null);
      pendingFitTokenRef.current = loadedWorkflow.token;
      addLog('system', '系统', 'info', `已加载工作流${loadedWorkflow.name ? `：${loadedWorkflow.name}` : ''}`);
    })();

    return () => {
      cancelled = true;
    };
  }, [loadedWorkflow?.token, loadedWorkflow?.name, loadedWorkflow?.prompt, loadedWorkflow?.input, loadedWorkflow?.nodes, loadedWorkflow?.edges, setNodes, setEdges, addLog, hydrateAgentBindingsFromRegistry]);

  useEffect(() => {
    if (!reactFlowInstance) {
      return;
    }
    const pendingToken = pendingFitTokenRef.current;
    if (!pendingToken) {
      return;
    }

    pendingFitTokenRef.current = null;
    requestAnimationFrame(() => {
      reactFlowInstance.fitView({ padding: 0.25, duration: 420 });
    });
  }, [reactFlowInstance, nodes.length, edges.length]);

  useEffect(() => {
    const onDisconnectByHandle = (event: Event) => {
      const customEvent = event as CustomEvent<DisconnectHandleEventDetail>;
      if (!isWorkflowEventForEditorScope(customEvent.detail?.editorScopeId, editorScopeId)) {
        return;
      }
      if (!customEvent.detail?.nodeId || !customEvent.detail?.direction) {
        return;
      }
      handleDisconnectByHandle(customEvent.detail);
    };

    window.addEventListener('workflow:disconnect-handle', onDisconnectByHandle as EventListener);
    return () => window.removeEventListener('workflow:disconnect-handle', onDisconnectByHandle as EventListener);
  }, [editorScopeId, handleDisconnectByHandle]);

  useEffect(() => {
    const onRemoveEdgeRequest = (event: Event) => {
      const customEvent = event as CustomEvent<WorkflowRemoveEdgeRequestDetail>;
      if (!isWorkflowEventForEditorScope(customEvent.detail?.editorScopeId, editorScopeId)) {
        return;
      }
      const edgeId = String(customEvent?.detail?.edgeId || '').trim();
      if (!edgeId) {
        return;
      }
      handleRemoveEdgeById(edgeId);
    };

    window.addEventListener('workflow:remove-edge-request', onRemoveEdgeRequest as EventListener);
    return () => window.removeEventListener('workflow:remove-edge-request', onRemoveEdgeRequest as EventListener);
  }, [editorScopeId, handleRemoveEdgeById]);

  useEffect(() => {
    const onFocusNodeField = (event: Event) => {
      const customEvent = event as CustomEvent<WorkflowNodeFieldFocusEventDetail>;
      if (!isWorkflowEventForEditorScope(customEvent.detail?.editorScopeId, editorScopeId)) {
        return;
      }
      const nodeId = String(customEvent?.detail?.nodeId || '').trim();
      const fieldKey = String(customEvent?.detail?.fieldKey || '').trim();
      if (!nodeId || !fieldKey) {
        return;
      }

      const matchedNode = nodes.find((node) => String(node.id) === nodeId);
      if (!matchedNode) {
        return;
      }
      setNodes((nds) => applySingleNodeSelection(nds as Node<WorkflowNodeData>[], nodeId));
      setEdges((eds) => applySingleEdgeSelection(eds, null));
      setPendingNodeFieldFocusRequest({
        nodeId,
        fieldKey,
        token: `${nodeId}-${fieldKey}-${Date.now()}`,
      });
    };

    window.addEventListener('workflow:focus-node-field', onFocusNodeField as EventListener);
    return () => window.removeEventListener('workflow:focus-node-field', onFocusNodeField as EventListener);
  }, [editorScopeId, nodes]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isKeyboardEventWithinEditableContext(event)) {
        return;
      }

      if (event.key !== 'Delete' && event.key !== 'Backspace') {
        return;
      }

      if (selectedEdgeId) {
        event.preventDefault();
        handleRemoveSelectedEdge();
        return;
      }

      if (selectedNode) {
        event.preventDefault();
        handleRemoveSelectedNode();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedNode, selectedEdgeId, handleRemoveSelectedNode, handleRemoveSelectedEdge]);

  const handleExecute = useCallback(async () => {
    if (!onExecute) {
      const message = '未配置执行处理器，无法启动工作流';
      addLog('system', '系统', 'warn', message);
      setExecuteErrorBanner(message);
      setShowLogs(true);
      return;
    }
    if (isExecuting) {
      const message = '工作流正在执行中，请稍候';
      addLog('system', '系统', 'warn', message);
      setExecuteErrorBanner(message);
      return;
    }

    try {
      setExecuteErrorBanner(null);
      const validation = validateWorkflow(nodes as Node<WorkflowNodeData>[], edges as Edge[]);
      if (!validation.isValid) {
        const nodeErrorDetails = Object.entries(validation.nodeErrors || {})
          .slice(0, 4)
          .map(([nodeId, errors]) => `${nodeId}: ${(errors || []).join('；')}`);
        const details = [
          ...(validation.globalErrors || []),
          ...(validation.edgeErrors || []),
          ...nodeErrorDetails,
        ].filter(Boolean);
        const message = details.length > 0
          ? `工作流结构校验失败：${details.join(' | ')}`
          : '工作流结构校验失败，请检查开始/结束节点及连线';
        throw new Error(message);
      }

      setIsExecuting(true);
      addLog('system', '系统', 'info', '开始执行工作流...');
      const pickFirstNodeValue = (candidateTypes: string[], key: keyof WorkflowNodeData) => {
        for (const node of (nodes as WorkflowNode[])) {
          const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
          if (!candidateTypes.includes(nodeType)) {
            continue;
          }
          const value = node?.data?.[key];
          const text = typeof value === 'string' ? value.trim() : '';
          if (text) {
            return text;
          }
        }
        return '';
      };
      const pickFirstNodeList = (
        candidateTypes: string[],
        listKey: keyof WorkflowNodeData,
        singleKey: keyof WorkflowNodeData,
      ): string[] => {
        for (const node of (nodes as WorkflowNode[])) {
          const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
          if (!candidateTypes.includes(nodeType)) {
            continue;
          }
          const listValue = mergeUniqueStringList(
            normalizeStringList(node?.data?.[listKey]),
            typeof node?.data?.[singleKey] === 'string'
              ? [String(node.data[singleKey] || '').trim()]
              : [],
          );
          if (listValue.length > 0) {
            return listValue;
          }
        }
        return [];
      };

      const startNode = (nodes as WorkflowNode[]).find((node) => {
        const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
        return nodeType === 'start';
      });
      const startTask = String(startNode?.data?.startTask || '').trim();
      const startImageInputs = mergeUniqueStringList(
        normalizeStringList(startNode?.data?.startImageUrls),
        startNode?.data?.startImageUrl ? [String(startNode.data.startImageUrl).trim()] : [],
      );
      const startFileInputs = mergeUniqueStringList(
        normalizeStringList(startNode?.data?.startFileUrls),
        startNode?.data?.startFileUrl ? [String(startNode.data.startFileUrl).trim()] : [],
      );
      const inputTextNodeTask = pickFirstNodeValue(['input_text'], 'startTask');
      const inputImageNodeUrls = pickFirstNodeList(['input_image'], 'startImageUrls', 'startImageUrl');
      const inputFileNodeUrls = pickFirstNodeList(['input_file'], 'startFileUrls', 'startFileUrl');

      const effectivePrompt = String(startTask || inputTextNodeTask || workflowPrompt || '').trim();
      const rawPrompt = effectivePrompt;
      let workflowInput: Record<string, any> = { task: effectivePrompt };
      if (rawPrompt.startsWith('{') && rawPrompt.endsWith('}')) {
        try {
          const parsed = JSON.parse(rawPrompt);
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            workflowInput = {
              ...parsed,
              task: parsed.task || parsed.prompt || parsed.text || effectivePrompt,
            };
          }
        } catch {
          // ignore invalid json prompt and use plain text input
        }
      }

      const promptImageInputs = mergeUniqueStringList(
        normalizeStringList(workflowInput.imageUrls),
        normalizeStringList((workflowInput as any).image_urls),
        typeof workflowInput.imageUrl === 'string' ? [workflowInput.imageUrl.trim()] : [],
      );
      const preferredImageInputs = (
        inputImageNodeUrls.length > 0
          ? inputImageNodeUrls
          : startImageInputs.length > 0
            ? startImageInputs
            : promptImageInputs.length > 0
              ? promptImageInputs
              : (workflowInputImageUrl.trim() ? [workflowInputImageUrl.trim()] : [])
      );
      const usableImageInputs = preferredImageInputs.filter((value) => hasUsableImageInput(value));
      if (usableImageInputs.length > 0) {
        workflowInput.imageUrl = usableImageInputs[0];
        workflowInput.imageUrls = usableImageInputs;
      } else {
        delete workflowInput.imageUrl;
        delete workflowInput.imageUrls;
      }

      const isUsableFileInput = (value: string) => {
        const normalized = String(value || '').trim();
        if (!normalized) return false;
        if (normalized.includes('{{') || normalized.includes('}}')) return false;
        return true;
      };
      const promptFileInputs = mergeUniqueStringList(
        normalizeStringList(workflowInput.fileUrls),
        normalizeStringList((workflowInput as any).file_urls),
        typeof workflowInput.fileUrl === 'string' ? [workflowInput.fileUrl.trim()] : [],
      );
      const preferredFileInputs = (
        inputFileNodeUrls.length > 0
          ? inputFileNodeUrls
          : startFileInputs.length > 0
            ? startFileInputs
            : promptFileInputs.length > 0
              ? promptFileInputs
              : (workflowInputFileUrl.trim() ? [workflowInputFileUrl.trim()] : [])
      );
      const usableFileInputs = preferredFileInputs.filter(isUsableFileInput);
      if (usableFileInputs.length > 0) {
        workflowInput.fileUrl = usableFileInputs[0];
        workflowInput.fileUrls = usableFileInputs;
      } else {
        delete workflowInput.fileUrl;
        delete workflowInput.fileUrls;
      }

      const hasGlobalImageInput = Array.isArray(workflowInput.imageUrls) && workflowInput.imageUrls.length > 0;
      const hasInvalidAgentImageTask = (nodes as WorkflowNode[]).some((node) => {
        const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
        if (nodeType !== 'agent') return false;
        const hasNodeImage = Boolean(String(node?.data?.agentReferenceImageUrl || '').trim());
        if (!hasNodeImage) return false;
        const taskType = String(node?.data?.agentTaskType || 'chat').toLowerCase().replace(/_/g, '-');
        return !(
          taskType === 'vision-understand'
          || taskType === 'image-understand'
          || taskType === 'vision-analyze'
          || taskType === 'image-analyze'
          || taskType === 'image-edit'
        );
      });
      if (hasInvalidAgentImageTask) {
        throw new Error('存在智能体节点已配置参考图，但任务类型不是 vision-understand 或 image-edit。请先修正节点配置。');
      }
      const requiresImageInput = (nodes as WorkflowNode[]).some((node) => {
        const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
        if (nodeType === 'agent') {
          const taskType = String(node?.data?.agentTaskType || '').toLowerCase();
          if (
            taskType === 'image-edit'
            || taskType === 'image_edit'
            || taskType === 'vision-understand'
            || taskType === 'vision_understand'
            || taskType === 'image-understand'
            || taskType === 'image_understand'
          ) {
            const hasNodeImage = Boolean(String(node?.data?.agentReferenceImageUrl || '').trim());
            return !hasNodeImage;
          }
        }
        if (nodeType === 'tool') {
          const toolName = String(node?.data?.toolName || '').toLowerCase().replace(/-/g, '_');
          const editTools = new Set([
            'image_edit', 'edit_image', 'image_chat_edit', 'image_mask_edit',
            'image_inpainting', 'image_background_edit', 'image_recontext',
            'image_outpaint', 'image_outpainting', 'expand_image',
          ]);
          if (editTools.has(toolName)) {
            const hasNodeImage = Boolean(String(node?.data?.toolReferenceImageUrl || '').trim());
            return !hasNodeImage;
          }
        }
        return false;
      });
      if (requiresImageInput && !hasGlobalImageInput) {
        throw new Error('当前工作流包含图像编辑节点，请提供有效参考图片（上传图片或填写真实 input.imageUrl）');
      }

      const currentFingerprint = buildWorkflowStructureFingerprint(
        nodes as Node<WorkflowNodeData>[],
        edges as Edge[],
      );
      const canSyncTemplateResult = Boolean(
        activeTemplateMeta?.templateId
        && activeTemplateFingerprint
        && activeTemplateFingerprint === currentFingerprint,
      );

      await onExecute({
        nodes: nodes as WorkflowNode[],
        edges: edges as WorkflowEdge[],
        prompt: effectivePrompt,
        input: workflowInput,
        meta: canSyncTemplateResult
          ? {
            source: 'template',
            templateId: activeTemplateMeta?.templateId,
            templateName: activeTemplateMeta.templateName || '',
          }
          : { source: 'editor' },
      });
      setExecuteErrorBanner(null);
      addLog('system', '系统', 'info', '工作流执行完成');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      setExecuteErrorBanner(errorMessage);
      setShowLogs(true);
      addLog('system', '系统', 'error', `工作流执行失败: ${errorMessage}`);
    } finally {
      setIsExecuting(false);
    }
  }, [addLog, onExecute, nodes, edges, workflowPrompt, workflowInputImageUrl, workflowInputFileUrl, activeTemplateMeta, activeTemplateFingerprint, isExecuting]);

  useEffect(() => {
    const onExecuteRequest = (event: Event) => {
      const customEvent = event as CustomEvent<WorkflowNodeActionEventDetail>;
      if (!isWorkflowEventForEditorScope(customEvent.detail?.editorScopeId, editorScopeId)) {
        return;
      }
      const requestNodeId = String(customEvent.detail?.nodeId || '').trim();
      if (!requestNodeId) {
        return;
      }
      const node = nodes.find((item) => String(item.id) === requestNodeId);
      const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
      if (nodeType !== 'start') {
        return;
      }
      void handleExecute();
    };

    const onEndRequest = (event: Event) => {
      const customEvent = event as CustomEvent<WorkflowNodeActionEventDetail>;
      if (!isWorkflowEventForEditorScope(customEvent.detail?.editorScopeId, editorScopeId)) {
        return;
      }
      const requestNodeId = String(customEvent.detail?.nodeId || '').trim();
      if (!requestNodeId) {
        return;
      }
      const node = nodes.find((item) => String(item.id) === requestNodeId);
      const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
      if (nodeType !== 'end') {
        return;
      }
      const finalStatus = String(executionStatus?.finalStatus || '').trim().toLowerCase();
      if (finalResult === null && !finalError && !isTerminalExecutionStatus(finalStatus)) {
        addLog('system', '系统', 'warn', '结束节点暂无结果，请先从开始节点执行工作流');
        return;
      }
      setShowResultPanel(true);
    };

    window.addEventListener('workflow:execute-request', onExecuteRequest as EventListener);
    window.addEventListener('workflow:end-request', onEndRequest as EventListener);
    return () => {
      window.removeEventListener('workflow:execute-request', onExecuteRequest as EventListener);
      window.removeEventListener('workflow:end-request', onEndRequest as EventListener);
    };
  }, [addLog, editorScopeId, executionStatus?.finalStatus, finalError, finalResult, handleExecute, nodes]);

  const handleCopyFinalResult = useCallback(async () => {
    const payload = finalError
      ? { error: finalError }
      : (finalResult ?? { message: '暂无可复制结果' });
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      addLog('system', '系统', 'info', '已复制最终结果到剪贴板');
    } catch {
      addLog('system', '系统', 'warn', '复制失败，请检查浏览器权限');
    }
  }, [finalResult, finalError, addLog]);

  const renderedResultItems = useMemo(() => {
    if (finalResult == null) {
      return [] as Array<{
        key: string;
        title: string;
        text: string;
        imageUrls: string[];
        audioUrls: string[];
        videoUrls: string[];
        urls: string[];
        thoughts: string[];
      }>;
    }

    const items: Array<{
      key: string;
      title: string;
      text: string;
      imageUrls: string[];
      audioUrls: string[];
      videoUrls: string[];
      urls: string[];
      thoughts: string[];
    }> = [];
    const seenSignatures = new Set<string>();
    const seenImageUrls = new Set<string>();
    const seenAudioUrls = new Set<string>();
    const seenVideoUrls = new Set<string>();
    const seenUrls = new Set<string>();
    const nodeTypeById = new Map(
      (nodes as WorkflowNode[]).map((node) => [
        String(node?.id || '').trim(),
        String(node?.data?.type || node?.type || '').trim().toLowerCase(),
      ])
    );

    const pushItem = (key: string, title: string, payload: unknown, prefer = false) => {
      const rawText = extractTextContent(payload);
      const text = rawText.length > 2000 ? `${rawText.slice(0, 2000)}\n...(内容已截断)` : rawText;
      const imageUrls = extractImageUrls(payload);
      const audioUrls = extractAudioUrls(payload);
      const videoUrls = extractVideoUrls(payload);
      const thoughtItems = extractThoughtContent(payload);
      const mergedUrls = [
        ...imageUrls.filter((imageUrl) => !String(imageUrl).startsWith('data:image/')),
        ...audioUrls.filter((audioUrl) => !String(audioUrl).startsWith('data:audio/')),
        ...videoUrls.filter((videoUrl) => !String(videoUrl).startsWith('data:video/')),
        ...extractUrlContent(payload),
      ];
      const urls = Array.from(new Set(mergedUrls));
      if (!text && imageUrls.length === 0 && audioUrls.length === 0 && videoUrls.length === 0 && thoughtItems.length === 0 && urls.length === 0) {
        return;
      }
      const hasUniqueImage = imageUrls.some((imageUrl) => !seenImageUrls.has(imageUrl));
      const hasUniqueAudio = audioUrls.some((audioUrl) => !seenAudioUrls.has(audioUrl));
      const hasUniqueVideo = videoUrls.some((videoUrl) => !seenVideoUrls.has(videoUrl));
      const hasUniqueUrl = urls.some((url) => !seenUrls.has(url));
      if (!prefer && !hasUniqueImage && !hasUniqueAudio && !hasUniqueVideo && !hasUniqueUrl && thoughtItems.length === 0 && text.length < 30) {
        return;
      }
      const normalizedText = text.replace(/\s+/g, ' ').trim().slice(0, 400);
      const normalizedImages = imageUrls.map((imageUrl) => imageUrl.trim()).sort();
      const normalizedAudio = audioUrls.map((audioUrl) => audioUrl.trim()).sort();
      const normalizedVideo = videoUrls.map((videoUrl) => videoUrl.trim()).sort();
      const normalizedUrls = urls.map((url) => url.trim()).sort();
      const normalizedThoughts = thoughtItems.map((item) => item.replace(/\s+/g, ' ').trim().slice(0, 240)).sort();
      const signature = `${normalizedText}::${normalizedImages.join('|')}::${normalizedAudio.join('|')}::${normalizedVideo.join('|')}::${normalizedUrls.join('|')}::${normalizedThoughts.join('|')}`;
      if (seenSignatures.has(signature)) {
        return;
      }
      seenSignatures.add(signature);
      imageUrls.forEach((imageUrl) => seenImageUrls.add(imageUrl));
      audioUrls.forEach((audioUrl) => seenAudioUrls.add(audioUrl));
      videoUrls.forEach((videoUrl) => seenVideoUrls.add(videoUrl));
      urls.forEach((url) => seenUrls.add(url));
      items.push({
        key,
        title,
        text,
        imageUrls,
        audioUrls,
        videoUrls,
        urls,
        thoughts: thoughtItems,
      });
    };

    const finalOutput = isPlainObject(finalResult)
      ? finalResult.finalOutput
      : undefined;
    if (finalOutput !== undefined) {
      pushItem('final-output', '最终输出', finalOutput, true);
    } else {
      pushItem('final-result', '执行结果', finalResult, true);
    }

    const outputs = isPlainObject(finalResult)
      ? (finalResult.outputs || finalResult.outputsMap || null)
      : null;
    if (isPlainObject(outputs)) {
      Object.entries(outputs).forEach(([nodeId, output]) => {
        const nodeType = nodeTypeById.get(String(nodeId || '').trim()) || '';
        if (isNonResultWorkflowOutputNode(nodeId, nodeType)) {
          return;
        }
        const title = isPlainObject(output) && typeof output.agentName === 'string' && output.agentName
          ? `${output.agentName} (${nodeId})`
          : `节点 ${nodeId}`;
        pushItem(`node-${nodeId}`, title, output);
      });
    }

    return items;
  }, [finalResult, nodes]);

  const sourceInputPreviewUrl = useMemo(() => {
    const inputImageNode = (nodes as WorkflowNode[]).find((node) => {
      const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
      return nodeType === 'input_image';
    });
    const fromInputNode = normalizeImageValue(
      mergeUniqueStringList(
        normalizeStringList(inputImageNode?.data?.startImageUrls),
        inputImageNode?.data?.startImageUrl ? [String(inputImageNode.data.startImageUrl).trim()] : [],
      )[0] || ''
    );
    if (fromInputNode) {
      return fromInputNode;
    }

    const startNode = (nodes as WorkflowNode[]).find((node) => {
      const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
      return nodeType === 'start';
    });
    const fromStartNode = normalizeImageValue(
      mergeUniqueStringList(
        normalizeStringList(startNode?.data?.startImageUrls),
        startNode?.data?.startImageUrl ? [String(startNode.data.startImageUrl).trim()] : [],
      )[0] || ''
    );
    if (fromStartNode) {
      return fromStartNode;
    }
    return normalizeImageValue(workflowInputImageUrl);
  }, [nodes, workflowInputImageUrl]);

  const {
    executionId,
    executionFinalStatus,
    mergedResultPanelPreviewImageUrls,
    resultPanelPreviewAudioUrls,
    resultPanelPreviewVideoUrls,
    resultPanelPreviewLoadingExecutionId,
    handleRetryResultPreview,
  } = useResultPanelPreviewState({
    executionStatus,
    finalResult,
    setFinalResult,
    setNodes,
    addLog,
  });

  const finalOutputImageUrls = useMemo(() => {
    const dedup = new Set<string>();
    renderedResultItems.forEach((item) => {
      item.imageUrls.forEach((imageUrl) => {
        if (imageUrl && isDirectlyRenderableImageUrl(imageUrl) && !dedup.has(imageUrl)) {
          dedup.add(imageUrl);
        }
      });
    });
    mergedResultPanelPreviewImageUrls.forEach((imageUrl) => {
      if (imageUrl && isDirectlyRenderableImageUrl(imageUrl) && !dedup.has(imageUrl)) {
        dedup.add(imageUrl);
      }
    });
    return Array.from(dedup);
  }, [mergedResultPanelPreviewImageUrls, renderedResultItems]);

  const finalOutputAudioUrls = useMemo(() => {
    const dedup = new Set<string>();
    renderedResultItems.forEach((item) => {
      item.audioUrls.forEach((audioUrl) => {
        if (audioUrl && isDirectlyRenderableAudioUrl(audioUrl) && !dedup.has(audioUrl)) {
          dedup.add(audioUrl);
        }
      });
    });
    resultPanelPreviewAudioUrls.forEach((audioUrl) => {
      if (audioUrl && isDirectlyRenderableAudioUrl(audioUrl) && !dedup.has(audioUrl)) {
        dedup.add(audioUrl);
      }
    });
    return Array.from(dedup);
  }, [renderedResultItems, resultPanelPreviewAudioUrls]);

  const finalOutputVideoUrls = useMemo(() => {
    const dedup = new Set<string>();
    renderedResultItems.forEach((item) => {
      item.videoUrls.forEach((videoUrl) => {
        if (videoUrl && isDirectlyRenderableVideoUrl(videoUrl) && !dedup.has(videoUrl)) {
          dedup.add(videoUrl);
        }
      });
    });
    resultPanelPreviewVideoUrls.forEach((videoUrl) => {
      if (videoUrl && isDirectlyRenderableVideoUrl(videoUrl) && !dedup.has(videoUrl)) {
        dedup.add(videoUrl);
      }
    });
    return Array.from(dedup);
  }, [renderedResultItems, resultPanelPreviewVideoUrls]);

  const renderableSourceInputPreviewUrl = useMemo(() => {
    if (!sourceInputPreviewUrl || !isDirectlyRenderableImageUrl(sourceInputPreviewUrl)) {
      return null;
    }
    return sourceInputPreviewUrl;
  }, [sourceInputPreviewUrl]);

  const triggerWorkflowMediaDownload = useCallback((mediaKind: 'images' | 'audio' | 'video', successMessage: string) => {
    if (!executionId) {
      addLog('system', '系统', 'warn', '当前结果没有可用的执行记录，无法下载媒体');
      return;
    }
    const anchor = document.createElement('a');
    anchor.href = `/api/workflows/history/${encodeURIComponent(executionId)}/${mediaKind}/download`;
    anchor.rel = 'noreferrer';
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    addLog('system', '系统', 'info', successMessage);
  }, [addLog, executionId]);

  const handleBatchDownloadImages = useCallback(() => {
    if (finalOutputImageUrls.length === 0) {
      addLog('system', '系统', 'warn', '当前结果没有可下载图片');
      return;
    }
    triggerWorkflowMediaDownload('images', `已开始下载 ${finalOutputImageUrls.length} 张结果图片`);
  }, [addLog, finalOutputImageUrls.length, triggerWorkflowMediaDownload]);

  const handleBatchDownloadAudio = useCallback(() => {
    if (finalOutputAudioUrls.length === 0) {
      addLog('system', '系统', 'warn', '当前结果没有可下载音频');
      return;
    }
    triggerWorkflowMediaDownload('audio', `已开始下载 ${finalOutputAudioUrls.length} 条结果音频`);
  }, [addLog, finalOutputAudioUrls.length, triggerWorkflowMediaDownload]);

  const handleBatchDownloadVideo = useCallback(() => {
    if (finalOutputVideoUrls.length === 0) {
      addLog('system', '系统', 'warn', '当前结果没有可下载视频');
      return;
    }
    triggerWorkflowMediaDownload('video', `已开始下载 ${finalOutputVideoUrls.length} 条结果视频`);
  }, [addLog, finalOutputVideoUrls.length, triggerWorkflowMediaDownload]);

  const handleLoadTemplate = useCallback((template: WorkflowTemplate) => {
    void loadTemplateIntoEditor({
      template: template as unknown as Record<string, unknown>,
      setWorkflowPrompt,
      setWorkflowInputImageUrl,
      setWorkflowInputFileUrl,
      setNodes,
      setEdges,
      setActiveTemplateMeta,
      setActiveTemplateFingerprint,
      setFinalResult,
      setFinalError,
      setFinalCompletedAt,
      setFinalRuntime,
      setFinalRuntimeHints,
      setShowTemplateSelector,
      setPendingFitToken: (token: string) => {
        pendingFitTokenRef.current = token;
      },
      addLog,
      hydrateAgentBindingsFromRegistry,
    });
  }, [
    addLog,
    hydrateAgentBindingsFromRegistry,
    setActiveTemplateFingerprint,
    setActiveTemplateMeta,
    setEdges,
    setFinalCompletedAt,
    setFinalError,
    setFinalResult,
    setFinalRuntime,
    setFinalRuntimeHints,
    setNodes,
    setShowTemplateSelector,
    setWorkflowInputFileUrl,
    setWorkflowInputImageUrl,
    setWorkflowPrompt,
  ]);

  const handleTemplateSaved = useCallback((template: WorkflowTemplate, meta?: { mode: 'create' | 'update' }) => {
    const normalizedTemplateId = String(template?.id || '').trim();
    if (normalizedTemplateId) {
      setActiveTemplateMeta({
        templateId: normalizedTemplateId,
        id: normalizedTemplateId,
        templateName: String(template?.name || '').trim(),
        name: String(template?.name || '').trim(),
        description: String(template?.description || '').trim(),
        category: String(template?.category || '').trim(),
        tags: Array.isArray(template?.tags) ? template.tags.filter((item: unknown) => typeof item === 'string') : [],
        isEditable: template?.isEditable !== false,
        isLocked: false,
      });
      setActiveTemplateFingerprint(buildWorkflowStructureFingerprint(
        nodes as Node<WorkflowNodeData>[],
        edges as Edge[],
      ));
    }
    setShowTemplateSave(false);
    addLog(
      'system',
      '系统',
      'info',
      `${meta?.mode === 'update' ? '已更新模板' : '已保存模板'}: ${template.name}`,
    );
    onSave?.({ nodes: nodes as WorkflowNode[], edges: edges as WorkflowEdge[] });
  }, [addLog, onSave, nodes, edges]);

  const canClearCanvas = useMemo(() => (
    !isExecuting && (
      nodes.length > 0
      || edges.length > 0
      || Boolean(String(workflowPrompt || '').trim())
      || Boolean(String(workflowInputImageUrl || '').trim())
      || Boolean(String(workflowInputFileUrl || '').trim())
      || Boolean(activeTemplateMeta?.templateId)
      || finalResult !== null
      || Boolean(finalError)
      || showResultPanel
    )
  ), [
    activeTemplateMeta?.templateId,
    edges.length,
    finalError,
    finalResult,
    isExecuting,
    nodes.length,
    showResultPanel,
    workflowInputFileUrl,
    workflowInputImageUrl,
    workflowPrompt,
  ]);

  const handleClearCanvas = useCallback(() => {
    if (!canClearCanvas) {
      return;
    }
    if (nodes.length > 0 || edges.length > 0) {
      takeSnapshot(nodes as Node<WorkflowNodeData>[], edges as Edge[]);
    }
    setNodes([]);
    setEdges([]);
    setWorkflowPrompt('');
    setWorkflowInputImageUrl('');
    setWorkflowInputFileUrl('');
    setActiveTemplateMeta(null);
    setActiveTemplateFingerprint(null);
    setFinalResult(null);
    setFinalError(null);
    setFinalCompletedAt(null);
    setFinalRuntime('');
    setFinalRuntimeHints([]);
    setPendingNodeFieldFocusRequest(null);
    setExecuteErrorBanner(null);
    setShowResultPanel(false);
    addLog('system', '系统', 'info', '已清除画布');
  }, [
    addLog,
    canClearCanvas,
    edges,
    nodes,
    takeSnapshot,
  ]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    const type = event.dataTransfer.getData('application/reactflow') as NodeType;
    if (!type || !reactFlowInstance) return;
    const rawNodePayload = event.dataTransfer.getData('application/reactflow-node-payload');
    let parsedNodePayload: Record<string, unknown> | null = null;
    if (rawNodePayload) {
      try {
        parsedNodePayload = JSON.parse(rawNodePayload);
      } catch {
        parsedNodePayload = null;
      }
    }

    const droppedAgent = (
      type === 'agent'
      && parsedNodePayload?.kind === 'agentPreset'
      && parsedNodePayload?.agent
    ) ? (parsedNodePayload.agent as AgentDef) : undefined;

    const droppedAgentName = String(droppedAgent?.name || '').trim();
    const droppedAgentProvider = String(droppedAgent?.providerId || '').trim();
    const droppedAgentModel = String(droppedAgent?.modelId || '').trim();
    const agentPresetUpdates: Partial<WorkflowNodeData> = droppedAgent ? {
      agentId: String(droppedAgent.id || '').trim(),
      agentName: droppedAgentName,
      agentProviderId: droppedAgentProvider,
      agentModelId: droppedAgentModel,
      ...buildAgentNodeDefaultsFromAgent(droppedAgent),
    } : {};

    const position = reactFlowInstance.screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const config = nodeTypeConfigs[type];
    if (!config) return;
    const newNode: Node<WorkflowNodeData> = {
      id: `node-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      type: config.type,
      position,
      data: {
        label: droppedAgentName || config.label,
        description: String(droppedAgent?.description || '').trim() || config.description,
        icon: config.icon,
        iconColor: config.iconColor,
        type: config.type,
        ...getDefaultNodeConfig(type),
        ...agentPresetUpdates,
      },
    };
    takeSnapshot(nodes, edges);
    setNodes((nds) => applySingleNodeSelection(
      nds.concat(newNode) as Node<WorkflowNodeData>[],
      newNode.id,
    ));
    setEdges((eds) => applySingleEdgeSelection(eds, null));
    const defaultFocusField = NODE_DEFAULT_FOCUS_FIELD_BY_TYPE[type];
    if (defaultFocusField) {
      setPendingNodeFieldFocusRequest({
        nodeId: String(newNode.id),
        fieldKey: defaultFocusField,
        token: `${newNode.id}-${defaultFocusField}-${Date.now()}`,
      });
    }
  }, [reactFlowInstance, setEdges, setNodes, takeSnapshot, nodes, edges]);

  return (
    <div
      ref={editorRootRef}
      {...{ [WORKFLOW_EDITOR_SCOPE_ATTRIBUTE]: editorScopeId }}
      className="flex flex-col h-full bg-slate-950 overflow-hidden"
    >
      <WorkflowEditorTopBar
        nodesCount={nodes.length}
        edgesCount={edges.length}
        selectedNodeLabel={selectedNode ? selectedNode.data.label : null}
        activeTemplateName={activeTemplateMeta?.templateName || activeTemplateMeta?.name || null}
        templateSaveLabel={activeTemplateMeta?.templateId && activeTemplateMeta?.isEditable !== false ? '覆盖' : '保存'}
        templateSaveTitle={
          activeTemplateMeta?.templateId && activeTemplateMeta?.isEditable !== false
            ? `覆盖模板：${activeTemplateMeta.templateName || activeTemplateMeta.name || '未命名模板'}`
            : '保存为新模板'
        }
        onOpenTemplateSelector={() => setShowTemplateSelector(true)}
        onOpenTemplateSave={() => setShowTemplateSave(true)}
        canSaveTemplate={nodes.length > 0}
        onClearCanvas={handleClearCanvas}
        canClearCanvas={canClearCanvas}
        onUndo={handleUndo}
        canUndo={canUndo}
        onRedo={handleRedo}
        canRedo={canRedo}
        onDeleteSelectedNode={handleRemoveSelectedNode}
        canDeleteSelectedNode={Boolean(selectedNode)}
        onAutoLayout={handleAutoLayout}
        canAutoLayout={nodes.length > 0}
        onToggleResultPanel={() => setShowResultPanel((prev) => !prev)}
        canToggleResultPanel={finalResult !== null || Boolean(finalError) || isTerminalExecutionStatus(executionFinalStatus)}
        showResultPanel={showResultPanel}
        onExportImage={() => {
          void handleDownloadWorkflowImage();
        }}
        canExportImage={Boolean(reactFlowInstance) && nodes.length > 0}
        isExportingImage={isExportingWorkflowImage}
        onToggleFullscreen={() => {
          void handleToggleMainWorkspaceFullscreen();
        }}
        isFullscreen={isMainWorkspaceFullscreen}
        onExit={onExit}
        executeErrorBanner={executeErrorBanner}
        onDismissExecuteErrorBanner={() => setExecuteErrorBanner(null)}
      />

      <WorkflowEditorCanvasPane
        reactFlowWrapperRef={reactFlowWrapper}
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        onInit={setReactFlowInstance}
        onDrop={onDrop}
        onDragOver={onDragOver}
        isValidConnection={isValidConnection}
        selectedNode={selectedNode}
        onCloseSelectedNode={handleCloseSelectedNode}
        onUpdateNode={handleUpdateNode}
        onDeleteNode={handleRemoveNodeById}
        focusRequest={pendingNodeFieldFocusRequest}
        onConsumeFocusRequest={(token) => {
          setPendingNodeFieldFocusRequest((prev) => (prev?.token === token ? null : prev));
        }}
      />

      {/* Execution Log Panel */}
      {showLogs && (
        <ExecutionLogPanel logs={logs} isOpen={showLogs} onClose={() => setShowLogs(false)} />
      )}

      <WorkflowResultPanel
        show={showResultPanel}
        executionId={executionId}
        finalCompletedAt={finalCompletedAt}
        finalRuntime={finalRuntime}
        finalRuntimeHints={finalRuntimeHints}
        finalError={finalError}
        finalResult={finalResult}
        renderedResultItems={renderedResultItems}
        finalOutputImageUrls={finalOutputImageUrls}
        finalOutputAudioUrls={finalOutputAudioUrls}
        finalOutputVideoUrls={finalOutputVideoUrls}
        renderableSourceInputPreviewUrl={renderableSourceInputPreviewUrl}
        resultPanelPreviewLoadingExecutionId={resultPanelPreviewLoadingExecutionId}
        onBatchDownloadImages={handleBatchDownloadImages}
        onBatchDownloadAudio={handleBatchDownloadAudio}
        onBatchDownloadVideo={handleBatchDownloadVideo}
        onCopyResult={handleCopyFinalResult}
        onClose={() => setShowResultPanel(false)}
        onRetryResultPreview={handleRetryResultPreview}
      />

      {/* Template Dialogs */}
      <WorkflowTemplateSelector isOpen={showTemplateSelector} onClose={() => setShowTemplateSelector(false)} onLoadTemplate={handleLoadTemplate} />
      <WorkflowTemplateSaveDialog
        isOpen={showTemplateSave}
        onClose={() => setShowTemplateSave(false)}
        nodes={nodes}
        edges={edges}
        activeTemplate={activeTemplateMeta ? {
          id: activeTemplateMeta.templateId,
          name: activeTemplateMeta.templateName || activeTemplateMeta.name || '',
          description: activeTemplateMeta.description,
          category: activeTemplateMeta.category,
          tags: activeTemplateMeta.tags,
          isEditable: activeTemplateMeta.isEditable,
          isLocked: activeTemplateMeta.isLocked,
        } : null}
        onSaveSuccess={handleTemplateSaved}
      />
    </div>
  );
};

export const MultiAgentWorkflowEditorReactFlow: React.FC<MultiAgentWorkflowEditorReactFlowProps> = (props) => {
  return (
    <ReactFlowProvider>
      <MultiAgentWorkflowEditorReactFlowInner {...props} />
    </ReactFlowProvider>
  );
};

export default MultiAgentWorkflowEditorReactFlow;

/**
 * useWorkflowCanvasActions
 *
 * Consolidated hook that owns the canvas-level mutation handlers previously
 * defined inline in MultiAgentWorkflowEditorReactFlow.tsx:
 *
 * - hydrateAgentBindingsFromRegistry (L193-210)
 * - handleUndo / handleRedo (L212-226)
 * - handleToggleMainWorkspaceFullscreen + fullscreenchange effect (L228-268)
 * - isValidConnection / onConnect (L270-301)
 * - onNodeClick / onEdgeClick / onPaneClick / handleCloseSelectedNode (L303-326)
 * - handleRemoveSelectedEdge / handleRemoveEdgeById /
 *   handleDisconnectByHandle / handleRemoveNodeById / handleRemoveSelectedNode
 *   (L328-395)
 * - handleAutoLayout (L397-409)
 * - handleUpdateNode (L622-674)
 * - canClearCanvas / handleClearCanvas (L1806-1855)
 * - onDragOver / onDrop (L1857-1930)
 *
 * Behaviour is preserved 1:1 — every takeSnapshot, addLog, setNodes/setEdges
 * call and dependency mirrors the original component logic.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Connection, Edge, Node, ReactFlowInstance } from 'reactflow';
import { addEdge } from 'reactflow';

import type { AgentDef, WorkflowNodeData } from '../types';
import type { ActiveTemplateMeta } from '../workflowTemplateLoader';
import { nodeTypeConfigs, NodeType } from '../nodeTypeConfigs';
import { autoLayoutWorkflow } from '../workflowUtils';
import { buildAgentNodeDefaultsFromAgent } from '../agentNodeDefaults';
import {
  applyAgentBindingsToNodes,
  applySingleEdgeSelection,
  applySingleNodeSelection,
  DisconnectHandleEventDetail,
  getDefaultNodeConfig,
  NODE_DEFAULT_FOCUS_FIELD_BY_TYPE,
  WorkflowNodeFieldFocusRequest,
} from '../workflowEditorUtils';
import { filterEdgesByNodePortLayouts, resolveNodePortLayout } from '../workflowPorts';
import { DEFAULT_WORKFLOW_EDGE_TYPE } from '../workflowEdgeTypes';

import type { LogLevel } from '../ExecutionLogPanel';

type AddLog = (
  nodeId: string,
  nodeName: string,
  level: LogLevel,
  message: string,
  timestamp?: number
) => void;

type SetNodes = (
  updater: Node<WorkflowNodeData>[] | ((prev: Node<WorkflowNodeData>[]) => Node<WorkflowNodeData>[])
) => void;
type SetEdges = (updater: Edge[] | ((prev: Edge[]) => Edge[])) => void;

export interface UseWorkflowCanvasActionsArgs {
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  setNodes: SetNodes;
  setEdges: SetEdges;
  selectedNode: Node<WorkflowNodeData> | null;
  selectedEdgeId: string | null;
  registryAgents: AgentDef[];
  refreshAgents: () => Promise<AgentDef[]>;
  reactFlowInstance: ReactFlowInstance | null;
  editorRootRef: React.RefObject<HTMLDivElement | null>;
  takeSnapshot: (nodes: Node<WorkflowNodeData>[], edges: Edge[]) => void;
  undo: () => { nodes: Node<WorkflowNodeData>[]; edges: Edge[] } | null;
  redo: () => { nodes: Node<WorkflowNodeData>[]; edges: Edge[] } | null;
  addLog: AddLog;
  setPendingNodeFieldFocusRequest: React.Dispatch<
    React.SetStateAction<WorkflowNodeFieldFocusRequest | null>
  >;
  isExecuting: boolean;
  workflowPrompt: string;
  workflowInputImageUrl: string;
  workflowInputFileUrl: string;
  activeTemplateMeta: ActiveTemplateMeta | null;
  finalResult: any;
  finalError: string | null;
  showResultPanel: boolean;
  setWorkflowPrompt: React.Dispatch<React.SetStateAction<string>>;
  setWorkflowInputImageUrl: React.Dispatch<React.SetStateAction<string>>;
  setWorkflowInputFileUrl: React.Dispatch<React.SetStateAction<string>>;
  setActiveTemplateMeta: React.Dispatch<React.SetStateAction<ActiveTemplateMeta | null>>;
  setActiveTemplateFingerprint: React.Dispatch<React.SetStateAction<string | null>>;
  setFinalResult: React.Dispatch<React.SetStateAction<any>>;
  setFinalError: React.Dispatch<React.SetStateAction<string | null>>;
  setFinalCompletedAt: React.Dispatch<React.SetStateAction<number | null>>;
  setFinalRuntime: React.Dispatch<React.SetStateAction<string>>;
  setFinalRuntimeHints: React.Dispatch<React.SetStateAction<string[]>>;
  setExecuteErrorBanner: React.Dispatch<React.SetStateAction<string | null>>;
  setShowResultPanel: React.Dispatch<React.SetStateAction<boolean>>;
}

export interface UseWorkflowCanvasActionsResult {
  hydrateAgentBindingsFromRegistry: (
    inputNodes: Node<WorkflowNodeData>[]
  ) => Promise<Node<WorkflowNodeData>[]>;
  handleUndo: () => void;
  handleRedo: () => void;
  handleToggleMainWorkspaceFullscreen: () => Promise<void>;
  isMainWorkspaceFullscreen: boolean;
  isValidConnection: (connection: Connection) => boolean;
  onConnect: (params: Connection) => void;
  onNodeClick: (event: React.MouseEvent, node: Node) => void;
  onEdgeClick: (event: React.MouseEvent, edge: Edge) => void;
  onPaneClick: () => void;
  handleCloseSelectedNode: () => void;
  handleRemoveSelectedEdge: () => void;
  handleRemoveEdgeById: (edgeId: string) => void;
  handleDisconnectByHandle: (detail: DisconnectHandleEventDetail) => void;
  handleRemoveNodeById: (nodeId: string) => void;
  handleRemoveSelectedNode: () => void;
  handleAutoLayout: () => void;
  handleUpdateNode: (nodeId: string, updates: Partial<WorkflowNodeData>) => void;
  canClearCanvas: boolean;
  handleClearCanvas: () => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (event: React.DragEvent) => void;
}

export const useWorkflowCanvasActions = ({
  nodes,
  edges,
  setNodes,
  setEdges,
  selectedNode,
  selectedEdgeId,
  registryAgents,
  refreshAgents,
  reactFlowInstance,
  editorRootRef,
  takeSnapshot,
  undo,
  redo,
  addLog,
  setPendingNodeFieldFocusRequest,
  isExecuting,
  workflowPrompt,
  workflowInputImageUrl,
  workflowInputFileUrl,
  activeTemplateMeta,
  finalResult,
  finalError,
  showResultPanel,
  setWorkflowPrompt,
  setWorkflowInputImageUrl,
  setWorkflowInputFileUrl,
  setActiveTemplateMeta,
  setActiveTemplateFingerprint,
  setFinalResult,
  setFinalError,
  setFinalCompletedAt,
  setFinalRuntime,
  setFinalRuntimeHints,
  setExecuteErrorBanner,
  setShowResultPanel,
}: UseWorkflowCanvasActionsArgs): UseWorkflowCanvasActionsResult => {
  const [isMainWorkspaceFullscreen, setIsMainWorkspaceFullscreen] = useState(false);

  // Ref-shadow pattern: keep refs in sync with state so callbacks can read
  // latest nodes/edges without listing them in dep arrays. This prevents
  // callback churn on every node edit, which would otherwise force React
  // Flow to reinstall its internal event handlers each render.
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  useEffect(() => {
    nodesRef.current = nodes;
    edgesRef.current = edges;
  }, [nodes, edges]);

  const hydrateAgentBindingsFromRegistry = useCallback(
    async (inputNodes: Node<WorkflowNodeData>[]): Promise<Node<WorkflowNodeData>[]> => {
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
    },
    [registryAgents, refreshAgents]
  );

  const handleUndo = useCallback(() => {
    const state = undo();
    if (state) {
      setNodes(state.nodes);
      setEdges(state.edges);
    }
  }, [undo, setNodes, setEdges]);

  const handleRedo = useCallback(() => {
    const state = redo();
    if (state) {
      setNodes(state.nodes);
      setEdges(state.edges);
    }
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
  }, [editorRootRef]);

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
  }, [editorRootRef]);

  const isValidConnection = useCallback((connection: Connection) => {
    const { source, target } = connection;
    if (!source || !target || source === target) return false;
    const currentNodes = nodesRef.current;
    const currentEdges = edgesRef.current;
    const sourceNode = currentNodes.find((n) => n.id === source);
    const targetNode = currentNodes.find((n) => n.id === target);
    if (!sourceNode || !targetNode) return false;
    if (targetNode.data.type === 'start') return false;
    if (sourceNode.data.type === 'end') return false;
    if (currentEdges.find((e) => e.source === source && e.target === target)) return false;
    return true;
  }, []);

  const onConnect = useCallback(
    (params: Connection) => {
      takeSnapshot(nodesRef.current, edgesRef.current);
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            type: DEFAULT_WORKFLOW_EDGE_TYPE,
            animated: true,
            style: { stroke: '#14b8a6', strokeWidth: 2 },
          },
          eds
        )
      );
    },
    [setEdges, takeSnapshot]
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setNodes((nds) => applySingleNodeSelection(nds as Node<WorkflowNodeData>[], node.id));
      setEdges((eds) => applySingleEdgeSelection(eds, null));
    },
    [setEdges, setNodes]
  );

  const onEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      setEdges((eds) => applySingleEdgeSelection(eds, edge.id));
      setNodes((nds) => applySingleNodeSelection(nds as Node<WorkflowNodeData>[], null));
    },
    [setEdges, setNodes]
  );

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
    takeSnapshot(nodesRef.current, edgesRef.current);
    setEdges((eds) => eds.filter((edge) => edge.id !== selectedEdgeId));
    addLog('system', '系统', 'info', '已断开 1 条连接');
  }, [selectedEdgeId, takeSnapshot, setEdges, addLog]);

  const handleRemoveEdgeById = useCallback(
    (edgeId: string) => {
      const normalizedId = String(edgeId || '').trim();
      const currentEdges = edgesRef.current;
      if (!normalizedId || !currentEdges.some((edge) => edge.id === normalizedId)) {
        return;
      }
      takeSnapshot(nodesRef.current, currentEdges);
      setEdges((eds) => eds.filter((edge) => edge.id !== normalizedId));
      addLog('system', '系统', 'info', '已移除连接线');
    },
    [takeSnapshot, setEdges, addLog]
  );

  const handleDisconnectByHandle = useCallback(
    (detail: DisconnectHandleEventDetail) => {
      const normalizeHandleId = (value?: string | null) => value ?? '__default__';

      const currentEdges = edgesRef.current;
      const matchedEdges = currentEdges.filter((edge) => {
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
      takeSnapshot(nodesRef.current, currentEdges);
      setEdges((eds) => eds.filter((edge) => !matchedIds.has(edge.id)));
      addLog('system', '系统', 'info', `端口已断开 ${matchedEdges.length} 条连接`);
    },
    [addLog, takeSnapshot, setEdges]
  );

  const handleRemoveNodeById = useCallback(
    (nodeId: string) => {
      const currentNodes = nodesRef.current;
      const node = currentNodes.find((item) => item.id === nodeId);
      if (!node) {
        return;
      }
      takeSnapshot(currentNodes, edgesRef.current);
      setNodes((nds) => nds.filter((item) => item.id !== nodeId));
      setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
      addLog('system', '系统', 'info', `已移除节点：${node.data.label}`);
    },
    [takeSnapshot, setNodes, setEdges, addLog]
  );

  const handleRemoveSelectedNode = useCallback(() => {
    if (!selectedNode) {
      return;
    }
    handleRemoveNodeById(selectedNode.id);
  }, [selectedNode, handleRemoveNodeById]);

  const handleAutoLayout = useCallback(() => {
    const currentNodes = nodesRef.current;
    const currentEdges = edgesRef.current;
    if (currentNodes.length === 0) {
      return;
    }
    takeSnapshot(currentNodes, currentEdges);
    setNodes(
      autoLayoutWorkflow(
        currentNodes as Node<WorkflowNodeData>[],
        currentEdges
      ) as Node<WorkflowNodeData>[]
    );
    requestAnimationFrame(() => {
      reactFlowInstance?.fitView({ padding: 0.25, duration: 450 });
    });
    addLog('system', '系统', 'info', '已完成自动排版');
  }, [takeSnapshot, setNodes, reactFlowInstance, addLog]);

  const handleUpdateNode = useCallback(
    (nodeId: string, updates: Partial<WorkflowNodeData>) => {
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
          nextData.portLayout = resolveNodePortLayout(
            nodeType,
            updates.portLayout ?? node.data?.portLayout
          );
        }
        return {
          ...node,
          data: nextData,
        };
      };

      if (includesPortLayoutUpdate) {
        takeSnapshot(nodesRef.current, edgesRef.current);
      }

      setNodes((nds) => nds.map((node) => mergeNodeData(node as Node<WorkflowNodeData>)));

      if (includesPortLayoutUpdate) {
        setEdges((eds) => {
          // Read latest nodes from setNodes updater to avoid stale closure
          let currentNodes: Node<WorkflowNodeData>[] = [];
          setNodes((nds) => {
            currentNodes = nds.map((n) => mergeNodeData(n as Node<WorkflowNodeData>));
            return nds;
          });
          const updatedNodes =
            currentNodes.length > 0
              ? currentNodes
              : nodesRef.current.map((node) => mergeNodeData(node as Node<WorkflowNodeData>));
          const filteredEdges = filterEdgesByNodePortLayouts(updatedNodes, eds);
          const removedCount = eds.length - filteredEdges.length;
          if (removedCount > 0) {
            addLog('system', '系统', 'warn', `端口配置变更后，已移除 ${removedCount} 条不匹配连接`);
          }
          return filteredEdges;
        });
      }
    },
    [addLog, setEdges, setNodes, takeSnapshot]
  );

  const canClearCanvas = useMemo(
    () =>
      !isExecuting &&
      (nodes.length > 0 ||
        edges.length > 0 ||
        Boolean(String(workflowPrompt || '').trim()) ||
        Boolean(String(workflowInputImageUrl || '').trim()) ||
        Boolean(String(workflowInputFileUrl || '').trim()) ||
        Boolean(activeTemplateMeta?.templateId) ||
        finalResult !== null ||
        Boolean(finalError) ||
        showResultPanel),
    [
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
    ]
  );

  const handleClearCanvas = useCallback(() => {
    if (!canClearCanvas) {
      return;
    }
    const currentNodes = nodesRef.current;
    const currentEdges = edgesRef.current;
    if (currentNodes.length > 0 || currentEdges.length > 0) {
      takeSnapshot(currentNodes as Node<WorkflowNodeData>[], currentEdges as Edge[]);
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
    takeSnapshot,
    setNodes,
    setEdges,
    setWorkflowPrompt,
    setWorkflowInputImageUrl,
    setWorkflowInputFileUrl,
    setActiveTemplateMeta,
    setActiveTemplateFingerprint,
    setFinalResult,
    setFinalError,
    setFinalCompletedAt,
    setFinalRuntime,
    setFinalRuntimeHints,
    setPendingNodeFieldFocusRequest,
    setExecuteErrorBanner,
    setShowResultPanel,
  ]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
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

      const droppedAgent =
        type === 'agent' && parsedNodePayload?.kind === 'agentPreset' && parsedNodePayload?.agent
          ? (parsedNodePayload.agent as AgentDef)
          : undefined;

      const droppedAgentName = String(droppedAgent?.name || '').trim();
      const droppedAgentProvider = String(droppedAgent?.providerId || '').trim();
      const droppedAgentModel = String(droppedAgent?.modelId || '').trim();
      const agentPresetUpdates: Partial<WorkflowNodeData> = droppedAgent
        ? {
            agentId: String(droppedAgent.id || '').trim(),
            agentName: droppedAgentName,
            agentProviderId: droppedAgentProvider,
            agentModelId: droppedAgentModel,
            ...buildAgentNodeDefaultsFromAgent(droppedAgent),
          }
        : {};

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
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
      takeSnapshot(nodesRef.current, edgesRef.current);
      setNodes((nds) =>
        applySingleNodeSelection(nds.concat(newNode) as Node<WorkflowNodeData>[], newNode.id)
      );
      setEdges((eds) => applySingleEdgeSelection(eds, null));
      const defaultFocusField = NODE_DEFAULT_FOCUS_FIELD_BY_TYPE[type];
      if (defaultFocusField) {
        setPendingNodeFieldFocusRequest({
          nodeId: String(newNode.id),
          fieldKey: defaultFocusField,
          token: `${newNode.id}-${defaultFocusField}-${Date.now()}`,
        });
      }
    },
    [reactFlowInstance, setEdges, setNodes, takeSnapshot, setPendingNodeFieldFocusRequest]
  );

  return {
    hydrateAgentBindingsFromRegistry,
    handleUndo,
    handleRedo,
    handleToggleMainWorkspaceFullscreen,
    isMainWorkspaceFullscreen,
    isValidConnection,
    onConnect,
    onNodeClick,
    onEdgeClick,
    onPaneClick,
    handleCloseSelectedNode,
    handleRemoveSelectedEdge,
    handleRemoveEdgeById,
    handleDisconnectByHandle,
    handleRemoveNodeById,
    handleRemoveSelectedNode,
    handleAutoLayout,
    handleUpdateNode,
    canClearCanvas,
    handleClearCanvas,
    onDragOver,
    onDrop,
  };
};

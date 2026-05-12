/**
 * Multi-Agent Workflow Editor - React Flow Implementation (Redesigned)
 *
 * Dark-themed visual workflow editor with:
 * - Start/End entry buttons in flow-control nodes
 * - Drag-and-drop node composition
 * - Properties panel with per-node instructions
 * - Execution log panel
 * - Template management
 *
 * Decomposition reference (1:1 lossless extraction — see editor/):
 * - useWorkflowImageExport.ts      → handleDownloadWorkflowImage
 * - useWorkflowExecuteHandler.ts   → handleExecute + final-result state
 * - useWorkflowResultMedia.ts      → renderedResultItems + media downloads
 * - useWorkflowCanvasActions.ts    → selection / mutation / drag-and-drop
 * - useWorkflowEditorEvents.ts     → window event listeners
 * - useWorkflowEditorLoading.ts    → executionStatus + loadedWorkflow sync
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  ReactFlowInstance,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { ExecutionLogPanel } from './ExecutionLogPanel';
import { WorkflowResultPanel } from './WorkflowResultPanel';
import { WorkflowTemplateSelector, type WorkflowTemplate } from './WorkflowTemplateSelector';
import { WorkflowTemplateSaveDialog } from './WorkflowTemplateSaveDialog';
import { WorkflowEditorTopBar } from './WorkflowEditorTopBar';
import { WorkflowEditorCanvasPane } from './WorkflowEditorCanvasPane';
import { useExecutionLogs } from './WorkflowExecutionHooks';
import { useUndoRedo } from './useUndoRedo';
import type { ExecutionStatus, WorkflowNode, WorkflowEdge, WorkflowNodeData } from './types';
import { useAgentRegistry } from './useAgentRegistry';
import { loadTemplateIntoEditor, ActiveTemplateMeta } from './workflowTemplateLoader';
import { useResultPanelPreviewState } from './useResultPanelPreviewState';
import {
  buildWorkflowStructureFingerprint,
  createWorkflowEditorScopeId,
  isTerminalExecutionStatus,
  WORKFLOW_EDITOR_SCOPE_ATTRIBUTE,
  WorkflowNodeFieldFocusRequest,
} from './workflowEditorUtils';

import { useWorkflowImageExport } from './editor/useWorkflowImageExport';
import { useWorkflowExecuteHandler } from './editor/useWorkflowExecuteHandler';
import { useWorkflowResultMedia } from './editor/useWorkflowResultMedia';
import { useWorkflowCanvasActions } from './editor/useWorkflowCanvasActions';
import { useWorkflowEditorEvents } from './editor/useWorkflowEditorEvents';
import { useWorkflowEditorLoading } from './editor/useWorkflowEditorLoading';

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

  // Ref-shadow of nodes/edges so callbacks can read latest values without
  // listing nodes/edges in their useCallback deps (prevents callback churn
  // that would otherwise cause React Flow to reinstall event handlers on
  // every node edit).
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  useEffect(() => {
    nodesRef.current = nodes;
    edgesRef.current = edges;
  }, [nodes, edges]);

  // UI state
  const [showLogs, setShowLogs] = useState(false);
  const [showResultPanel, setShowResultPanel] = useState(() => {
    const initialFinalStatus = String(executionStatus?.finalStatus || '')
      .trim()
      .toLowerCase();
    return isTerminalExecutionStatus(initialFinalStatus);
  });
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [showTemplateSave, setShowTemplateSave] = useState(false);
  const [workflowPrompt, setWorkflowPrompt] = useState('');
  const [workflowInputImageUrl, setWorkflowInputImageUrl] = useState('');
  const [workflowInputFileUrl, setWorkflowInputFileUrl] = useState('');
  const [activeTemplateMeta, setActiveTemplateMeta] = useState<ActiveTemplateMeta | null>(null);
  const [activeTemplateFingerprint, setActiveTemplateFingerprint] = useState<string | null>(null);
  const [pendingNodeFieldFocusRequest, setPendingNodeFieldFocusRequest] =
    useState<WorkflowNodeFieldFocusRequest | null>(null);

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

  // Execution handler + final-result state slice
  const {
    handleExecute,
    isExecuting,
    executeErrorBanner,
    setExecuteErrorBanner,
    finalResult,
    setFinalResult,
    finalError,
    setFinalError,
    finalCompletedAt,
    setFinalCompletedAt,
    finalRuntime,
    setFinalRuntime,
    finalRuntimeHints,
    setFinalRuntimeHints,
  } = useWorkflowExecuteHandler({
    onExecute,
    nodes: nodes as Node<WorkflowNodeData>[],
    edges: edges as Edge[],
    workflowPrompt,
    workflowInputImageUrl,
    workflowInputFileUrl,
    activeTemplateMeta,
    activeTemplateFingerprint,
    addLog,
    setShowLogs,
  });

  // Image export
  const { handleDownloadWorkflowImage, isExportingWorkflowImage } = useWorkflowImageExport({
    reactFlowInstance,
    reactFlowWrapperRef: reactFlowWrapper,
    addLog,
    setExecuteErrorBanner,
  });

  // Canvas-level actions (selection / mutation / drag-and-drop)
  const {
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
  } = useWorkflowCanvasActions({
    nodes: nodes as Node<WorkflowNodeData>[],
    edges: edges as Edge[],
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
  });

  // executionStatus + loadedWorkflow synchronization effects
  useWorkflowEditorLoading({
    executionStatus,
    loadedWorkflow,
    nodes: nodes as Node<WorkflowNodeData>[],
    setNodes,
    setEdges,
    reactFlowInstance,
    pendingFitTokenRef,
    importedExecutionLogCountRef,
    lastResultSignatureRef,
    hydrateAgentBindingsFromRegistry,
    setWorkflowPrompt,
    setWorkflowInputImageUrl,
    setWorkflowInputFileUrl,
    setActiveTemplateMeta,
    setActiveTemplateFingerprint,
    setExecuteErrorBanner,
    setFinalResult,
    setFinalError,
    setFinalCompletedAt,
    setFinalRuntime,
    setFinalRuntimeHints,
    setShowResultPanel,
    addLog,
  });

  // Window event listeners + keyboard delete
  useWorkflowEditorEvents({
    editorScopeId,
    nodes: nodes as Node<WorkflowNodeData>[],
    setNodes,
    setEdges,
    selectedNode,
    selectedEdgeId,
    handleDisconnectByHandle,
    handleRemoveEdgeById,
    handleRemoveSelectedEdge,
    handleRemoveSelectedNode,
    setPendingNodeFieldFocusRequest,
    handleExecute,
    executionStatus,
    finalResult,
    finalError,
    setShowResultPanel,
    addLog,
  });

  // Result-panel preview state (existing dedicated hook)
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

  // Derived result media + batch download handlers + copy
  const {
    renderedResultItems,
    renderableSourceInputPreviewUrl,
    finalOutputImageUrls,
    finalOutputAudioUrls,
    finalOutputVideoUrls,
    handleBatchDownloadImages,
    handleBatchDownloadAudio,
    handleBatchDownloadVideo,
    handleCopyFinalResult,
  } = useWorkflowResultMedia({
    finalResult,
    finalError,
    nodes: nodes as Node<WorkflowNodeData>[],
    workflowInputImageUrl,
    mergedResultPanelPreviewImageUrls,
    resultPanelPreviewAudioUrls,
    resultPanelPreviewVideoUrls,
    executionId,
    addLog,
  });

  const handleLoadTemplate = React.useCallback(
    (template: WorkflowTemplate) => {
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
    },
    [
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
    ]
  );

  const handleTemplateSaved = React.useCallback(
    (template: WorkflowTemplate, meta?: { mode: 'create' | 'update' }) => {
      const normalizedTemplateId = String(template?.id || '').trim();
      if (normalizedTemplateId) {
        setActiveTemplateMeta({
          templateId: normalizedTemplateId,
          id: normalizedTemplateId,
          templateName: String(template?.name || '').trim(),
          name: String(template?.name || '').trim(),
          description: String(template?.description || '').trim(),
          category: String(template?.category || '').trim(),
          tags: Array.isArray(template?.tags)
            ? template.tags.filter((item: unknown) => typeof item === 'string')
            : [],
          isEditable: template?.isEditable !== false,
          isLocked: false,
        });
        setActiveTemplateFingerprint(
          buildWorkflowStructureFingerprint(
            nodesRef.current as Node<WorkflowNodeData>[],
            edgesRef.current as Edge[]
          )
        );
      }
      setShowTemplateSave(false);
      addLog(
        'system',
        '系统',
        'info',
        `${meta?.mode === 'update' ? '已更新模板' : '已保存模板'}: ${template.name}`
      );
      onSave?.({
        nodes: nodesRef.current as WorkflowNode[],
        edges: edgesRef.current as WorkflowEdge[],
      });
    },
    [addLog, onSave]
  );

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
        templateSaveLabel={
          activeTemplateMeta?.templateId && activeTemplateMeta?.isEditable !== false
            ? '覆盖'
            : '保存'
        }
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
        canToggleResultPanel={
          finalResult !== null ||
          Boolean(finalError) ||
          isTerminalExecutionStatus(executionFinalStatus)
        }
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
      <WorkflowTemplateSelector
        isOpen={showTemplateSelector}
        onClose={() => setShowTemplateSelector(false)}
        onLoadTemplate={handleLoadTemplate}
      />
      <WorkflowTemplateSaveDialog
        isOpen={showTemplateSave}
        onClose={() => setShowTemplateSave(false)}
        nodes={nodes}
        edges={edges}
        activeTemplate={
          activeTemplateMeta
            ? {
                id: activeTemplateMeta.templateId,
                name: activeTemplateMeta.templateName || activeTemplateMeta.name || '',
                description: activeTemplateMeta.description,
                category: activeTemplateMeta.category,
                tags: activeTemplateMeta.tags,
                isEditable: activeTemplateMeta.isEditable,
                isLocked: activeTemplateMeta.isLocked,
              }
            : null
        }
        onSaveSuccess={handleTemplateSaved}
      />
    </div>
  );
};

export const MultiAgentWorkflowEditorReactFlow: React.FC<MultiAgentWorkflowEditorReactFlowProps> = (
  props
) => {
  return (
    <ReactFlowProvider>
      <MultiAgentWorkflowEditorReactFlowInner {...props} />
    </ReactFlowProvider>
  );
};

export default MultiAgentWorkflowEditorReactFlow;

/**
 * useWorkflowEditorLoading
 *
 * Houses the data-synchronization effects previously defined inline in
 * MultiAgentWorkflowEditorReactFlow.tsx:
 *
 * - executionStatus → node status/result merging   (L676-766)
 * - executionStatus → log import                   (L768-791)
 * - executionStatus → final result projection      (L793-870)
 * - loadedWorkflow token → editor hydration        (L872-986)
 * - pendingFitToken → reactFlowInstance.fitView    (L988-1001)
 *
 * Behaviour is preserved 1:1 — the same merge helpers, normalization, and
 * dependency arrays as the original component.
 */

import { useEffect } from 'react';
import type { Edge, Node, ReactFlowInstance } from 'reactflow';

import type { ExecutionStatus, WorkflowEdge, WorkflowNode, WorkflowNodeData } from '../types';
import { ActiveTemplateMeta } from '../workflowTemplateLoader';
import {
  applySingleEdgeSelection,
  applySingleNodeSelection,
  isTerminalExecutionStatus,
  normalizeLoadedNode,
} from '../workflowEditorUtils';
import { hydrateNodePortLayoutsFromEdges } from '../workflowPorts';
import { DEFAULT_WORKFLOW_EDGE_TYPE } from '../workflowEdgeTypes';
import {
  extractAudioUrls,
  extractImageUrls,
  extractVideoUrls,
  mergePreviewImagesIntoResult,
  mergePreviewMediaIntoResult,
} from '../workflowResultUtils';
import { mergeUniqueStringList, normalizeStringList } from '../workflowGraphUtils';

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

const toPreviewStringList = (items: unknown): string[] =>
  Array.isArray(items) ? items.map((item) => String(item || '').trim()).filter(Boolean) : [];

const mergeWorkflowEndResult = ({
  rawResult,
  nodeType,
  existingResult,
  finalResult,
  previewImages,
  previewAudioUrls,
  previewVideoUrls,
}: {
  rawResult: unknown;
  nodeType: string;
  existingResult: unknown;
  finalResult: unknown;
  previewImages: string[];
  previewAudioUrls: string[];
  previewVideoUrls: string[];
}) => {
  const normalizedNodeType = String(nodeType || '').toLowerCase();
  if (normalizedNodeType !== 'end') {
    return rawResult;
  }
  const mergedFinalResult =
    finalResult !== undefined && finalResult !== null
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
  if (
    existingImages.length === 0 &&
    existingAudioUrls.length === 0 &&
    existingVideoUrls.length === 0
  ) {
    return mergedWithPreview;
  }
  let mergedExistingResult = mergePreviewImagesIntoResult(mergedWithPreview, existingImages);
  if (existingAudioUrls.length > 0) {
    mergedExistingResult = mergePreviewMediaIntoResult(
      mergedExistingResult,
      'audio',
      existingAudioUrls
    );
  }
  if (existingVideoUrls.length > 0) {
    mergedExistingResult = mergePreviewMediaIntoResult(
      mergedExistingResult,
      'video',
      existingVideoUrls
    );
  }
  return mergedExistingResult;
};

export interface UseWorkflowEditorLoadingArgs {
  executionStatus?: ExecutionStatus;
  loadedWorkflow?: {
    token: string;
    name?: string;
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    prompt?: string;
    input?: Record<string, any>;
    executionStatus?: ExecutionStatus;
  } | null;
  nodes: Node<WorkflowNodeData>[];
  setNodes: SetNodes;
  setEdges: SetEdges;
  reactFlowInstance: ReactFlowInstance | null;
  pendingFitTokenRef: React.MutableRefObject<string | null>;
  importedExecutionLogCountRef: React.MutableRefObject<number>;
  lastResultSignatureRef: React.MutableRefObject<string | null>;
  hydrateAgentBindingsFromRegistry: (
    inputNodes: Node<WorkflowNodeData>[]
  ) => Promise<Node<WorkflowNodeData>[]>;
  setWorkflowPrompt: React.Dispatch<React.SetStateAction<string>>;
  setWorkflowInputImageUrl: React.Dispatch<React.SetStateAction<string>>;
  setWorkflowInputFileUrl: React.Dispatch<React.SetStateAction<string>>;
  setActiveTemplateMeta: React.Dispatch<React.SetStateAction<ActiveTemplateMeta | null>>;
  setActiveTemplateFingerprint: React.Dispatch<React.SetStateAction<string | null>>;
  setExecuteErrorBanner: React.Dispatch<React.SetStateAction<string | null>>;
  setFinalResult: React.Dispatch<React.SetStateAction<any>>;
  setFinalError: React.Dispatch<React.SetStateAction<string | null>>;
  setFinalCompletedAt: React.Dispatch<React.SetStateAction<number | null>>;
  setFinalRuntime: React.Dispatch<React.SetStateAction<string>>;
  setFinalRuntimeHints: React.Dispatch<React.SetStateAction<string[]>>;
  addLog: AddLog;
}

export const useWorkflowEditorLoading = ({
  executionStatus,
  loadedWorkflow,
  nodes,
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
  addLog,
}: UseWorkflowEditorLoadingArgs): void => {
  useEffect(() => {
    if (!executionStatus) {
      return;
    }

    const previewImages = toPreviewStringList(executionStatus.resultPreviewImageUrls);
    const previewAudioUrls = toPreviewStringList(executionStatus.resultPreviewAudioUrls);
    const previewVideoUrls = toPreviewStringList(executionStatus.resultPreviewVideoUrls);
    const finalResult = executionStatus.finalResult;
    const mergeNodeResult = (rawResult: unknown, nodeType: string, existingResult: unknown) =>
      mergeWorkflowEndResult({
        rawResult,
        nodeType,
        existingResult,
        finalResult,
        previewImages,
        previewAudioUrls,
        previewVideoUrls,
      });

    setNodes((nds) =>
      nds.map((node) => {
        const status = executionStatus.nodeStatuses[node.id];
        if (!status) {
          return node;
        }
        const nodeType = String(node?.data?.type || node?.type || '')
          .trim()
          .toLowerCase();
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
      const nodeName =
        log.nodeId === 'system' ? '系统' : nodeNameMap.get(log.nodeId) || log.nodeId || '节点';
      addLog(log.nodeId || 'system', nodeName, log.level, log.message, log.timestamp);
    }
    importedExecutionLogCountRef.current = sourceLogs.length;
  }, [nodes, addLog, importedExecutionLogCountRef, executionStatus]);

  useEffect(() => {
    const status = String(executionStatus?.finalStatus || '')
      .trim()
      .toLowerCase();
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

    const statusPreviewImages = toPreviewStringList(executionStatus?.resultPreviewImageUrls);
    const statusPreviewAudioUrls = toPreviewStringList(executionStatus?.resultPreviewAudioUrls);
    const statusPreviewVideoUrls = toPreviewStringList(executionStatus?.resultPreviewVideoUrls);
    const previewSignature = [
      statusPreviewImages.join('|'),
      statusPreviewAudioUrls.join('|'),
      statusPreviewVideoUrls.join('|'),
    ].join('::');
    const signature = `${executionStatus?.executionId || ''}:${executionStatus?.completedAt || ''}:${status}:${previewSignature}`;
    if (signature === lastResultSignatureRef.current) {
      return;
    }
    lastResultSignatureRef.current = signature;

    let mergedFinalResult = mergePreviewImagesIntoResult(
      executionStatus?.finalResult ?? null,
      statusPreviewImages
    );
    if (statusPreviewAudioUrls.length > 0) {
      mergedFinalResult = mergePreviewMediaIntoResult(
        mergedFinalResult,
        'audio',
        statusPreviewAudioUrls
      );
    }
    if (statusPreviewVideoUrls.length > 0) {
      mergedFinalResult = mergePreviewMediaIntoResult(
        mergedFinalResult,
        'video',
        statusPreviewVideoUrls
      );
    }
    setFinalResult(mergedFinalResult);
    setFinalError(executionStatus?.finalError || null);
    setFinalCompletedAt(executionStatus?.completedAt || Date.now());
    setFinalRuntime(String(executionStatus?.finalRuntime || '').trim());
    setFinalRuntimeHints(toPreviewStringList(executionStatus?.runtimeHints));
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
    lastResultSignatureRef,
    setExecuteErrorBanner,
    setFinalCompletedAt,
    setFinalError,
    setFinalResult,
    setFinalRuntime,
    setFinalRuntimeHints,
  ]);

  useEffect(() => {
    if (!loadedWorkflow?.token) {
      return;
    }

    const normalizedNodes = (loadedWorkflow.nodes || []).map((node, index) =>
      normalizeLoadedNode(node, index)
    );
    const nodeIdSet = new Set(normalizedNodes.map((node) => node.id));
    const normalizedEdges = (loadedWorkflow.edges || [])
      .map((edge: Record<string, unknown>, index: number) => ({
        ...edge,
        id: String(edge?.id || `edge-loaded-${index}-${Date.now()}`),
        type: String(edge?.type || DEFAULT_WORKFLOW_EDGE_TYPE),
      }))
      .filter(
        (edge: Record<string, unknown>) =>
          nodeIdSet.has(String(edge?.source || '')) && nodeIdSet.has(String(edge?.target || ''))
      );
    const normalizedNodesWithPortLayout = hydrateNodePortLayoutsFromEdges(
      normalizedNodes as Node<WorkflowNodeData>[],
      normalizedEdges as Edge[]
    );

    const loadedInput =
      loadedWorkflow.input &&
      typeof loadedWorkflow.input === 'object' &&
      !Array.isArray(loadedWorkflow.input)
        ? loadedWorkflow.input
        : {};
    const loadedPrompt = String(
      loadedInput.task || loadedInput.prompt || loadedInput.text || loadedWorkflow.prompt || ''
    );
    const loadedImageUrls = mergeUniqueStringList(
      normalizeStringList(loadedInput.imageUrls),
      normalizeStringList(loadedInput.image_urls),
      typeof loadedInput.imageUrl === 'string' ? [loadedInput.imageUrl.trim()] : []
    );
    const loadedImageUrl = loadedImageUrls[0] || '';
    const loadedFileUrls = mergeUniqueStringList(
      normalizeStringList(loadedInput.fileUrls),
      normalizeStringList(loadedInput.file_urls),
      typeof loadedInput.fileUrl === 'string' ? [loadedInput.fileUrl.trim()] : []
    );
    const loadedFileUrl = loadedFileUrls[0] || '';
    const loadedExecutionStatus = loadedWorkflow.executionStatus;
    const loadedPreviewImages = toPreviewStringList(loadedExecutionStatus?.resultPreviewImageUrls);
    const loadedPreviewAudioUrls = toPreviewStringList(
      loadedExecutionStatus?.resultPreviewAudioUrls
    );
    const loadedPreviewVideoUrls = toPreviewStringList(
      loadedExecutionStatus?.resultPreviewVideoUrls
    );
    const applyLoadedExecutionState = (node: Node<WorkflowNodeData>) => {
      if (!loadedExecutionStatus) {
        return node;
      }

      const nodeType = String(node?.data?.type || node?.type || '')
        .trim()
        .toLowerCase();
      const nextData: Record<string, any> = { ...node.data };
      const nodeStatus = loadedExecutionStatus.nodeStatuses?.[node.id];
      if (nodeStatus) {
        nextData.status = nodeStatus;
      }
      const nodeProgress = loadedExecutionStatus.nodeProgress?.[node.id];
      if (nodeProgress !== undefined) {
        nextData.progress = nodeProgress;
      }

      const nodeResult = loadedExecutionStatus.nodeResults?.[node.id];
      if (nodeResult !== undefined && nodeResult !== null) {
        nextData.result = mergeWorkflowEndResult({
          rawResult: nodeResult,
          nodeType,
          existingResult: node.data?.result,
          finalResult: loadedExecutionStatus.finalResult,
          previewImages: loadedPreviewImages,
          previewAudioUrls: loadedPreviewAudioUrls,
          previewVideoUrls: loadedPreviewVideoUrls,
        });
      } else if (
        nodeType === 'end' &&
        loadedExecutionStatus.finalResult !== undefined &&
        loadedExecutionStatus.finalResult !== null
      ) {
        nextData.result = mergeWorkflowEndResult({
          rawResult: loadedExecutionStatus.finalResult,
          nodeType,
          existingResult: node.data?.result,
          finalResult: loadedExecutionStatus.finalResult,
          previewImages: loadedPreviewImages,
          previewAudioUrls: loadedPreviewAudioUrls,
          previewVideoUrls: loadedPreviewVideoUrls,
        });
      }

      const nodeError = loadedExecutionStatus.nodeErrors?.[node.id];
      if (nodeError) {
        nextData.error = nodeError;
      }
      const nodeRuntime = loadedExecutionStatus.nodeRuntimes?.[node.id];
      if (nodeRuntime) {
        nextData.runtime = nodeRuntime;
      }

      return {
        ...node,
        data: nextData,
      };
    };
    const hydratedNodes = normalizedNodesWithPortLayout
      .map((node) => {
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
            loadedImageUrls
          );
          nextData.startImageUrl = nodeImageUrls[0] || '';
          nextData.startImageUrls = nodeImageUrls;
        }
        if (nodeType === 'start' || nodeType === 'input_file') {
          const nodeFileUrls = mergeUniqueStringList(
            normalizeStringList(node.data?.startFileUrls),
            node.data?.startFileUrl ? [String(node.data.startFileUrl).trim()] : [],
            loadedFileUrls
          );
          nextData.startFileUrl = nodeFileUrls[0] || '';
          nextData.startFileUrls = nodeFileUrls;
        }
        return {
          ...node,
          data: nextData,
        };
      })
      .map((node) => applyLoadedExecutionState(node as Node<WorkflowNodeData>));

    let cancelled = false;
    void (async () => {
      const nodesWithAgentBinding = await hydrateAgentBindingsFromRegistry(
        hydratedNodes as Node<WorkflowNodeData>[]
      );
      if (cancelled) return;
      setNodes(applySingleNodeSelection(nodesWithAgentBinding as Node<WorkflowNodeData>[], null));
      setEdges(applySingleEdgeSelection(normalizedEdges as Edge[], null));
      setWorkflowPrompt(loadedPrompt);
      setWorkflowInputImageUrl(loadedImageUrl);
      setWorkflowInputFileUrl(loadedFileUrl);
      setActiveTemplateMeta(null);
      setActiveTemplateFingerprint(null);
      pendingFitTokenRef.current = loadedWorkflow.token;
      addLog(
        'system',
        '系统',
        'info',
        `已加载工作流${loadedWorkflow.name ? `：${loadedWorkflow.name}` : ''}`
      );
    })();

    return () => {
      cancelled = true;
    };
  }, [
    setNodes,
    setEdges,
    addLog,
    hydrateAgentBindingsFromRegistry,
    pendingFitTokenRef,
    setActiveTemplateFingerprint,
    setActiveTemplateMeta,
    setWorkflowInputFileUrl,
    setWorkflowInputImageUrl,
    setWorkflowPrompt,
    loadedWorkflow,
  ]);

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
  }, [reactFlowInstance, nodes.length, pendingFitTokenRef]);
};

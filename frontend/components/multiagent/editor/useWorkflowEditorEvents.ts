/**
 * useWorkflowEditorEvents
 *
 * Houses the window-level event listeners and keyboard shortcuts previously
 * defined inline in MultiAgentWorkflowEditorReactFlow.tsx:
 *
 * - workflow:disconnect-handle      (L1003-1021)
 * - workflow:remove-edge-request    (L1023-1042)
 * - workflow:focus-node-field       (L1044-1072)
 * - Delete/Backspace keyboard       (L1074-1098)
 * - workflow:execute-request /
 *   workflow:end-request            (L1379-1435)
 *
 * Behaviour is preserved 1:1 — including the same dependency arrays and
 * editor-scope filtering used by the source effects.
 */

import { useEffect } from 'react';
import type { Edge, Node } from 'reactflow';

import type { ExecutionStatus, WorkflowNodeData } from '../types';
import {
  applySingleEdgeSelection,
  applySingleNodeSelection,
  DisconnectHandleEventDetail,
  isKeyboardEventWithinEditableContext,
  isTerminalExecutionStatus,
  isWorkflowEventForEditorScope,
  WorkflowNodeActionEventDetail,
  WorkflowNodeFieldFocusEventDetail,
  WorkflowNodeFieldFocusRequest,
  WorkflowRemoveEdgeRequestDetail,
} from '../workflowEditorUtils';

import type { LogLevel } from '../ExecutionLogPanel';

type AddLog = (
  nodeId: string,
  nodeName: string,
  level: LogLevel,
  message: string,
  timestamp?: number
) => void;

type SetNodes = (
  updater:
    | Node<WorkflowNodeData>[]
    | ((prev: Node<WorkflowNodeData>[]) => Node<WorkflowNodeData>[])
) => void;
type SetEdges = (updater: Edge[] | ((prev: Edge[]) => Edge[])) => void;

export interface UseWorkflowEditorEventsArgs {
  editorScopeId: string;
  nodes: Node<WorkflowNodeData>[];
  setNodes: SetNodes;
  setEdges: SetEdges;
  selectedNode: Node<WorkflowNodeData> | null;
  selectedEdgeId: string | null;
  handleDisconnectByHandle: (detail: DisconnectHandleEventDetail) => void;
  handleRemoveEdgeById: (edgeId: string) => void;
  handleRemoveSelectedEdge: () => void;
  handleRemoveSelectedNode: () => void;
  setPendingNodeFieldFocusRequest: React.Dispatch<
    React.SetStateAction<WorkflowNodeFieldFocusRequest | null>
  >;
  handleExecute: () => Promise<void>;
  executionStatus?: ExecutionStatus;
  finalResult: any;
  finalError: string | null;
  setShowResultPanel: React.Dispatch<React.SetStateAction<boolean>>;
  addLog: AddLog;
}

export const useWorkflowEditorEvents = ({
  editorScopeId,
  nodes,
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
}: UseWorkflowEditorEventsArgs): void => {
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
    return () =>
      window.removeEventListener(
        'workflow:disconnect-handle',
        onDisconnectByHandle as EventListener
      );
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
    return () =>
      window.removeEventListener(
        'workflow:remove-edge-request',
        onRemoveEdgeRequest as EventListener
      );
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
    return () =>
      window.removeEventListener('workflow:focus-node-field', onFocusNodeField as EventListener);
  }, [editorScopeId, nodes, setEdges, setNodes, setPendingNodeFieldFocusRequest]);

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
      const finalStatus = String(executionStatus?.finalStatus || '')
        .trim()
        .toLowerCase();
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
  }, [
    addLog,
    editorScopeId,
    executionStatus?.finalStatus,
    finalError,
    finalResult,
    handleExecute,
    nodes,
    setShowResultPanel,
  ]);
};

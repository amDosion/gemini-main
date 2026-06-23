/**
 * Undo/Redo Hook
 *
 * Provides undo/redo functionality for workflow editor
 * with configurable history size.
 *
 * 设计要点（Codex review 修复）:
 * - 栈以 ref 为唯一真源,useState 仅存计数用于驱动 canUndo/canRedo 重渲染——
 *   避免同一渲染周期内连续 undo/redo 重放闭包捕获的旧栈。
 * - 快照在变更"前"拍下,hook 无从得知变更后的画布实时状态,因此 undo/redo
 *   由调用方传入当前实时 nodes/edges:undo 把它压入 redo 栈(修复"首次 undo
 *   后无法 redo"),redo 把它压回 undo 栈。
 */

import { useState, useCallback, useRef } from 'react';
import { Node, Edge } from '@xyflow/react';
import { CustomNodeData } from './CustomNode';

interface WorkflowState {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
}

interface UseUndoRedoOptions {
  maxHistorySize?: number;
}

interface UseUndoRedoResult {
  undo: (currentNodes: Node<CustomNodeData>[], currentEdges: Edge[]) => WorkflowState | null;
  redo: (currentNodes: Node<CustomNodeData>[], currentEdges: Edge[]) => WorkflowState | null;
  canUndo: boolean;
  canRedo: boolean;
  takeSnapshot: (nodes: Node<CustomNodeData>[], edges: Edge[]) => void;
  clear: () => void;
}

// ✅ structuredClone 比 JSON.parse(JSON.stringify(...)) 快 2-3x（原生 structured
// clone algorithm）。WorkflowNodeData 全为基本类型，完全兼容。
const cloneState = (nodes: Node<CustomNodeData>[], edges: Edge[]): WorkflowState => ({
  nodes: structuredClone(nodes),
  edges: structuredClone(edges),
});

export const useUndoRedo = (options: UseUndoRedoOptions = {}): UseUndoRedoResult => {
  const { maxHistorySize = 50 } = options;

  const pastRef = useRef<WorkflowState[]>([]);
  const futureRef = useRef<WorkflowState[]>([]);
  const [counts, setCounts] = useState({ past: 0, future: 0 });

  const syncCounts = useCallback(() => {
    setCounts({ past: pastRef.current.length, future: futureRef.current.length });
  }, []);

  // Take a snapshot of the (pre-change) state; callers invoke this right
  // before mutating the canvas.
  const takeSnapshot = useCallback(
    (nodes: Node<CustomNodeData>[], edges: Edge[]) => {
      pastRef.current.push(cloneState(nodes, edges));
      if (pastRef.current.length > maxHistorySize) {
        pastRef.current.splice(0, pastRef.current.length - maxHistorySize);
      }
      // Clear future when new action is taken
      futureRef.current = [];
      syncCounts();
    },
    [maxHistorySize, syncCounts]
  );

  // Undo last action. Callers pass the CURRENT live canvas state so it can be
  // pushed onto the redo stack (snapshots only ever capture pre-change state).
  const undo = useCallback(
    (currentNodes: Node<CustomNodeData>[], currentEdges: Edge[]) => {
      const previous = pastRef.current.pop();
      if (!previous) return null;

      futureRef.current.push(cloneState(currentNodes, currentEdges));
      syncCounts();
      return previous;
    },
    [syncCounts]
  );

  // Redo last undone action; the current live state goes back onto the undo stack.
  const redo = useCallback(
    (currentNodes: Node<CustomNodeData>[], currentEdges: Edge[]) => {
      const next = futureRef.current.pop();
      if (!next) return null;

      pastRef.current.push(cloneState(currentNodes, currentEdges));
      syncCounts();
      return next;
    },
    [syncCounts]
  );

  // Clear history
  const clear = useCallback(() => {
    pastRef.current = [];
    futureRef.current = [];
    syncCounts();
  }, [syncCounts]);

  return {
    undo,
    redo,
    canUndo: counts.past > 0,
    canRedo: counts.future > 0,
    takeSnapshot,
    clear,
  };
};

export default useUndoRedo;

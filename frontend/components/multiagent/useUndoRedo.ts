/**
 * Undo/Redo Hook
 *
 * Provides undo/redo functionality for workflow editor
 * with configurable history size.
 */

import { useState, useCallback, useRef } from 'react';
import { Node, Edge } from 'reactflow';
import { CustomNodeData } from './CustomNode';

interface WorkflowState {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
}

interface UseUndoRedoOptions {
  maxHistorySize?: number;
}

interface UseUndoRedoResult {
  undo: () => WorkflowState | null;
  redo: () => WorkflowState | null;
  canUndo: boolean;
  canRedo: boolean;
  takeSnapshot: (nodes: Node<CustomNodeData>[], edges: Edge[]) => void;
  clear: () => void;
}

export const useUndoRedo = (options: UseUndoRedoOptions = {}): UseUndoRedoResult => {
  const { maxHistorySize = 50 } = options;

  const [past, setPast] = useState<WorkflowState[]>([]);
  const [future, setFuture] = useState<WorkflowState[]>([]);
  // Last state the hook knows to be live on the canvas. Snapshots are taken
  // BEFORE each mutation, so right after takeSnapshot the live canvas diverges
  // from anything the hook has seen and this ref is cleared; undo/redo
  // re-synchronize it with the state they hand back to the caller.
  const knownLiveState = useRef<WorkflowState | null>(null);

  // Take a snapshot of the (pre-change) state; callers invoke this right
  // before mutating the canvas.
  const takeSnapshot = useCallback(
    (nodes: Node<CustomNodeData>[], edges: Edge[]) => {
      // ✅ Wave 2 perf: structuredClone 比 JSON.parse(JSON.stringify(...)) 快 2-3x，
      // 原生 API（structured clone algorithm），支持更多类型且不需序列化两次。
      // WorkflowNodeData 全为基本类型（无 Function/Map/RegExp），完全兼容。
      const newState: WorkflowState = {
        nodes: structuredClone(nodes),
        edges: structuredClone(edges),
      };

      setPast((prev) => {
        const newPast = [...prev, newState];
        // Limit history size
        if (newPast.length > maxHistorySize) {
          return newPast.slice(newPast.length - maxHistorySize);
        }
        return newPast;
      });

      knownLiveState.current = null;

      // Clear future when new action is taken
      setFuture([]);
    },
    [maxHistorySize]
  );

  // Undo last action
  const undo = useCallback(() => {
    if (past.length === 0) return null;

    const previous = past[past.length - 1];
    // Capture eagerly: state updaters run during the next render, after refs
    // may have been reassigned, so they must never read refs lazily.
    const currentLive = knownLiveState.current;

    setPast(past.slice(0, -1));
    if (currentLive) {
      setFuture((prev) => [...prev, currentLive]);
    }
    knownLiveState.current = previous;

    return previous;
  }, [past]);

  // Redo last undone action
  const redo = useCallback(() => {
    if (future.length === 0) return null;

    const next = future[future.length - 1];
    const currentLive = knownLiveState.current;

    setFuture(future.slice(0, -1));
    if (currentLive) {
      setPast((prev) => [...prev, currentLive]);
    }
    knownLiveState.current = next;

    return next;
  }, [future]);

  // Clear history
  const clear = useCallback(() => {
    setPast([]);
    setFuture([]);
    knownLiveState.current = null;
  }, []);

  return {
    undo,
    redo,
    canUndo: past.length > 0,
    canRedo: future.length > 0,
    takeSnapshot,
    clear,
  };
};

export default useUndoRedo;

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

export const useUndoRedo = (
  options: UseUndoRedoOptions = {}
): UseUndoRedoResult => {
  const { maxHistorySize = 50 } = options;

  const [past, setPast] = useState<WorkflowState[]>([]);
  const [future, setFuture] = useState<WorkflowState[]>([]);
  const currentState = useRef<WorkflowState | null>(null);

  // Take a snapshot of current state
  const takeSnapshot = useCallback(
    (nodes: Node<CustomNodeData>[], edges: Edge[]) => {
      const newState: WorkflowState = {
        nodes: JSON.parse(JSON.stringify(nodes)),
        edges: JSON.parse(JSON.stringify(edges)),
      };

      // If there's a current state, push it to past
      if (currentState.current) {
        setPast((prev) => {
          const newPast = [...prev, currentState.current!];
          // Limit history size
          if (newPast.length > maxHistorySize) {
            return newPast.slice(newPast.length - maxHistorySize);
          }
          return newPast;
        });
      }

      currentState.current = newState;
      
      // Clear future when new action is taken
      setFuture([]);
    },
    [maxHistorySize]
  );

  // Undo last action
  const undo = useCallback(() => {
    if (past.length === 0 || !currentState.current) return null;

    const previous = past[past.length - 1];
    const newPast = past.slice(0, -1);

    setPast(newPast);
    setFuture((prev) => [...prev, currentState.current!]);
    currentState.current = previous;

    return previous;
  }, [past]);

  // Redo last undone action
  const redo = useCallback(() => {
    if (future.length === 0) return null;

    const next = future[future.length - 1];
    const newFuture = future.slice(0, -1);

    if (currentState.current) {
      setPast((prev) => [...prev, currentState.current!]);
    }
    setFuture(newFuture);
    currentState.current = next;

    return next;
  }, [future]);

  // Clear history
  const clear = useCallback(() => {
    setPast([]);
    setFuture([]);
    currentState.current = null;
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

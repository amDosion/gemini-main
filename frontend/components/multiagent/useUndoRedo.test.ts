// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { Node, Edge } from 'reactflow';
import { useUndoRedo } from './useUndoRedo';
import type { CustomNodeData } from './CustomNode';

const makeNodes = (label: string): Node<CustomNodeData>[] => [
  {
    id: 'n1',
    type: 'custom',
    position: { x: 0, y: 0 },
    data: { label } as CustomNodeData,
  },
];

const noEdges: Edge[] = [];

const labelOf = (state: { nodes: Node<CustomNodeData>[] } | null): string | undefined =>
  state?.nodes[0]?.data?.label;

describe('useUndoRedo', () => {
  it('restores the snapshot on undo and supports redo back to the live state', () => {
    const { result } = renderHook(() => useUndoRedo());
    const s0 = makeNodes('s0');
    const s1 = makeNodes('s1');

    // 调用方契约：变更前拍快照（s0），随后画布变为 s1
    act(() => {
      result.current.takeSnapshot(s0, noEdges);
    });
    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);

    // 首次 undo：传入当前实时状态 s1，应回到 s0 且 redo 可用（修复前 canRedo 恒为 false）
    let undone: ReturnType<typeof result.current.undo> = null;
    act(() => {
      undone = result.current.undo(s1, noEdges);
    });
    expect(labelOf(undone)).toBe('s0');
    expect(result.current.canUndo).toBe(false);
    expect(result.current.canRedo).toBe(true);

    // redo：传入当前实时状态 s0，应回到 s1，且 s0 重新可 undo
    let redone: ReturnType<typeof result.current.redo> = null;
    act(() => {
      redone = result.current.redo(s0, noEdges);
    });
    expect(labelOf(redone)).toBe('s1');
    expect(result.current.canUndo).toBe(true);
    expect(result.current.canRedo).toBe(false);
  });

  it('handles consecutive undos within a single tick without replaying stale stacks', () => {
    const { result } = renderHook(() => useUndoRedo());
    const s0 = makeNodes('s0');
    const s1 = makeNodes('s1');
    const s2 = makeNodes('s2');

    act(() => {
      result.current.takeSnapshot(s0, noEdges); // 画布 s0 -> s1
      result.current.takeSnapshot(s1, noEdges); // 画布 s1 -> s2
    });

    // 同一 tick 内连续两次 undo（修复前闭包捕获旧栈，两次都返回 s1）
    const labels: Array<string | undefined> = [];
    act(() => {
      labels.push(labelOf(result.current.undo(s2, noEdges)));
      labels.push(labelOf(result.current.undo(s1, noEdges)));
    });
    expect(labels).toEqual(['s1', 's0']);
    expect(result.current.canUndo).toBe(false);

    // redo 两次依次回放 s1、s2
    const redoLabels: Array<string | undefined> = [];
    act(() => {
      redoLabels.push(labelOf(result.current.redo(s0, noEdges)));
      redoLabels.push(labelOf(result.current.redo(s1, noEdges)));
    });
    expect(redoLabels).toEqual(['s1', 's2']);
  });

  it('clears the redo stack when a new snapshot is taken', () => {
    const { result } = renderHook(() => useUndoRedo());
    const s0 = makeNodes('s0');
    const s1 = makeNodes('s1');
    const s2 = makeNodes('s2');

    act(() => {
      result.current.takeSnapshot(s0, noEdges);
    });
    act(() => {
      result.current.undo(s1, noEdges);
    });
    expect(result.current.canRedo).toBe(true);

    act(() => {
      result.current.takeSnapshot(s0, noEdges); // 新动作：画布 s0 -> s2
    });
    expect(result.current.canRedo).toBe(false);
    expect(result.current.canUndo).toBe(true);

    let undone: ReturnType<typeof result.current.undo> = null;
    act(() => {
      undone = result.current.undo(s2, noEdges);
    });
    expect(labelOf(undone)).toBe('s0');
  });
});

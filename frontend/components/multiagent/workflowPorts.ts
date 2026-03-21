import type { Edge, Node } from 'reactflow';
import type { WorkflowNodeData, WorkflowNodePortLayout } from './types';

export type WorkflowNodePortSide = 'left' | 'right' | 'top' | 'bottom';
export type WorkflowNodeHandleDirection = 'source' | 'target';

export interface WorkflowNodePortHandle {
  side: WorkflowNodePortSide;
  direction: WorkflowNodeHandleDirection;
  index: number;
  count: number;
  id?: string;
  key: string;
}

export const DEFAULT_HANDLE_KEY = '__default__';
const MAX_PORTS_PER_SIDE = 12;

const toNodeType = (value: unknown): string => String(value || '').trim().toLowerCase().replace(/-/g, '_');

const clampPortCount = (value: unknown, fallback: number): number => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, Math.min(MAX_PORTS_PER_SIDE, Math.floor(parsed)));
};

const isPortLayoutObject = (value: unknown): value is Partial<WorkflowNodePortLayout> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

export const isFixedPortLayoutNodeType = (nodeType: unknown): boolean => {
  const normalized = toNodeType(nodeType);
  return normalized === 'start' || normalized === 'end';
};

export const getDefaultNodePortLayout = (nodeType: unknown): WorkflowNodePortLayout => {
  const normalized = toNodeType(nodeType);
  if (normalized === 'start') {
    return { left: 0, right: 1, top: 0, bottom: 0 };
  }
  if (normalized === 'end') {
    return { left: 1, right: 0, top: 0, bottom: 0 };
  }
  return { left: 1, right: 1, top: 0, bottom: 0 };
};

export const resolveNodePortLayout = (
  nodeType: unknown,
  rawPortLayout?: Partial<WorkflowNodePortLayout> | null,
): WorkflowNodePortLayout => {
  const defaults = getDefaultNodePortLayout(nodeType);
  if (isFixedPortLayoutNodeType(nodeType)) {
    return defaults;
  }
  const safeRaw = isPortLayoutObject(rawPortLayout) ? rawPortLayout : {};
  return {
    left: clampPortCount(safeRaw.left, defaults.left),
    right: clampPortCount(safeRaw.right, defaults.right),
    top: clampPortCount(safeRaw.top, defaults.top),
    bottom: clampPortCount(safeRaw.bottom, defaults.bottom),
  };
};

const getHandleIdForSide = (
  nodeType: string,
  side: WorkflowNodePortSide,
  index: number,
  count: number,
): string | undefined => {
  if (count <= 0) return undefined;

  if (side === 'left') {
    if (count === 1) return undefined;
    if (count === 2) return index === 0 ? 'input-1' : 'input-2';
    return `left-${index}`;
  }

  if (side === 'right') {
    const isConditionLike = nodeType === 'condition' || nodeType === 'loop';
    if (count === 1) return undefined;
    if (isConditionLike && index === 0) return 'output-true';
    if (isConditionLike && index === 1) return 'output-false';
    return `output-${index}`;
  }

  if (side === 'top') {
    return `top-${index}`;
  }

  return `bottom-${index}`;
};

const directionBySide: Record<WorkflowNodePortSide, WorkflowNodeHandleDirection> = {
  left: 'target',
  top: 'target',
  right: 'source',
  bottom: 'source',
};

export const toHandleKey = (handleId?: string | null): string => {
  const normalized = String(handleId || '').trim();
  return normalized || DEFAULT_HANDLE_KEY;
};

export const buildHandlesForSide = (
  nodeType: unknown,
  side: WorkflowNodePortSide,
  rawPortLayout?: Partial<WorkflowNodePortLayout> | null,
): WorkflowNodePortHandle[] => {
  const normalizedType = toNodeType(nodeType);
  const layout = resolveNodePortLayout(normalizedType, rawPortLayout);
  const count = layout[side];
  if (count <= 0) return [];

  return Array.from({ length: count }).map((_, index) => {
    const id = getHandleIdForSide(normalizedType, side, index, count);
    return {
      side,
      direction: directionBySide[side],
      index,
      count,
      id,
      key: `${side}-${index}-${id || DEFAULT_HANDLE_KEY}`,
    };
  });
};

export const getValidHandleKeysForDirection = (
  nodeType: unknown,
  rawPortLayout: Partial<WorkflowNodePortLayout> | null | undefined,
  direction: WorkflowNodeHandleDirection,
): Set<string> => {
  const sides = direction === 'source' ? (['right', 'bottom'] as const) : (['left', 'top'] as const);
  const keys = new Set<string>();
  sides.forEach((side) => {
    buildHandlesForSide(nodeType, side, rawPortLayout).forEach((handle) => {
      keys.add(toHandleKey(handle.id));
    });
  });
  return keys;
};

const getEdgeHandleValue = (edge: Edge, field: 'sourceHandle' | 'targetHandle'): string | undefined => {
  const value = (edge as Record<string, unknown>)?.[field];
  if (value === undefined || value === null) return undefined;
  return String(value);
};

const inferLayoutFromEdges = (
  nodeId: string,
  nodeType: unknown,
  edges: Edge[],
): WorkflowNodePortLayout => {
  const layout = getDefaultNodePortLayout(nodeType);
  if (isFixedPortLayoutNodeType(nodeType)) {
    return layout;
  }

  edges.forEach((edge) => {
    if (String(edge.source) === nodeId) {
      const handleId = getEdgeHandleValue(edge, 'sourceHandle');
      const normalized = String(handleId || '').trim();
      if (!normalized) {
        layout.right = Math.max(layout.right, 1);
      } else if (normalized === 'output-true' || normalized === 'output-false') {
        layout.right = Math.max(layout.right, 2);
      } else {
        const outputMatch = normalized.match(/^output-(\d+)$/);
        const bottomMatch = normalized.match(/^bottom-(\d+)$/);
        const rightMatch = normalized.match(/^right-(\d+)$/);
        if (outputMatch) {
          layout.right = Math.max(layout.right, Number(outputMatch[1]) + 1);
        } else if (bottomMatch) {
          layout.bottom = Math.max(layout.bottom, Number(bottomMatch[1]) + 1);
        } else if (rightMatch) {
          layout.right = Math.max(layout.right, Number(rightMatch[1]) + 1);
        } else {
          layout.right = Math.max(layout.right, 1);
        }
      }
    }

    if (String(edge.target) === nodeId) {
      const handleId = getEdgeHandleValue(edge, 'targetHandle');
      const normalized = String(handleId || '').trim();
      if (!normalized) {
        layout.left = Math.max(layout.left, 1);
      } else if (normalized === 'input-1' || normalized === 'input-2') {
        layout.left = Math.max(layout.left, 2);
      } else {
        const leftMatch = normalized.match(/^left-(\d+)$/);
        const topMatch = normalized.match(/^top-(\d+)$/);
        if (leftMatch) {
          layout.left = Math.max(layout.left, Number(leftMatch[1]) + 1);
        } else if (topMatch) {
          layout.top = Math.max(layout.top, Number(topMatch[1]) + 1);
        } else {
          layout.left = Math.max(layout.left, 1);
        }
      }
    }
  });

  return resolveNodePortLayout(nodeType, layout);
};

const isSamePortLayout = (a: WorkflowNodePortLayout, b: WorkflowNodePortLayout): boolean => {
  return a.left === b.left && a.right === b.right && a.top === b.top && a.bottom === b.bottom;
};

export const hydrateNodePortLayoutsFromEdges = (
  nodes: Node<WorkflowNodeData>[],
  edges: Edge[],
): Node<WorkflowNodeData>[] => {
  return nodes.map((node) => {
    const nodeType = node?.data?.type || node?.type || 'agent';
    const rawLayout = node?.data?.portLayout;
    const resolvedLayout = isPortLayoutObject(rawLayout)
      ? resolveNodePortLayout(nodeType, rawLayout)
      : inferLayoutFromEdges(String(node.id), nodeType, edges);

    if (isPortLayoutObject(rawLayout)) {
      const currentLayout = resolveNodePortLayout(nodeType, rawLayout);
      if (isSamePortLayout(currentLayout, resolvedLayout)) {
        return node;
      }
    }

    return {
      ...node,
      data: {
        ...node.data,
        portLayout: resolvedLayout,
      },
    };
  });
};

export const filterEdgesByNodePortLayouts = (
  nodes: Node<WorkflowNodeData>[],
  edges: Edge[],
): Edge[] => {
  const nodeMap = new Map<string, Node<WorkflowNodeData>>(nodes.map((node) => [String(node.id), node]));
  return edges.filter((edge) => {
    const sourceNode = nodeMap.get(String(edge.source));
    const targetNode = nodeMap.get(String(edge.target));
    if (!sourceNode || !targetNode) return false;

    const sourceType = sourceNode?.data?.type || sourceNode.type || 'agent';
    const targetType = targetNode?.data?.type || targetNode.type || 'agent';
    const sourceKeys = getValidHandleKeysForDirection(sourceType, sourceNode.data?.portLayout, 'source');
    const targetKeys = getValidHandleKeysForDirection(targetType, targetNode.data?.portLayout, 'target');

    if (sourceKeys.size === 0 || targetKeys.size === 0) {
      return false;
    }

    return (
      sourceKeys.has(toHandleKey(getEdgeHandleValue(edge, 'sourceHandle')))
      && targetKeys.has(toHandleKey(getEdgeHandleValue(edge, 'targetHandle')))
    );
  });
};

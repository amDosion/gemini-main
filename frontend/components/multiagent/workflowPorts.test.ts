import { describe, expect, it } from 'vitest';
import type { Edge, Node } from 'reactflow';
import type { WorkflowNodeData } from './types';
import {
  buildHandlesForSide,
  filterEdgesByNodePortLayouts,
  hydrateNodePortLayoutsFromEdges,
  resolveNodePortLayout,
} from './workflowPorts';

describe('workflowPorts', () => {
  it('keeps start/end port layout fixed', () => {
    expect(resolveNodePortLayout('start', { left: 3, right: 0, top: 9, bottom: 9 })).toEqual({
      left: 0,
      right: 1,
      top: 0,
      bottom: 0,
    });
    expect(resolveNodePortLayout('end', { left: 0, right: 2, top: 1, bottom: 1 })).toEqual({
      left: 1,
      right: 0,
      top: 0,
      bottom: 0,
    });
  });

  it('generates condition branch handles with legacy ids', () => {
    const handles = buildHandlesForSide('condition', 'right', { left: 1, right: 2, top: 0, bottom: 0 });
    expect(handles.map((item) => item.id)).toEqual(['output-true', 'output-false']);
  });

  it('hydrates missing port layout by existing edge handle ids', () => {
    const nodes: Array<Node<WorkflowNodeData>> = [
      {
        id: 'node-condition',
        type: 'condition',
        position: { x: 0, y: 0 },
        data: {
          label: '条件',
          description: '',
          icon: '🔀',
          iconColor: 'bg-yellow-500',
          type: 'condition',
        },
      },
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'node-condition', target: 'a', sourceHandle: 'output-true' } as Edge,
      { id: 'e2', source: 'node-condition', target: 'b', sourceHandle: 'output-false' } as Edge,
    ];
    const hydrated = hydrateNodePortLayoutsFromEdges(nodes, edges);
    expect(hydrated[0].data.portLayout).toEqual({
      left: 1,
      right: 2,
      top: 0,
      bottom: 0,
    });
  });

  it('filters edges that no longer match port handles', () => {
    const nodes: Array<Node<WorkflowNodeData>> = [
      {
        id: 'node-a',
        type: 'agent',
        position: { x: 0, y: 0 },
        data: {
          label: 'A',
          description: '',
          icon: '🤖',
          iconColor: 'bg-teal-500',
          type: 'agent',
          portLayout: { left: 1, right: 1, top: 0, bottom: 0 },
        },
      },
      {
        id: 'node-b',
        type: 'agent',
        position: { x: 200, y: 0 },
        data: {
          label: 'B',
          description: '',
          icon: '🤖',
          iconColor: 'bg-teal-500',
          type: 'agent',
          portLayout: { left: 1, right: 1, top: 0, bottom: 0 },
        },
      },
    ];
    const edges: Edge[] = [
      { id: 'e-valid', source: 'node-a', target: 'node-b' } as Edge,
      { id: 'e-invalid', source: 'node-a', target: 'node-b', sourceHandle: 'bottom-0' } as Edge,
    ];
    const filtered = filterEdgesByNodePortLayouts(nodes, edges);
    expect(filtered.map((edge) => edge.id)).toEqual(['e-valid']);
  });
});

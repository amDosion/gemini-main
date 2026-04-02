import { describe, expect, it } from 'vitest';
import type { Edge, Node } from 'reactflow';

import { validateWorkflow } from './workflowUtils';
import type { WorkflowNodeData } from './types';

const buildNode = (
  id: string,
  type: string,
  data: Partial<WorkflowNodeData> = {},
): Node<WorkflowNodeData> => ({
  id,
  type,
  position: { x: 0, y: 0 },
  data: {
    label: id,
    description: '',
    icon: '🔧',
    iconColor: 'bg-slate-500',
    type,
    ...data,
  } as WorkflowNodeData,
});

describe('validateWorkflow inline agent bindings', () => {
  it('accepts active-profile inline agents without registry binding', () => {
    const nodes: Node<WorkflowNodeData>[] = [
      buildNode('start', 'start', { type: 'start' }),
      buildNode('inline-agent', 'agent', {
        type: 'agent',
        label: 'Inline Video',
        inlineUseActiveProfile: true,
        agentTaskType: 'video-gen',
      }),
      buildNode('end', 'end', { type: 'end' }),
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'inline-agent' },
      { id: 'e2', source: 'inline-agent', target: 'end' },
    ];

    const result = validateWorkflow(nodes, edges);

    expect(result.isValid).toBe(true);
    expect(result.nodeErrors['inline-agent']).toBeUndefined();
  });

  it('still rejects agent nodes without registry or inline runtime binding', () => {
    const nodes: Node<WorkflowNodeData>[] = [
      buildNode('start', 'start', { type: 'start' }),
      buildNode('broken-agent', 'agent', {
        type: 'agent',
        label: 'Broken Agent',
        agentTaskType: 'chat',
      }),
      buildNode('end', 'end', { type: 'end' }),
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'broken-agent' },
      { id: 'e2', source: 'broken-agent', target: 'end' },
    ];

    const result = validateWorkflow(nodes, edges);

    expect(result.isValid).toBe(false);
    expect(result.nodeErrors['broken-agent']).toContain(
      '智能体节点必须配置智能体（agentId / agentName），或配置 inlineProviderId + inlineModelId，或启用 inlineUseActiveProfile',
    );
  });
});

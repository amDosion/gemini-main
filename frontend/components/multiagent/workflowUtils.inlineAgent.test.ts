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

  it('rejects human nodes unless autoApprove is explicitly enabled', () => {
    const nodes: Node<WorkflowNodeData>[] = [
      buildNode('start', 'start', { type: 'start' }),
      buildNode('review', 'human', {
        type: 'human',
        label: 'Review',
        approvalPrompt: '确认后继续',
      }),
      buildNode('end', 'end', { type: 'end' }),
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'review' },
      { id: 'e2', source: 'review', target: 'end' },
    ];

    const result = validateWorkflow(nodes, edges);

    expect(result.isValid).toBe(false);
    expect(result.nodeErrors.review).toContain(
      '人工审核节点当前没有真实确认流程，必须显式启用自动通过后才能执行',
    );
  });

  it('rejects unsupported node types before execution', () => {
    const nodes: Node<WorkflowNodeData>[] = [
      buildNode('start', 'start', { type: 'start' }),
      buildNode('mystery', 'mystery_box', {
        type: 'mystery_box',
        label: 'Mystery',
      }),
      buildNode('end', 'end', { type: 'end' }),
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'mystery' },
      { id: 'e2', source: 'mystery', target: 'end' },
    ];

    const result = validateWorkflow(nodes, edges);

    expect(result.isValid).toBe(false);
    expect(result.nodeErrors.mystery).toContain('不支持的节点类型：mystery_box');
  });

  it('allows reference images when agent task type is inherited from the bound Agent', () => {
    const nodes: Node<WorkflowNodeData>[] = [
      buildNode('start', 'start', { type: 'start' }),
      buildNode('image-agent', 'agent', {
        type: 'agent',
        label: 'Image Edit Agent',
        agentName: '图片编辑优化师',
        agentReferenceImageUrl: 'https://example.com/ref.png',
      }),
      buildNode('end', 'end', { type: 'end' }),
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'image-agent' },
      { id: 'e2', source: 'image-agent', target: 'end' },
    ];

    const result = validateWorkflow(nodes, edges);

    expect(result.isValid).toBe(true);
    expect(result.nodeErrors['image-agent']).toBeUndefined();
  });

  it('allows reference images for video generation source-image workflows', () => {
    const nodes: Node<WorkflowNodeData>[] = [
      buildNode('start', 'start', { type: 'start' }),
      buildNode('video-agent', 'agent', {
        type: 'agent',
        label: 'Video Agent',
        inlineUseActiveProfile: true,
        agentTaskType: 'video-gen',
        agentReferenceImageUrl: 'https://example.com/source.png',
      }),
      buildNode('end', 'end', { type: 'end' }),
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'video-agent' },
      { id: 'e2', source: 'video-agent', target: 'end' },
    ];

    const result = validateWorkflow(nodes, edges);

    expect(result.isValid).toBe(true);
    expect(result.nodeErrors['video-agent']).toBeUndefined();
  });

  it('normalizes agent task aliases through the shared workflow contract when validating reference images', () => {
    const nodes: Node<WorkflowNodeData>[] = [
      buildNode('start', 'start', { type: 'start' }),
      buildNode('video-agent', 'agent', {
        type: 'agent',
        label: 'Video Agent',
        inlineUseActiveProfile: true,
        agentTaskType: 'video',
        agentReferenceImageUrl: 'https://example.com/source.png',
      }),
      buildNode('end', 'end', { type: 'end' }),
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'video-agent' },
      { id: 'e2', source: 'video-agent', target: 'end' },
    ];

    const result = validateWorkflow(nodes, edges);

    expect(result.isValid).toBe(true);
    expect(result.nodeErrors['video-agent']).toBeUndefined();
  });
});

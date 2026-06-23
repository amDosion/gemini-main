// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Edge, Node } from '@xyflow/react';

import { useWorkflowExecuteHandler } from './useWorkflowExecuteHandler';
import type { WorkflowNodeData } from '../types';

const node = (
  id: string,
  type: string,
  data: Partial<WorkflowNodeData> = {}
): Node<WorkflowNodeData> => ({
  id,
  type,
  position: { x: 0, y: 0 },
  data: {
    type,
    label: id,
    description: '',
    icon: '🤖',
    iconColor: 'bg-slate-500',
    ...data,
  } as WorkflowNodeData,
});

describe('useWorkflowExecuteHandler media validation', () => {
  it('allows video generation agents with reference images to execute', async () => {
    const onExecute = vi.fn();
    const addLog = vi.fn();
    const setShowLogs = vi.fn();
    const nodes: Node<WorkflowNodeData>[] = [
      node('start', 'start'),
      node('video-agent', 'agent', {
        inlineUseActiveProfile: true,
        agentTaskType: 'video-gen',
        agentReferenceImageUrl: 'https://example.com/source.png',
      }),
      node('end', 'end'),
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'video-agent' },
      { id: 'e2', source: 'video-agent', target: 'end' },
    ];

    const { result } = renderHook(() =>
      useWorkflowExecuteHandler({
        onExecute,
        nodes,
        edges,
        workflowPrompt: 'animate this image',
        workflowInputImageUrl: '',
        workflowInputFileUrl: '',
        activeTemplateMeta: null,
        activeTemplateFingerprint: null,
        addLog,
        setShowLogs,
      })
    );

    await act(async () => {
      await result.current.handleExecute();
    });

    expect(onExecute).toHaveBeenCalledTimes(1);
    expect(result.current.executeErrorBanner).toBeNull();
    expect(setShowLogs).not.toHaveBeenCalledWith(true);
  });
});

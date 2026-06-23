// @vitest-environment jsdom
import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Edge, Node, ReactFlowInstance } from '@xyflow/react';
import type { ExecutionStatus, WorkflowEdge, WorkflowNode, WorkflowNodeData } from '../types';
import { useWorkflowEditorLoading } from './useWorkflowEditorLoading';

const noopStateSetter = vi.fn();

const buildExecutionStatus = (imageUrl: string): ExecutionStatus => ({
  executionId: 'exec-history-canvas',
  finalStatus: 'completed',
  finalResult: {
    finalOutput: {
      imageUrl,
      imageUrls: [imageUrl],
    },
  },
  finalError: undefined,
  logs: [],
  nodeStatuses: {
    'end-node': 'completed',
  },
  nodeProgress: {
    'end-node': 100,
  },
  nodeResults: {
    'end-node': {
      finalOutput: {
        imageUrl,
        imageUrls: [imageUrl],
      },
    },
  },
  nodeErrors: {},
});

describe('useWorkflowEditorLoading history hydration', () => {
  it('hydrates loaded history nodes with their persisted execution result', async () => {
    const imageUrl = '/api/storage/local-files/2026/05/24/workflow-result-01-generated.png';
    const executionStatus = buildExecutionStatus(imageUrl);
    const setNodes = vi.fn();
    const setEdges = vi.fn();

    renderHook(() =>
      useWorkflowEditorLoading({
        executionStatus: undefined,
        loadedWorkflow: {
          token: 'history-load-token',
          name: '历史工作流',
          prompt: '',
          input: {},
          nodes: [
            {
              id: 'end-node',
              type: 'end',
              position: { x: 0, y: 0 },
              data: {
                type: 'end',
                label: '结束',
                description: '',
                icon: 'square',
                iconColor: '#fff',
              },
            },
          ],
          edges: [],
          executionStatus,
        } as any,
        nodes: [],
        setNodes,
        setEdges,
        reactFlowInstance: null as ReactFlowInstance<WorkflowNode, WorkflowEdge> | null,
        pendingFitTokenRef: React.createRef() as React.MutableRefObject<string | null>,
        importedExecutionLogCountRef: React.createRef() as React.MutableRefObject<number>,
        lastResultSignatureRef: React.createRef() as React.MutableRefObject<string | null>,
        hydrateAgentBindingsFromRegistry: vi.fn(async (nodes: Node<WorkflowNodeData>[]) => nodes),
        setWorkflowPrompt: noopStateSetter,
        setWorkflowInputImageUrl: noopStateSetter,
        setWorkflowInputFileUrl: noopStateSetter,
        setActiveTemplateMeta: noopStateSetter,
        setActiveTemplateFingerprint: noopStateSetter,
        setExecuteErrorBanner: noopStateSetter,
        setFinalResult: noopStateSetter,
        setFinalError: noopStateSetter,
        setFinalCompletedAt: noopStateSetter,
        setFinalRuntime: noopStateSetter,
        setFinalRuntimeHints: noopStateSetter,
        addLog: vi.fn(),
      })
    );

    await waitFor(() => {
      expect(setNodes).toHaveBeenCalled();
    });

    const hydratedNodes = setNodes.mock.calls.at(-1)?.[0] as Node<WorkflowNodeData>[];
    const endNode = hydratedNodes.find((node) => node.id === 'end-node');
    expect(endNode?.data.status).toBe('completed');
    expect(endNode?.data.progress).toBe(100);
    expect((endNode?.data.result as any)?.finalOutput?.imageUrl).toBe(imageUrl);
    expect(setEdges).toHaveBeenCalledWith([] as Edge[]);
  });
});

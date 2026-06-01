// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

const addLogMock = vi.fn();
const undoMock = vi.fn(() => null);
const redoMock = vi.fn(() => null);
const takeSnapshotMock = vi.fn();
const setCenterMock = vi.fn();

vi.mock('reactflow', () => {
  const useNodesState = (initial: any[]) => {
    const [nodes, setNodes] = React.useState(initial);
    return [nodes, setNodes, vi.fn()] as const;
  };
  const useEdgesState = (initial: any[]) => {
    const [edges, setEdges] = React.useState(initial);
    return [edges, setEdges, vi.fn()] as const;
  };
  return {
    default: ({ children, onInit }: any) => {
      React.useEffect(() => {
        onInit?.({ setCenter: setCenterMock, fitView: vi.fn() });
      }, [onInit]);
      return <div data-testid="reactflow">{children}</div>;
    },
    ReactFlowProvider: ({ children }: any) => <>{children}</>,
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    useNodesState,
    useEdgesState,
    addEdge: (edge: any, eds: any[]) => [...eds, edge],
  };
});

vi.mock('../common/CachedImage', () => ({
  CachedImage: ({ src, alt, source: _source, ...props }: any) => (
    <img src={src} alt={alt} {...props} />
  ),
}));

vi.mock('./ComponentLibrary', () => ({
  ComponentLibrary: ({ headerActions }: any) => (
    <div data-testid="component-library">{headerActions}</div>
  ),
}));

vi.mock('./PropertiesPanel', () => ({
  PropertiesPanel: ({ selectedNode }: any) => (
    <div data-testid="properties-panel">selected:{selectedNode?.id}</div>
  ),
}));

vi.mock('./ExecutionLogPanel', () => ({
  ExecutionLogPanel: () => <div data-testid="execution-log-panel" />,
}));

vi.mock('./WorkflowTemplateSelector', () => ({
  WorkflowTemplateSelector: () => null,
}));

vi.mock('./WorkflowTemplateSaveDialog', () => ({
  WorkflowTemplateSaveDialog: () => null,
}));

vi.mock('./WorkflowExecutionHooks', () => ({
  useExecutionLogs: () => ({
    logs: [],
    addLog: addLogMock,
    clearLogs: vi.fn(),
  }),
}));

vi.mock('./useUndoRedo', () => ({
  useUndoRedo: () => ({
    undo: undoMock,
    redo: redoMock,
    canUndo: false,
    canRedo: false,
    takeSnapshot: takeSnapshotMock,
  }),
}));

vi.mock('./useAgentRegistry', () => ({
  useAgentRegistry: () => ({
    agents: [],
    loading: false,
    error: null,
    refreshAgents: vi.fn(async () => []),
  }),
}));

vi.mock('./workflowUtils', () => ({
  autoLayoutWorkflow: (nodes: any[]) => nodes,
  validateWorkflow: () => ({
    isValid: true,
    nodeErrors: {},
    edgeErrors: [],
    globalErrors: [],
  }),
}));

vi.mock('../../services/apiClient', () => ({
  getAuthHeaders: () => ({}),
}));

const {
  fetchWorkflowPreviewImagesMock,
  fetchWorkflowPreviewImagesWithMetaMock,
  fetchWorkflowPreviewMediaWithMetaMock,
} = vi.hoisted(() => ({
  fetchWorkflowPreviewImagesMock: vi.fn(),
  fetchWorkflowPreviewImagesWithMetaMock: vi.fn(),
  fetchWorkflowPreviewMediaWithMetaMock: vi.fn(),
}));

vi.mock('../../services/workflowHistoryService', () => ({
  fetchWorkflowPreviewImages: fetchWorkflowPreviewImagesMock,
  fetchWorkflowPreviewImagesWithMeta: fetchWorkflowPreviewImagesWithMetaMock,
  fetchWorkflowPreviewMediaWithMeta: fetchWorkflowPreviewMediaWithMetaMock,
}));

import { MultiAgentWorkflowEditorReactFlow } from './MultiAgentWorkflowEditorReactFlow';

const finalImageUrl = 'https://cdn.example.com/workflow/final.png';

const executionStatus = {
  executionId: 'exec-ui-end-result',
  finalStatus: 'completed' as const,
  finalResult: {
    finalOutput: {
      text: '生成完成',
      imageUrl: finalImageUrl,
      imageUrls: [finalImageUrl],
    },
  },
  finalError: undefined,
  logs: [],
  nodeStatuses: {
    'end-node': 'completed' as const,
  },
  nodeProgress: {
    'end-node': 100,
  },
  nodeResults: {
    'end-node': {
      finalOutput: {
        imageUrl: finalImageUrl,
        imageUrls: [finalImageUrl],
      },
    },
  },
  nodeErrors: {},
};

const loadedWorkflow = {
  token: 'loaded-end-workflow',
  name: '生成图片工作流',
  prompt: '生成图片',
  input: {},
  nodes: [
    {
      id: 'end-node',
      type: 'end',
      position: { x: 120, y: 80 },
      data: {
        label: '结束',
        description: 'final result',
        icon: 'E',
        iconColor: '#f43f5e',
        type: 'end',
      },
    },
  ],
  edges: [],
  executionStatus,
};

describe('MultiAgentWorkflowEditorReactFlow final result surface', () => {
  beforeEach(() => {
    addLogMock.mockReset();
    undoMock.mockClear();
    redoMock.mockClear();
    takeSnapshotMock.mockClear();
    setCenterMock.mockClear();
    fetchWorkflowPreviewImagesMock.mockReset();
    fetchWorkflowPreviewImagesWithMetaMock.mockReset();
    fetchWorkflowPreviewMediaWithMetaMock.mockReset();
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });
    fetchWorkflowPreviewMediaWithMetaMock.mockResolvedValue({
      mediaType: 'audio',
      items: [],
      skippedCount: 0,
      count: 0,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('opens the end-node properties panel instead of a separate final-result panel', async () => {
    render(
      <MultiAgentWorkflowEditorReactFlow
        loadedWorkflow={loadedWorkflow as any}
        executionStatus={executionStatus}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('1 节点 · 0 连接')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle('定位结束节点结果'));

    await waitFor(() => {
      expect(screen.getByTestId('properties-panel')).toHaveTextContent('selected:end-node');
    });
    expect(screen.queryByText('最终结果')).not.toBeInTheDocument();
    await waitFor(() => {
      expect(setCenterMock).toHaveBeenCalled();
    });
  });

  it('routes scoped image viewer requests to the parent result-image surface', async () => {
    const onOpenResultImages = vi.fn();
    render(
      <MultiAgentWorkflowEditorReactFlow
        loadedWorkflow={loadedWorkflow as any}
        executionStatus={executionStatus}
        onOpenResultImages={onOpenResultImages}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('1 节点 · 0 连接')).toBeInTheDocument();
    });

    const editorRoot = document.querySelector('[data-workflow-editor-scope]') as HTMLElement;
    const editorScopeId = editorRoot?.getAttribute('data-workflow-editor-scope');
    expect(editorScopeId).toBeTruthy();

    window.dispatchEvent(
      new CustomEvent('workflow:image-gallery-request', {
        detail: {
          editorScopeId,
          imageUrls: [finalImageUrl, 'https://cdn.example.com/workflow/second.png'],
          initialIndex: 1,
          title: '最终结果图片',
        },
      })
    );

    expect(onOpenResultImages).toHaveBeenCalledWith({
      title: '最终结果图片',
      imageUrls: [finalImageUrl, 'https://cdn.example.com/workflow/second.png'],
      initialIndex: 1,
    });
  });
});

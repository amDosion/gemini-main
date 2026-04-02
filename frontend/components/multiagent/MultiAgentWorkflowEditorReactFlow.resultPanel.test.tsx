// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

const addLogMock = vi.fn();
const clearLogsMock = vi.fn();
const undoMock = vi.fn(() => null);
const redoMock = vi.fn(() => null);
const takeSnapshotMock = vi.fn();

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
    default: ({ children }: any) => <div data-testid="reactflow">{children}</div>,
    ReactFlowProvider: ({ children }: any) => <>{children}</>,
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    useNodesState,
    useEdgesState,
    addEdge: (edge: any, eds: any[]) => [...eds, edge],
  };
});

vi.mock('./ComponentLibrary', () => ({
  ComponentLibrary: () => <div data-testid="component-library" />,
}));

vi.mock('./PropertiesPanel', () => ({
  PropertiesPanel: () => <div data-testid="properties-panel" />,
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
    clearLogs: clearLogsMock,
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

const { fetchWorkflowPreviewImagesMock, fetchWorkflowPreviewImagesWithMetaMock, fetchWorkflowPreviewMediaWithMetaMock } = vi.hoisted(() => ({
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

describe('MultiAgentWorkflowEditorReactFlow result panel image rendering', () => {
  const previewDataUrl =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z4xkAAAAASUVORK5CYII=';
  const ensureResultPanelOpen = async () => {
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    if (screen.queryAllByText('最终结果').length === 0) {
      const toggleButton = screen.getByRole('button', { name: /结果/ });
      await waitFor(() => {
        expect(toggleButton).not.toBeDisabled();
      });
      fireEvent.click(toggleButton);
    }
    await waitFor(() => {
      expect(screen.queryAllByText('最终结果').length).toBeGreaterThan(0);
    });
  };

  beforeEach(() => {
    addLogMock.mockReset();
    clearLogsMock.mockReset();
    undoMock.mockClear();
    redoMock.mockClear();
    takeSnapshotMock.mockClear();
    fetchWorkflowPreviewImagesMock.mockReset();
    fetchWorkflowPreviewImagesMock.mockResolvedValue([previewDataUrl]);
    fetchWorkflowPreviewImagesWithMetaMock.mockReset();
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [previewDataUrl],
      skippedCount: 0,
      count: 1,
    });
    fetchWorkflowPreviewMediaWithMetaMock.mockReset();
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

  it('renders preview image in final result panel when final result only contains local path', async () => {
    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-test-1',
          finalStatus: 'completed',
          finalResult: {
            finalOutput: {
              imageUrl: '/Users/demo/generated/final.png',
              imageUrls: ['/Users/demo/generated/final.png'],
            },
          },
          finalError: undefined,
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      expect(screen.getByAltText('workflow-output-image')).toBeInTheDocument();
    });
    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith('exec-ui-test-1', 40);

    const outputImage = screen.getByAltText('workflow-output-image') as HTMLImageElement;
    expect(outputImage.src.startsWith('data:image/png;base64,')).toBe(true);

    expect(screen.getByText('/Users/demo/generated/final.png')).toBeInTheDocument();
  });

  it('renders thought summaries and returned urls in final result panel', async () => {
    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-test-2',
          finalStatus: 'completed',
          finalResult: {
            finalOutput: {
              text: '图像生成完成',
              imageUrl: 'https://img.example.com/final.png',
              cloudUrl: 'https://cdn.example.com/final.png',
              thoughts: [
                { text: '先分析输入素材和约束。' },
                { summary: '再输出符合品牌调性的结果。' },
              ],
            },
          },
          finalError: undefined,
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      expect(screen.getByText('思考摘要')).toBeInTheDocument();
    });

    expect(screen.getByText('先分析输入素材和约束。')).toBeInTheDocument();
    expect(screen.getAllByText(/返回 URL/).length).toBeGreaterThan(0);
    expect(screen.getByText('https://img.example.com/final.png')).toBeInTheDocument();
  });

  it('loads preview images for failed execution history results', async () => {
    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-test-failed',
          finalStatus: 'failed',
          finalResult: {
            finalOutput: {
              text: '执行失败，但已有中间图片结果',
              imageUrl: '[inline-image-omitted; use history images preview/download endpoint]',
            },
          },
          finalError: 'workflow failed',
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      expect(screen.getAllByAltText('workflow-output-image').length).toBeGreaterThan(0);
    });

    const outputImages = screen.getAllByAltText('workflow-output-image') as HTMLImageElement[];
    expect(outputImages.some((img) => img.src.startsWith('data:image/png;base64,'))).toBe(true);
  });

  it('renders workflow video metadata badges in final result panel', async () => {
    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-test-video-meta',
          finalStatus: 'completed',
          finalResult: {
            finalOutput: {
              videoUrl: 'https://cdn.example.com/final.mp4',
              continuationStrategy: 'video_extension_chain',
              videoExtensionApplied: 3,
              totalDurationSeconds: 29,
              subtitleMode: 'vtt',
              subtitleFileCount: 1,
              continuedFromVideo: true,
            },
          },
          finalError: undefined,
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    expect(screen.getByText('延长 3 次')).toBeInTheDocument();
    expect(screen.getByText('总时长 29s')).toBeInTheDocument();
    expect(screen.getByText('字幕 · 1')).toBeInTheDocument();
    expect(screen.getByText('官方续接')).toBeInTheDocument();
  });

  it('does not auto-retry preview fetching after failure until user explicitly retries', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockRejectedValue(new Error('加载图片预览失败 (HTTP 500)'));

    render(
      <MultiAgentWorkflowEditorReactFlow
        loadedWorkflow={{
          token: 'retry-preview-workflow',
          nodes: [],
          edges: [],
          input: {
            imageUrl: previewDataUrl,
            imageUrls: [previewDataUrl],
          },
        }}
        executionStatus={{
          executionId: 'exec-ui-test-failed-no-spin',
          finalStatus: 'failed',
          finalResult: {
            finalOutput: {
              text: '执行失败，等待用户手动重试预览',
              imageUrl: '[inline-image-omitted; use history images preview/download endpoint]',
            },
          },
          finalError: 'workflow failed',
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    const countPreviewRequests = () => fetchWorkflowPreviewImagesWithMetaMock.mock.calls.length;

    await waitFor(() => {
      expect(countPreviewRequests()).toBe(1);
    });

    await new Promise((resolve) => window.setTimeout(resolve, 80));
    expect(countPreviewRequests()).toBe(1);

    const retryButton = await screen.findByRole('button', { name: '重试加载结果媒体' });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(countPreviewRequests()).toBe(2);
    });
  });

  it('adds warning log when preview metadata reports skipped images', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [previewDataUrl],
      skippedCount: 2,
      count: 1,
    });

    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-test-skipped',
          finalStatus: 'failed',
          finalResult: {
            finalOutput: {
              text: '执行失败，部分预览图被跳过',
              imageUrl: '[inline-image-omitted; use history images preview/download endpoint]',
            },
          },
          finalError: 'workflow failed',
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      const warningMessages = addLogMock.mock.calls
        .filter((call) => call[2] === 'warn')
        .map((call) => String(call[3] || ''));
      expect(warningMessages.some((message) => message.includes('跳过 2 张'))).toBe(true);
    });
  });

  it('does not truncate template result images when outputs contain many image nodes', async () => {
    const outputs: Record<string, any> = {};
    for (let i = 1; i <= 10; i += 1) {
      outputs[`node-${i}`] = {
        imageUrl: `https://img.example.com/batch-${i}.png`,
      };
    }

    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-many-images',
          finalStatus: 'completed',
          finalResult: {
            outputs,
            finalOutput: {
              text: '批量图片生成完成',
            },
          },
          finalError: undefined,
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      expect(screen.getByText('全部输出（10）')).toBeInTheDocument();
    });
  });

  it('renders audio and video outputs in the final result panel', async () => {
    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-media-output',
          finalStatus: 'completed',
          finalResult: {
            finalOutput: {
              text: '媒体生成完成',
              audioUrl: 'https://cdn.example.com/final.mp3',
              videoUrl: 'https://cdn.example.com/final.mp4',
            },
          },
          finalError: undefined,
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      expect(screen.getByText('媒体结果')).toBeInTheDocument();
    });

    const audio = document.querySelector('audio');
    const video = document.querySelector('video');
    expect(audio).toBeTruthy();
    expect(video).toBeTruthy();
    expect(video?.className).toContain('aspect-video');
    expect(screen.getByRole('button', { name: '视 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '音 1' })).toBeInTheDocument();
    expect(screen.getByText('结果预览')).toBeInTheDocument();
  });

  it('clears canvas state from top bar button', async () => {
    render(
      <MultiAgentWorkflowEditorReactFlow
        loadedWorkflow={{
          token: 'loaded-workflow-clear-canvas',
          name: 'Clear Me',
          prompt: 'hello world',
          input: {
            task: 'hello world',
            imageUrl: previewDataUrl,
          },
          nodes: [
            {
              id: 'node-start',
              type: 'start',
              position: { x: 0, y: 0 },
              data: {
                label: 'Start',
                description: 'start node',
                icon: 'S',
                iconColor: '#0ea5e9',
                type: 'start',
              },
            },
          ],
          edges: [],
        }}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('1 节点 · 0 连接')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /清空/i }));

    await waitFor(() => {
      expect(screen.getByText('0 节点 · 0 连接')).toBeInTheDocument();
    });
    expect(addLogMock).toHaveBeenCalledWith('system', '系统', 'info', '已清除画布');
  });

  it('hydrates audio and video previews from history media endpoints when final result has no direct media urls', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });
    fetchWorkflowPreviewMediaWithMetaMock.mockImplementation(async (_executionId: string, mediaKind: 'audio' | 'video') => {
      if (mediaKind === 'audio') {
        return {
          mediaType: 'audio' as const,
          items: [{ index: 1, previewUrl: 'https://cdn.example.com/history.mp3', sourceUrl: '', resolvedUrl: '', mimeType: 'audio/mpeg', fileName: 'history.mp3' }],
          skippedCount: 0,
          count: 1,
        };
      }
      return {
        mediaType: 'video' as const,
        items: [{ index: 1, previewUrl: 'https://cdn.example.com/history.mp4', sourceUrl: '', resolvedUrl: '', mimeType: 'video/mp4', fileName: 'history.mp4' }],
        skippedCount: 0,
        count: 1,
      };
    });

    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-media-preview',
          finalStatus: 'completed',
          finalResult: {
            finalOutput: {
              text: '媒体结果待补全',
            },
          },
          finalError: undefined,
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith('exec-ui-media-preview', 'audio', 12);
      expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith('exec-ui-media-preview', 'video', 12);
    });
    await waitFor(() => {
      expect(document.querySelector('audio')).toBeTruthy();
      expect(document.querySelector('video')).toBeTruthy();
    });
  });

  it('renders execution-status preview audio and video without extra history media fetches', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });

    render(
      <MultiAgentWorkflowEditorReactFlow
        executionStatus={{
          executionId: 'exec-ui-status-preview-media',
          finalStatus: 'completed',
          finalResult: {
            finalOutput: {
              text: '媒体预览已在状态层恢复',
            },
          },
          resultPreviewAudioUrls: ['https://cdn.example.com/status-preview.mp3'],
          resultPreviewVideoUrls: ['https://cdn.example.com/status-preview.mp4'],
          finalError: undefined,
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      expect(document.querySelector('audio')).toBeTruthy();
      expect(document.querySelector('video')).toBeTruthy();
    });

    expect(fetchWorkflowPreviewMediaWithMetaMock).not.toHaveBeenCalled();
  });

  it('does not surface input-video node output as final generated video result', async () => {
    render(
      <MultiAgentWorkflowEditorReactFlow
        loadedWorkflow={{
          token: 'continuation-source-vs-output',
          nodes: [
            {
              id: 'input-video-long-continuation',
              type: 'input_video',
              position: { x: 0, y: 0 },
              data: {
                label: '上一段视频',
                description: 'input video node',
                icon: 'V',
                iconColor: '#6366f1',
                type: 'input_video',
              },
            },
            {
              id: 'agent-video-long-continuation',
              type: 'agent',
              position: { x: 200, y: 0 },
              data: {
                label: '长视频续写',
                description: 'agent node',
                icon: 'A',
                iconColor: '#d946ef',
                type: 'agent',
              },
            },
          ],
          edges: [],
        }}
        executionStatus={{
          executionId: 'exec-ui-continuation-source-vs-output',
          finalStatus: 'completed',
          finalResult: {
            finalOutput: {
              text: '续写完成',
              videoUrl: 'https://cdn.example.com/generated.mp4',
            },
            outputs: {
              'input-video-long-continuation': {
                videoUrl: 'https://cdn.example.com/source.mp4',
                videoUrls: ['https://cdn.example.com/source.mp4'],
              },
            },
          },
          finalError: undefined,
          logs: [],
          nodeStatuses: {},
          nodeProgress: {},
          nodeResults: {},
          nodeErrors: {},
        }}
      />
    );
    await ensureResultPanelOpen();

    await waitFor(() => {
      expect(screen.getByText('https://cdn.example.com/generated.mp4')).toBeInTheDocument();
    });

    expect(screen.queryByText('https://cdn.example.com/source.mp4')).not.toBeInTheDocument();
    expect(document.querySelectorAll('video')).toHaveLength(2);
  });
});

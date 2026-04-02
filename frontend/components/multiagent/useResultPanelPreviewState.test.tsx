// @vitest-environment jsdom
import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Node } from 'reactflow';
import type { ExecutionStatus, WorkflowNodeData } from './types';
import { extractAudioUrls, extractImageUrls, extractVideoUrls } from './workflowResultUtils';
import { useResultPanelPreviewState } from './useResultPanelPreviewState';

const { fetchWorkflowPreviewImagesWithMetaMock, fetchWorkflowPreviewMediaWithMetaMock } = vi.hoisted(() => ({
  fetchWorkflowPreviewImagesWithMetaMock: vi.fn(),
  fetchWorkflowPreviewMediaWithMetaMock: vi.fn(),
}));

vi.mock('../../services/workflowHistoryService', () => ({
  fetchWorkflowPreviewImagesWithMeta: fetchWorkflowPreviewImagesWithMetaMock,
  fetchWorkflowPreviewMediaWithMeta: fetchWorkflowPreviewMediaWithMetaMock,
}));

interface HookHarnessProps {
  executionStatus?: ExecutionStatus;
  addLog: ReturnType<typeof vi.fn>;
  initialFinalResult?: any;
  initialNodes?: Node<WorkflowNodeData>[];
}

const buildExecutionStatus = (overrides: Partial<ExecutionStatus> = {}): ExecutionStatus => ({
  executionId: 'exec-hook-test',
  finalStatus: 'failed',
  finalResult: {
    finalOutput: {
      text: '执行失败，等待预览图片加载',
      imageUrl: '[inline-image-omitted; use history images preview/download endpoint]',
    },
  },
  finalError: 'workflow failed',
  logs: [],
  nodeStatuses: {},
  nodeProgress: {},
  nodeResults: {},
  nodeErrors: {},
  ...overrides,
});

const useHookHarness = ({ executionStatus, addLog, initialFinalResult, initialNodes }: HookHarnessProps) => {
  const [finalResult, setFinalResult] = React.useState<any>(initialFinalResult ?? executionStatus?.finalResult ?? null);
  const [nodes, setNodes] = React.useState<Node<WorkflowNodeData>[]>(initialNodes || []);

  const previewState = useResultPanelPreviewState({
    executionStatus,
    finalResult,
    setFinalResult,
    setNodes,
    addLog,
  });

  return {
    ...previewState,
    finalResult,
    nodes,
  };
};

describe('useResultPanelPreviewState', () => {
  const previewDataUrlA =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z4xkAAAAASUVORK5CYII=';
  const previewDataUrlB =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAMAAABFaP0WAAAABlBMVEUAAAD///+l2Z/dAAAAEElEQVR4nGP4z8AARMAEMAAAHQABf7c2WwAAAABJRU5ErkJggg==';

  beforeEach(() => {
    fetchWorkflowPreviewImagesWithMetaMock.mockReset();
    fetchWorkflowPreviewMediaWithMetaMock.mockReset();
  });

  it('consumes preview metadata with explicit limit and logs skipped warning', async () => {
    const addLog = vi.fn();
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [previewDataUrlA],
      skippedCount: 2,
      count: 1,
    });

    const executionStatus = buildExecutionStatus({ executionId: 'exec-hook-meta' });
    const { result } = renderHook((props: HookHarnessProps) => useHookHarness(props), {
      initialProps: {
        executionStatus,
        addLog,
      },
    });

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith('exec-hook-meta', 40);
    });
    await waitFor(() => {
      const warningMessages = addLog.mock.calls
        .filter((call) => call[2] === 'warn')
        .map((call) => String(call[3] || ''));
      expect(warningMessages.some((message) => message.includes('跳过 2 张'))).toBe(true);
    });
    expect(result.current.resultPanelPreviewImageUrls).toEqual([previewDataUrlA]);
  });

  it('does not auto-retry after failure until explicit retry is triggered', async () => {
    const addLog = vi.fn();
    fetchWorkflowPreviewImagesWithMetaMock
      .mockRejectedValueOnce(new Error('加载图片预览失败 (HTTP 500)'))
      .mockResolvedValueOnce({
        imageUrls: [previewDataUrlA],
        skippedCount: 0,
        count: 1,
      });

    const executionStatus = buildExecutionStatus({ executionId: 'exec-hook-no-auto-retry' });
    const { result, rerender } = renderHook((props: HookHarnessProps) => useHookHarness(props), {
      initialProps: {
        executionStatus,
        addLog,
      },
    });

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(1);
    });
    rerender({
      executionStatus: { ...executionStatus },
      addLog,
    });
    await new Promise((resolve) => window.setTimeout(resolve, 80));
    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(1);

    act(() => {
      result.current.handleRetryResultPreview();
    });

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(2);
    });
    const infoMessages = addLog.mock.calls
      .filter((call) => call[2] === 'info')
      .map((call) => String(call[3] || ''));
    expect(infoMessages).toContain('已触发结果媒体重新加载');
  });

  it('merges fetched preview images into final result and end-node result', async () => {
    const addLog = vi.fn();
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [previewDataUrlA],
      skippedCount: 0,
      count: 1,
    });

    const initialFinalResult = {
      finalOutput: {
        text: '生成完成',
      },
    };
    const initialNodes = [{
      id: 'end-node-1',
      type: 'end',
      position: { x: 0, y: 0 },
      data: {
        label: '结束',
        description: '结束节点',
        icon: 'square',
        iconColor: '#fff',
        type: 'end',
        result: {
          finalOutput: {
            text: '节点结果',
          },
        },
      },
    }] as Node<WorkflowNodeData>[];

    const executionStatus = buildExecutionStatus({
      executionId: 'exec-hook-merge',
      finalStatus: 'completed',
      finalResult: initialFinalResult,
      finalError: undefined,
    });
    const { result } = renderHook((props: HookHarnessProps) => useHookHarness(props), {
      initialProps: {
        executionStatus,
        addLog,
        initialFinalResult,
        initialNodes,
      },
    });

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith('exec-hook-merge', 40);
    });
    await waitFor(() => {
      expect(extractImageUrls(result.current.finalResult)).toContain(previewDataUrlA);
    });

    const endNode = result.current.nodes.find((node) => node.id === 'end-node-1');
    expect(endNode).toBeTruthy();
    expect(extractImageUrls(endNode?.data?.result)).toContain(previewDataUrlA);
  });

  it('aggregates execution-status and fetched preview image urls without duplicates', async () => {
    const addLog = vi.fn();
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [previewDataUrlA],
      skippedCount: 0,
      count: 1,
    });

    const baseStatus = buildExecutionStatus({
      executionId: 'exec-hook-aggregate',
      finalStatus: 'completed',
    });
    const { result, rerender } = renderHook((props: HookHarnessProps) => useHookHarness(props), {
      initialProps: {
        executionStatus: baseStatus,
        addLog,
      },
    });

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(1);
    });

    rerender({
      executionStatus: {
        ...baseStatus,
        resultPreviewImageUrls: [previewDataUrlB, previewDataUrlA],
      },
      addLog,
    });

    await waitFor(() => {
      expect(result.current.mergedResultPanelPreviewImageUrls).toEqual([previewDataUrlB, previewDataUrlA]);
    });
    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(1);
  });

  it('caps execution-status preview images to the explicit preview limit', async () => {
    const addLog = vi.fn();
    const manyPreviewImages = Array.from({ length: 60 }, (_, index) => `data:image/png;base64,preview-${index}`);
    const executionStatus = buildExecutionStatus({
      executionId: 'exec-hook-limit-cap',
      finalStatus: 'completed',
      resultPreviewImageUrls: manyPreviewImages,
    });

    const { result } = renderHook((props: HookHarnessProps) => useHookHarness(props), {
      initialProps: {
        executionStatus,
        addLog,
      },
    });

    await waitFor(() => {
      expect(result.current.executionStatusPreviewImageUrls).toHaveLength(40);
    });
    expect(result.current.mergedResultPanelPreviewImageUrls).toHaveLength(40);
    expect(fetchWorkflowPreviewImagesWithMetaMock).not.toHaveBeenCalled();
  });

  it('caps merged preview images to limit when cached and execution-status lists are both present', async () => {
    const addLog = vi.fn();
    const statusPreviewImages = Array.from(
      { length: 25 },
      (_, index) => `data:image/png;base64,status-${index}`
    );
    const fetchedPreviewImages = Array.from(
      { length: 30 },
      (_, index) => `data:image/png;base64,fetched-${index}`
    );
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: fetchedPreviewImages,
      skippedCount: 0,
      count: fetchedPreviewImages.length,
    });

    const executionStatus = buildExecutionStatus({
      executionId: 'exec-hook-merged-cap',
      finalStatus: 'completed',
    });

    const { result, rerender } = renderHook((props: HookHarnessProps) => useHookHarness(props), {
      initialProps: {
        executionStatus,
        addLog,
      },
    });

    await waitFor(() => {
      expect(result.current.resultPanelPreviewImageUrls).toHaveLength(30);
    });
    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith('exec-hook-merged-cap', 40);

    rerender({
      executionStatus: {
        ...executionStatus,
        resultPreviewImageUrls: statusPreviewImages,
      },
      addLog,
    });

    await waitFor(() => {
      expect(result.current.mergedResultPanelPreviewImageUrls).toHaveLength(40);
    });
  });

  it('merges fetched audio and video previews into final result and end-node result', async () => {
    const addLog = vi.fn();
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });
    fetchWorkflowPreviewMediaWithMetaMock.mockImplementation(async (_executionId: string, mediaKind: 'audio' | 'video') => {
      if (mediaKind === 'audio') {
        return {
          mediaType: 'audio' as const,
          items: [{ index: 1, previewUrl: 'https://cdn.example.com/final.mp3', sourceUrl: '', resolvedUrl: '', mimeType: 'audio/mpeg', fileName: 'final.mp3' }],
          skippedCount: 0,
          count: 1,
        };
      }
      return {
        mediaType: 'video' as const,
        items: [{ index: 1, previewUrl: 'https://cdn.example.com/final.mp4', sourceUrl: '', resolvedUrl: '', mimeType: 'video/mp4', fileName: 'final.mp4' }],
        skippedCount: 0,
        count: 1,
      };
    });

    const initialFinalResult = {
      finalOutput: {
        text: '媒体执行完成',
      },
    };
    const initialNodes = [{
      id: 'end-node-media',
      type: 'end',
      position: { x: 0, y: 0 },
      data: {
        label: '结束',
        description: '结束节点',
        icon: 'square',
        iconColor: '#fff',
        type: 'end',
        result: {
          finalOutput: {
            text: '节点结果',
          },
        },
      },
    }] as Node<WorkflowNodeData>[];

    const executionStatus = buildExecutionStatus({
      executionId: 'exec-hook-media-merge',
      finalStatus: 'completed',
      finalResult: initialFinalResult,
      finalError: undefined,
    });
    const { result } = renderHook((props: HookHarnessProps) => useHookHarness(props), {
      initialProps: {
        executionStatus,
        addLog,
        initialFinalResult,
        initialNodes,
      },
    });

    await waitFor(() => {
      expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith('exec-hook-media-merge', 'audio', 12);
      expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith('exec-hook-media-merge', 'video', 12);
    });
    await waitFor(() => {
      expect(extractAudioUrls(result.current.finalResult)).toContain('https://cdn.example.com/final.mp3');
      expect(extractVideoUrls(result.current.finalResult)).toContain('https://cdn.example.com/final.mp4');
    });

    const endNode = result.current.nodes.find((node) => node.id === 'end-node-media');
    expect(endNode).toBeTruthy();
    expect(extractAudioUrls(endNode?.data?.result)).toContain('https://cdn.example.com/final.mp3');
    expect(extractVideoUrls(endNode?.data?.result)).toContain('https://cdn.example.com/final.mp4');
  });

  it('uses execution-status audio and video preview urls without extra preview fetches', async () => {
    const addLog = vi.fn();
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });

    const initialFinalResult = {
      finalOutput: {
        text: 'history restore media',
      },
    };
    const executionStatus = buildExecutionStatus({
      executionId: 'exec-hook-status-media',
      finalStatus: 'completed',
      finalResult: initialFinalResult,
      finalError: undefined,
      resultPreviewAudioUrls: ['https://cdn.example.com/status.mp3'],
      resultPreviewVideoUrls: ['https://cdn.example.com/status.mp4'],
    });

    const { result } = renderHook((props: HookHarnessProps) => useHookHarness(props), {
      initialProps: {
        executionStatus,
        addLog,
        initialFinalResult,
      },
    });

    await waitFor(() => {
      expect(extractAudioUrls(result.current.finalResult)).toContain('https://cdn.example.com/status.mp3');
      expect(extractVideoUrls(result.current.finalResult)).toContain('https://cdn.example.com/status.mp4');
    });

    expect(fetchWorkflowPreviewMediaWithMetaMock).not.toHaveBeenCalled();
    expect(result.current.executionStatusPreviewAudioUrls).toEqual(['https://cdn.example.com/status.mp3']);
    expect(result.current.executionStatusPreviewVideoUrls).toEqual(['https://cdn.example.com/status.mp4']);
    expect(result.current.resultPanelPreviewAudioUrls).toEqual(['https://cdn.example.com/status.mp3']);
    expect(result.current.resultPanelPreviewVideoUrls).toEqual(['https://cdn.example.com/status.mp4']);
  });
});

// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { WorkflowHistoryItem } from './types';
import { useWorkflowHistoryPreviewState } from './useWorkflowHistoryPreviewState';

const {
  fetchWorkflowPreviewImagesWithMetaMock,
  fetchWorkflowPreviewMediaWithMetaMock,
} = vi.hoisted(() => ({
  fetchWorkflowPreviewImagesWithMetaMock: vi.fn(),
  fetchWorkflowPreviewMediaWithMetaMock: vi.fn(),
}));

vi.mock('../../../services/workflowHistoryService', () => ({
  fetchWorkflowPreviewImagesWithMeta: fetchWorkflowPreviewImagesWithMetaMock,
  fetchWorkflowPreviewMediaWithMeta: fetchWorkflowPreviewMediaWithMetaMock,
}));

const buildHistoryItem = (executionId: string): WorkflowHistoryItem => ({
  id: executionId,
  status: 'completed',
  title: `Title ${executionId}`,
  source: 'history',
  task: `Task ${executionId}`,
  resultPreview: '',
  resultImageCount: 1,
  resultImageUrls: [],
  resultAudioCount: 0,
  resultAudioUrls: [],
  resultVideoCount: 0,
  resultVideoUrls: [],
  primaryRuntime: '',
  runtimeHints: [],
  startedAt: Date.now(),
  nodeCount: 0,
  edgeCount: 0,
});

describe('useWorkflowHistoryPreviewState', () => {
  beforeEach(() => {
    fetchWorkflowPreviewImagesWithMetaMock.mockReset();
    fetchWorkflowPreviewMediaWithMetaMock.mockReset();
  });

  it('consumes detail-preview metadata with explicit limit and warns on skipped images', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const showError = vi.fn();
    const releaseRequestController = vi.fn();
    const isMountedRef = { current: true };

    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: ['preview-exec-meta'],
      skippedCount: 2,
      count: 1,
    });

    const controller = new AbortController();
    const { result } = renderHook(() =>
      useWorkflowHistoryPreviewState({
        isMountedRef,
        createRequestController: () => new AbortController(),
        releaseRequestController,
        showError,
      })
    );

    let previewImagesForDetail: string[] | null = null;
    await act(async () => {
      previewImagesForDetail = await result.current.resolveHistoryDetailPreviewImages({
        executionId: 'exec-meta',
        summaryImageCount: 2,
        signal: controller.signal,
        isStaleRequest: () => false,
      });
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
      'exec-meta',
      40,
      controller.signal
    );
    expect(previewImagesForDetail).toEqual(['preview-exec-meta']);
    expect(result.current.historyPreviewImages['exec-meta']).toEqual(['preview-exec-meta']);
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('execution=exec-meta'));
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('skipped=2'));
    expect(showError).not.toHaveBeenCalled();
  });

  it('toggles sidebar preview with explicit limit and warns on skipped images', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const showError = vi.fn();
    const releaseRequestController = vi.fn();
    const isMountedRef = { current: true };

    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: ['preview-exec-toggle'],
      skippedCount: 1,
      count: 1,
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryPreviewState({
        isMountedRef,
        createRequestController: () => new AbortController(),
        releaseRequestController,
        showError,
      })
    );

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview(buildHistoryItem('exec-toggle'));
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
      'exec-toggle',
      40,
      expect.any(AbortSignal)
    );
    expect(result.current.expandedPreviewHistoryId).toBe('exec-toggle');
    expect(result.current.historyPreviewImages['exec-toggle']).toEqual(['preview-exec-toggle']);
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('execution=exec-toggle'));
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('skipped=1'));
    expect(showError).not.toHaveBeenCalled();
  });

  it('does not auto-retry or fallback after sidebar preview fetch failure', async () => {
    const showError = vi.fn();
    const releaseRequestController = vi.fn();
    const isMountedRef = { current: true };

    fetchWorkflowPreviewImagesWithMetaMock.mockRejectedValueOnce(new Error('加载图片预览失败 (HTTP 500)'));

    const { result } = renderHook(() =>
      useWorkflowHistoryPreviewState({
        isMountedRef,
        createRequestController: () => new AbortController(),
        releaseRequestController,
        showError,
      })
    );

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview(buildHistoryItem('exec-no-retry'));
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(1);
    expect(result.current.historyPreviewImages['exec-no-retry']).toBeUndefined();
    expect(showError).toHaveBeenCalledWith('加载图片预览失败 (HTTP 500)');

    await new Promise((resolve) => window.setTimeout(resolve, 50));
    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(1);
  });

  it('fails closed for detail preview fetch errors without silent fallback', async () => {
    const showError = vi.fn();
    const releaseRequestController = vi.fn();
    const isMountedRef = { current: true };
    const controller = new AbortController();

    fetchWorkflowPreviewImagesWithMetaMock.mockRejectedValue(new Error('加载图片预览失败 (HTTP 500)'));

    const { result } = renderHook(() =>
      useWorkflowHistoryPreviewState({
        isMountedRef,
        createRequestController: () => new AbortController(),
        releaseRequestController,
        showError,
      })
    );

    let previewImagesForDetail: string[] | null = ['placeholder'];
    await act(async () => {
      previewImagesForDetail = await result.current.resolveHistoryDetailPreviewImages({
        executionId: 'exec-detail-fail-closed',
        summaryImageCount: 1,
        signal: controller.signal,
        isStaleRequest: () => false,
      });
    });

    expect(previewImagesForDetail).toBeNull();
    expect(showError).toHaveBeenCalledWith('加载图片预览失败 (HTTP 500)');
  });

  it('loads video preview metadata into media cache without image fallback', async () => {
    const showError = vi.fn();
    const releaseRequestController = vi.fn();
    const isMountedRef = { current: true };

    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });
    fetchWorkflowPreviewMediaWithMetaMock.mockResolvedValue({
      mediaType: 'video',
      items: [
        {
          index: 1,
          sourceUrl: 'https://cdn.example.com/video/1.mp4',
          resolvedUrl: 'https://cdn.example.com/video/1.mp4',
          mimeType: 'video/mp4',
          fileName: 'video-01.mp4',
          previewUrl: '/api/workflows/history/exec-video/video/items/1',
        },
      ],
      skippedCount: 0,
      count: 1,
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryPreviewState({
        isMountedRef,
        createRequestController: () => new AbortController(),
        releaseRequestController,
        showError,
      })
    );

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview({
        ...buildHistoryItem('exec-video'),
        resultImageCount: 0,
        resultVideoCount: 1,
      });
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).not.toHaveBeenCalled();
    expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith(
      'exec-video',
      'video',
      12,
      expect.any(AbortSignal)
    );
    expect(result.current.historyPreviewMedia['exec-video']?.videoItems).toHaveLength(1);
    expect(result.current.expandedPreviewHistoryId).toBe('exec-video');
    expect(showError).not.toHaveBeenCalled();
  });

  it('keeps empty media preview as cached non-error state', async () => {
    const showError = vi.fn();
    const releaseRequestController = vi.fn();
    const isMountedRef = { current: true };

    fetchWorkflowPreviewMediaWithMetaMock.mockResolvedValue({
      mediaType: 'video',
      items: [],
      skippedCount: 0,
      count: 0,
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryPreviewState({
        isMountedRef,
        createRequestController: () => new AbortController(),
        releaseRequestController,
        showError,
      })
    );

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview({
        ...buildHistoryItem('exec-empty-video'),
        resultImageCount: 0,
        resultVideoCount: 1,
      });
    });

    expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledTimes(1);
    expect(result.current.expandedPreviewHistoryId).toBe('exec-empty-video');
    expect(result.current.historyPreviewMedia['exec-empty-video']).toEqual({
      audioItems: [],
      videoItems: [],
    });
    expect(showError).not.toHaveBeenCalled();

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview({
        ...buildHistoryItem('exec-empty-video'),
        resultImageCount: 0,
        resultVideoCount: 1,
      });
    });
    expect(result.current.expandedPreviewHistoryId).toBeNull();

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview({
        ...buildHistoryItem('exec-empty-video'),
        resultImageCount: 0,
        resultVideoCount: 1,
      });
    });
    expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledTimes(1);
    expect(result.current.expandedPreviewHistoryId).toBe('exec-empty-video');
  });

  it('resolves audio and video preview urls for history detail restoration', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const showError = vi.fn();
    const releaseRequestController = vi.fn();
    const isMountedRef = { current: true };
    const controller = new AbortController();

    fetchWorkflowPreviewMediaWithMetaMock.mockImplementation(async (_executionId: string, mediaKind: 'audio' | 'video') => {
      if (mediaKind === 'audio') {
        return {
          mediaType: 'audio' as const,
          items: [
            {
              index: 1,
              sourceUrl: 'https://cdn.example.com/audio/1.mp3',
              resolvedUrl: 'https://cdn.example.com/audio/1.mp3',
              mimeType: 'audio/mpeg',
              fileName: 'audio-01.mp3',
              previewUrl: '/api/workflows/history/exec-media/audio/items/1',
            },
          ],
          skippedCount: 0,
          count: 1,
        };
      }
      return {
        mediaType: 'video' as const,
        items: [
          {
            index: 1,
            sourceUrl: 'https://cdn.example.com/video/1.mp4',
            resolvedUrl: 'https://cdn.example.com/video/1.mp4',
            mimeType: 'video/mp4',
            fileName: 'video-01.mp4',
            previewUrl: '/api/workflows/history/exec-media/video/items/1',
          },
        ],
        skippedCount: 1,
        count: 1,
      };
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryPreviewState({
        isMountedRef,
        createRequestController: () => new AbortController(),
        releaseRequestController,
        showError,
      })
    );

    let previewMediaForDetail: { audioUrls: string[]; videoUrls: string[] } | null = null;
    await act(async () => {
      previewMediaForDetail = await result.current.resolveHistoryDetailPreviewMedia({
        executionId: 'exec-media',
        summaryAudioCount: 1,
        summaryVideoCount: 1,
        signal: controller.signal,
        isStaleRequest: () => false,
      });
    });

    expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith(
      'exec-media',
      'audio',
      12,
      controller.signal
    );
    expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith(
      'exec-media',
      'video',
      12,
      controller.signal
    );
    expect(previewMediaForDetail).toEqual({
      audioUrls: ['/api/workflows/history/exec-media/audio/items/1'],
      videoUrls: ['/api/workflows/history/exec-media/video/items/1'],
    });
    expect(result.current.historyPreviewMedia['exec-media']?.audioItems).toHaveLength(1);
    expect(result.current.historyPreviewMedia['exec-media']?.videoItems).toHaveLength(1);
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('kind=video'));
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('skipped=1'));
    expect(showError).not.toHaveBeenCalled();
  });
});

// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkflowHistoryController } from './useWorkflowHistoryController';

const {
  requestJsonMock,
  fetchWorkflowPreviewImagesWithMetaMock,
  fetchWorkflowPreviewMediaWithMetaMock,
} = vi.hoisted(() => ({
  requestJsonMock: vi.fn(),
  fetchWorkflowPreviewImagesWithMetaMock: vi.fn(),
  fetchWorkflowPreviewMediaWithMetaMock: vi.fn(),
}));

vi.mock('../../../services/http', () => ({
  requestJson: requestJsonMock,
}));

vi.mock('../../../services/workflowHistoryService', () => ({
  fetchWorkflowPreviewImagesWithMeta: fetchWorkflowPreviewImagesWithMetaMock,
  fetchWorkflowPreviewMediaWithMeta: fetchWorkflowPreviewMediaWithMetaMock,
}));

describe('useWorkflowHistoryController media', () => {
  beforeEach(() => {
    requestJsonMock.mockReset();
    fetchWorkflowPreviewImagesWithMetaMock.mockReset();
    fetchWorkflowPreviewMediaWithMetaMock.mockReset();
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({ imageUrls: [], skippedCount: 0, count: 0 });
    fetchWorkflowPreviewMediaWithMetaMock.mockResolvedValue({ mediaType: 'video', items: [], skippedCount: 0, count: 0 });
  });

  it('maps video summary fields and loads video preview metadata', async () => {
    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({
          executions: [
            {
              id: 'exec-video',
              title: 'Video title',
              task: 'Video task',
              status: 'completed',
              resultSummary: {
                imageCount: 0,
                imageUrls: [],
                videoCount: 1,
                videoUrls: ['https://cdn.example.com/video/1.mp4'],
                continuationStrategy: 'video_extension_chain',
                videoExtensionApplied: 3,
                totalDurationSeconds: 29,
                subtitleMode: 'vtt',
                subtitleFileCount: 1,
              },
            },
          ],
        });
      }
      throw new Error(`Unexpected URL: ${url}`);
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
      useWorkflowHistoryController({
        setExecutionStatus: vi.fn(),
        showError: vi.fn(),
      })
    );

    await waitFor(() => {
      expect(result.current.displayedWorkflowHistory).toHaveLength(1);
    });

    expect(result.current.displayedWorkflowHistory[0].resultVideoCount).toBe(1);
    expect(result.current.displayedWorkflowHistory[0].resultVideoUrls).toEqual(['https://cdn.example.com/video/1.mp4']);
    expect(result.current.displayedWorkflowHistory[0].continuationStrategy).toBe('video_extension_chain');
    expect(result.current.displayedWorkflowHistory[0].videoExtensionApplied).toBe(3);
    expect(result.current.displayedWorkflowHistory[0].totalDurationSeconds).toBe(29);
    expect(result.current.displayedWorkflowHistory[0].subtitleMode).toBe('vtt');
    expect(result.current.displayedWorkflowHistory[0].subtitleFileCount).toBe(1);

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview(result.current.displayedWorkflowHistory[0]);
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).not.toHaveBeenCalled();
    expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith(
      'exec-video',
      'video',
      12,
      expect.any(AbortSignal)
    );
    expect(result.current.historyPreviewMedia['exec-video']?.videoItems).toHaveLength(1);
  });

  it('hydrates execution status with preview audio and video urls when loading history detail', async () => {
    const setExecutionStatus = vi.fn();
    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({ executions: [] });
      }
      if (url === '/api/workflows/history/exec-history-media') {
        return Promise.resolve({
          id: 'exec-history-media',
          title: 'History media',
          task: 'Restore media',
          status: 'completed',
          workflow: { nodes: [], edges: [] },
          input: { task: 'Restore media' },
          resultSummary: {
            imageCount: 0,
            imageUrls: [],
            audioCount: 1,
            audioUrls: [],
            videoCount: 1,
            videoUrls: [],
          },
        });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
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
              previewUrl: '/api/workflows/history/exec-history-media/audio/items/1',
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
            previewUrl: '/api/workflows/history/exec-history-media/video/items/1',
          },
        ],
        skippedCount: 0,
        count: 1,
      };
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError: vi.fn(),
      })
    );

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history?limit=100',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    await act(async () => {
      await result.current.handleLoadWorkflowFromHistory('exec-history-media');
    });

    const latestExecutionStatus = setExecutionStatus.mock.calls.at(-1)?.[0];
    expect(latestExecutionStatus?.executionId).toBe('exec-history-media');
    expect(latestExecutionStatus?.resultPreviewAudioUrls).toEqual([
      '/api/workflows/history/exec-history-media/audio/items/1',
    ]);
    expect(latestExecutionStatus?.resultPreviewVideoUrls).toEqual([
      '/api/workflows/history/exec-history-media/video/items/1',
    ]);
  });
});

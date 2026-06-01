// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkflowHistoryController } from './useWorkflowHistoryController';
import { __resetWorkflowPreviewCacheForTest } from '../../../services/workflowPreviewCache';
import { clearPrivateMemoryCaches } from '../../../services/privateClientCache';
import { setPrivateCacheUserScope } from '../../../services/privateCacheScope';

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

const createDeferred = <T>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const createHistoryDetailPayload = (executionId: string, overrides: Record<string, any> = {}) => ({
  id: executionId,
  title: `Title ${executionId}`,
  task: `Task ${executionId}`,
  status: 'completed',
  workflow: {
    nodes: [],
    edges: [],
  },
  input: {
    task: `Task ${executionId}`,
  },
  resultSummary: {
    imageCount: 0,
    imageUrls: [],
    audioCount: 0,
    audioUrls: [],
    videoCount: 0,
    videoUrls: [],
  },
  ...overrides,
});

describe('useWorkflowHistoryController race handling', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    requestJsonMock.mockReset();
    fetchWorkflowPreviewImagesWithMetaMock.mockReset();
    fetchWorkflowPreviewMediaWithMetaMock.mockReset();
    __resetWorkflowPreviewCacheForTest();

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({ executions: [] });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });
    fetchWorkflowPreviewMediaWithMetaMock.mockResolvedValue({
      mediaType: 'video',
      items: [],
      skippedCount: 0,
      count: 0,
    });
    setPrivateCacheUserScope(null);
  });

  it('does not apply a late history list response after private cache lifecycle resets', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const historyList = createDeferred<any>();
    setPrivateCacheUserScope('user-a');

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return historyList.promise;
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history?limit=100',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    setPrivateCacheUserScope('user-b');
    clearPrivateMemoryCaches();

    await act(async () => {
      historyList.resolve({
        executions: [
          {
            id: 'exec-user-a',
            title: 'User A history',
            task: 'Private task',
            status: 'completed',
            resultSummary: { imageCount: 0, imageUrls: [] },
          },
        ],
      });
      await historyList.promise;
    });

    expect(result.current.displayedWorkflowHistory).toEqual([]);
    expect(result.current.historyLoading).toBe(false);
  });

  it('clears loaded history and sidebar previews when the private user scope changes', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    setPrivateCacheUserScope('user-a');

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({
          executions: [
            {
              id: 'exec-user-a-visible',
              title: 'User A history',
              task: 'Private task',
              status: 'completed',
              resultSummary: { imageCount: 1, imageUrls: [] },
            },
          ],
        });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: ['https://cdn.example.com/user-a-preview.png'],
      skippedCount: 0,
      count: 1,
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(result.current.displayedWorkflowHistory.map((item) => item.id)).toEqual([
        'exec-user-a-visible',
      ]);
    });

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview(
        result.current.displayedWorkflowHistory[0]
      );
    });

    expect(result.current.expandedPreviewHistoryId).toBe('exec-user-a-visible');
    expect(result.current.historyPreviewImages['exec-user-a-visible']).toEqual([
      'https://cdn.example.com/user-a-preview.png',
    ]);

    await act(async () => {
      setPrivateCacheUserScope('user-b');
    });

    expect(result.current.displayedWorkflowHistory).toEqual([]);
    expect(result.current.expandedPreviewHistoryId).toBeNull();
    expect(result.current.historyPreviewImages['exec-user-a-visible']).toBeUndefined();
    expect(result.current.selectedHistoryId).toBeNull();
  });

  it('does not expand a late sidebar preview after private cache lifecycle resets', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const previewImages = createDeferred<any>();
    setPrivateCacheUserScope('user-a');

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({
          executions: [
            {
              id: 'exec-preview-user-a',
              title: 'User A preview',
              task: 'Private preview task',
              status: 'completed',
              resultSummary: { imageCount: 1, imageUrls: [] },
            },
          ],
        });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    fetchWorkflowPreviewImagesWithMetaMock.mockReturnValue(previewImages.promise);

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(result.current.displayedWorkflowHistory).toHaveLength(1);
    });

    act(() => {
      void result.current.handleToggleWorkflowMediaPreview(
        result.current.displayedWorkflowHistory[0]
      );
    });

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
        'exec-preview-user-a',
        40
      );
    });

    setPrivateCacheUserScope('user-b');
    clearPrivateMemoryCaches();

    await act(async () => {
      previewImages.resolve({
        imageUrls: ['https://cdn.example.com/user-a-sidebar.png'],
        skippedCount: 0,
        count: 1,
      });
      await previewImages.promise;
    });

    expect(result.current.expandedPreviewHistoryId).toBeNull();
    expect(result.current.historyPreviewImages['exec-preview-user-a']).toBeUndefined();
  });

  it('aborts and cleans up active execution before loading history detail', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const cleanupSpy = vi.fn();
    let abortSpy: ReturnType<typeof vi.spyOn> | null = null;

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({ executions: [] });
      }
      if (url === '/api/workflows/history/exec-1') {
        expect(abortSpy).not.toBeNull();
        expect(abortSpy).toHaveBeenCalledTimes(1);
        expect(cleanupSpy).toHaveBeenCalledTimes(1);
        return Promise.resolve(createHistoryDetailPayload('exec-1'));
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history?limit=100',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    const activeExecutionController = new AbortController();
    abortSpy = vi.spyOn(activeExecutionController, 'abort');

    act(() => {
      result.current.activeExecutionControllerRef.current = activeExecutionController;
      result.current.activeExecutionCleanupRef.current = cleanupSpy;
    });

    await act(async () => {
      await result.current.handleLoadWorkflowFromHistory('exec-1');
    });

    expect(abortSpy).toHaveBeenCalledTimes(1);
    expect(cleanupSpy).toHaveBeenCalledTimes(1);
    expect(result.current.selectedHistoryId).toBe('exec-1');
    expect(showError).not.toHaveBeenCalled();
  });

  it('keeps only latest history detail response when requests overlap', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const firstDetail = createDeferred<any>();
    const secondDetail = createDeferred<any>();
    let firstRequestSignal: AbortSignal | undefined;

    requestJsonMock.mockImplementation((url: string, options?: { signal?: AbortSignal }) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({ executions: [] });
      }
      if (url === '/api/workflows/history/exec-a') {
        firstRequestSignal = options?.signal;
        return firstDetail.promise;
      }
      if (url === '/api/workflows/history/exec-b') {
        return secondDetail.promise;
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history?limit=100',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    let loadFirstPromise!: Promise<void>;
    let loadSecondPromise!: Promise<void>;

    act(() => {
      loadFirstPromise = result.current.handleLoadWorkflowFromHistory('exec-a');
    });

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history/exec-a',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    act(() => {
      loadSecondPromise = result.current.handleLoadWorkflowFromHistory('exec-b');
    });

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history/exec-b',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    await waitFor(() => {
      expect(firstRequestSignal?.aborted).toBe(true);
    });

    await act(async () => {
      secondDetail.resolve(createHistoryDetailPayload('exec-b', { title: 'B Workflow' }));
      await loadSecondPromise;
    });

    expect(result.current.selectedHistoryId).toBe('exec-b');
    expect(result.current.workflowLoadRequest?.name).toBe('B Workflow');
    expect(result.current.workflowLoadRequest?.prompt).toBe('Task exec-b');

    await act(async () => {
      firstDetail.resolve(createHistoryDetailPayload('exec-a', { title: 'A Workflow' }));
      await loadFirstPromise;
    });

    expect(result.current.selectedHistoryId).toBe('exec-b');
    expect(result.current.workflowLoadRequest?.name).toBe('B Workflow');
    const latestExecutionStatus = setExecutionStatus.mock.calls.at(-1)?.[0];
    expect(latestExecutionStatus?.executionId).toBe('exec-b');
    expect(showError).not.toHaveBeenCalled();
  });

  it('evicts oldest history preview cache key when cache exceeds max entries', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const historyItems = Array.from({ length: 41 }, (_, index) => {
      const id = `exec-${String(index + 1).padStart(3, '0')}`;
      return {
        id,
        title: `Title ${id}`,
        task: `Task ${id}`,
        status: 'completed',
        resultSummary: {
          imageCount: 1,
          imageUrls: [],
        },
      };
    });

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({ executions: historyItems });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    fetchWorkflowPreviewImagesWithMetaMock.mockImplementation(
      async (executionId: string, limit: number) => ({
        imageUrls: [`preview-${executionId}`],
        skippedCount: 0,
        count: limit,
      })
    );

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(result.current.displayedWorkflowHistory).toHaveLength(41);
    });

    for (const item of result.current.displayedWorkflowHistory) {
      await act(async () => {
        await result.current.handleToggleWorkflowMediaPreview(item);
      });
    }

    const cacheKeys = Object.keys(result.current.historyPreviewImages);
    expect(cacheKeys).toHaveLength(40);
    expect(cacheKeys).not.toContain('exec-001');
    expect(cacheKeys).toContain('exec-041');
    expect(result.current.historyPreviewImages['exec-041']).toEqual(['preview-exec-041']);
    expect(showError).not.toHaveBeenCalled();
  });

  it('loads history detail preview with explicit limit and warns when skippedCount > 0', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({ executions: [] });
      }
      if (url === '/api/workflows/history/exec-meta') {
        return Promise.resolve(
          createHistoryDetailPayload('exec-meta', {
            resultSummary: {
              imageCount: 2,
              imageUrls: [],
            },
          })
        );
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: ['preview-exec-meta'],
      skippedCount: 2,
      count: 1,
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history?limit=100',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    await act(async () => {
      await result.current.handleLoadWorkflowFromHistory('exec-meta');
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
      'exec-meta',
      40
    );
    await waitFor(() => {
      expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('execution=exec-meta'));
      expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('skipped=2'));
      const immediateExecutionStatus = setExecutionStatus.mock.calls[0]?.[0];
      const latestCall = setExecutionStatus.mock.calls.at(-1)?.[0];
      const latestExecutionStatus =
        typeof latestCall === 'function' ? latestCall(immediateExecutionStatus) : latestCall;
      expect(latestExecutionStatus?.resultPreviewImageUrls).toEqual(['preview-exec-meta']);
    });
    expect(showError).not.toHaveBeenCalled();
  });

  it('uses persisted result image urls directly when loading history detail', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const persistedImageUrl =
      '/api/storage/local-files/2026/05/24/workflow-result-01-generated.png';

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({ executions: [] });
      }
      if (url === '/api/workflows/history/exec-persisted-image') {
        return Promise.resolve(
          createHistoryDetailPayload('exec-persisted-image', {
            workflow: {
              nodes: [
                {
                  id: 'end-node',
                  type: 'end',
                  position: { x: 0, y: 0 },
                  data: {
                    type: 'end',
                    label: '结束',
                  },
                },
              ],
              edges: [],
            },
            result: {
              finalOutput: {
                text: '生成完成',
                imageUrl: persistedImageUrl,
                imageUrls: [persistedImageUrl],
              },
            },
            resultSummary: {
              imageCount: 1,
              imageUrls: [persistedImageUrl],
              audioCount: 0,
              audioUrls: [],
              videoCount: 0,
              videoUrls: [],
            },
            nodeExecutions: [
              {
                nodeId: 'end-node',
                status: 'completed',
                progress: 100,
                output: {
                  finalOutput: {
                    imageUrl: persistedImageUrl,
                    imageUrls: [persistedImageUrl],
                  },
                },
              },
            ],
          })
        );
      }
      throw new Error(`Unexpected URL: ${url}`);
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history?limit=100',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    await act(async () => {
      await result.current.handleLoadWorkflowFromHistory('exec-persisted-image');
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).not.toHaveBeenCalled();
    const latestExecutionStatus = setExecutionStatus.mock.calls.at(-1)?.[0];
    expect(latestExecutionStatus?.resultPreviewImageUrls).toEqual([]);
    expect(latestExecutionStatus?.finalResult?.finalOutput?.imageUrl).toBe(persistedImageUrl);
    expect((result.current.workflowLoadRequest as any)?.executionStatus?.executionId).toBe(
      'exec-persisted-image'
    );
    expect(
      (result.current.workflowLoadRequest as any)?.executionStatus?.nodeResults?.['end-node']
        ?.finalOutput?.imageUrl
    ).toBe(persistedImageUrl);
    expect(showError).not.toHaveBeenCalled();
  });

  it('loads the canvas before legacy preview images finish and hydrates previews later', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const previewImages = createDeferred<{
      imageUrls: string[];
      skippedCount: number;
      count: number;
    }>();

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({ executions: [] });
      }
      if (url === '/api/workflows/history/exec-slow-preview') {
        return Promise.resolve(
          createHistoryDetailPayload('exec-slow-preview', {
            workflow: {
              nodes: [
                {
                  id: 'end-node',
                  type: 'end',
                  position: { x: 0, y: 0 },
                  data: {
                    type: 'end',
                    label: '结束',
                  },
                },
              ],
              edges: [],
            },
            result: {
              finalOutput: {
                imageUrl: '/Users/demo/generated/final.png',
                imageUrls: ['/Users/demo/generated/final.png'],
              },
            },
            resultSummary: {
              imageCount: 1,
              imageUrls: [],
              audioCount: 0,
              audioUrls: [],
              videoCount: 0,
              videoUrls: [],
            },
            nodeExecutions: [
              {
                nodeId: 'end-node',
                status: 'completed',
                progress: 100,
                output: {
                  finalOutput: {
                    imageUrl: '/Users/demo/generated/final.png',
                    imageUrls: ['/Users/demo/generated/final.png'],
                  },
                },
              },
            ],
          })
        );
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    fetchWorkflowPreviewImagesWithMetaMock.mockReturnValue(previewImages.promise);

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(requestJsonMock).toHaveBeenCalledWith(
        '/api/workflows/history?limit=100',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    let loadPromise!: Promise<void>;
    act(() => {
      loadPromise = result.current.handleLoadWorkflowFromHistory('exec-slow-preview');
    });

    await waitFor(() => {
      expect(result.current.workflowLoadRequest?.name).toBe('Title exec-slow-preview');
    });
    await expect(loadPromise).resolves.toBeUndefined();

    const immediateExecutionStatus = setExecutionStatus.mock.calls.at(-1)?.[0];
    expect(immediateExecutionStatus?.executionId).toBe('exec-slow-preview');
    expect(immediateExecutionStatus?.resultPreviewImageUrls).toEqual([]);

    await act(async () => {
      previewImages.resolve({
        imageUrls: ['data:image/png;base64,preview'],
        skippedCount: 0,
        count: 1,
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      const latestCall = setExecutionStatus.mock.calls.at(-1)?.[0];
      const latestExecutionStatus =
        typeof latestCall === 'function' ? latestCall(immediateExecutionStatus) : latestCall;
      expect(latestExecutionStatus?.resultPreviewImageUrls).toEqual([
        'data:image/png;base64,preview',
      ]);
    });
    expect(showError).not.toHaveBeenCalled();
  });

  it('loads sidebar preview with explicit limit and warns when skippedCount > 0', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    requestJsonMock.mockImplementation((url: string) => {
      if (url === '/api/workflows/history?limit=100') {
        return Promise.resolve({
          executions: [
            {
              id: 'exec-preview',
              title: 'Preview title',
              task: 'Preview task',
              status: 'completed',
              resultSummary: {
                imageCount: 1,
                imageUrls: [],
              },
            },
          ],
        });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: ['preview-exec-preview'],
      skippedCount: 1,
      count: 1,
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryController({
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(result.current.displayedWorkflowHistory).toHaveLength(1);
    });

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview(
        result.current.displayedWorkflowHistory[0]
      );
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
      'exec-preview',
      40
    );
    expect(result.current.expandedPreviewHistoryId).toBe('exec-preview');
    expect(result.current.historyPreviewImages['exec-preview']).toEqual(['preview-exec-preview']);
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('execution=exec-preview'));
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('skipped=1'));
    expect(showError).not.toHaveBeenCalled();
  });

  it('maps video summary fields and caches video preview metadata', async () => {
    const setExecutionStatus = vi.fn();
    const showError = vi.fn();

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
        setExecutionStatus,
        showError,
      })
    );

    await waitFor(() => {
      expect(result.current.displayedWorkflowHistory).toHaveLength(1);
    });

    expect(result.current.displayedWorkflowHistory[0].resultVideoCount).toBe(1);
    expect(result.current.displayedWorkflowHistory[0].resultVideoUrls).toEqual([
      'https://cdn.example.com/video/1.mp4',
    ]);

    await act(async () => {
      await result.current.handleToggleWorkflowMediaPreview(
        result.current.displayedWorkflowHistory[0]
      );
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).not.toHaveBeenCalled();
    expect(fetchWorkflowPreviewMediaWithMetaMock).toHaveBeenCalledWith(
      'exec-video',
      'video',
      12
    );
    expect(result.current.historyPreviewMedia['exec-video']?.videoItems).toHaveLength(1);
    expect(showError).not.toHaveBeenCalled();
  });
});

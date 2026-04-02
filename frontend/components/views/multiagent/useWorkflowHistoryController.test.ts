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

const createDeferred = <T,>() => {
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
    fetchWorkflowPreviewImagesWithMetaMock.mockImplementation(async (executionId: string, limit: number) => ({
      imageUrls: [`preview-${executionId}`],
      skippedCount: 0,
      count: limit,
    }));

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
        return Promise.resolve(createHistoryDetailPayload('exec-meta', {
          resultSummary: {
            imageCount: 2,
            imageUrls: [],
          },
        }));
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
      40,
      expect.any(AbortSignal)
    );
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('execution=exec-meta'));
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('skipped=2'));
    const latestExecutionStatus = setExecutionStatus.mock.calls.at(-1)?.[0];
    expect(latestExecutionStatus?.resultPreviewImageUrls).toEqual(['preview-exec-meta']);
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
      await result.current.handleToggleWorkflowMediaPreview(result.current.displayedWorkflowHistory[0]);
    });

    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
      'exec-preview',
      40,
      expect.any(AbortSignal)
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
    expect(result.current.displayedWorkflowHistory[0].resultVideoUrls).toEqual(['https://cdn.example.com/video/1.mp4']);

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
    expect(showError).not.toHaveBeenCalled();
  });
});

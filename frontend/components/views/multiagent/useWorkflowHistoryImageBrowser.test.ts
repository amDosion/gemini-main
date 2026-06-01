// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkflowHistoryItem } from './types';
import { useWorkflowHistoryImageBrowser } from './useWorkflowHistoryImageBrowser';
import { __resetWorkflowPreviewCacheForTest } from '../../../services/workflowPreviewCache';
import { clearPrivateMemoryCaches } from '../../../services/privateClientCache';
import { setPrivateCacheUserScope } from '../../../services/privateCacheScope';

const { fetchWorkflowPreviewImagesWithMetaMock } = vi.hoisted(() => ({
  fetchWorkflowPreviewImagesWithMetaMock: vi.fn(),
}));

vi.mock('../../../services/workflowHistoryService', () => ({
  fetchWorkflowPreviewImagesWithMeta: fetchWorkflowPreviewImagesWithMetaMock,
}));

const buildHistoryItem = (overrides: Partial<WorkflowHistoryItem>): WorkflowHistoryItem => ({
  id: 'exec-history-images',
  status: 'completed',
  title: '历史图片工作流',
  source: 'history',
  task: '生成图片',
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
  nodeCount: 1,
  edgeCount: 0,
  ...overrides,
});

describe('useWorkflowHistoryImageBrowser', () => {
  beforeEach(() => {
    fetchWorkflowPreviewImagesWithMetaMock.mockReset();
    __resetWorkflowPreviewCacheForTest();
    setPrivateCacheUserScope(null);
  });

  it('lazy-loads the current page and raises preview limit when later pages need more images', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockImplementation(
      async (_executionId: string, limit: number) => ({
        imageUrls: Array.from(
          { length: Math.min(limit, 40) },
          (_, index) => `https://cdn.example.com/preview-${index + 1}.png`
        ),
        skippedCount: 0,
        count: Math.min(limit, 40),
      })
    );

    const { result } = renderHook(() =>
      useWorkflowHistoryImageBrowser({
        items: [buildHistoryItem({ id: 'exec-large', resultImageCount: 48 })],
        seedPreviewImages: {},
        enabled: true,
        showError: vi.fn(),
      })
    );

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
        'exec-large',
        40
      );
    });

    await waitFor(() => {
      expect(result.current.currentPageCards[0].imageUrl).toBe(
        'https://cdn.example.com/preview-1.png'
      );
    });

    act(() => {
      result.current.setPage(2);
    });

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
        'exec-large',
        48
      );
    });
    await waitFor(() => {
      expect(result.current.currentPageCards.slice(16)).toHaveLength(8);
      expect(
        result.current.currentPageCards.slice(16).every((card) => card.loadState === 'error')
      ).toBe(true);
    });
    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(2);
  });

  it('reuses cached preview images after the browser is remounted', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: ['https://cdn.example.com/reused-preview.png'],
      skippedCount: 0,
      count: 1,
    });

    const first = renderHook(() =>
      useWorkflowHistoryImageBrowser({
        items: [buildHistoryItem({ id: 'exec-reused-preview', resultImageCount: 1 })],
        seedPreviewImages: {},
        enabled: true,
        showError: vi.fn(),
      })
    );

    await waitFor(() => {
      expect(first.result.current.currentPageCards[0].imageUrl).toBe(
        'https://cdn.example.com/reused-preview.png'
      );
    });
    expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledTimes(1);

    first.unmount();
    fetchWorkflowPreviewImagesWithMetaMock.mockClear();

    const second = renderHook(() =>
      useWorkflowHistoryImageBrowser({
        items: [buildHistoryItem({ id: 'exec-reused-preview', resultImageCount: 1 })],
        seedPreviewImages: {},
        enabled: true,
        showError: vi.fn(),
      })
    );

    expect(second.result.current.currentPageCards[0].imageUrl).toBe(
      'https://cdn.example.com/reused-preview.png'
    );
    expect(fetchWorkflowPreviewImagesWithMetaMock).not.toHaveBeenCalled();
  });

  it('does not reuse stale blob urls from persisted workflow history', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: ['/api/storage/local-files/2026/06/01/workflow-preview.png'],
      skippedCount: 0,
      count: 1,
    });

    const { result } = renderHook(() =>
      useWorkflowHistoryImageBrowser({
        items: [
          buildHistoryItem({
            id: 'exec-stale-blob-preview',
            resultImageCount: 1,
            resultImageUrls: ['blob:https://gemini.dicry.cn:18443/stale-workflow-history'],
          }),
        ],
        seedPreviewImages: {},
        enabled: true,
        showError: vi.fn(),
      })
    );

    expect(result.current.currentPageCards[0].imageUrl).toBeUndefined();

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
        'exec-stale-blob-preview',
        40
      );
    });
    await waitFor(() => {
      expect(result.current.currentPageCards[0].imageUrl).toBe(
        '/api/storage/local-files/2026/06/01/workflow-preview.png'
      );
    });
  });

  it('does not apply a late preview response after private cache lifecycle resets', async () => {
    let resolvePreview!: (value: { imageUrls: string[]; skippedCount: number; count: number }) => void;
    fetchWorkflowPreviewImagesWithMetaMock.mockReturnValue(
      new Promise((resolve) => {
        resolvePreview = resolve;
      })
    );
    setPrivateCacheUserScope('user-a');

    const { result } = renderHook(() =>
      useWorkflowHistoryImageBrowser({
        items: [buildHistoryItem({ id: 'exec-late-preview', resultImageCount: 1 })],
        seedPreviewImages: {},
        enabled: true,
        showError: vi.fn(),
      })
    );

    await waitFor(() => {
      expect(fetchWorkflowPreviewImagesWithMetaMock).toHaveBeenCalledWith(
        'exec-late-preview',
        40
      );
    });

    setPrivateCacheUserScope('user-b');
    clearPrivateMemoryCaches();

    await act(async () => {
      resolvePreview({
        imageUrls: ['https://cdn.example.com/user-a-preview.png'],
        skippedCount: 0,
        count: 1,
      });
    });

    await waitFor(() => {
      expect(result.current.currentPageCards[0].imageUrl).toBeUndefined();
    });
  });

  it('clears local preview images when the private user scope changes', async () => {
    fetchWorkflowPreviewImagesWithMetaMock.mockResolvedValue({
      imageUrls: ['https://cdn.example.com/user-a-preview.png'],
      skippedCount: 0,
      count: 1,
    });
    setPrivateCacheUserScope('user-a');

    const { result } = renderHook(() =>
      useWorkflowHistoryImageBrowser({
        items: [buildHistoryItem({ id: 'exec-scope-preview', resultImageCount: 1 })],
        seedPreviewImages: {},
        enabled: true,
        showError: vi.fn(),
      })
    );

    await waitFor(() => {
      expect(result.current.currentPageCards[0].imageUrl).toBe(
        'https://cdn.example.com/user-a-preview.png'
      );
    });

    await act(async () => {
      setPrivateCacheUserScope('user-b');
    });

    expect(result.current.currentPageCards[0].imageUrl).toBeUndefined();
  });
});

import { beforeEach, describe, expect, it, vi } from 'vitest';

const { requestJsonMock } = vi.hoisted(() => ({
  requestJsonMock: vi.fn(),
}));

vi.mock('./http', () => ({
  requestJson: requestJsonMock,
}));

import {
  fetchWorkflowPreviewMediaWithMeta,
  fetchWorkflowPreviewImages,
  fetchWorkflowPreviewImagesWithMeta,
} from './workflowHistoryService';

describe('workflowHistoryService', () => {
  beforeEach(() => {
    requestJsonMock.mockReset();
  });

  it('parses preview images and metadata', async () => {
    const signal = new AbortController().signal;
    requestJsonMock.mockResolvedValue({
      images: [
        { dataUrl: 'data:image/png;base64,AAA=' },
        { dataUrl: '   ' },
        {},
        { dataUrl: 'data:image/png;base64,BBB=' },
      ],
      skippedCount: 2,
      count: 4,
    });

    const result = await fetchWorkflowPreviewImagesWithMeta(' exec-1 ', 5.9, signal);

    expect(requestJsonMock).toHaveBeenCalledWith(
      '/api/workflows/history/exec-1/images/preview?limit=5',
      expect.objectContaining({
        credentials: 'include',
        signal,
        timeoutMs: 0,
        withAuth: true,
      })
    );
    expect(result).toEqual({
      imageUrls: ['data:image/png;base64,AAA=', 'data:image/png;base64,BBB='],
      skippedCount: 2,
      count: 4,
    });
  });

  it('normalizes metadata with fallback count', async () => {
    requestJsonMock.mockResolvedValue({
      images: [{ dataUrl: 'data:image/png;base64,AAA=' }],
      skippedCount: '3',
      count: 'invalid',
    });

    const result = await fetchWorkflowPreviewImagesWithMeta('exec-meta-fallback');

    expect(result).toEqual({
      imageUrls: ['data:image/png;base64,AAA='],
      skippedCount: 3,
      count: 1,
    });
  });

  it('returns empty metadata when execution id is blank', async () => {
    const result = await fetchWorkflowPreviewImagesWithMeta('   ');
    expect(result).toEqual({
      imageUrls: [],
      skippedCount: 0,
      count: 0,
    });
    expect(requestJsonMock).not.toHaveBeenCalled();
  });

  it('keeps fetchWorkflowPreviewImages backward compatible', async () => {
    requestJsonMock.mockResolvedValue({
      images: [{ dataUrl: 'data:image/png;base64,AAA=' }],
      skippedCount: 9,
      count: 10,
    });

    await expect(fetchWorkflowPreviewImages('exec-legacy')).resolves.toEqual([
      'data:image/png;base64,AAA=',
    ]);
  });

  it('maps request failed status errors to localized http message', async () => {
    requestJsonMock.mockRejectedValue(new Error('Request failed: 500'));

    await expect(fetchWorkflowPreviewImagesWithMeta('exec-error')).rejects.toThrow(
      '加载图片预览失败 (HTTP 500)'
    );
  });

  it('preserves non-status error messages', async () => {
    const upstreamError = new Error('network exploded');
    requestJsonMock.mockRejectedValue(upstreamError);

    await expect(fetchWorkflowPreviewImagesWithMeta('exec-error-2')).rejects.toBe(upstreamError);
  });

  it('maps non-Error rejection to fallback message', async () => {
    requestJsonMock.mockRejectedValue({ code: 'unexpected' });

    await expect(fetchWorkflowPreviewImagesWithMeta('exec-error-3')).rejects.toThrow('加载图片预览失败');
  });

  it('parses preview media items and filters unsafe urls', async () => {
    const signal = new AbortController().signal;
    requestJsonMock.mockResolvedValue({
      mediaType: 'video',
      items: [
        {
          index: 1,
          sourceUrl: 'https://cdn.example.com/video/1.mp4',
          resolvedUrl: 'https://cdn.example.com/video/1.mp4',
          mimeType: 'video/mp4',
          fileName: 'video-01.mp4',
          previewUrl: '/api/workflows/history/exec-1/video/items/1',
        },
        {
          index: 2,
          previewUrl: 'file:///tmp/leak.mp4',
        },
      ],
      skippedCount: 1,
      count: 2,
    });

    const result = await fetchWorkflowPreviewMediaWithMeta(' exec-1 ', 'video', 3.9, signal);

    expect(requestJsonMock).toHaveBeenCalledWith(
      '/api/workflows/history/exec-1/video/preview?limit=3',
      expect.objectContaining({
        credentials: 'include',
        signal,
        timeoutMs: 0,
        withAuth: true,
      })
    );
    expect(result).toEqual({
      mediaType: 'video',
      items: [
        {
          index: 1,
          sourceUrl: 'https://cdn.example.com/video/1.mp4',
          resolvedUrl: 'https://cdn.example.com/video/1.mp4',
          mimeType: 'video/mp4',
          fileName: 'video-01.mp4',
          previewUrl: '/api/workflows/history/exec-1/video/items/1',
        },
      ],
      skippedCount: 1,
      count: 2,
    });
  });

  it('maps media preview request failures to localized http message', async () => {
    requestJsonMock.mockRejectedValue(new Error('Request failed: 404'));

    await expect(fetchWorkflowPreviewMediaWithMeta('exec-audio', 'audio')).rejects.toThrow(
      '加载媒体预览失败 (HTTP 404)'
    );
  });
});

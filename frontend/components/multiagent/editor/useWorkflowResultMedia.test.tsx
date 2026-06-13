// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkflowResultMedia } from './useWorkflowResultMedia';

const { triggerBrowserDownloadMock } = vi.hoisted(() => ({
  triggerBrowserDownloadMock: vi.fn(),
}));

vi.mock('../../../services/downloadService', () => ({
  triggerBrowserDownload: triggerBrowserDownloadMock,
}));

describe('useWorkflowResultMedia', () => {
  beforeEach(() => {
    triggerBrowserDownloadMock.mockClear();
  });

  it('does not expose rendered image urls again as generic returned urls', () => {
    const imageUrl = '/api/storage/local-files/2026/05/24/workflow-result-01-generated.png';
    const { result } = renderHook(() =>
      useWorkflowResultMedia({
        finalResult: {
          finalOutput: {
            text: '生成完成',
            imageUrl,
            imageUrls: [imageUrl],
          },
        },
        finalError: null,
        nodes: [],
        workflowInputImageUrl: '',
        mergedResultPanelPreviewImageUrls: [],
        resultPanelPreviewAudioUrls: [],
        resultPanelPreviewVideoUrls: [],
        executionId: 'exec-result-media',
        addLog: vi.fn(),
      })
    );

    expect(result.current.finalOutputImageUrls).toEqual([imageUrl]);
    expect(result.current.renderedResultItems[0]?.imageUrls).toEqual([imageUrl]);
    expect(result.current.renderedResultItems[0]?.urls).toEqual([]);
  });

  it('routes workflow history media downloads through the shared browser download service', () => {
    const addLog = vi.fn();
    const { result } = renderHook(() =>
      useWorkflowResultMedia({
        finalResult: null,
        finalError: null,
        nodes: [],
        workflowInputImageUrl: '',
        mergedResultPanelPreviewImageUrls: [],
        resultPanelPreviewAudioUrls: [],
        resultPanelPreviewVideoUrls: [],
        executionId: 'exec/result media',
        addLog,
      })
    );

    act(() => {
      result.current.triggerWorkflowMediaDownload('images', 'download started');
    });

    expect(triggerBrowserDownloadMock).toHaveBeenCalledWith({
      href: '/api/workflows/history/exec%2Fresult%20media/images/download',
    });
    expect(addLog).toHaveBeenCalledWith('system', '系统', 'info', 'download started');
  });
});

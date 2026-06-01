// @vitest-environment jsdom
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useWorkflowResultMedia } from './useWorkflowResultMedia';

describe('useWorkflowResultMedia', () => {
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
});

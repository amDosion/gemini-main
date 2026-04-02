import { beforeEach, describe, expect, it, vi } from 'vitest';

const { requestJsonMock } = vi.hoisted(() => ({
  requestJsonMock: vi.fn(),
}));

vi.mock('./http', () => ({
  requestJson: requestJsonMock,
}));

import { fetchWorkflowPreviewMediaWithMeta } from './workflowHistoryService';

describe('workflowHistoryService media', () => {
  beforeEach(() => {
    requestJsonMock.mockReset();
  });

  it('parses media preview payload and filters unsafe preview urls', async () => {
    requestJsonMock.mockResolvedValue({
      mediaType: 'audio',
      items: [
        {
          index: 1,
          sourceUrl: 'https://cdn.example.com/audio/1.mp3',
          resolvedUrl: 'https://cdn.example.com/audio/1.mp3',
          mimeType: 'audio/mpeg',
          fileName: 'audio-01.mp3',
          previewUrl: '/api/workflows/history/exec-audio/audio/items/1',
        },
        {
          index: 2,
          previewUrl: 'file:///tmp/leak.mp3',
        },
      ],
      skippedCount: 1,
      count: 2,
    });

    await expect(fetchWorkflowPreviewMediaWithMeta('exec-audio', 'audio')).resolves.toEqual({
      mediaType: 'audio',
      items: [
        {
          index: 1,
          sourceUrl: 'https://cdn.example.com/audio/1.mp3',
          resolvedUrl: 'https://cdn.example.com/audio/1.mp3',
          mimeType: 'audio/mpeg',
          fileName: 'audio-01.mp3',
          previewUrl: '/api/workflows/history/exec-audio/audio/items/1',
        },
      ],
      skippedCount: 1,
      count: 2,
    });
  });
});

// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';

const {
  triggerBrowserDownloadMock
} = vi.hoisted(() => ({
  triggerBrowserDownloadMock: vi.fn()
}));

vi.mock('../../../services/downloadService', async () => {
  const actual = await vi.importActual<typeof import('../../../services/downloadService')>(
    '../../../services/downloadService'
  );
  return {
    ...actual,
    triggerBrowserDownload: triggerBrowserDownloadMock
  };
});

import { startPreparedCloudStorageDownload } from './cloudStorageActionService';

describe('cloudStorageActionService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('hands prepared storage files off to the browser download manager', async () => {
    await startPreparedCloudStorageDownload('/api/storage/downloads/download-123', 'fallback.zip');

    expect(triggerBrowserDownloadMock).toHaveBeenCalledWith({
      href: '/api/storage/downloads/download-123'
    });
  });
});

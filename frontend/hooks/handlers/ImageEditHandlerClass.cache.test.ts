// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ImageEditHandler } from './ImageEditHandlerClass';
import { llmService } from '../../services/llmService';
import { storageUpload } from '../../services/storage/storageUpload';
import type { ExecutionContext } from './types';

vi.mock('../../services/llmService', () => ({
  llmService: {
    editImage: vi.fn(),
  },
}));

vi.mock('../../services/storage/storageUpload', () => ({
  storageUpload: {
    uploadFileAsync: vi.fn(),
  },
}));

const makeContext = (): ExecutionContext => ({
  sessionId: 'session-cache',
  userMessageId: 'user-message-cache',
  modelMessageId: 'model-message-cache',
  mode: 'image-chat-edit',
  text: 'edit this image',
  attachments: [
    {
      id: 'att-uploaded-relative-cloud',
      name: 'uploaded.png',
      mimeType: 'image/png',
      url: 'blob:https://gemini.dicry.cn:18443/revoked-uploaded',
      tempUrl: 'data:image/png;base64,abc',
      cloudUrl: '/api/storage/local-files/2026/05/31/uploaded.png',
      uploadStatus: 'completed',
      file: new File(['image'], 'uploaded.png', { type: 'image/png' }),
    },
  ],
  currentModel: {
    id: 'model-image-edit',
    name: 'Image Edit',
    provider: 'google',
    capabilities: ['image-edit'],
  } as any,
  options: {
    enableSearch: false,
    enableThinking: false,
    enableCodeExecution: false,
  },
  protocol: 'google',
  llmService,
  storageService: storageUpload,
  pollingManager: {
    startPolling: vi.fn(),
    stopPolling: vi.fn(),
    cleanup: vi.fn(),
  },
});

describe('ImageEditHandler media cache attachment handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(llmService.editImage).mockResolvedValue([
      {
        url: '/api/storage/local-files/2026/05/31/edited.png',
        mimeType: 'image/png',
        filename: 'edited.png',
        attachmentId: 'edited-result',
        uploadStatus: 'completed',
        cloudUrl: '/api/storage/local-files/2026/05/31/edited.png',
        openaiResponseId: 'resp_edited_result',
      },
    ] as any);
  });

  it('does not re-upload already completed relative cloud attachments with stale blob urls', async () => {
    const handler = new ImageEditHandler();
    const result = await handler.execute(makeContext());
    const uploadResult = await result.uploadTask;

    expect(storageUpload.uploadFileAsync).not.toHaveBeenCalled();
    expect(result.attachments[0]).toEqual(
      expect.objectContaining({
        id: 'edited-result',
        openaiResponseId: 'resp_edited_result',
      }),
    );
    expect(uploadResult?.dbUserAttachments).toEqual([
      expect.objectContaining({
        id: 'att-uploaded-relative-cloud',
        url: '/api/storage/local-files/2026/05/31/uploaded.png',
        cloudUrl: '/api/storage/local-files/2026/05/31/uploaded.png',
        uploadStatus: 'completed',
      }),
    ]);
  });
});

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ImageOutpaintingHandler } from './AllHandlerClasses';
import { llmService } from '../../services/llmService';
import type { Attachment, ChatOptions, ModelConfig } from '../../types/types';

const mocks = vi.hoisted(() => ({
  outPaintImage: vi.fn(),
}));

vi.mock('../../services/llmService', () => ({
  llmService: {
    outPaintImage: mocks.outPaintImage,
  },
}));

describe('ImageOutpaintingHandler', () => {
  const attachment: Attachment = {
    id: 'source-att',
    name: 'source.png',
    mimeType: 'image/png',
    url: 'data:image/png;base64,AAAA',
  };

  const currentModel: ModelConfig = {
    id: 'imagen-3.0-capability-001',
    name: 'Imagen Edit',
    description: 'Outpaint',
    capabilities: {
      vision: true,
      search: false,
      reasoning: false,
      coding: false,
    },
    contextWindow: 0,
  };

  beforeEach(() => {
    mocks.outPaintImage.mockReset();
  });

  it('preserves prompt and AI metadata returned by outpainting', async () => {
    mocks.outPaintImage.mockResolvedValue([
      {
        url: '/api/temp-images/result-att',
        mimeType: 'image/png',
        filename: 'expanded.png',
        attachmentId: 'result-att',
        uploadStatus: 'pending',
        taskId: 'task-1',
        sessionId: 'session-1',
        messageId: 'model-1',
        userId: 'user-1',
        cloudUrl: '',
        size: 123,
        openaiResponseId: 'resp_outpaint',
        enhancedPrompt: 'extend the studio background with soft light',
        thoughts: [{ type: 'text', content: 'Need wider composition.' }],
        text: 'Expanded one image.',
      },
    ]);

    const result = await new ImageOutpaintingHandler().execute({
      sessionId: 'session-1',
      userMessageId: 'user-1',
      modelMessageId: 'model-1',
      mode: 'image-outpainting',
      text: 'extend background',
      attachments: [attachment],
      currentModel,
      options: {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
      } as ChatOptions,
      protocol: 'google',
      llmService,
      storageService: {} as never,
      pollingManager: {
        startPolling: vi.fn(),
        stopPolling: vi.fn(),
        cleanup: vi.fn(),
      },
    });

    expect(mocks.outPaintImage).toHaveBeenCalledWith(
      attachment,
      expect.objectContaining({
        frontendSessionId: 'session-1',
        sessionId: 'session-1',
        messageId: 'model-1',
      }),
    );
    expect(result.content).toBe('extend background');
    expect(result.enhancedPrompt).toBe('extend the studio background with soft light');
    expect(result.textResponse).toBe('Expanded one image.');
    expect(result.thoughts).toEqual([{ type: 'text', content: 'Need wider composition.' }]);
    expect(result.attachments[0]).toMatchObject({
      id: 'result-att',
      url: '/api/temp-images/result-att',
      enhancedPrompt: 'extend the studio background with soft light',
      sessionId: 'session-1',
      messageId: 'model-1',
      userId: 'user-1',
      cloudUrl: '',
      size: 123,
      openaiResponseId: 'resp_outpaint',
    });
  });
});

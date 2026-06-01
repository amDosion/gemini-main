import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ImageGenHandler } from './ImageGenHandlerClass';
import { llmService } from '../../services/llmService';
import type { ChatOptions, ModelConfig } from '../../types/types';

const mocks = vi.hoisted(() => ({
  generateImage: vi.fn(),
}));

vi.mock('../../services/llmService', () => ({
  llmService: {
    generateImage: mocks.generateImage,
  },
}));

describe('ImageGenHandler', () => {
  const currentModel: ModelConfig = {
    id: 'gpt-image-2',
    name: 'GPT Image 2',
    description: 'OpenAI image model',
    capabilities: {
      vision: true,
      search: false,
      reasoning: false,
      coding: false,
    },
    contextWindow: 0,
  };

  beforeEach(() => {
    mocks.generateImage.mockReset();
  });

  it('preserves OpenAI response id on generated canvas attachments', async () => {
    mocks.generateImage.mockResolvedValue([
      {
        url: '/api/temp-images/generated-att',
        mimeType: 'image/png',
        filename: 'generated.png',
        attachmentId: 'generated-att',
        uploadStatus: 'pending',
        openaiResponseId: 'resp_generated',
      },
    ]);

    const result = await new ImageGenHandler().execute({
      sessionId: 'session-1',
      userMessageId: 'user-1',
      modelMessageId: 'model-1',
      mode: 'image-gen',
      text: 'generate image',
      attachments: [],
      currentModel,
      options: {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
      } as ChatOptions,
      protocol: 'openai',
      llmService,
      storageService: {} as never,
      pollingManager: {
        startPolling: vi.fn(),
        stopPolling: vi.fn(),
        cleanup: vi.fn(),
      },
    });

    expect(result.attachments[0]).toEqual(
      expect.objectContaining({
        id: 'generated-att',
        openaiResponseId: 'resp_generated',
      }),
    );
  });
});

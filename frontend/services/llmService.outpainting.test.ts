import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LLMService } from './llmService';
import { LLMFactory } from './LLMFactory';
import type { Attachment, ChatOptions, ModelConfig } from '../types/types';

const mocks = vi.hoisted(() => ({
  executeMode: vi.fn(),
  getProvider: vi.fn(),
  getDashScopeKey: vi.fn(),
  getProfiles: vi.fn(),
}));

vi.mock('./LLMFactory', () => ({
  LLMFactory: {
    getProvider: mocks.getProvider,
  },
}));

vi.mock('./configurationService', () => ({
  configService: {
    getDashScopeKey: mocks.getDashScopeKey,
    getProfiles: mocks.getProfiles,
  },
}));

describe('LLMService outPaintImage model routing', () => {
  const baseOptions: ChatOptions = {
    enableSearch: false,
    enableThinking: false,
    enableCodeExecution: false,
    imageAspectRatio: '1:1',
    imageResolution: '1K',
  };

  const attachment: Attachment = {
    id: 'input-1',
    name: 'input.png',
    mimeType: 'image/png',
    url: 'data:image/png;base64,AAAA',
  };

  const makeModel = (id: string): ModelConfig => ({
    id,
    name: id,
    description: id,
    capabilities: {
      vision: true,
      search: false,
      reasoning: false,
      coding: false,
    },
    contextWindow: 0,
  });

  beforeEach(() => {
    mocks.executeMode.mockResolvedValue([
      { url: 'data:image/png;base64,BBBB', mimeType: 'image/png' },
    ]);
    mocks.getProvider.mockReturnValue({ executeMode: mocks.executeMode });
    mocks.getDashScopeKey.mockResolvedValue(null);
    mocks.getProfiles.mockResolvedValue([]);
    vi.stubGlobal('localStorage', {
      getItem: () => null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('uses the active UI-selected model instead of replacing upscale requests with a fixed model', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'google', 'google');
    service.startNewChat([], makeModel('custom-vertex-upscale-model'), baseOptions);

    await service.outPaintImage(attachment, {
      outpaintMode: 'upscale',
      upscaleFactor: 'x3',
    } as unknown as Partial<ChatOptions>);

    expect(LLMFactory.getProvider).toHaveBeenCalledWith('google', 'google');
    expect(mocks.executeMode).toHaveBeenCalledWith(
      'image-outpainting',
      'custom-vertex-upscale-model',
      'Extend the image naturally',
      [attachment],
      expect.objectContaining({
        outpaintMode: 'upscale',
        upscaleFactor: 'x3',
      }),
      {},
    );
  });

  it('lets an explicit options.modelId override the cached model without static replacement', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'google', 'google');
    service.startNewChat([], makeModel('imagen-3.0-capability-001'), baseOptions);

    await service.outPaintImage(attachment, {
      modelId: 'json-configured-outpaint-model',
      outpaintMode: 'ratio',
    } as unknown as Partial<ChatOptions>);

    expect(mocks.executeMode).toHaveBeenCalledWith(
      'image-outpainting',
      'json-configured-outpaint-model',
      'Extend the image naturally',
      [attachment],
      expect.objectContaining({
        modelId: 'json-configured-outpaint-model',
        outpaintMode: 'ratio',
      }),
      {},
    );
  });
});

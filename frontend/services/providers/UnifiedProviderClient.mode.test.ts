import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UnifiedProviderClient } from './UnifiedProviderClient';
import type { ChatOptions } from '../../types/types';

const successResponse = () =>
  new Response(JSON.stringify({ success: true, data: {} }), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });

describe('UnifiedProviderClient mode payload sanitization', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: () => null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  const getPostedBody = (fetchMock: ReturnType<typeof vi.fn>) => {
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    return JSON.parse(String(init?.body || '{}'));
  };

  it('drops non-mode chat and workflow fields from image mode requests', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    const options: ChatOptions = {
      enableSearch: false,
      enableThinking: false,
      enableCodeExecution: false,
      imageAspectRatio: '1:1',
      imageResolution: '1K',
      enableUrlContext: false,
      googleCacheMode: 'none',
      enableDeepResearch: true,
      deepResearchAgentId: 'deep-research-pro',
      sessionId: 'session-1',
      messageId: 'message-1',
      multiAgentConfig: { nodes: [], edges: [] },
      liveAPIConfig: { agentId: 'agent-1' },
      modelId: 'should-not-be-sent-in-options',
      prompt: 'should-not-be-sent-in-options',
    };

    await client.executeMode(
      'image-gen',
      'gemini-3.1-flash-image-preview',
      'draw a cat',
      [],
      options,
      {
        responseFormat: 'b64_json',
        unknownExtra: 'drop-me',
      }
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = getPostedBody(fetchMock);

    expect(body.options).toMatchObject({
      enableSearch: false,
      enableThinking: false,
      enableCodeExecution: false,
      imageAspectRatio: '1:1',
      imageResolution: '1K',
      sessionId: 'session-1',
      messageId: 'message-1',
    });
    expect(body.options).not.toHaveProperty('enableUrlContext');
    expect(body.options).not.toHaveProperty('googleCacheMode');
    expect(body.options).not.toHaveProperty('enableDeepResearch');
    expect(body.options).not.toHaveProperty('deepResearchAgentId');
    expect(body.options).not.toHaveProperty('multiAgentConfig');
    expect(body.options).not.toHaveProperty('liveAPIConfig');
    expect(body.options).not.toHaveProperty('modelId');
    expect(body.options).not.toHaveProperty('prompt');
    expect(body.extra).toEqual({
      responseFormat: 'b64_json',
    });
  });

  it('keeps media-specific mode params that backend actually supports', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    await client.executeMode(
      'virtual-try-on',
      'virtual-try-on-001',
      'fit this garment',
      [],
      {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        imageAspectRatio: '1:1',
        imageResolution: '1K',
        baseSteps: 32,
        sessionId: 'session-2',
        messageId: 'message-2',
      },
      {}
    );

    const body = getPostedBody(fetchMock);

    expect(body.options).toMatchObject({
      baseSteps: 32,
      sessionId: 'session-2',
      messageId: 'message-2',
    });
  });

  it('flattens legacy outPainting options into the unified outpainting payload', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    await client.executeMode(
      'image-outpainting',
      'imagen-3.0-capability-001',
      'extend background',
      [],
      {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        imageAspectRatio: '1:1',
        imageResolution: '1K',
        outPainting: {
          mode: 'ratio',
          aspectRatio: '16:9',
        },
      } as ChatOptions,
      {}
    );

    const body = getPostedBody(fetchMock);

    expect(body.options).toMatchObject({
      outpaintMode: 'ratio',
      outputRatio: '16:9',
    });
    expect(body.options).not.toHaveProperty('outPainting');
  });

  it('keeps OpenAI video params and forwards the selected model id', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('openai');
    await client.generateVideo(
      'sora-2-pro',
      'make a portrait product teaser',
      [],
      {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        imageAspectRatio: '16:9',
        imageResolution: '1K',
        aspectRatio: '9:16',
        resolution: '2K',
        seconds: '8',
        sessionId: 'session-3',
        messageId: 'message-3',
      } as ChatOptions,
      '',
      ''
    );

    const body = getPostedBody(fetchMock);

    expect(body.modelId).toBe('sora-2-pro');
    expect(body.options).toMatchObject({
      aspectRatio: '9:16',
      resolution: '2K',
      seconds: '8',
      sessionId: 'session-3',
      messageId: 'message-3',
    });
  });

  it('keeps audio mode model id when generating speech', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('openai');
    await client.generateSpeech(
      'tts-1-hd',
      'narrate this',
      'nova',
      '',
      ''
    );

    const body = getPostedBody(fetchMock);

    expect(body.modelId).toBe('tts-1-hd');
    expect(body.extra).toEqual({
      voice: 'nova',
    });
  });
});

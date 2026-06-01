import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UnifiedProviderClient } from './UnifiedProviderClient';
import type { Attachment, ChatOptions } from '../../types/types';
import { removeAccessToken, setAccessToken } from '../authTokenStore';

const successResponse = () =>
  new Response(JSON.stringify({ success: true, data: {} }), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });

describe('UnifiedProviderClient mode payload sanitization', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: () => null,
      removeItem: () => undefined,
    });
  });

  afterEach(() => {
    removeAccessToken();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  const getPostedBody = (fetchMock: ReturnType<typeof vi.fn>) => {
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    return JSON.parse(String(init?.body || '{}'));
  };

  const getRequestInit = (fetchMock: ReturnType<typeof vi.fn>) =>
    fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;

  it('uses cookie-first auth for model listing even when a stale memory token exists', async () => {
    setAccessToken('stale-access-token');
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ models: [] }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    await client.getAvailableModels();

    const init = getRequestInit(fetchMock);
    const headers = new Headers(init?.headers);
    expect(headers.has('Authorization')).toBe(false);
    expect(init?.credentials).toBe('include');
  });

  it('uses cookie-first auth for mode execution even when a stale memory token exists', async () => {
    setAccessToken('stale-access-token');
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    await client.executeMode(
      'image-gen',
      'gemini-3.1-flash-image-preview',
      'draw a cat',
      [],
      {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
      },
      {}
    );

    const init = getRequestInit(fetchMock);
    const headers = new Headers(init?.headers);
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.has('Authorization')).toBe(false);
    expect(init?.credentials).toBe('include');
  });

  it('uses cookie-first auth for provider file uploads', async () => {
    setAccessToken('stale-access-token');
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ fileId: 'file-1' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    await client.uploadFile(new File(['hello'], 'hello.txt', { type: 'text/plain' }), '', '');

    const init = getRequestInit(fetchMock);
    const headers = new Headers(init?.headers);
    expect(headers.has('Authorization')).toBe(false);
    expect(init?.credentials).toBe('include');
  });

  it('drops non-mode chat and workflow fields from image mode requests', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    const options: ChatOptions = {
      enableSearch: false,
      enableThinking: true,
      enhancePrompt: true,
      enhancePromptThinkingLevel: 'high',
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
      enableThinking: true,
      enhancePrompt: true,
      enhancePromptThinkingLevel: 'high',
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

  it('keeps OpenAI previous response id for image continuation state', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          success: true,
          data: {
            images: [
              {
                url: 'data:image/png;base64,result',
                mimeType: 'image/png',
                openaiResponseId: 'resp_456',
              },
            ],
          },
        }),
        {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('openai');
    const result = await client.executeMode(
      'image-gen',
      'gpt-image-2',
      'draw a product scene',
      [],
      {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        imageAspectRatio: '1:1',
        imageResolution: '1K',
        openaiPreviousResponseId: 'resp_123',
      },
      {}
    );

    const body = getPostedBody(fetchMock);
    expect(body.options).toMatchObject({
      openaiPreviousResponseId: 'resp_123',
    });
    expect(body.options).not.toHaveProperty('openaiImageApi');
    expect(body.options).not.toHaveProperty('openaiResponsesModel');
    expect(result[0].openaiResponseId).toBe('resp_456');
  });

  it('keeps pdf extraction template options instead of dropping them before backend mapping', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('openai');
    await client.executeMode(
      'pdf-extract',
      'gpt-5.4-mini',
      'extract fields',
      [],
      {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        pdfExtractTemplate: 'invoice',
        pdfAdditionalInstructions: 'Use USD totals.',
      },
      {}
    );

    const body = getPostedBody(fetchMock);
    expect(body.options).toMatchObject({
      pdfExtractTemplate: 'invoice',
      pdfAdditionalInstructions: 'Use USD totals.',
    });
  });

  it('marks mask reference attachments with role=mask when using image-mask-edit', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const rawAttachment: Attachment = {
      id: 'raw-1',
      name: 'raw.png',
      mimeType: 'image/png',
      url: 'data:image/png;base64,raw',
    };
    const maskAttachment: Attachment = {
      id: 'mask-1',
      name: 'mask.png',
      mimeType: 'image/png',
      url: 'data:image/png;base64,mask',
    };

    const client = new UnifiedProviderClient('google');
    await client.editImage(
      'imagen-3.0-capability-001',
      'insert a product detail in the masked area',
      {
        raw: rawAttachment,
        mask: maskAttachment,
      },
      {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        maskMode: 'MASK_MODE_USER_PROVIDED',
      },
      '',
      'image-mask-edit'
    );

    const body = getPostedBody(fetchMock);

    expect(body.attachments).toHaveLength(2);
    expect(body.attachments[0]).toMatchObject({
      id: 'raw-1',
      url: 'data:image/png;base64,raw',
    });
    expect(body.attachments[1]).toMatchObject({
      id: 'mask-1',
      url: 'data:image/png;base64,mask',
      role: 'mask',
    });
  });

  it('keeps semantic mask class ids for image-mask-edit People mode', async () => {
    const fetchMock = vi.fn(async () => successResponse());
    vi.stubGlobal('fetch', fetchMock);

    const client = new UnifiedProviderClient('google');
    await client.executeMode(
      'image-mask-edit',
      'imagen-3.0-capability-001',
      'replace the person outfit',
      [],
      {
        enableSearch: false,
        enableThinking: false,
        enableCodeExecution: false,
        maskMode: 'MASK_MODE_SEMANTIC',
        segmentationClasses: [125],
      } as ChatOptions,
      {}
    );

    const body = getPostedBody(fetchMock);

    expect(body.options).toMatchObject({
      maskMode: 'MASK_MODE_SEMANTIC',
      segmentationClasses: [125],
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

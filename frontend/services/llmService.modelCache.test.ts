// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager } from './CacheManager';
import { scopedPrivateCacheKey, setPrivateCacheUserScope } from './privateCacheScope';
import { LLMService } from './llmService';

const mocks = vi.hoisted(() => ({
  fetchWithTimeout: vi.fn(),
  readJsonResponse: vi.fn(),
}));

vi.mock('./http', () => ({
  fetchWithTimeout: mocks.fetchWithTimeout,
  parseHttpError: vi.fn(async () => ({ message: '', status: 500 })),
  readJsonResponse: mocks.readJsonResponse,
}));

const model = (id: string) => ({
  id,
  name: id,
  description: id,
  capabilities: {
    vision: false,
    search: false,
    reasoning: false,
    coding: false,
  },
  contextWindow: 0,
});

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('LLMService model cache scope', () => {
  beforeEach(() => {
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
    vi.clearAllMocks();
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
  });

  it('keeps provider model payloads isolated by current private cache user scope', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'google', 'google');
    mocks.readJsonResponse
      .mockResolvedValueOnce({
        models: [model('user-one-model')],
        defaultModelId: 'user-one-model',
        modeCatalog: [],
      })
      .mockResolvedValueOnce({
        models: [model('user-two-model')],
        defaultModelId: 'user-two-model',
        modeCatalog: [],
      });

    setPrivateCacheUserScope('user-1');
    await expect(service.getAvailableModelsPayload(true)).resolves.toMatchObject({
      models: [{ id: 'user-one-model' }],
    });

    setPrivateCacheUserScope('user-2');
    await expect(service.getAvailableModelsPayload(true)).resolves.toMatchObject({
      models: [{ id: 'user-two-model' }],
    });

    setPrivateCacheUserScope('user-1');
    await expect(service.getAvailableModelsPayload(true)).resolves.toMatchObject({
      models: [{ id: 'user-one-model' }],
    });
    expect(mocks.fetchWithTimeout).toHaveBeenCalledTimes(2);
  });

  it('returns an in-flight same-provider payload after cache clear without writing it back to cache', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'google', 'google');
    setPrivateCacheUserScope('user-1');
    const pendingPayload = createDeferred<{
      models: ReturnType<typeof model>[];
      defaultModelId: string;
      modeCatalog: unknown[];
    }>();
    mocks.readJsonResponse.mockReturnValueOnce(pendingPayload.promise);

    const pendingModels = service.getAvailableModelsPayload(true);
    await Promise.resolve();

    service.clearModelCache();
    pendingPayload.resolve({
      models: [model('late-model')],
      defaultModelId: 'late-model',
      modeCatalog: [],
    });

    await expect(pendingModels).resolves.toMatchObject({
      models: [{ id: 'late-model' }],
      defaultModelId: 'late-model',
      provider: 'google',
    });
    expect(cacheManager.get(scopedPrivateCacheKey('models:', 'google:visible'))).toBeNull();
  });

  it('fails closed when an in-flight model request resolves after provider changes', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'google', 'google');
    setPrivateCacheUserScope('user-1');
    const pendingPayload = createDeferred<{
      models: ReturnType<typeof model>[];
      defaultModelId: string;
      modeCatalog: unknown[];
    }>();
    mocks.readJsonResponse.mockReturnValueOnce(pendingPayload.promise);

    const pendingModels = service.getAvailableModelsPayload(true);
    await Promise.resolve();

    service.setConfig('', '', 'openai', 'openai');
    pendingPayload.resolve({
      models: [model('late-google-model')],
      defaultModelId: 'late-google-model',
      modeCatalog: [],
    });

    await expect(pendingModels).resolves.toEqual({
      models: [],
      defaultModelId: null,
      modeCatalog: [],
      filteredByMode: null,
      cached: false,
      provider: 'google',
    });
    expect(cacheManager.get(scopedPrivateCacheKey('models:', 'google:visible'))).toBeNull();
  });

  it('fails closed when an in-flight model request resolves after private scope changes', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'google', 'google');
    setPrivateCacheUserScope('user-1');
    const pendingPayload = createDeferred<{
      models: ReturnType<typeof model>[];
      defaultModelId: string;
      modeCatalog: unknown[];
    }>();
    mocks.readJsonResponse.mockReturnValueOnce(pendingPayload.promise);

    const pendingModels = service.getAvailableModelsPayload(true, 'chat');
    await Promise.resolve();

    setPrivateCacheUserScope('user-2');
    pendingPayload.resolve({
      models: [model('user-one-late-chat-model')],
      defaultModelId: 'user-one-late-chat-model',
      modeCatalog: [],
    });

    await expect(pendingModels).resolves.toEqual({
      models: [],
      defaultModelId: null,
      modeCatalog: [],
      filteredByMode: 'chat',
      cached: false,
      provider: 'google',
    });
    setPrivateCacheUserScope('user-1');
    expect(cacheManager.get(scopedPrivateCacheKey('models:', 'google:chat:visible'))).toBeNull();
  });
});

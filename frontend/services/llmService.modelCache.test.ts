// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
    vi.useRealTimers();
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
    vi.clearAllMocks();
    mocks.fetchWithTimeout.mockResolvedValue(new Response('{}', { status: 200 }));
  });

  afterEach(() => {
    vi.useRealTimers();
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

  it('reuses an in-flight model payload request for the same scoped key', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'openai', 'openai');
    setPrivateCacheUserScope('user-1');
    const pendingPayload = createDeferred<{
      models: ReturnType<typeof model>[];
      defaultModelId: string;
      modeCatalog: unknown[];
      filteredByMode: string;
    }>();
    mocks.readJsonResponse.mockReturnValueOnce(pendingPayload.promise);

    const first = service.getAvailableModelsPayload(true, 'chat');
    const second = service.getAvailableModelsPayload(true, 'chat');
    await Promise.resolve();

    expect(mocks.fetchWithTimeout).toHaveBeenCalledTimes(1);

    pendingPayload.resolve({
      models: [model('gpt-4o')],
      defaultModelId: 'gpt-4o',
      modeCatalog: [],
      filteredByMode: 'chat',
    });

    await expect(Promise.all([first, second])).resolves.toEqual([
      expect.objectContaining({ models: [{ id: 'gpt-4o', name: 'gpt-4o', description: 'gpt-4o', capabilities: expect.any(Object), contextWindow: 0 }] }),
      expect.objectContaining({ models: [{ id: 'gpt-4o', name: 'gpt-4o', description: 'gpt-4o', capabilities: expect.any(Object), contextWindow: 0 }] }),
    ]);
  });

  it('keeps all-model and mode-model payload requests as separate keys', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'openai', 'openai');
    setPrivateCacheUserScope('user-1');
    mocks.readJsonResponse
      .mockResolvedValueOnce({
        models: [model('all-model')],
        defaultModelId: 'all-model',
        modeCatalog: [],
      })
      .mockResolvedValueOnce({
        models: [model('chat-model')],
        defaultModelId: 'chat-model',
        modeCatalog: [],
        filteredByMode: 'chat',
      });

    await Promise.all([
      service.getAvailableModelsPayload(true),
      service.getAvailableModelsPayload(true, 'chat'),
    ]);

    expect(mocks.fetchWithTimeout).toHaveBeenCalledTimes(2);
    expect(mocks.fetchWithTimeout.mock.calls[0][0]).toContain('/api/models/openai?');
    expect(mocks.fetchWithTimeout.mock.calls[1][0]).toContain('mode=chat');
  });

  it('rethrows an in-flight model request error and allows retrying the key', async () => {
    const service = new LLMService();
    service.setConfig('', '', 'openai', 'openai');
    setPrivateCacheUserScope('user-1');
    mocks.fetchWithTimeout.mockRejectedValueOnce(new Error('network down'));

    const first = service.getAvailableModelsPayload(true, 'chat');
    const second = service.getAvailableModelsPayload(true, 'chat');
    await Promise.resolve();

    expect(mocks.fetchWithTimeout).toHaveBeenCalledTimes(1);
    await expect(Promise.all([first, second])).rejects.toThrow('network down');

    mocks.fetchWithTimeout.mockResolvedValueOnce(new Response('{}', { status: 200 }));
    mocks.readJsonResponse.mockResolvedValueOnce({
      models: [model('retry-model')],
      defaultModelId: 'retry-model',
      modeCatalog: [],
      filteredByMode: 'chat',
    });

    await expect(service.getAvailableModelsPayload(true, 'chat')).resolves.toMatchObject({
      models: [{ id: 'retry-model' }],
    });
    expect(mocks.fetchWithTimeout).toHaveBeenCalledTimes(2);
  });

  it('keeps model payload cache for the default window (not shortened to 30s)', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-14T00:00:00Z'));
    const service = new LLMService();
    service.setConfig('', '', 'openai', 'openai');
    setPrivateCacheUserScope('user-1');
    mocks.readJsonResponse.mockResolvedValueOnce({
      models: [model('initial-model')],
      defaultModelId: 'initial-model',
      modeCatalog: [],
    });

    await expect(service.getAvailableModelsPayload(true)).resolves.toMatchObject({
      models: [{ id: 'initial-model' }],
    });
    await expect(service.getAvailableModelsPayload(true)).resolves.toMatchObject({
      models: [{ id: 'initial-model' }],
    });
    expect(mocks.fetchWithTimeout).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(30001);

    await expect(service.getAvailableModelsPayload(true)).resolves.toMatchObject({
      models: [{ id: 'initial-model' }],
    });
    expect(mocks.fetchWithTimeout).toHaveBeenCalledTimes(1);
  });
});

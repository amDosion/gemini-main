// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ModelConfig } from '../types/types';
import { cacheManager, CACHE_DOMAINS } from '../services/CacheManager';
import { clearPrivateMemoryCaches } from '../services/privateClientCache';
import {
  scopedPrivateCacheKey,
  setPrivateCacheUserScope,
} from '../services/privateCacheScope';
import {
  __resetEnhancePromptModelsCacheForTesting,
  useEnhancePromptModels,
} from './useEnhancePromptModels';

const getAvailableModelsPayloadMock = vi.hoisted(() => vi.fn());

vi.mock('../services/llmService', () => ({
  llmService: {
    getProviderId: () => 'openai',
    getAvailableModelsPayload: getAvailableModelsPayloadMock,
  },
}));

const model = (id: string, name = id): ModelConfig => ({
  id,
  name,
  description: id,
  capabilities: {
    vision: false,
    search: false,
    reasoning: id.startsWith('gpt-') && !id.startsWith('gpt-image'),
    coding: false,
  },
});

const visionModel = (id: string, name = id): ModelConfig => ({
  ...model(id, name),
  capabilities: {
    ...model(id, name).capabilities,
    vision: true,
  },
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

afterEach(() => {
  cleanup();
  __resetEnhancePromptModelsCacheForTesting();
  cacheManager.clearAll();
  setPrivateCacheUserScope(null);
  getAvailableModelsPayloadMock.mockReset();
});

describe('useEnhancePromptModels', () => {
  it('uses current profile models instead of a stale provider-level empty cache', async () => {
    getAvailableModelsPayloadMock.mockResolvedValue({
      provider: 'openai',
      models: [model('gpt-image-2', 'GPT Image 2')],
      defaultModelId: null,
      modeCatalog: [],
    });

    const first = renderHook(() => useEnhancePromptModels('openai'));

    await waitFor(() => {
      expect(first.result.current).toEqual([]);
    });

    const currentProfileModels = [
      model('gpt-5.5', 'GPT 5.5'),
      model('gpt-image-2', 'GPT Image 2'),
    ];

    const second = renderHook(() => useEnhancePromptModels('openai', currentProfileModels));

    await waitFor(() => {
      expect(second.result.current.map((item) => item.id)).toEqual(['gpt-5.5']);
    });
  });

  it('does not fetch provider-wide models when caller supplies a model list with no valid prompt enhancers', async () => {
    getAvailableModelsPayloadMock.mockResolvedValue({
      provider: 'tongyi',
      models: [
        model('qwen-plus', 'Qwen Plus'),
        visionModel('qwen-vl-max', 'Qwen VL Max'),
        visionModel('wan2.7-image-pro', 'Wan 2.7 Image Pro'),
      ],
      defaultModelId: null,
      modeCatalog: [],
    });

    const modeSpecificModels = [
      visionModel('qwen-image-edit-plus', 'Qwen Image Edit Plus'),
      visionModel('wan2.7-image-pro', 'Wan 2.7 Image Pro'),
    ];

    const hook = renderHook(() =>
      useEnhancePromptModels('tongyi', modeSpecificModels, { requiresVision: true })
    );

    await waitFor(() => {
      expect(hook.result.current).toEqual([]);
    });
    expect(getAvailableModelsPayloadMock).not.toHaveBeenCalled();
  });

  it('can explicitly load hidden provider models for utility prompt enhancers', async () => {
    getAvailableModelsPayloadMock.mockResolvedValue({
      provider: 'tongyi',
      models: [
        visionModel('qwen-vl-max-latest', 'Qwen VL Max Latest'),
        visionModel('wan2.7-image-pro', 'Wan 2.7 Image Pro'),
      ],
      defaultModelId: null,
      modeCatalog: [],
    });

    const hook = renderHook(() =>
      useEnhancePromptModels('tongyi', undefined, {
        requiresVision: true,
        includeHidden: true,
      })
    );

    await waitFor(() => {
      expect(hook.result.current.map((item) => item.id)).toEqual(['qwen-vl-max-latest']);
    });
    expect(getAvailableModelsPayloadMock).toHaveBeenCalledWith(true, undefined, {
      includeHidden: true,
    });
  });

  it('does not reuse provider-wide prompt enhancer cache across private user scopes', async () => {
    setPrivateCacheUserScope('user-1');
    getAvailableModelsPayloadMock.mockResolvedValueOnce({
      provider: 'openai',
      models: [model('gpt-5.5', 'GPT 5.5')],
      defaultModelId: null,
      modeCatalog: [],
    });

    const first = renderHook(() => useEnhancePromptModels('openai'));

    await waitFor(() => {
      expect(first.result.current.map((item) => item.id)).toEqual(['gpt-5.5']);
    });
    first.unmount();

    setPrivateCacheUserScope('user-2');
    getAvailableModelsPayloadMock.mockResolvedValueOnce({
      provider: 'openai',
      models: [model('gpt-5.6', 'GPT 5.6')],
      defaultModelId: null,
      modeCatalog: [],
    });

    const second = renderHook(() => useEnhancePromptModels('openai'));

    await waitFor(() => {
      expect(second.result.current.map((item) => item.id)).toEqual(['gpt-5.6']);
    });
    expect(getAvailableModelsPayloadMock).toHaveBeenCalledTimes(2);
  });

  it('reloads mounted provider-wide prompt enhancers when private user scope changes', async () => {
    let activeUser = 'user-1';
    getAvailableModelsPayloadMock.mockImplementation(async () => ({
      provider: 'openai',
      models: [
        model(activeUser === 'user-1' ? 'gpt-5.5' : 'gpt-5.6'),
      ],
      defaultModelId: null,
      modeCatalog: [],
    }));

    setPrivateCacheUserScope('user-1');
    const hook = renderHook(() => useEnhancePromptModels('openai'));

    await waitFor(() => {
      expect(hook.result.current.map((item) => item.id)).toEqual(['gpt-5.5']);
    });

    activeUser = 'user-2';
    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    await waitFor(() => {
      expect(hook.result.current.map((item) => item.id)).toEqual(['gpt-5.6']);
    });
  });

  it('does not repopulate prompt enhancer cache when an in-flight request resolves after cache clear', async () => {
    setPrivateCacheUserScope('user-1');
    const staleRequest = createDeferred<{
      provider: string;
      models: ModelConfig[];
      defaultModelId: string | null;
      modeCatalog: unknown[];
    }>();
    const currentRequest = createDeferred<{
      provider: string;
      models: ModelConfig[];
      defaultModelId: string | null;
      modeCatalog: unknown[];
    }>();
    getAvailableModelsPayloadMock
      .mockReturnValueOnce(staleRequest.promise)
      .mockReturnValueOnce(currentRequest.promise);

    const hook = renderHook(() => useEnhancePromptModels('openai'));

    await waitFor(() => {
      expect(getAvailableModelsPayloadMock).toHaveBeenCalledTimes(1);
    });

    setPrivateCacheUserScope('user-2');
    clearPrivateMemoryCaches();
    await waitFor(() => {
      expect(getAvailableModelsPayloadMock).toHaveBeenCalledTimes(2);
    });

    await act(async () => {
      staleRequest.resolve({
        provider: 'openai',
        models: [model('gpt-5.5', 'GPT 5.5')],
        defaultModelId: null,
        modeCatalog: [],
      });
      await staleRequest.promise;
    });

    await waitFor(() => {
      expect(hook.result.current).toEqual([]);
    });
    expect(
      cacheManager.get<ModelConfig[]>(
        scopedPrivateCacheKey(
          CACHE_DOMAINS.ENHANCE_PROMPT_MODELS,
          'openai:default:visible',
          'user-1'
        )
      )
    ).toBeNull();

    await act(async () => {
      currentRequest.resolve({
        provider: 'openai',
        models: [model('gpt-5.6', 'GPT 5.6')],
        defaultModelId: null,
        modeCatalog: [],
      });
      await currentRequest.promise;
    });

    await waitFor(() => {
      expect(hook.result.current.map((item) => item.id)).toEqual(['gpt-5.6']);
    });
  });
});

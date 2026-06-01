// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { clearPrivateMemoryCaches } from '../services/privateClientCache';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';
import { useModels } from './useModels';

const { getAvailableModelsPayloadMock, clearModelCacheMock } = vi.hoisted(() => ({
  getAvailableModelsPayloadMock: vi.fn(),
  clearModelCacheMock: vi.fn(),
}));

vi.mock('../services/llmService', () => ({
  llmService: {
    getAvailableModelsPayload: getAvailableModelsPayloadMock,
    clearModelCache: clearModelCacheMock,
  },
}));

const DEFAULT_MODEL = {
  id: 'gemini-3.1-pro-preview',
  name: 'Gemini 3.1 Pro Preview',
  description: 'test model',
  capabilities: {
    vision: true,
    search: true,
    reasoning: true,
    coding: true,
  },
};

const IMAGE_MODEL = {
  id: 'imagen-4',
  name: 'Imagen 4',
  description: 'image model',
  capabilities: {
    vision: true,
    search: false,
    reasoning: false,
    coding: false,
  },
};

const USER_TWO_MODEL = {
  id: 'gemini-user-two',
  name: 'Gemini User Two',
  description: 'user two model',
  capabilities: {
    vision: true,
    search: true,
    reasoning: true,
    coding: true,
  },
};

const LEGACY_RECONTEXT_MODEL = {
  id: 'imagen-3.0-capability-001',
  name: 'Imagen Capability',
  description: 'legacy edit model',
  capabilities: {
    vision: true,
    search: false,
    reasoning: false,
    coding: false,
  },
};

const GEMINI_IMAGE_MODEL = {
  id: 'gemini-2.5-flash-image',
  name: 'Gemini 2.5 Flash Image',
  description: 'image generation and editing',
  capabilities: {
    vision: true,
    search: true,
    reasoning: false,
    coding: false,
  },
};

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('useModels cache invalidation', () => {
  beforeEach(() => {
    setPrivateCacheUserScope(null);
    getAvailableModelsPayloadMock.mockReset();
    clearModelCacheMock.mockReset();

    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => ({
      models: [DEFAULT_MODEL],
      defaultModelId: DEFAULT_MODEL.id,
      modeCatalog: [{ id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 }],
      filteredByMode: mode || null,
    }));
  });

  it('invalidates model cache and bypasses cache when active profile cache key changes', async () => {
    const { rerender } = renderHook(
      ({ profileKey }) => useModels(true, 'google', 'chat', profileKey),
      { initialProps: { profileKey: 'profile-a:1' } }
    );

    await waitFor(() => {
      expect(getAvailableModelsPayloadMock).toHaveBeenCalled();
    });

    getAvailableModelsPayloadMock.mockClear();
    clearModelCacheMock.mockClear();

    rerender({ profileKey: 'profile-a:2' });

    await waitFor(() => {
      expect(getAvailableModelsPayloadMock.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    expect(clearModelCacheMock).toHaveBeenCalledTimes(1);
    expect(
      getAvailableModelsPayloadMock.mock.calls.some(
        ([useCache, mode]) => useCache === false && mode === undefined
      )
    ).toBe(true);
  });

  it('returns empty mode models when mode refresh fails', async () => {
    getAvailableModelsPayloadMock.mockRejectedValue(new Error('provider unavailable'));

    const { result } = renderHook(() =>
      useModels(true, 'google', 'chat', 'profile-a:1', [DEFAULT_MODEL])
    );

    await waitFor(() => {
      expect(result.current.visibleModels.length).toBe(0);
    });
    await waitFor(() => {
      expect(result.current.isLoadingModels).toBe(false);
    });
  });

  it('ignores model payloads from before private cache reset', async () => {
    const staleAll = createDeferred<unknown>();
    const staleMode = createDeferred<unknown>();
    const currentAll = createDeferred<unknown>();
    const currentMode = createDeferred<unknown>();

    let requestPhase: 'stale' | 'current' = 'stale';
    getAvailableModelsPayloadMock.mockImplementation((_useCache: boolean, mode?: string) => {
      if (requestPhase === 'stale') {
        return mode ? staleMode.promise : staleAll.promise;
      }
      return mode ? currentMode.promise : currentAll.promise;
    });

    const { result } = renderHook(() => useModels(true, 'google', 'chat', 'profile-a:1'));

    await waitFor(() => {
      expect(getAvailableModelsPayloadMock).toHaveBeenCalledTimes(2);
    });

    requestPhase = 'current';
    act(() => {
      clearPrivateMemoryCaches();
    });

    await waitFor(() => {
      expect(result.current.visibleModels).toEqual([]);
    });

    await act(async () => {
      staleAll.resolve({
        models: [DEFAULT_MODEL],
        defaultModelId: DEFAULT_MODEL.id,
        modeCatalog: [{ id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 }],
      });
      staleMode.resolve({
        models: [DEFAULT_MODEL],
        defaultModelId: DEFAULT_MODEL.id,
        modeCatalog: [{ id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 }],
        filteredByMode: 'chat',
      });
      await Promise.all([staleAll.promise, staleMode.promise]);
    });

    expect(result.current.visibleModels).toEqual([]);

    await act(async () => {
      currentAll.resolve({
        models: [USER_TWO_MODEL],
        defaultModelId: USER_TWO_MODEL.id,
        modeCatalog: [{ id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 }],
      });
      currentMode.resolve({
        models: [USER_TWO_MODEL],
        defaultModelId: USER_TWO_MODEL.id,
        modeCatalog: [{ id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 }],
        filteredByMode: 'chat',
      });
      await Promise.all([currentAll.promise, currentMode.promise]);
    });

    await waitFor(() => {
      expect(result.current.visibleModels.map((model) => model.id)).toEqual([USER_TWO_MODEL.id]);
    });
  });

  it('reloads models when private cache user scope changes without an explicit cache reset', async () => {
    let activeUser = 'user-1';
    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => {
      const model = activeUser === 'user-1' ? DEFAULT_MODEL : USER_TWO_MODEL;
      return {
        models: [model],
        defaultModelId: model.id,
        modeCatalog: [{ id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 }],
        filteredByMode: mode || null,
      };
    });

    setPrivateCacheUserScope('user-1');
    const { result } = renderHook(() => useModels(true, 'google', 'chat', 'profile-a:1'));

    await waitFor(() => {
      expect(result.current.visibleModels.map((model) => model.id)).toEqual([DEFAULT_MODEL.id]);
    });

    activeUser = 'user-2';
    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    await waitFor(() => {
      expect(result.current.visibleModels.map((model) => model.id)).toEqual([USER_TWO_MODEL.id]);
    });
  });

  it('clears stale models immediately when switching mode and then loads new mode models', async () => {
    // 用 object 容器规避 TS strict 模式下闭包内可变 `let` 的 narrowing 失效（never）
    const resolveImageModeRef: { current: ((value: unknown) => void) | null } = { current: null };

    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => {
      if (!mode) {
        return {
          models: [DEFAULT_MODEL, IMAGE_MODEL],
          defaultModelId: DEFAULT_MODEL.id,
          modeCatalog: [
            { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
            { id: 'image-gen', label: 'Image', hasModels: true, availableModelCount: 1 },
          ],
          filteredByMode: null,
        };
      }

      if (mode === 'chat') {
        return {
          models: [DEFAULT_MODEL],
          defaultModelId: DEFAULT_MODEL.id,
          modeCatalog: [
            { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
            { id: 'image-gen', label: 'Image', hasModels: true, availableModelCount: 1 },
          ],
          filteredByMode: 'chat',
        };
      }

      if (mode === 'image-gen') {
        return await new Promise((resolve) => {
          resolveImageModeRef.current = resolve;
        });
      }

      return {
        models: [],
        defaultModelId: null,
        modeCatalog: [
          { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
          { id: 'image-gen', label: 'Image', hasModels: true, availableModelCount: 1 },
        ],
        filteredByMode: mode,
      };
    });

    const initialProps: { mode: 'chat' | 'image-gen' } = { mode: 'chat' };
    const { result, rerender } = renderHook(
      ({ mode }: { mode: 'chat' | 'image-gen' }) =>
        useModels(true, 'google', mode, 'profile-a:1', [DEFAULT_MODEL, IMAGE_MODEL]),
      { initialProps }
    );

    await waitFor(() => {
      expect(result.current.visibleModels.map((m) => m.id)).toEqual([DEFAULT_MODEL.id]);
    });

    rerender({ mode: 'image-gen' as const });

    await waitFor(() => {
      expect(result.current.isLoadingModels).toBe(true);
      expect(result.current.visibleModels).toEqual([]);
    });

    resolveImageModeRef.current?.({
      models: [IMAGE_MODEL],
      defaultModelId: IMAGE_MODEL.id,
      modeCatalog: [
        { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
        { id: 'image-gen', label: 'Image', hasModels: true, availableModelCount: 1 },
      ],
      filteredByMode: 'image-gen',
    });

    await waitFor(() => {
      expect(result.current.isLoadingModels).toBe(false);
      expect(result.current.visibleModels.map((m) => m.id)).toEqual([IMAGE_MODEL.id]);
    });
  });

  it('keeps the navigation mode catalog visible while a provider switch reload is in flight', async () => {
    const initialCatalog = [
      { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
      { id: 'image-gen', label: 'Image', hasModels: true, availableModelCount: 1 },
    ];
    const nextCatalog = [
      { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
      { id: 'image-gen', label: 'Image', hasModels: true, availableModelCount: 1 },
      { id: 'video-gen', label: 'Video', hasModels: false, availableModelCount: 0 },
    ];
    const openaiAll = createDeferred<unknown>();
    const openaiMode = createDeferred<unknown>();
    let providerPhase: 'google' | 'openai' = 'google';

    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => {
      if (providerPhase === 'google') {
        return {
          models: [DEFAULT_MODEL],
          defaultModelId: DEFAULT_MODEL.id,
          modeCatalog: initialCatalog,
          filteredByMode: mode || null,
        };
      }
      return mode ? openaiMode.promise : openaiAll.promise;
    });

    const { result, rerender } = renderHook(
      ({ provider, profileKey }) => useModels(true, provider, 'chat', profileKey),
      { initialProps: { provider: 'google', profileKey: 'google-profile:1' } }
    );

    await waitFor(() => {
      expect(result.current.modeCatalog.map((mode) => mode.id)).toEqual(['chat', 'image-gen']);
    });

    providerPhase = 'openai';
    rerender({ provider: 'openai', profileKey: 'openai-profile:1' });

    await waitFor(() => {
      expect(result.current.isLoadingModels).toBe(true);
    });
    expect(result.current.modeCatalog.map((mode) => mode.id)).toEqual(['chat', 'image-gen']);

    await act(async () => {
      openaiAll.resolve({
        models: [DEFAULT_MODEL],
        defaultModelId: DEFAULT_MODEL.id,
        modeCatalog: nextCatalog,
        filteredByMode: null,
      });
      openaiMode.resolve({
        models: [DEFAULT_MODEL],
        defaultModelId: DEFAULT_MODEL.id,
        modeCatalog: nextCatalog,
        filteredByMode: 'chat',
      });
      await Promise.all([openaiAll.promise, openaiMode.promise]);
    });

    await waitFor(() => {
      expect(result.current.modeCatalog.map((mode) => mode.id)).toEqual([
        'chat',
        'image-gen',
        'video-gen',
      ]);
    });
  });

  it('keeps the navigation mode catalog visible while a profile switch reload is in flight', async () => {
    const initialCatalog = [
      { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
      { id: 'image-gen', label: 'Image', hasModels: true, availableModelCount: 1 },
    ];
    const nextCatalog = [
      { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
      { id: 'video-gen', label: 'Video', hasModels: true, availableModelCount: 1 },
    ];
    const nextAll = createDeferred<unknown>();
    const nextMode = createDeferred<unknown>();
    let profilePhase: 'profile-a' | 'profile-b' = 'profile-a';

    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => {
      if (profilePhase === 'profile-a') {
        return {
          models: [DEFAULT_MODEL],
          defaultModelId: DEFAULT_MODEL.id,
          modeCatalog: initialCatalog,
          filteredByMode: mode || null,
        };
      }
      return mode ? nextMode.promise : nextAll.promise;
    });

    const { result, rerender } = renderHook(
      ({ profileKey }) => useModels(true, 'google', 'chat', profileKey),
      { initialProps: { profileKey: 'profile-a:1' } }
    );

    await waitFor(() => {
      expect(result.current.modeCatalog.map((mode) => mode.id)).toEqual(['chat', 'image-gen']);
    });

    profilePhase = 'profile-b';
    rerender({ profileKey: 'profile-b:1' });

    await waitFor(() => {
      expect(result.current.isLoadingModels).toBe(true);
    });
    expect(result.current.modeCatalog.map((mode) => mode.id)).toEqual(['chat', 'image-gen']);

    await act(async () => {
      nextAll.resolve({
        models: [DEFAULT_MODEL],
        defaultModelId: DEFAULT_MODEL.id,
        modeCatalog: nextCatalog,
        filteredByMode: null,
      });
      nextMode.resolve({
        models: [DEFAULT_MODEL],
        defaultModelId: DEFAULT_MODEL.id,
        modeCatalog: nextCatalog,
        filteredByMode: 'chat',
      });
      await Promise.all([nextAll.promise, nextMode.promise]);
    });

    await waitFor(() => {
      expect(result.current.modeCatalog.map((mode) => mode.id)).toEqual(['chat', 'video-gen']);
    });
  });

  it('clears preserved navigation mode catalog when a provider switch reload fails', async () => {
    const initialCatalog = [
      { id: 'chat', label: 'Chat', hasModels: true, availableModelCount: 1 },
      { id: 'image-gen', label: 'Image', hasModels: true, availableModelCount: 1 },
    ];
    const failedAll = createDeferred<unknown>();
    const failedMode = createDeferred<unknown>();
    let providerPhase: 'google' | 'openai' = 'google';

    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => {
      if (providerPhase === 'google') {
        return {
          models: [DEFAULT_MODEL],
          defaultModelId: DEFAULT_MODEL.id,
          modeCatalog: initialCatalog,
          filteredByMode: mode || null,
        };
      }
      return mode ? failedMode.promise : failedAll.promise;
    });

    const { result, rerender } = renderHook(
      ({ provider, profileKey }) => useModels(true, provider, 'chat', profileKey),
      { initialProps: { provider: 'google', profileKey: 'google-profile:1' } }
    );

    await waitFor(() => {
      expect(result.current.modeCatalog.map((mode) => mode.id)).toEqual(['chat', 'image-gen']);
    });

    providerPhase = 'openai';
    rerender({ provider: 'openai', profileKey: 'openai-profile:1' });

    await waitFor(() => {
      expect(result.current.isLoadingModels).toBe(true);
    });
    expect(result.current.modeCatalog.map((mode) => mode.id)).toEqual(['chat', 'image-gen']);

    await act(async () => {
      failedAll.reject(new Error('openai models unavailable'));
      failedMode.reject(new Error('openai chat models unavailable'));
      await Promise.allSettled([failedAll.promise, failedMode.promise]);
    });

    await waitFor(() => {
      expect(result.current.isLoadingModels).toBe(false);
      expect(result.current.modeCatalog).toEqual([]);
    });
  });

  it('filters recontext mode to Gemini image models and selects the replacement model', async () => {
    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => {
      if (!mode) {
        return {
          models: [LEGACY_RECONTEXT_MODEL, GEMINI_IMAGE_MODEL],
          defaultModelId: DEFAULT_MODEL.id,
          modeCatalog: [
            { id: 'image-recontext', label: 'Recontext', hasModels: true, availableModelCount: 2 },
          ],
          filteredByMode: null,
        };
      }

      return {
        models: [LEGACY_RECONTEXT_MODEL, GEMINI_IMAGE_MODEL],
        defaultModelId: LEGACY_RECONTEXT_MODEL.id,
        modeCatalog: [
          { id: 'image-recontext', label: 'Recontext', hasModels: true, availableModelCount: 2 },
        ],
        filteredByMode: 'image-recontext',
      };
    });

    const { result } = renderHook(() =>
      useModels(true, 'google', 'image-recontext', 'profile-a:1')
    );

    await waitFor(() => {
      expect(result.current.visibleModels.map((m) => m.id)).toEqual([GEMINI_IMAGE_MODEL.id]);
      expect(result.current.currentModelId).toBe(GEMINI_IMAGE_MODEL.id);
    });
  });

  it('keeps recontext model filtering when models are manually refreshed', async () => {
    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => ({
      models: [LEGACY_RECONTEXT_MODEL, GEMINI_IMAGE_MODEL],
      defaultModelId: LEGACY_RECONTEXT_MODEL.id,
      modeCatalog: [
        { id: 'image-recontext', label: 'Recontext', hasModels: true, availableModelCount: 2 },
      ],
      filteredByMode: mode || null,
    }));

    const { result } = renderHook(() =>
      useModels(true, 'google', 'image-recontext', 'profile-a:1')
    );

    await waitFor(() => {
      expect(result.current.visibleModels.map((m) => m.id)).toEqual([GEMINI_IMAGE_MODEL.id]);
    });

    await act(async () => {
      await result.current.refreshModels();
    });

    expect(result.current.visibleModels.map((m) => m.id)).toEqual([GEMINI_IMAGE_MODEL.id]);
    expect(result.current.currentModelId).toBe(GEMINI_IMAGE_MODEL.id);
  });

  it('filters background edit mode to Imagen edit models and excludes Gemini image recontext models', async () => {
    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => ({
      models: [LEGACY_RECONTEXT_MODEL, GEMINI_IMAGE_MODEL, DEFAULT_MODEL],
      defaultModelId: GEMINI_IMAGE_MODEL.id,
      modeCatalog: [
        {
          id: 'image-background-edit',
          label: 'Background',
          hasModels: true,
          availableModelCount: 3,
        },
      ],
      filteredByMode: mode || null,
    }));

    const { result } = renderHook(() =>
      useModels(true, 'google', 'image-background-edit', 'profile-a:1')
    );

    await waitFor(() => {
      expect(result.current.visibleModels.map((m) => m.id)).toEqual([LEGACY_RECONTEXT_MODEL.id]);
      expect(result.current.currentModelId).toBe(LEGACY_RECONTEXT_MODEL.id);
    });
  });

  it('filters mask edit mode to Imagen edit models and excludes Gemini image models', async () => {
    getAvailableModelsPayloadMock.mockImplementation(async (_useCache: boolean, mode?: string) => ({
      models: [LEGACY_RECONTEXT_MODEL, GEMINI_IMAGE_MODEL, DEFAULT_MODEL],
      defaultModelId: GEMINI_IMAGE_MODEL.id,
      modeCatalog: [
        { id: 'image-mask-edit', label: 'Mask', hasModels: true, availableModelCount: 3 },
      ],
      filteredByMode: mode || null,
    }));

    const { result } = renderHook(() =>
      useModels(true, 'google', 'image-mask-edit', 'profile-a:1')
    );

    await waitFor(() => {
      expect(result.current.visibleModels.map((m) => m.id)).toEqual([LEGACY_RECONTEXT_MODEL.id]);
      expect(result.current.currentModelId).toBe(LEGACY_RECONTEXT_MODEL.id);
    });
  });
});

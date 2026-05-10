// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
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

describe('useModels cache invalidation', () => {
  beforeEach(() => {
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

  it('clears stale models immediately when switching mode and then loads new mode models', async () => {
    let resolveImageMode: ((value: any) => void) | null = null;

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
          resolveImageMode = resolve;
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

    const { result, rerender } = renderHook(
      ({ mode }: { mode: 'chat' | 'image-gen' }) => useModels(true, 'google', mode, 'profile-a:1', [DEFAULT_MODEL, IMAGE_MODEL]),
      { initialProps: { mode: 'chat' as const } }
    );

    await waitFor(() => {
      expect(result.current.visibleModels.map((m) => m.id)).toEqual([DEFAULT_MODEL.id]);
    });

    rerender({ mode: 'image-gen' as const });

    await waitFor(() => {
      expect(result.current.isLoadingModels).toBe(true);
      expect(result.current.visibleModels).toEqual([]);
    });

    resolveImageMode?.({
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
        { id: 'image-background-edit', label: 'Background', hasModels: true, availableModelCount: 3 },
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

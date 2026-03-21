// @vitest-environment jsdom
import { renderHook, waitFor } from '@testing-library/react';
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
});

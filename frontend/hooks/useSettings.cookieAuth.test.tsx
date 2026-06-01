// @vitest-environment jsdom

import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSettings } from './useSettings';
import { setPrivateCacheUserScope } from '../services/privateCacheScope';
import { clearPrivateMemoryCaches } from '../services/privateClientCache';

const mocks = vi.hoisted(() => ({
  clearEnhancePromptModelsCache: vi.fn(),
  getAccessToken: vi.fn(),
  getFullSettings: vi.fn(),
  llmClearModelCache: vi.fn(),
  llmSetConfig: vi.fn(),
}));

vi.mock('../services/apiClient', () => ({
  getAccessToken: mocks.getAccessToken,
}));

vi.mock('../services/configurationService', () => ({
  configService: {
    getFullSettings: mocks.getFullSettings,
    saveProfile: vi.fn(),
    setActiveProfileId: vi.fn(),
    clearProviderModelCache: vi.fn(),
  },
}));

vi.mock('../services/llmService', () => ({
  llmService: {
    clearModelCache: mocks.llmClearModelCache,
    setConfig: mocks.llmSetConfig,
  },
}));

vi.mock('./useEnhancePromptModels', () => ({
  clearEnhancePromptModelsCache: mocks.clearEnhancePromptModelsCache,
}));

const initialData = {
  profiles: [],
  activeProfileId: null,
  activeProfile: null,
  dashscopeKey: '',
};

const userOneInitialData = {
  profiles: [
    {
      id: 'profile-user-1',
      name: 'User 1 Profile',
      providerId: 'google',
      protocol: 'google',
      apiKey: 'user-1-api-key',
      baseUrl: '',
      isProxy: false,
      hiddenModels: [],
      savedModels: [],
      cachedModelCount: 0,
      createdAt: 1,
      updatedAt: 1,
    },
  ],
  activeProfileId: 'profile-user-1',
  activeProfile: {
    id: 'profile-user-1',
    name: 'User 1 Profile',
    providerId: 'google',
    protocol: 'google',
    apiKey: 'user-1-api-key',
    baseUrl: '',
    isProxy: false,
    hiddenModels: [],
    savedModels: [],
    cachedModelCount: 0,
    createdAt: 1,
    updatedAt: 1,
  },
  dashscopeKey: '',
};

const userTwoInitialData = {
  profiles: [
    {
      id: 'profile-user-2',
      name: 'User 2 Profile',
      providerId: 'openai',
      protocol: 'openai',
      apiKey: 'user-2-api-key',
      baseUrl: 'https://api.example.test/v1',
      isProxy: true,
      hiddenModels: [],
      savedModels: [],
      cachedModelCount: 0,
      createdAt: 2,
      updatedAt: 2,
    },
  ],
  activeProfileId: 'profile-user-2',
  activeProfile: {
    id: 'profile-user-2',
    name: 'User 2 Profile',
    providerId: 'openai',
    protocol: 'openai',
    apiKey: 'user-2-api-key',
    baseUrl: 'https://api.example.test/v1',
    isProxy: true,
    hiddenModels: [],
    savedModels: [],
    cachedModelCount: 0,
    createdAt: 2,
    updatedAt: 2,
  },
  dashscopeKey: '',
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

describe('useSettings cookie auth compatibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setPrivateCacheUserScope(null);
    mocks.getAccessToken.mockReturnValue(null);
    mocks.getFullSettings.mockResolvedValue({
      profiles: [],
      activeProfileId: null,
      activeProfile: null,
      dashscopeKey: '',
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('refreshes settings on focus even when auth is cookie-only and no access token is in JS memory', async () => {
    renderHook(() => useSettings(initialData));

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
    });

    await waitFor(() => {
      expect(mocks.getFullSettings).toHaveBeenCalledTimes(1);
    });
  });

  it('does not apply a late settings refresh after the private cache scope changes', async () => {
    setPrivateCacheUserScope('user-1');
    const settingsRequest = createDeferred<any>();
    mocks.getFullSettings.mockReturnValueOnce(settingsRequest.promise);

    const { result } = renderHook(() => useSettings(initialData));

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
    });

    await waitFor(() => {
      expect(mocks.getFullSettings).toHaveBeenCalledTimes(1);
    });

    setPrivateCacheUserScope('user-2');
    await act(async () => {
      settingsRequest.resolve({
        profiles: [
          {
            id: 'profile-user-1',
            name: 'User 1 Profile',
            providerId: 'google',
            protocol: 'google',
            apiKey: 'user-1-api-key',
            baseUrl: '',
            isProxy: false,
            hiddenModels: [],
            savedModels: [],
            cachedModelCount: 0,
            createdAt: 1,
            updatedAt: 1,
          },
        ],
        activeProfileId: 'profile-user-1',
        activeProfile: {
          id: 'profile-user-1',
          name: 'User 1 Profile',
          providerId: 'google',
          protocol: 'google',
          apiKey: 'user-1-api-key',
          baseUrl: '',
          isProxy: false,
          hiddenModels: [],
          savedModels: [],
          cachedModelCount: 0,
          createdAt: 1,
          updatedAt: 1,
        },
        dashscopeKey: '',
      });
      await settingsRequest.promise;
    });

    expect(result.current.activeProfileId).toBeNull();
    expect(result.current.profiles).toEqual([]);
    expect(mocks.llmSetConfig).toHaveBeenCalledWith('', '', null, '');
    expect(mocks.llmSetConfig).not.toHaveBeenCalledWith(
      'user-1-api-key',
      '',
      'google',
      'google'
    );
  });

  it('does not apply a late settings refresh after private cache lifecycle is reset', async () => {
    setPrivateCacheUserScope('user-1');
    const settingsRequest = createDeferred<any>();
    mocks.getFullSettings.mockReturnValueOnce(settingsRequest.promise);

    const { result } = renderHook(() => useSettings(initialData));

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
    });

    await waitFor(() => {
      expect(mocks.getFullSettings).toHaveBeenCalledTimes(1);
    });

    clearPrivateMemoryCaches();

    await act(async () => {
      settingsRequest.resolve({
        profiles: [
          {
            id: 'profile-user-1',
            name: 'User 1 Profile',
            providerId: 'google',
            protocol: 'google',
            apiKey: 'user-1-api-key',
            baseUrl: '',
            isProxy: false,
            hiddenModels: [],
            savedModels: [],
            cachedModelCount: 0,
            createdAt: 1,
            updatedAt: 1,
          },
        ],
        activeProfileId: 'profile-user-1',
        activeProfile: {
          id: 'profile-user-1',
          name: 'User 1 Profile',
          providerId: 'google',
          protocol: 'google',
          apiKey: 'user-1-api-key',
          baseUrl: '',
          isProxy: false,
          hiddenModels: [],
          savedModels: [],
          cachedModelCount: 0,
          createdAt: 1,
          updatedAt: 1,
        },
        dashscopeKey: '',
      });
      await settingsRequest.promise;
    });

    expect(result.current.activeProfileId).toBeNull();
    expect(result.current.profiles).toEqual([]);
    expect(mocks.llmSetConfig).not.toHaveBeenCalled();
  });

  it('clears stale profile state on private scope change and waits for new initial data', async () => {
    setPrivateCacheUserScope('user-1');
    const { result, rerender } = renderHook(
      ({ data }) => useSettings(data),
      { initialProps: { data: userOneInitialData } }
    );

    expect(result.current.activeProfileId).toBe('profile-user-1');
    expect(result.current.profiles).toHaveLength(1);

    await act(async () => {
      setPrivateCacheUserScope('user-2');
    });

    expect(result.current.activeProfileId).toBeNull();
    expect(result.current.profiles).toEqual([]);
    expect(result.current.config.providerId).toBe('');

    rerender({ data: userOneInitialData });

    expect(result.current.activeProfileId).toBeNull();
    expect(result.current.profiles).toEqual([]);

    rerender({ data: userTwoInitialData });

    expect(result.current.activeProfileId).toBe('profile-user-2');
    expect(result.current.profiles).toHaveLength(1);
    expect(result.current.config.providerId).toBe('openai');
  });
});

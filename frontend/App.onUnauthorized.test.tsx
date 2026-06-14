// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

const { mocks } = vi.hoisted(() => {
  const callbackRef: { current?: () => void } = {};

  return {
    mocks: {
      callbackRef,
      navigate: vi.fn(),
      logout: vi.fn(() => Promise.resolve()),
      setOnUnauthorized: vi.fn((callback: () => void) => {
        callbackRef.current = callback;
      }),
    },
  };
});

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');

  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock('./services/apiClient', () => ({
  apiClient: {
    setOnUnauthorized: mocks.setOnUnauthorized,
  },
}));

vi.mock('./services/auth', () => ({
  authService: {
    logout: mocks.logout,
  },
}));

vi.mock('./services/frontendTelemetry', () => ({
  startTelemetrySpan: () => ({ end: vi.fn() }),
}));

vi.mock('./utils/globalErrorHandler', () => ({
  initGlobalErrorHandlers: vi.fn(),
  registerGlobalErrorNotifier: vi.fn(),
}));

vi.mock('./contexts/ToastContext', async () => {
  const ReactModule = await import('react');

  return {
    ToastProvider: ({ children }: { children: React.ReactNode }) =>
      ReactModule.createElement(ReactModule.Fragment, null, children),
    useToastContext: () => ({ showError: vi.fn(), showWarning: vi.fn() }),
  };
});

vi.mock('./components/common/LoadingSpinner', () => ({
  LoadingSpinner: () => null,
}));

vi.mock('./components/common/ErrorView', () => ({
  ErrorView: () => null,
}));

vi.mock('./components/common/WelcomeScreen', () => ({
  WelcomeScreen: () => null,
}));

vi.mock('./components/app/AppShell', () => ({
  AppShell: () => null,
}));

vi.mock('./components/AppRoutes', () => ({
  AppRoutes: () => null,
}));

vi.mock('./hooks/useWorkspaceModeHandlers', () => ({
  useWorkspaceModeHandlers: () => ({
    handleWorkspaceModeSelect: vi.fn(),
    handleModeNavigationSelect: vi.fn(),
    handleWorkspaceModesClose: vi.fn(),
    handleWorkspaceModeClose: vi.fn(),
    handleWorkspaceModeReload: vi.fn(),
  }),
}));

vi.mock('./hooks', () => {
  const model = {
    id: 'model-1',
    name: 'Model 1',
    description: 'm',
    capabilities: { vision: true, search: true, reasoning: true, coding: true },
  };

  return {
    useSettings: () => ({
      config: {
        apiKey: 'test-api-key',
        providerId: 'google',
        dashscopeApiKey: '',
        protocol: 'google',
        baseUrl: '',
      },
      isSettingsOpen: false,
      setIsSettingsOpen: vi.fn(),
      profiles: [],
      activeProfileId: 'profile-1',
      activeProfile: {
        id: 'profile-1',
        providerId: 'google',
        updatedAt: 1,
        savedModels: [model],
      },
      saveProfile: vi.fn(),
      deleteProfile: vi.fn(),
      activateProfile: vi.fn(),
      hiddenModelIds: [],
    }),
    useModels: () => ({
      visibleModels: [model],
      allVisibleModels: [model],
      modeCatalog: [],
      currentModelId: 'model-1',
      setCurrentModelId: vi.fn(),
      activeModelConfig: model,
      isLoadingModels: false,
      isModelMenuOpen: false,
      setIsModelMenuOpen: vi.fn(),
    }),
    useSessions: () => ({
      sessions: [],
      currentSessionId: null,
      setCurrentSessionId: vi.fn(),
      createNewSession: vi.fn(() => ({
        id: 's1',
        title: 't',
        messages: [],
        createdAt: 1,
        mode: 'chat',
      })),
      updateSessionMessages: vi.fn(),
      updateSessionPersona: vi.fn(),
      updateSessionTitle: vi.fn(),
      deleteSession: vi.fn(),
      selectLatestSessionForMode: vi.fn(() => true),
      cacheStatus: {
        isFromCache: false,
        isStale: false,
        isRefreshing: false,
        timestamp: 0,
        refresh: vi.fn(),
        updateStatus: vi.fn(),
      },
      refreshSessions: vi.fn(),
      hasMoreSessions: false,
      isLoadingMore: false,
      loadMoreSessions: vi.fn(),
    }),
    useChat: () => ({
      messages: [],
      setMessages: vi.fn(),
      loadingState: 'idle',
      sendMessage: vi.fn(),
      submitResearchAction: vi.fn(),
      stopGeneration: vi.fn(),
    }),
    usePersonas: () => ({
      personas: [],
      activePersona: null,
      activePersonaId: null,
      setActivePersonaId: vi.fn(),
      createPersona: vi.fn(),
      updatePersona: vi.fn(),
      deletePersona: vi.fn(),
      refreshPersonas: vi.fn(),
    }),
    useAuth: () => ({
      user: null,
      isAuthenticated: true,
      isLoading: false,
      allowRegistration: false,
      hasActiveProfile: true,
      login: vi.fn(),
      register: vi.fn(),
      error: null,
      logout: vi.fn(),
      refreshUser: vi.fn(),
      changePassword: vi.fn(),
    }),
    useInitData: () => ({
      criticalData: {
        profiles: [],
        activeProfileId: 'profile-1',
        activeProfile: null,
        dashscopeKey: '',
        cachedModels: [],
        cachedModeCatalog: [],
        cachedChatModels: [],
        cachedDefaultModelId: null,
      },
      nonCriticalData: {
        personas: [],
        storageConfigs: [],
        activeStorageId: null,
        sessions: [],
        sessionsHasMore: false,
      },
      isLoading: false,
      error: null,
      retry: vi.fn(),
    }),
    useStorageConfigs: () => ({
      storageConfigs: [],
      activeStorageId: null,
      handleSaveStorage: vi.fn(),
      handleDeleteStorage: vi.fn(),
      handleActivateStorage: vi.fn(),
    }),
    useImageNavigation: () => ({
      previewImage: null,
      setPreviewImage: vi.fn(),
      allImages: [],
      handleNextImage: vi.fn(),
      handlePrevImage: vi.fn(),
      handleImageClick: vi.fn(),
    }),
    useModeMessages: () => [],
    setModeMessages: vi.fn(),
    resetModeMessages: vi.fn(),
    useLLMService: vi.fn(),
    useModeSwitch: ({ setAppMode }: { setAppMode: (mode: string) => void }) => ({
      handleModeSwitch: setAppMode,
    }),
    useImageHandlers: () => ({ handleEditImage: vi.fn(), handleExpandImage: vi.fn() }),
    useSessionSync: vi.fn(),
  };
});

describe('App onUnauthorized navigation', () => {
  beforeEach(() => {
    mocks.callbackRef.current = undefined;
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('keeps the shell mounted by navigating to login through React Router', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => expect(mocks.setOnUnauthorized).toHaveBeenCalledTimes(1));

    const hrefBeforeUnauthorized = window.location.href;

    await act(async () => {
      mocks.callbackRef.current?.();
    });

    expect(mocks.logout).toHaveBeenCalledTimes(1);
    expect(mocks.navigate).toHaveBeenCalledTimes(1);
    expect(mocks.navigate).toHaveBeenCalledWith('/login', { replace: true });
    expect(window.location.href).toBe(hrefBeforeUnauthorized);
  });
});

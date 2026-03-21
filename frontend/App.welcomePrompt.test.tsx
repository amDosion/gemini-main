// @vitest-environment jsdom
import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

const {
  sendMessageMock,
  setCurrentModelIdMock,
  setIsModelMenuOpenMock,
  createNewSessionMock,
  handleModeSwitchMock,
  showErrorMock,
  showWarningMock,
  startTelemetrySpanMock,
  telemetryEndMock,
} = vi.hoisted(() => ({
  sendMessageMock: vi.fn(),
  setCurrentModelIdMock: vi.fn(),
  setIsModelMenuOpenMock: vi.fn(),
  createNewSessionMock: vi.fn(),
  handleModeSwitchMock: vi.fn(),
  showErrorMock: vi.fn(),
  showWarningMock: vi.fn(),
  startTelemetrySpanMock: vi.fn(),
  telemetryEndMock: vi.fn(),
}));

vi.mock('./services/frontendTelemetry', () => ({
  startTelemetrySpan: startTelemetrySpanMock,
}));

vi.mock('./contexts/ToastContext', async () => {
  const ReactModule = await import('react');
  return {
    ToastProvider: ({ children }: { children: React.ReactNode }) =>
      ReactModule.createElement(ReactModule.Fragment, null, children),
    useToastContext: () => ({
      showError: showErrorMock,
      showWarning: showWarningMock,
    }),
  };
});

vi.mock('./components', async () => {
  const ReactModule = await import('react');

  const ChatView = (props: { onPromptSelect: (text: string, mode: string, modelId: string, requiredCap: string) => void }) => {
    ReactModule.useEffect(() => {
      props.onPromptSelect('welcome prompt', 'chat', 'model-target', 'search');
    }, []);
    return ReactModule.createElement('div', null, 'chat-view');
  };

  return {
    AppLayout: ({ children }: { children: React.ReactNode }) => ReactModule.createElement('div', null, children),
    ChatView,
    SettingsModal: () => null,
    ImageModal: () => null,
    LoadingSpinner: () => null,
    ErrorView: () => null,
    WelcomeScreen: () => null,
  };
});

vi.mock('./components/auth', () => ({
  LoginPage: () => null,
  RegisterPage: () => null,
}));

vi.mock('./hooks', () => {
  const oldModel = {
    id: 'model-old',
    name: 'Model Old',
    description: 'old',
    capabilities: { vision: true, search: true, reasoning: true, coding: true },
  };
  const targetModel = {
    id: 'model-target',
    name: 'Model Target',
    description: 'target',
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
        hiddenModels: [],
        savedModels: [oldModel, targetModel],
      },
      saveProfile: vi.fn(),
      deleteProfile: vi.fn(),
      activateProfile: vi.fn(),
      hiddenModelIds: [],
    }),
    useModels: () => ({
      visibleModels: [oldModel],
      allVisibleModels: [oldModel, targetModel],
      modeCatalog: [],
      currentModelId: 'model-old',
      setCurrentModelId: setCurrentModelIdMock,
      activeModelConfig: oldModel,
      isLoadingModels: false,
      isModelMenuOpen: false,
      setIsModelMenuOpen: setIsModelMenuOpenMock,
    }),
    useSessions: () => ({
      sessions: [],
      currentSessionId: null,
      setCurrentSessionId: vi.fn(),
      createNewSession: createNewSessionMock,
      updateSessionMessages: vi.fn(),
      updateSessionPersona: vi.fn(),
      updateSessionTitle: vi.fn(),
      deleteSession: vi.fn(),
      cacheStatus: { isFromCache: false, isStale: false, isRefreshing: false, timestamp: Date.now(), refresh: vi.fn(), updateStatus: vi.fn() },
      refreshSessions: vi.fn(),
      hasMoreSessions: false,
      isLoadingMore: false,
      loadMoreSessions: vi.fn(),
    }),
    useChat: () => ({
      messages: [],
      setMessages: vi.fn(),
      loadingState: 'idle',
      sendMessage: sendMessageMock,
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
      initData: {
        profiles: [],
        activeProfileId: 'profile-1',
        activeProfile: null,
        dashscopeKey: '',
        personas: [],
        storageConfigs: [],
        activeStorageId: null,
        sessions: [],
        sessionsHasMore: false,
        cachedModels: [oldModel, targetModel],
        cachedModeCatalog: [],
      },
      isLoading: false,
      error: null,
      isConfigReady: true,
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
    useViewMessages: (messages: any[]) => messages,
    useLLMService: vi.fn(),
    useModeSwitch: () => ({
      handleModeSwitch: handleModeSwitchMock,
    }),
    useImageHandlers: () => ({
      handleEditImage: vi.fn(),
      handleExpandImage: vi.fn(),
    }),
    useSessionSync: vi.fn(),
  };
});

describe('App welcome prompt quick send model selection', () => {
  beforeEach(() => {
    sendMessageMock.mockReset();
    setCurrentModelIdMock.mockReset();
    setIsModelMenuOpenMock.mockReset();
    createNewSessionMock.mockReset();
    handleModeSwitchMock.mockReset();
    showErrorMock.mockReset();
    showWarningMock.mockReset();
    startTelemetrySpanMock.mockReset();
    telemetryEndMock.mockReset();

    createNewSessionMock.mockReturnValue({
      id: 'session-new',
      title: 'New Chat',
      messages: [],
      createdAt: 1,
      mode: 'chat',
    });
    startTelemetrySpanMock.mockReturnValue({ end: telemetryEndMock });
  });

  it('uses the prompt-specified model for the first send before currentModelId state updates', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalled();
    });

    const firstCall = sendMessageMock.mock.calls[0];
    const sentModel = firstCall?.[4] as { id?: string } | undefined;
    const sentSessionId = firstCall?.[6] as string | undefined;

    expect(setCurrentModelIdMock).toHaveBeenCalledWith('model-target');
    expect(sentModel?.id).toBe('model-target');
    expect(sentModel?.id).not.toBe('model-old');
    expect(sentSessionId).toBe('session-new');
  });
});

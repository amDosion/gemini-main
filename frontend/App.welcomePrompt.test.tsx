// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

const {
  sendMessageMock,
  setCurrentModelIdMock,
  setIsModelMenuOpenMock,
  createNewSessionMock,
  selectLatestSessionForModeMock,
  refreshSessionsMock,
  setIsSettingsOpenMock,
  handleModeSwitchMock,
  showErrorMock,
  showWarningMock,
  startTelemetrySpanMock,
  telemetryEndMock,
  mockSettingsState,
} = vi.hoisted(() => ({
  sendMessageMock: vi.fn(),
  setCurrentModelIdMock: vi.fn(),
  setIsModelMenuOpenMock: vi.fn(),
  createNewSessionMock: vi.fn(),
  selectLatestSessionForModeMock: vi.fn(),
  refreshSessionsMock: vi.fn(),
  setIsSettingsOpenMock: vi.fn(),
  handleModeSwitchMock: vi.fn(),
  showErrorMock: vi.fn(),
  showWarningMock: vi.fn(),
  startTelemetrySpanMock: vi.fn(),
  telemetryEndMock: vi.fn(),
  mockSettingsState: {
    apiKey: 'test-api-key',
    activeProfileId: 'profile-1' as string | null,
  },
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

  const ChatView = (props: {
    onPromptSelect: (text: string, mode: string, modelId: string, requiredCap: string) => void;
    onSend: (text: string, options: any, attachments: any[], mode: any) => void;
  }) => {
    ReactModule.useEffect(() => {
      props.onPromptSelect('welcome prompt', 'chat', 'model-target', 'search');
    }, []);
    return ReactModule.createElement(
      'div',
      null,
      'chat-view',
      ReactModule.createElement(
        'button',
        {
          onClick: () =>
            props.onSend(
              'expand prompt',
              { outpaintMode: 'ratio' },
              [
                {
                  id: 'attachment-1',
                  name: 'source.png',
                  mimeType: 'image/png',
                  url: 'data:image/png;base64,AAAA',
                },
              ],
              'image-outpainting'
            ),
          'data-testid': 'send-google-expand',
        },
        'send google expand'
      )
    );
  };

  return {
    AppLayout: ({
      children,
      onNewChat,
      setAppMode,
      workspaceTabs,
    }: {
      children: React.ReactNode;
      onNewChat: () => void;
      setAppMode?: (mode: string) => void;
      workspaceTabs?: React.ReactNode;
    }) =>
      ReactModule.createElement(
        'div',
        null,
        ReactModule.createElement('button', { onClick: onNewChat, 'data-testid': 'new-session' }, 'new session'),
        ReactModule.createElement('button', { onClick: () => setAppMode?.('image-gen'), 'data-testid': 'mode-nav-image-gen' }, 'mode nav image gen'),
        ReactModule.createElement('div', { 'data-testid': 'workspace-tabs' }, workspaceTabs),
        children
      ),
    ChatView,
    SettingsModal: () => null,
    ImageModal: () => null,
    LoadingSpinner: () => null,
    ErrorView: () => null,
    WelcomeScreen: () => null,
  };
});

vi.mock('./components/layout/WorkspaceTagViews', async () => {
  const ReactModule = await import('react');
  return {
    WorkspaceTagViews: ({
      activeMode,
      onSelectMode,
      onReloadMode,
    }: {
      activeMode: string;
      onSelectMode: (mode: string) => void;
      onReloadMode?: (mode: string) => void;
    }) =>
      ReactModule.createElement(
        ReactModule.Fragment,
        null,
        ReactModule.createElement(
          'button',
          { onClick: () => onSelectMode('image-gen'), 'data-testid': 'workspace-tab-image-gen' },
          'tag image gen'
        ),
        ReactModule.createElement(
          'button',
          { onClick: () => onReloadMode?.(activeMode), 'data-testid': 'workspace-tab-reload' },
          'reload tab'
        )
      ),
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
        apiKey: mockSettingsState.apiKey,
        providerId: 'google',
        dashscopeApiKey: '',
        protocol: 'google',
        baseUrl: '',
      },
      isSettingsOpen: false,
      setIsSettingsOpen: setIsSettingsOpenMock,
      profiles: [],
      activeProfileId: mockSettingsState.activeProfileId,
      activeProfile: mockSettingsState.activeProfileId
        ? {
            id: mockSettingsState.activeProfileId,
            providerId: 'google',
            updatedAt: 1,
            hiddenModels: [],
            savedModels: [oldModel, targetModel],
          }
        : null,
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
      selectLatestSessionForMode: selectLatestSessionForModeMock,
      cacheStatus: { isFromCache: false, isStale: false, isRefreshing: false, timestamp: Date.now(), refresh: vi.fn(), updateStatus: vi.fn() },
      refreshSessions: refreshSessionsMock,
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
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    sendMessageMock.mockReset();
    setCurrentModelIdMock.mockReset();
    setIsModelMenuOpenMock.mockReset();
    createNewSessionMock.mockReset();
    selectLatestSessionForModeMock.mockReset();
    refreshSessionsMock.mockReset();
    setIsSettingsOpenMock.mockReset();
    handleModeSwitchMock.mockReset();
    showErrorMock.mockReset();
    showWarningMock.mockReset();
    startTelemetrySpanMock.mockReset();
    telemetryEndMock.mockReset();
    mockSettingsState.apiKey = 'test-api-key';
    mockSettingsState.activeProfileId = 'profile-1';

    createNewSessionMock.mockReturnValue({
      id: 'session-new',
      title: 'New Chat',
      messages: [],
      createdAt: 1,
      mode: 'chat',
    });
    startTelemetrySpanMock.mockReturnValue({ end: telemetryEndMock });
    selectLatestSessionForModeMock.mockReturnValue(true);
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

  it('starts a new session without forcing chat mode', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalled();
    });

    createNewSessionMock.mockClear();
    handleModeSwitchMock.mockClear();

    fireEvent.click(screen.getByTestId('new-session'));

    expect(createNewSessionMock).toHaveBeenCalledTimes(1);
    expect(handleModeSwitchMock).not.toHaveBeenCalledWith('chat');
  });

  it('selects the latest session for left mode navigation but preserves tag-view session cache', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalled();
    });

    selectLatestSessionForModeMock.mockClear();
    handleModeSwitchMock.mockClear();

    fireEvent.click(screen.getByTestId('mode-nav-image-gen'));

    expect(selectLatestSessionForModeMock).toHaveBeenCalledWith('image-gen');
    expect(handleModeSwitchMock).toHaveBeenCalledWith('image-gen');

    selectLatestSessionForModeMock.mockClear();
    handleModeSwitchMock.mockClear();

    fireEvent.click(screen.getByTestId('workspace-tab-image-gen'));

    expect(selectLatestSessionForModeMock).not.toHaveBeenCalled();
    expect(handleModeSwitchMock).toHaveBeenCalledWith('image-gen');
  });

  it('reloads the active workspace tab with a forced session refresh', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalled();
    });

    refreshSessionsMock.mockClear();

    fireEvent.click(screen.getByTestId('workspace-tab-reload'));

    expect(refreshSessionsMock).toHaveBeenCalledWith({ force: true });
  });

  it('does not require a DashScope key before sending Google image outpainting', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalled();
    });

    sendMessageMock.mockClear();
    showWarningMock.mockClear();
    setIsSettingsOpenMock.mockClear();

    fireEvent.click(screen.getByTestId('send-google-expand'));

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledTimes(1);
    });

    const sentMode = sendMessageMock.mock.calls[0]?.[3];

    expect(sentMode).toBe('image-outpainting');
    expect(showWarningMock).not.toHaveBeenCalledWith(
      expect.stringContaining('DashScope API Key is required')
    );
    expect(setIsSettingsOpenMock).not.toHaveBeenCalled();
  });

  it('allows sending with an active server-side profile when the API key is redacted', async () => {
    mockSettingsState.apiKey = '';
    mockSettingsState.activeProfileId = 'profile-1';

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalled();
    });

    expect(setIsSettingsOpenMock).not.toHaveBeenCalled();
  });
});

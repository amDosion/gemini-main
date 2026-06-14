// @vitest-environment jsdom
//
// Discriminating tests for the App workspace view-stack rendering surface.
//
// These lock the behavior that the `renderWorkspaceViewStack` / `renderView`
// extraction (App.tsx -> frontend/components/app/) MUST preserve regardless of
// whether the render helpers live inline in App.tsx or in sibling modules:
//
//   1. Keep-alive stack: every OPEN workspace mode (chat / multi-agent / studio)
//      stays mounted simultaneously; switching `appMode` toggles CSS `display`
//      (contents vs none) instead of unmounting/remounting the view.
//   2. lastStudioMode memory: after visiting a studio mode and switching back to
//      chat, the studio view remains mounted (hidden) so its state survives and
//      its `mode` prop stays at the last studio mode.
//   3. renderView panel override: opening the persona overlay wraps the workspace
//      stack in a `.hidden` container and renders the overlay; closing it restores
//      the stack. The workspace views are never unmounted across the transition.
//
// All hook/service dependencies are mocked so the test exercises only the
// composition + prop wiring done by App's render helpers.
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

const { mockSettingsState, mockPersonaState } = vi.hoisted(() => ({
  mockSettingsState: {
    apiKey: 'test-api-key',
    activeProfileId: 'profile-1' as string | null,
  },
  mockPersonaState: {
    personas: [{ id: 'p1', name: 'Persona One' }] as Array<{ id: string; name: string }>,
  },
}));

vi.mock('./services/frontendTelemetry', () => ({
  startTelemetrySpan: () => ({ end: vi.fn() }),
}));

vi.mock('./contexts/ToastContext', async () => {
  const ReactModule = await import('react');
  return {
    ToastProvider: ({ children }: { children: React.ReactNode }) =>
      ReactModule.createElement(ReactModule.Fragment, null, children),
    useToastContext: () => ({ showError: vi.fn(), showWarning: vi.fn() }),
  };
});

// Identifiable stubs for the eagerly-imported views. Each renders its appMode so
// we can assert which workspace surface is mounted and active.
vi.mock('./components', async () => {
  const ReactModule = await import('react');

  const ChatView = (props: { appMode?: string }) =>
    ReactModule.createElement(
      'div',
      { 'data-testid': 'chat-view', 'data-appmode': props.appMode },
      'chat-view'
    );

  const AppLayout = ({
    children,
    setAppMode,
    onOpenPersonaView,
  }: {
    children: React.ReactNode;
    setAppMode?: (mode: string) => void;
    onOpenPersonaView?: () => void;
  }) =>
    ReactModule.createElement(
      'div',
      null,
      ReactModule.createElement(
        'button',
        { onClick: () => setAppMode?.('image-gen'), 'data-testid': 'go-image-gen' },
        'go image gen'
      ),
      ReactModule.createElement(
        'button',
        { onClick: () => setAppMode?.('chat'), 'data-testid': 'go-chat' },
        'go chat'
      ),
      ReactModule.createElement(
        'button',
        { onClick: () => onOpenPersonaView?.(), 'data-testid': 'open-persona' },
        'open persona'
      ),
      children
    );

  return {
    AppLayout,
    ChatView,
    SettingsModal: () => null,
    ImageModal: () => null,
    LoadingSpinner: () => null,
    ErrorView: () => null,
    WelcomeScreen: () => null,
  };
});

// Lazy view stubs. StudioView echoes its `mode` prop so we can verify the
// active studio mode (lastStudioMode) is forwarded correctly.
vi.mock('./lazyViews', async () => {
  const ReactModule = await import('react');
  return {
    MultiAgentView: (props: { appMode?: string }) =>
      ReactModule.createElement(
        'div',
        { 'data-testid': 'multi-agent-view', 'data-appmode': props.appMode },
        'multi-agent-view'
      ),
    StudioView: (props: { mode?: string }) =>
      ReactModule.createElement(
        'div',
        { 'data-testid': 'studio-view', 'data-studio-mode': props.mode },
        'studio-view'
      ),
    CloudStorageView: (props: { onClose: () => void }) =>
      ReactModule.createElement(
        'div',
        { 'data-testid': 'cloud-storage-view' },
        ReactModule.createElement(
          'button',
          { onClick: props.onClose, 'data-testid': 'cloud-storage-close' },
          'close'
        )
      ),
    PersonaManagementView: (props: { onClose: () => void }) =>
      ReactModule.createElement(
        'div',
        { 'data-testid': 'persona-view' },
        ReactModule.createElement(
          'button',
          { onClick: props.onClose, 'data-testid': 'persona-close' },
          'close'
        )
      ),
  };
});

vi.mock('./components/layout/WorkspaceTagViews', async () => {
  const ReactModule = await import('react');
  return { WorkspaceTagViews: () => ReactModule.createElement(ReactModule.Fragment, null) };
});

vi.mock('./components/auth', () => ({ LoginPage: () => null, RegisterPage: () => null }));

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
        apiKey: mockSettingsState.apiKey,
        providerId: 'google',
        dashscopeApiKey: '',
        protocol: 'google',
        baseUrl: '',
      },
      isSettingsOpen: false,
      setIsSettingsOpen: vi.fn(),
      profiles: [],
      activeProfileId: mockSettingsState.activeProfileId,
      activeProfile: mockSettingsState.activeProfileId
        ? {
            id: mockSettingsState.activeProfileId,
            providerId: 'google',
            updatedAt: 1,
            savedModels: [model],
          }
        : null,
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
      personas: mockPersonaState.personas,
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
        personas: mockPersonaState.personas,
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
      // Mirror real behavior: the base switch drives setAppMode so the keep-alive
      // stack + lastStudioMode effects run exactly as in production.
      handleModeSwitch: setAppMode,
    }),
    useImageHandlers: () => ({ handleEditImage: vi.fn(), handleExpandImage: vi.fn() }),
    useSessionSync: vi.fn(),
  };
});

const renderApp = () =>
  render(
    <MemoryRouter initialEntries={['/']}>
      <App />
    </MemoryRouter>
  );

// CSS `display` is set on the wrapper <div> around each view. Walk up to find it.
const wrapperDisplayOf = (testId: string): string => {
  const el = screen.getByTestId(testId).closest('div[style]') as HTMLElement | null;
  return el?.style.display ?? '';
};

describe('App workspace view stack (renderWorkspaceViewStack / renderView)', () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    mockSettingsState.apiKey = 'test-api-key';
    mockSettingsState.activeProfileId = 'profile-1';
  });

  it('mounts only the initially-open chat view and shows it via display:contents', async () => {
    renderApp();

    expect(await screen.findByTestId('chat-view')).toBeTruthy();
    // Only chat is in openWorkspaceModes at startup.
    expect(screen.queryByTestId('multi-agent-view')).toBeNull();
    expect(screen.queryByTestId('studio-view')).toBeNull();
    expect(wrapperDisplayOf('chat-view')).toBe('contents');
  });

  it('keeps the chat view mounted (display:none) when switching to a studio mode, and adds the studio view', async () => {
    renderApp();
    await screen.findByTestId('chat-view');

    fireEvent.click(screen.getByTestId('go-image-gen'));

    // Studio view appears...
    expect(await screen.findByTestId('studio-view')).toBeTruthy();
    // ...chat view is NOT unmounted (keep-alive), only hidden.
    expect(screen.getByTestId('chat-view')).toBeTruthy();
    expect(wrapperDisplayOf('chat-view')).toBe('none');
    expect(wrapperDisplayOf('studio-view')).toBe('contents');
  });

  it('forwards the active studio mode to StudioView and remembers it as lastStudioMode after returning to chat', async () => {
    renderApp();
    await screen.findByTestId('chat-view');

    fireEvent.click(screen.getByTestId('go-image-gen'));
    const studio = await screen.findByTestId('studio-view');
    // Active studio mode is forwarded as `mode`.
    expect(studio.getAttribute('data-studio-mode')).toBe('image-gen');

    // Switch back to chat: studio stays mounted (hidden) and retains lastStudioMode.
    fireEvent.click(screen.getByTestId('go-chat'));
    await waitFor(() => expect(wrapperDisplayOf('chat-view')).toBe('contents'));

    expect(screen.getByTestId('studio-view')).toBeTruthy();
    expect(wrapperDisplayOf('studio-view')).toBe('none');
    // lastStudioMode preserved while chat is active (not reset to a default).
    expect(screen.getByTestId('studio-view').getAttribute('data-studio-mode')).toBe('image-gen');
  });

  it('renderView override: opening the persona panel wraps the workspace stack in a hidden container without unmounting it, and closing restores it', async () => {
    renderApp();
    const chat = await screen.findByTestId('chat-view');

    // Before opening any overlay, the workspace stack is rendered directly.
    expect(chat.closest('.hidden')).toBeNull();
    expect(screen.queryByTestId('persona-view')).toBeNull();

    // Open the persona overlay.
    fireEvent.click(screen.getByTestId('open-persona'));

    const persona = await screen.findByTestId('persona-view');
    expect(persona).toBeTruthy();
    // Workspace stack is still mounted (chat-view present) but now inside `.hidden`.
    const chatAfterOpen = screen.getByTestId('chat-view');
    expect(chatAfterOpen).toBeTruthy();
    expect(chatAfterOpen.closest('.hidden')).not.toBeNull();
    // The overlay itself is NOT inside the hidden container.
    expect(persona.closest('.hidden')).toBeNull();

    // Close the persona overlay → workspace stack restored to the foreground.
    fireEvent.click(screen.getByTestId('persona-close'));
    await waitFor(() => expect(screen.queryByTestId('persona-view')).toBeNull());
    expect(screen.getByTestId('chat-view').closest('.hidden')).toBeNull();
  });
});

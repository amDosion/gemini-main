
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';

import { AppMode, Attachment, Role } from './types/types';
import { llmService } from './services/llmService';

// Cleaner Imports via Barrel Files
import {
  AppLayout,
  ChatView,
  AgentView,
  MultiAgentView,
  StudioView,
  SettingsModal,
  ImageModal,
  LoadingSpinner,
  ErrorView,
  WelcomeScreen
} from './components';

// Import Auth Components
import { LoginPage, RegisterPage } from './components/auth';

import {
  useSettings,
  useModels,
  useSessions,
  useChat,
  usePersonas,
  useAuth,
  useInitData,
  useStorageConfigs,
  useImageNavigation,
  useViewMessages,
  useLLMService,
  useModeSwitch,
  useImageHandlers,
  useSessionSync
} from './hooks';
import { ToastProvider, useToastContext } from './contexts/ToastContext';

const AppContent: React.FC = () => {
  // --- Router Hooks ---
  const navigate = useNavigate();
  const location = useLocation();
  const { showError, showWarning } = useToastContext();

  // --- Auth State (使用真实认证) ---
  const {
    isAuthenticated,
    isLoading: isAuthLoading,
    allowRegistration,
    login,
    register,
    error: authError,
    logout
  } = useAuth();

  // --- 统一初始化数据 ---
  const { initData, isLoading: isInitLoading, error: initError, isConfigReady, retry } = useInitData(isAuthenticated);


  // --- UI State ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState<'profiles' | 'editor'>('profiles');

  // App Mode State
  const [appMode, setAppMode] = useState<AppMode>('chat');
  const [initialAttachments, setInitialAttachments] = useState<Attachment[] | undefined>(undefined);
  const [initialPrompt, setInitialPrompt] = useState<string | undefined>(undefined);


  // --- Domain Hooks ---
  const {
    config, isSettingsOpen, setIsSettingsOpen,
    profiles, activeProfileId, activeProfile: activeProfileFromSettings, saveProfile, deleteProfile, activateProfile,
    hiddenModelIds
  } = useSettings(initData ? {
    profiles: initData.profiles || [],  // ✅ 确保不为 undefined
    activeProfileId: initData.activeProfileId || null,  // ✅ 确保不为 undefined
    activeProfile: initData.activeProfile || null,  // ✅ 确保不为 undefined
    dashscopeKey: initData.dashscopeKey || ''  // ✅ 确保不为 undefined
  } : undefined);


  const {
    personas, activePersona, activePersonaId, setActivePersonaId,
    createPersona, updatePersona, deletePersona, refreshPersonas
  } = usePersonas(initData ? {
    personas: initData.personas
  } : undefined);

  // --- 云存储管理 ---
  const {
    storageConfigs,
    activeStorageId,
    handleSaveStorage,
    handleDeleteStorage,
    handleActivateStorage
  } = useStorageConfigs(initData ? {
    storageConfigs: initData.storageConfigs,
    activeStorageId: initData.activeStorageId
  } : undefined);

  // --- Auth 路由重定向 ---
  useEffect(() => {
    if (isAuthenticated && (location.pathname === '/login' || location.pathname === '/register')) {
      navigate('/', { replace: true });
    } else if (!isAuthenticated && !isAuthLoading && location.pathname !== '/login' && location.pathname !== '/register') {
      navigate('/login', { replace: true });
    }
  }, [isAuthenticated, isAuthLoading, location.pathname, navigate]);

  // ✅ 使用 useSettings 返回的 activeProfile（已包含回退逻辑）
  // 必须在所有使用 activeProfile 的 useEffect 之前定义
  const activeProfile = activeProfileFromSettings;

  // --- LLM Service 初始化 ---
  useLLMService(initData, activeProfile);

  // PDF 模板会在 PdfExtractView 组件中按需加载，无需预加载

  // ✅ 稳定 cachedModels 引用，避免触发不必要的 useEffect
  const cachedModels = useMemo(() => activeProfile?.savedModels, [activeProfile?.savedModels]);

  // ✅ 修复竞态条件：只有当配置完全加载后才允许获取模型
  // 条件：已认证 + activeProfile 已加载（不是 null）
  // 注意：isConfigReady 已从 useInitData Hook 中获取，这里使用 isProfileReady 避免重复声明
  const isProfileReady = isAuthenticated && activeProfile !== undefined && activeProfile !== null;

  // Always try to fetch models when provider changes. 
  const {
    availableModels,
    visibleModels,
    currentModelId,
    setCurrentModelId,
    activeModelConfig,
    isLoadingModels,
    isModelMenuOpen,
    setIsModelMenuOpen,
  } = useModels(
    isProfileReady, // ✅ 使用 isProfileReady 而不是 isConfigReady
    hiddenModelIds,
    config.providerId,
    cachedModels,  // ✅ 使用稳定的引用
    appMode  // ✅ 传递 appMode，后端会根据模式过滤模型
    // apiKey 已移除 - 后端从数据库获取 API Key
  );

  const {
    sessions,
    currentSessionId,
    setCurrentSessionId,
    createNewSession,
    updateSessionMessages,
    updateSessionPersona,
    updateSessionTitle, // ✅ 新增
    deleteSession,
    // 缓存相关
    cacheStatus,
    refreshSessions,
  } = useSessions(initData ? {
    sessions: initData.sessions
  } : undefined);


  const {
    messages,
    setMessages,
    loadingState,
    sendMessage,
    stopGeneration
  } = useChat(currentSessionId, updateSessionMessages, config.apiKey, activeStorageId);


  // --- 消息过滤 ---
  const currentViewMessages = useViewMessages(messages, appMode);

  // --- 图片导航 ---
  const {
    previewImage,
    setPreviewImage,
    allImages,
    handleNextImage,
    handlePrevImage,
    handleImageClick
  } = useImageNavigation(currentViewMessages);

  // --- Effects ---
  useEffect(() => {
    if (window.innerWidth >= 1280) setIsRightSidebarOpen(true);
  }, []);

  // --- 模式切换（需要在其他 handlers 之前定义）---
  const { handleModeSwitch } = useModeSwitch({
    availableModels,
    hiddenModelIds,
    currentModelId,
    setCurrentModelId,
    setAppMode
  });

  // --- 会话同步 ---
  useSessionSync({
    currentSessionId,
    sessions,
    activeModelConfig,
    setMessages,
    setAppMode: handleModeSwitch // ✅ 使用 handleModeSwitch 确保模型选择逻辑正确
  });

  // --- Handlers ---
  const handleNewChat = () => {
    createNewSession(activePersonaId); // ✅ 传递当前激活的 persona
    if (activeModelConfig) llmService.startNewChat([], activeModelConfig);
    if (window.innerWidth < 768) setIsSidebarOpen(false);
    handleModeSwitch('chat'); // ✅ 使用 handleModeSwitch 确保模型选择逻辑正确
    setInitialAttachments(undefined);
    setInitialPrompt(undefined);
  };

  const handleModelSelect = useCallback((id: string) => {
    setCurrentModelId(id);
    setIsModelMenuOpen(false);
    // Let useEffect handle llmService.startNewChat to avoid duplicate calls
  }, [setCurrentModelId, setIsModelMenuOpen]);

  const handlePersonaSelect = (id: string) => {
    setActivePersonaId(id);

    // ✅ 如果有当前会话，更新会话的 persona
    if (currentSessionId) {
      updateSessionPersona(currentSessionId, id);
    }

    const persona = personas.find(p => p.id === id);
        if (persona && persona.category === 'Image Generation') {
          const match = persona.systemPrompt.match(/"([^"]*\[[^"]*\][^"]*)"/);

          if (match && match[1]) {
            if (appMode !== 'image-gen' && !appMode.startsWith('image-')) {
              handleModeSwitch('image-gen'); // ✅ 使用 handleModeSwitch 确保模型选择逻辑正确
            }
            setInitialPrompt(match[1]);
          }
        }
  };

  const onSend = useCallback((text: string, options: any, attachments: Attachment[], mode: AppMode) => {
    // Only check for Key if not Ollama
    if (!config.apiKey && config.providerId !== 'ollama') {
      setSettingsInitialTab('profiles');
      setIsSettingsOpen(true);
      return;
    }

    if (mode === 'image-outpainting' && !config.dashscopeApiKey && config.providerId !== 'tongyi') {
      showWarning("DashScope API Key is required for 'Expand Image'. Please configure it in Settings.");
      setIsSettingsOpen(true);
      return;
    }

    // ✅ 如果没有当前会话，自动创建一个新会话
    if (!currentSessionId) {
      createNewSession(activePersonaId);
    }

    const optionsWithPersona = { ...options, persona: activePersona };
    const selectedModel = visibleModels.find(m => m.id === currentModelId);
    const modelForSend = mode === 'pdf-extract' ? selectedModel : activeModelConfig;
    
    // For PDF extraction, enforce using the user-selected model only (no fallback).
    if (mode === 'pdf-extract' && !selectedModel) {
      showError('当前选择的模型不可用，请在模型列表中重新选择后再进行 PDF 提取。');
      return;
    }

    if (modelForSend) {
      sendMessage(text, optionsWithPersona, attachments, mode, modelForSend, config.protocol);
    }
    setInitialAttachments(undefined);
    setInitialPrompt(undefined);
  }, [
    config.apiKey,
    config.providerId,
    config.dashscopeApiKey,
    config.protocol,
    currentSessionId,
    showError,
    showWarning,
    createNewSession,
    activePersonaId,
    activePersona,
    visibleModels,
    currentModelId,
    activeModelConfig,
    sendMessage,
    setInitialAttachments,
    setInitialPrompt,
    setIsSettingsOpen,
    setSettingsInitialTab
  ]);

  // --- 图片处理 Handlers ---
  const { handleEditImage, handleExpandImage } = useImageHandlers({
    messages,
    currentSessionId,
    visibleModels,
    activeModelConfig,
    setAppMode: handleModeSwitch, // ✅ 使用 handleModeSwitch 确保模型选择逻辑正确
    setCurrentModelId,
    setInitialAttachments,
    setInitialPrompt
  });

  const handleWelcomePrompt = (text: string, mode: AppMode, modelId: string, requiredCap: string) => {
    handleModelSelect(modelId);
    handleModeSwitch(mode); // ✅ 使用 handleModeSwitch 确保模型选择逻辑正确
    onSend(text, {
      enableSearch: requiredCap === 'search',
      enableThinking: requiredCap === 'reasoning',
      enableCodeExecution: false,
      imageAspectRatio: '1:1',
      imageResolution: '1K',
      voiceName: 'Puck'
    }, [], mode);
  };

  const handleOpenSettings = (tab: 'profiles' | 'editor' = 'profiles') => {
    setSettingsInitialTab(tab);
    setIsSettingsOpen(true);
  };


  // 删除单条消息（同时删除对应的用户消息）
  const handleDeleteMessage = (messageId: string) => {
    if (!currentSessionId) return;

    // 找到要删除的消息
    const msgToDelete = messages.find(m => m.id === messageId);
    if (!msgToDelete) return;

    // 如果是 MODEL 消息，同时删除前一条 USER 消息（成对删除）
    let idsToDelete = [messageId];
    if (msgToDelete.role === Role.MODEL) {
      const msgIndex = messages.findIndex(m => m.id === messageId);
      if (msgIndex > 0) {
        const prevMsg = messages[msgIndex - 1];
        if (prevMsg.role === Role.USER && prevMsg.mode === msgToDelete.mode) {
          idsToDelete.push(prevMsg.id);
        }
      }
    }

    // 过滤掉要删除的消息
    const newMessages = messages.filter(m => !idsToDelete.includes(m.id));
    setMessages(newMessages);
    updateSessionMessages(currentSessionId, newMessages);
  };

  const renderView = () => {
    const commonProps = {
      messages: currentViewMessages,
      setAppMode: handleModeSwitch,
      onImageClick: handleImageClick,  // ✅ 使用稳定的引用
      loadingState,
      onSend,
      onStop: stopGeneration,
      activeModelConfig,
      onEditImage: handleEditImage,
      onExpandImage: handleExpandImage, // Pass the new handler
      providerId: config.providerId,
      sessionId: currentSessionId,  // ✅ 传递 sessionId 用于查询附件
      apiKey: config.apiKey  // ✅ 传递 apiKey 用于调用 API
    };

    if (appMode === 'deep-research') {
      return (
        <AgentView
          {...commonProps}
          isLoadingModels={isLoadingModels}
          visibleModels={visibleModels}
          apiKey={config.apiKey}
          protocol={config.protocol}
          onPromptSelect={handleWelcomePrompt}
          onOpenSettings={() => handleOpenSettings('profiles')}
          appMode={appMode}
        />
      );
    } else if (appMode === 'multi-agent') {
      return (
        <MultiAgentView
          {...commonProps}
          isLoadingModels={isLoadingModels}
          visibleModels={visibleModels}
          apiKey={config.apiKey}
          protocol={config.protocol}
          onPromptSelect={handleWelcomePrompt}
          onOpenSettings={() => handleOpenSettings('profiles')}
          appMode={appMode}
        />
      );
    } else if (appMode === 'chat') {
      return (
        <ChatView
          {...commonProps}
          isLoadingModels={isLoadingModels}
          visibleModels={visibleModels}
          apiKey={config.apiKey}
          protocol={config.protocol}
          onPromptSelect={handleWelcomePrompt}
          onOpenSettings={() => handleOpenSettings('profiles')}
          appMode={appMode}
        />
      );
    } else {
      return (
        <StudioView
          key={appMode}
          {...commonProps}
          mode={appMode}
          visibleModels={visibleModels}
          initialPrompt={initialPrompt}
          initialAttachments={initialAttachments}
          onDeleteMessage={handleDeleteMessage}
        />
      );
    }
  };

  // --- Early Return for Auth Check ---
  if (isAuthLoading) {
    return <LoadingSpinner message="正在验证身份..." showMessage={false} />;
  }

  // --- Early Return for Init Loading ---
  if (isInitLoading) {
    return <LoadingSpinner message="正在加载配置..." />;
  }

  // --- Early Return for Init Error ---
  if (initError) {
    return <ErrorView error={initError} onRetry={retry} />;
  }

  // --- 准备 SettingsModal（需要在所有地方都能访问） ---
  const settingsModal = isSettingsOpen && (
    <SettingsModal
      isOpen={isSettingsOpen}
      onClose={() => setIsSettingsOpen(false)}
      profiles={profiles}
      activeProfileId={activeProfileId}
      onSaveProfile={saveProfile}
      onDeleteProfile={deleteProfile}
      onActivateProfile={activateProfile}

      storageConfigs={storageConfigs}
      activeStorageId={activeStorageId}
      onSaveStorage={handleSaveStorage}
      onDeleteStorage={handleDeleteStorage}
      onActivateStorage={handleActivateStorage}

      initialApiKey={config.apiKey}
      initialBaseUrl={config.baseUrl}
      hiddenModelIds={hiddenModelIds}
      initialTab={settingsInitialTab}
    />
  );

  // --- Early Return for Unconfigured State ---
  // 新用户没有配置时，显示欢迎界面
  // 点击"打开设置"时，直接进入编辑器标签页创建第一个配置
  // ✅ 使用 activeProfileFromSettings 而不是 initData?.activeProfile
  // 因为 saveProfile 会更新 useSettings 的状态，但不会自动更新 initData
  // ✅ 同时渲染 SettingsModal，确保点击"打开设置"时能正常显示
  if (isConfigReady && !activeProfileFromSettings) {
    return (
      <>
        <WelcomeScreen onOpenSettings={() => handleOpenSettings('editor')} />
        {settingsModal}
      </>
    );
  }

  // --- 主应用内容 ---
  const mainAppElement = (
    <>
      <ImageModal
        isOpen={!!previewImage}
        imageUrl={previewImage}
        onClose={() => setPreviewImage(null)}
        onNext={handleNextImage}
        onPrev={handlePrevImage}
        hasNext={allImages.length > 1}
        hasPrev={allImages.length > 1}
      />

      <AppLayout
        isSidebarOpen={isSidebarOpen}
        setIsSidebarOpen={setIsSidebarOpen}
        sessions={sessions}
        currentSessionId={currentSessionId}
        onNewChat={handleNewChat}
        onSelectSession={setCurrentSessionId}
        onDeleteSession={deleteSession}
        onUpdateSessionTitle={updateSessionTitle}

        isLoadingModels={isLoadingModels}
        isModelMenuOpen={isModelMenuOpen}
        setIsModelMenuOpen={setIsModelMenuOpen}
        activeModelConfig={activeModelConfig}
        configApiKey={config.apiKey}
        visibleModels={visibleModels}
        currentModelId={currentModelId}
        onModelSelect={handleModelSelect}
        onOpenSettings={handleOpenSettings}
        appMode={appMode}
        // Passing Config Profile Data to Header
        profiles={profiles}
        activeProfileId={activeProfileId}
        onActivateProfile={activateProfile}
        onLogout={logout}
        // 缓存相关
        cacheStatus={cacheStatus}
        onRefreshSessions={refreshSessions}

        isRightSidebarOpen={isRightSidebarOpen}
        setIsRightSidebarOpen={setIsRightSidebarOpen}
        personas={personas}
        activePersonaId={activePersonaId}
        onSelectPersona={handlePersonaSelect}
        onCreatePersona={createPersona}
        onUpdatePersona={updatePersona}
        onDeletePersona={deletePersona}
        onRefreshPersonas={refreshPersonas}

        settings={settingsModal}
      >
        {renderView()}
      </AppLayout>
    </>
  );

  // --- 使用 Routes 渲染 ---
  return (
    <Routes>
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <LoginPage
              onLogin={login}
              isLoading={isAuthLoading}
              error={authError}
              allowRegistration={allowRegistration}
              onNavigateToRegister={allowRegistration ? () => navigate('/register') : undefined}
            />
          )
        }
      />
      <Route
        path="/register"
        element={
          isAuthenticated ? (
            <Navigate to="/" replace />
          ) : allowRegistration ? (
            <RegisterPage
              onRegister={register}
              isLoading={isAuthLoading}
              error={authError}
              onNavigateToLogin={() => navigate('/login')}
              allowRegistration={allowRegistration}
            />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route
        path="/*"
        element={
          isAuthenticated ? (
            mainAppElement
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  );
};

export default App;

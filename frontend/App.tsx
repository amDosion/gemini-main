
import React, { useState, useEffect, useMemo, useCallback, lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';

import { AppMode, Attachment, Role } from './types/types';
import { llmService } from './services/llmService';
import { ConfigProfile } from './services/db';  // ✅ 新增：ConfigProfile 类型

// Cleaner Imports via Barrel Files
import {
  AppLayout,
  ChatView,  // ✅ 保持同步加载（默认模式）
  SettingsModal,
  ImageModal,
  LoadingSpinner,
  ErrorView,
  WelcomeScreen
} from './components';

// ✅ 懒加载非关键视图组件（命名导出需要转换为默认导出）
const AgentView = lazy(() => import('./components/views/AgentView').then(m => ({ default: m.AgentView })));
const MultiAgentView = lazy(() => import('./components/views/MultiAgentView').then(m => ({ default: m.MultiAgentView })));
const StudioView = lazy(() => import('./components/views/StudioView').then(m => ({ default: m.StudioView })));
const LiveAPIView = lazy(() => import('./components/live/LiveAPIView').then(m => ({ default: m.LiveAPIView })));

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
    hasActiveProfile,  // ✅ 新增：配置状态
    login,
    register,
    error: authError,
    logout,
    refreshUser  // ✅ 新增：刷新用户信息（用于更新 hasActiveProfile）
  } = useAuth();

  // ✅ 条件加载：只要已认证就加载初始化数据（包括 storageConfigs、personas 等）
  // 修复：即使用户未配置 AI provider，也应该能看到和管理 storage 配置
  const shouldLoadInitData = isAuthenticated;

  // --- 统一初始化数据 ---
  const { initData, isLoading: isInitLoading, error: initError, isConfigReady, retry } = useInitData(shouldLoadInitData);


  // --- UI State ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState<'profiles' | 'editor'>('profiles');

  // App Mode State
  const [appMode, setAppMode] = useState<AppMode>('chat');
  const [initialAttachments, setInitialAttachments] = useState<Attachment[] | undefined>(undefined);
  const [initialPrompt, setInitialPrompt] = useState<string | undefined>(undefined);


  // --- Domain Hooks ---
  const {
    config, isSettingsOpen, setIsSettingsOpen,
    profiles, activeProfileId, activeProfile: activeProfileFromSettings,
    saveProfile: originalSaveProfile,
    deleteProfile,
    activateProfile: originalActivateProfile,
    hiddenModelIds
  } = useSettings(initData ? {
    profiles: initData.profiles || [],  // ✅ 确保不为 undefined
    activeProfileId: initData.activeProfileId || null,  // ✅ 确保不为 undefined
    activeProfile: initData.activeProfile || null,  // ✅ 确保不为 undefined
    dashscopeKey: initData.dashscopeKey || ''  // ✅ 确保不为 undefined
  } : undefined);

  // ✅ 包装 saveProfile：保存后刷新用户信息，更新 hasActiveProfile
  const saveProfile = useCallback(async (profile: ConfigProfile, autoActivate: boolean = false) => {
    await originalSaveProfile(profile, autoActivate);
    // 刷新用户信息，更新 hasActiveProfile 状态
    if (autoActivate) {
      await refreshUser();
    }
  }, [originalSaveProfile, refreshUser]);

  // ✅ 包装 activateProfile：激活后刷新用户信息，更新 hasActiveProfile
  const activateProfile = useCallback(async (id: string) => {
    await originalActivateProfile(id);
    // 刷新用户信息，更新 hasActiveProfile 状态
    await refreshUser();
  }, [originalActivateProfile, refreshUser]);


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
    allVisibleModels,  // ✅ 新增：用于 ModeSelector 判断模式可用性
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
    // ✅ 滚动加载相关
    hasMoreSessions,
    isLoadingMore,
    loadMoreSessions,
  } = useSessions(initData ? {
    sessions: initData.sessions,
    sessionsHasMore: initData.sessionsHasMore
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
  // RightSidebar 默认关闭，用户可以手动打开

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

    // ✅ 修复：所有模式都应该使用用户选择的模型，而不仅仅是 pdf-extract
    // 优先使用 selectedModel（用户在 Header 中选择的），如果找不到才使用 activeModelConfig
    const modelForSend = selectedModel || activeModelConfig;

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
        <Suspense fallback={<LoadingSpinner />}>
          <AgentView
            {...commonProps}
            isLoadingModels={isLoadingModels}
            visibleModels={visibleModels}
            allVisibleModels={allVisibleModels}  // ✅ 传递完整模型列表
            apiKey={config.apiKey}
            protocol={config.protocol}
            onPromptSelect={handleWelcomePrompt}
            onOpenSettings={() => handleOpenSettings('profiles')}
            appMode={appMode}
          />
        </Suspense>
      );
    } else if (appMode === 'multi-agent') {
      return (
        <Suspense fallback={<LoadingSpinner />}>
          <MultiAgentView
            {...commonProps}
            isLoadingModels={isLoadingModels}
            visibleModels={visibleModels}
            allVisibleModels={allVisibleModels}  // ✅ 传递完整模型列表
            apiKey={config.apiKey}
            protocol={config.protocol}
            onPromptSelect={handleWelcomePrompt}
            onOpenSettings={() => handleOpenSettings('profiles')}
            appMode={appMode}
          />
        </Suspense>
      );
    } else if (appMode === 'chat') {
      // ✅ ChatView 保持同步加载（默认模式）
      return (
        <ChatView
          {...commonProps}
          isLoadingModels={isLoadingModels}
          visibleModels={visibleModels}
          allVisibleModels={allVisibleModels}  // ✅ 传递完整模型列表
          apiKey={config.apiKey}
          protocol={config.protocol}
          onPromptSelect={handleWelcomePrompt}
          onOpenSettings={() => handleOpenSettings('profiles')}
          appMode={appMode}
        />
      );
    } else {
      return (
        <Suspense fallback={<LoadingSpinner />}>
          <StudioView
            key={appMode}
            {...commonProps}
            mode={appMode}
            visibleModels={visibleModels}
            allVisibleModels={allVisibleModels}  // ✅ 传递完整模型列表
            initialPrompt={initialPrompt}
            initialAttachments={initialAttachments}
            onDeleteMessage={handleDeleteMessage}
          />
        </Suspense>
      );
    }
  };

  // --- 准备 SettingsModal（需要在所有地方都能访问） ---
  // ✅ 必须在 Early Return 之前定义，否则会报错 "Cannot access before initialization"
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

  // ✅ 优化：统一加载状态（合并认证和初始化加载）
  const isAppLoading = isAuthLoading || (isAuthenticated && hasActiveProfile === true && isInitLoading);

  // --- Early Return for Loading ---
  if (isAppLoading) {
    return <LoadingSpinner message="正在登录..." showMessage={false} />;
  }

  // ✅ 优化：已认证但没有配置 → 直接显示欢迎屏（跳过初始化数据加载）
  if (isAuthenticated && hasActiveProfile === false) {
    return (
      <>
        <WelcomeScreen onOpenSettings={() => handleOpenSettings('editor')} />
        {settingsModal}
      </>
    );
  }

  // --- Early Return for Init Error ---
  if (initError) {
    return <ErrorView error={initError} onRetry={retry} />;
  }

  // ✅ 原有的 WelcomeScreen 逻辑已移至上方（优化后无需此检查）
  // 因为现在在认证阶段就知道是否有配置，不需要等待 initData 加载

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
        // ✅ 滚动加载相关
        hasMoreSessions={hasMoreSessions}
        isLoadingMore={isLoadingMore}
        loadMoreSessions={loadMoreSessions}

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

        // ✅ 模式导航相关
        showModeNavigation={true}
        setAppMode={handleModeSwitch}
        allVisibleModels={allVisibleModels}
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

import React, { useState, useEffect, useMemo, useCallback, Suspense } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';

import { AppMode, Attachment, Role, ChatOptions } from './types/types';
import { llmService } from './services/llmService';
import { initGlobalErrorHandlers, registerGlobalErrorNotifier } from './utils/globalErrorHandler';
import { ConfigProfile } from './services/db'; // ✅ 新增：ConfigProfile 类型

// Cleaner Imports via Barrel Files
import {
  AppLayout,
  ChatView, // ✅ 保持同步加载（默认模式）
  SettingsModal,
  ImageModal,
  LoadingSpinner,
  ErrorView,
  WelcomeScreen,
} from './components';
import { getErrorMessage } from './utils/errorMessage';

// ✅ 懒加载非关键视图组件（命名导出需要转换为默认导出）
// 顶层视图 lazy 包装抽离至 ./lazyViews（< 800 行合规）
import {
  MultiAgentView,
  StudioView,
  CloudStorageView,
  PersonaManagementView,
} from './lazyViews';
import {
  deleteMessageFromSession,
  submitWelcomePrompt,
  openSettingsPanel,
  openCloudStoragePanel,
  openPersonaPanel,
} from './appHandlers';

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
  useSessionSync,
} from './hooks';
import { ToastProvider, useToastContext } from './contexts/ToastContext';
import { startTelemetrySpan } from './services/frontendTelemetry';
import { resolveModelForModeSend } from './utils/modeModelSelection';
import { apiClient } from './services/apiClient';
import { authService } from './services/auth';

const AppContent: React.FC = () => {
  // --- Router Hooks ---
  const navigate = useNavigate();
  const location = useLocation();
  const { showError, showWarning } = useToastContext();

  // --- Auth State (使用真实认证) ---
  const {
    user,
    isAuthenticated,
    isLoading: isAuthLoading,
    allowRegistration,
    hasActiveProfile, // ✅ 新增：配置状态
    login,
    register,
    error: authError,
    logout,
    refreshUser, // ✅ 新增：刷新用户信息（用于更新 hasActiveProfile）
    changePassword,
  } = useAuth();

  // ✅ 条件加载：只要已认证就加载初始化数据（包括 storageConfigs、personas 等）
  // 修复：即使用户未配置 AI provider，也应该能看到和管理 storage 配置
  const shouldLoadInitData = isAuthenticated;

  // --- 统一初始化数据 ---
  // ✅ B-2: 使用独立的 criticalData / nonCriticalData,避免合并 memo 引用变化触发下游
  // useSettings / usePersonas / useStorageConfigs / useModels 整条 effect 链。
  const {
    criticalData,
    nonCriticalData,
    isLoading: isInitLoading,
    error: initError,
    isConfigReady,
    retry,
  } = useInitData(shouldLoadInitData);

  // --- UI State ---
  const [isPersonaViewOpen, setIsPersonaViewOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState<'profiles' | 'editor'>('profiles');
  const [isCloudStorageBrowserOpen, setIsCloudStorageBrowserOpen] = useState(false);

  // App Mode State
  const [appMode, setAppMode] = useState<AppMode>('chat');
  const [initialAttachments, setInitialAttachments] = useState<Attachment[] | undefined>(undefined);
  const [initialPrompt, setInitialPrompt] = useState<string | undefined>(undefined);

  useEffect(() => {
    setIsCloudStorageBrowserOpen(false);
    setIsPersonaViewOpen(false);
  }, [appMode]);

  // ✅ C-1: 挂载时一次性注册 onUnauthorized 回调,避免 token 失效后 UI 卡死
  useEffect(() => {
    apiClient.setOnUnauthorized(() => {
      // 异步 logout (清 token + 广播);不 await,确保即便后端 logout 失败也能跳转
      authService.logout().catch(() => {
        // 忽略后端登出错误,本地清理已在 logout finally 中完成
      });
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    });
  }, []);

  // --- Domain Hooks ---
  const {
    config,
    isSettingsOpen,
    setIsSettingsOpen,
    profiles,
    activeProfileId,
    activeProfile: activeProfileFromSettings,
    saveProfile: originalSaveProfile,
    deleteProfile,
    activateProfile: originalActivateProfile,
    hiddenModelIds,
  } = useSettings(
    criticalData
      ? {
          profiles: criticalData.profiles || [], // ✅ 确保不为 undefined
          activeProfileId: criticalData.activeProfileId || null, // ✅ 确保不为 undefined
          activeProfile: criticalData.activeProfile || null, // ✅ 确保不为 undefined
          dashscopeKey: criticalData.dashscopeKey || '', // ✅ 确保不为 undefined
        }
      : undefined
  );

  // ✅ 包装 saveProfile：保存后刷新用户信息，更新 hasActiveProfile
  const saveProfile = useCallback(
    async (profile: ConfigProfile, autoActivate: boolean = false) => {
      await originalSaveProfile(profile, autoActivate);
      // 刷新用户信息，更新 hasActiveProfile 状态
      if (autoActivate) {
        await refreshUser();
      }
    },
    [originalSaveProfile, refreshUser]
  );

  // ✅ 包装 activateProfile：激活后刷新用户信息，更新 hasActiveProfile
  const activateProfile = useCallback(
    async (id: string) => {
      await originalActivateProfile(id);
      // 刷新用户信息，更新 hasActiveProfile 状态
      await refreshUser();
    },
    [originalActivateProfile, refreshUser]
  );

  const {
    personas,
    activePersona,
    activePersonaId,
    setActivePersonaId,
    createPersona,
    updatePersona,
    deletePersona,
    refreshPersonas,
  } = usePersonas(
    nonCriticalData
      ? {
          personas: nonCriticalData.personas || [],
        }
      : undefined
  );

  // --- 云存储管理 ---
  const {
    storageConfigs,
    activeStorageId,
    handleSaveStorage,
    handleDeleteStorage,
    handleActivateStorage,
  } = useStorageConfigs(
    nonCriticalData
      ? {
          storageConfigs: nonCriticalData.storageConfigs || [],
          activeStorageId: nonCriticalData.activeStorageId ?? null,
        }
      : undefined
  );

  // --- Auth 路由重定向 ---
  useEffect(() => {
    if (isAuthenticated && (location.pathname === '/login' || location.pathname === '/register')) {
      navigate('/', { replace: true });
    } else if (
      !isAuthenticated &&
      !isAuthLoading &&
      location.pathname !== '/login' &&
      location.pathname !== '/register'
    ) {
      navigate('/login', { replace: true });
    }
  }, [isAuthenticated, isAuthLoading, location.pathname, navigate]);

  // ✅ 使用 useSettings 返回的 activeProfile（已包含回退逻辑）
  // 必须在所有使用 activeProfile 的 useEffect 之前定义
  const activeProfile = activeProfileFromSettings;
  const profileCacheKey = useMemo(() => {
    if (!activeProfile) return 'no-profile';
    return `${activeProfile.id}:${activeProfile.providerId}:${activeProfile.updatedAt || 0}`;
  }, [activeProfile]);
  const initialSavedModels = useMemo(() => {
    const fromActiveProfile = Array.isArray(activeProfile?.savedModels)
      ? activeProfile.savedModels
      : [];
    if (fromActiveProfile.length > 0) {
      return fromActiveProfile.filter((model) => model && typeof model.id === 'string');
    }

    const fromInitCache = Array.isArray(criticalData?.cachedModels)
      ? criticalData.cachedModels
      : [];
    return fromInitCache.filter((model) => model && typeof model.id === 'string');
  }, [activeProfile?.savedModels, criticalData?.cachedModels]);
  const initialModeCatalog = useMemo(() => {
    return Array.isArray(criticalData?.cachedModeCatalog) ? criticalData.cachedModeCatalog : [];
  }, [criticalData?.cachedModeCatalog]);
  const initialChatModels = useMemo(() => {
    const models = Array.isArray(criticalData?.cachedChatModels)
      ? criticalData.cachedChatModels
      : [];
    return models.filter((model) => model && typeof model.id === 'string');
  }, [criticalData?.cachedChatModels]);
  const initialDefaultModelId = useMemo(() => {
    return criticalData?.cachedDefaultModelId || null;
  }, [criticalData?.cachedDefaultModelId]);

  // --- LLM Service 初始化 ---
  useLLMService(undefined, activeProfile);

  // PDF 模板会在 PdfExtractView 组件中按需加载，无需预加载

  // ✅ 修复竞态条件：只有当配置完全加载后才允许获取模型
  // 条件：已认证 + activeProfile 已加载（不是 null）
  // 注意：isConfigReady 已从 useInitData Hook 中获取，这里使用 isProfileReady 避免重复声明
  const isProfileReady = isAuthenticated && activeProfile !== undefined && activeProfile !== null;

  // Always try to fetch models when provider changes.
  const {
    visibleModels,
    allVisibleModels,
    modeCatalog,
    currentModelId,
    setCurrentModelId,
    activeModelConfig,
    isLoadingModels,
    isModelMenuOpen,
    setIsModelMenuOpen,
  } = useModels(
    isProfileReady, // ✅ 使用 isProfileReady 而不是 isConfigReady
    config.providerId,
    appMode, // ✅ 传递 appMode，后端会根据模式过滤模型
    profileCacheKey,
    initialSavedModels,
    initialModeCatalog,
    initialChatModels, // ✅ init/critical 预过滤的 chat 模型
    initialDefaultModelId // ✅ init/critical 的默认模型 ID
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
  } = useSessions(
    appMode,
    nonCriticalData
      ? {
          sessions: nonCriticalData.sessions || [],
          sessionsHasMore: nonCriticalData.sessionsHasMore,
        }
      : undefined
  );

  const { messages, setMessages, loadingState, sendMessage, submitResearchAction, stopGeneration } =
    useChat(currentSessionId, updateSessionMessages, config.apiKey, activeStorageId);

  // --- 消息过滤 ---
  const currentViewMessages = useViewMessages(messages, appMode);

  // --- 图片导航 ---
  const {
    previewImage,
    setPreviewImage,
    allImages,
    handleNextImage,
    handlePrevImage,
    handleImageClick,
  } = useImageNavigation(currentViewMessages);

  // --- 模式切换（需要在其他 handlers 之前定义）---
  const { handleModeSwitch: baseHandleModeSwitch } = useModeSwitch({
    setAppMode,
  });
  const handleModeSwitch = useCallback(
    (mode: AppMode) => {
      const span = startTelemetrySpan(
        'app.mode.switch',
        { from: appMode, to: mode },
        { category: 'ui-interaction' }
      );
      try {
        baseHandleModeSwitch(mode);
        span.end('ok');
      } catch (error) {
        span.end('error', {
          message: getErrorMessage(error),
        });
        throw error;
      }
    },
    [appMode, baseHandleModeSwitch]
  );

  // ✅ B-7: 50ms debounce — 路由抖动期间(连续多次 location 变化)只创建一个 span。
  useEffect(() => {
    const debounceId = globalThis.setTimeout(() => {
      const span = startTelemetrySpan(
        'app.route.render',
        { path: location.pathname, search: location.search },
        { category: 'navigation' }
      );
      let finished = false;
      const finalize = () => {
        if (finished) return;
        finished = true;
        span.end('ok');
      };

      if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(finalize);
      } else {
        globalThis.setTimeout(finalize, 0);
      }
    }, 50);

    return () => {
      globalThis.clearTimeout(debounceId);
    };
  }, [location.pathname, location.search]);

  // --- 会话同步 ---
  useSessionSync({
    currentSessionId,
    sessions,
    activeModelConfig,
    setMessages,
    setAppMode: handleModeSwitch,
  });

  // --- Handlers ---
  const handleNewChat = () => {
    createNewSession(activePersonaId);
    if (activeModelConfig) llmService.startNewChat([], activeModelConfig);
    setInitialAttachments(undefined);
    setInitialPrompt(undefined);
  };

  const handleModelSelect = useCallback(
    (id: string) => {
      setCurrentModelId(id);
      setIsModelMenuOpen(false);
      // Let useEffect handle llmService.startNewChat to avoid duplicate calls
    },
    [setCurrentModelId, setIsModelMenuOpen]
  );

  const handlePersonaSelect = (id: string) => {
    setActivePersonaId(id);

    // ✅ 如果有当前会话，更新会话的 persona
    if (currentSessionId) {
      updateSessionPersona(currentSessionId, id);
    }
  };

  const onSend = useCallback(
    (
      text: string,
      options: ChatOptions,
      attachments: Attachment[],
      mode: AppMode,
      forcedModelId?: string
    ) => {
      // Only check for Key if not Ollama
      if (!config.apiKey && config.providerId !== 'ollama') {
        setSettingsInitialTab('profiles');
        setIsSettingsOpen(true);
        return;
      }

      if (
        mode === 'image-outpainting' &&
        !config.dashscopeApiKey &&
        config.providerId !== 'tongyi'
      ) {
        showWarning(
          "DashScope API Key is required for 'Expand Image'. Please configure it in Settings."
        );
        setIsSettingsOpen(true);
        return;
      }

      // ✅ 如果没有当前会话，自动创建一个新会话，并立即使用新会话 id 发送首条消息
      // ✅ Sprint 3 Phase B: 防御性——若当前 session 的 mode 与本次发送的 mode 不一致
      // （理论上切 mode 会重置 currentSessionId，不应触发；保留以防异步边界条件），
      // 也强制建一个属于当前 mode 的新 session，避免后端 message.mode != session.mode 拒绝。
      let targetSessionId = currentSessionId;
      const existingSession = targetSessionId
        ? sessions.find((s) => s.id === targetSessionId)
        : undefined;
      if (!targetSessionId || (existingSession && existingSession.mode !== mode)) {
        const newSession = createNewSession(activePersonaId);
        targetSessionId = newSession.id;
      }

      const optionsWithPersona = { ...options, personaId: activePersonaId };
      const selectedModel = resolveModelForModeSend({
        mode,
        currentModelId,
        visibleModels,
        allVisibleModels,
        activeModelConfig,
        forcedModelId,
        isLoadingModels,
      });

      if (forcedModelId && selectedModel.reason !== 'resolved') {
        showError('欢迎词指定模型当前不可用，请刷新模型列表后重试。');
        return;
      }

      if (!forcedModelId && selectedModel.reason === 'loading') {
        showError('当前模式模型正在加载，请稍后再试。');
        return;
      }

      if (!forcedModelId && selectedModel.reason !== 'resolved') {
        showError('当前模式没有可用模型，请先在模型列表中选择支持该模式的模型。');
        return;
      }

      const modelForSend = selectedModel.reason === 'resolved' ? selectedModel.model : undefined;

      // For PDF extraction, enforce using the user-selected model only (no fallback).
      if (mode === 'pdf-extract' && selectedModel.reason !== 'resolved') {
        showError('当前选择的模型不可用，请在模型列表中重新选择后再进行 PDF 提取。');
        return;
      }

      if (!modelForSend) {
        // 上游已守卫，但保留兜底防御
        return;
      }
      if (!config.protocol) {
        // 修复 code-reviewer Step 4 HIGH-1：原 `if (modelForSend)` 不含 protocol 检查；
        // strict 模式下 sendMessage 第 6 参 protocol 类型为 ApiProtocol 不接 null。
        // 不能静默 drop 调用，而要显式提示用户。
        showError('当前没有可用的协议配置（缺失 protocol），请检查模型/Profile 设置后重试。');
        return;
      }
      sendMessage(
        text,
        optionsWithPersona,
        attachments,
        mode,
        modelForSend,
        config.protocol,
        targetSessionId
      );
      setInitialAttachments(undefined);
      setInitialPrompt(undefined);
    },
    [
      config.apiKey,
      config.providerId,
      config.dashscopeApiKey,
      config.protocol,
      currentSessionId,
      sessions,
      showError,
      showWarning,
      createNewSession,
      activePersonaId,
      activePersona,
      visibleModels,
      allVisibleModels,
      currentModelId,
      activeModelConfig,
      isLoadingModels,
      sendMessage,
      setInitialAttachments,
      setInitialPrompt,
      setIsSettingsOpen,
      setSettingsInitialTab,
    ]
  );

  // --- 图片处理 Handlers ---
  const { handleEditImage, handleExpandImage } = useImageHandlers({
    messages,
    visibleModels,
    activeModelConfig,
    setAppMode: handleModeSwitch, // ✅ 使用 handleModeSwitch 确保模型选择逻辑正确
    setCurrentModelId,
    setInitialAttachments,
    setInitialPrompt,
  });

  // 欢迎屏 prompt 选择 — 抽离至 ./appHandlers
  const handleWelcomePrompt = (text: string, mode: AppMode, modelId: string, requiredCap: string) =>
    submitWelcomePrompt(text, mode, modelId, requiredCap, {
      handleModelSelect,
      handleModeSwitch,
      onSend,
    });

  // 3 个 open 面板 handler — 抽离至 ./appHandlers（deps 内联，setter 引用稳定无需 useCallback deps）
  const _panelDeps = { setIsSettingsOpen, setSettingsInitialTab, setIsPersonaViewOpen, setIsCloudStorageBrowserOpen };
  const handleOpenSettings = (tab?: string) => openSettingsPanel(tab, _panelDeps);
  const handleOpenCloudStorage = useCallback(() => openCloudStoragePanel(_panelDeps), []); // eslint-disable-line react-hooks/exhaustive-deps
  const handleOpenPersonaView = useCallback(() => openPersonaPanel(_panelDeps), []); // eslint-disable-line react-hooks/exhaustive-deps

  // 删除单条消息（同时删除对应的用户消息）— 抽离至 ./appHandlers
  const handleDeleteMessage = (messageId: string) =>
    deleteMessageFromSession(messageId, {
      currentSessionId,
      messages,
      setMessages,
      updateSessionMessages,
    });

  const renderView = () => {
    if (isCloudStorageBrowserOpen) {
      return (
        <Suspense fallback={<LoadingSpinner fullscreen={false} showMessage={false} />}>
          <CloudStorageView
            activeStorageId={activeStorageId}
            storageConfigs={storageConfigs}
            onClose={() => setIsCloudStorageBrowserOpen(false)}
          />
        </Suspense>
      );
    }

    if (isPersonaViewOpen) {
      return (
        <Suspense fallback={<LoadingSpinner fullscreen={false} showMessage={false} />}>
          <PersonaManagementView
            personas={personas}
            activePersonaId={activePersonaId}
            onSelectPersona={handlePersonaSelect}
            onCreatePersona={createPersona}
            onUpdatePersona={updatePersona}
            onDeletePersona={deletePersona}
            onRefreshPersonas={refreshPersonas}
            onClose={() => setIsPersonaViewOpen(false)}
          />
        </Suspense>
      );
    }

    const commonProps = {
      messages: currentViewMessages,
      setAppMode: handleModeSwitch,
      onImageClick: handleImageClick, // ✅ 使用稳定的引用
      loadingState,
      onSend,
      onStop: stopGeneration,
      onSubmitResearchAction: submitResearchAction,
      activeModelConfig,
      onEditImage: handleEditImage,
      onExpandImage: handleExpandImage, // Pass the new handler
      providerId: config.providerId,
      personas,
      activePersonaId,
      onSelectPersona: handlePersonaSelect,
      sessionId: currentSessionId, // ✅ 传递 sessionId 用于查询附件
      apiKey: config.apiKey, // ✅ 传递 apiKey 用于调用 API
    };

    if (appMode === 'multi-agent') {
      return (
        <Suspense fallback={<LoadingSpinner fullscreen={false} showMessage={false} />}>
          <MultiAgentView
            {...commonProps}
            isLoadingModels={isLoadingModels}
            visibleModels={visibleModels}
            allVisibleModels={allVisibleModels} // ✅ 传递完整模型列表
            apiKey={config.apiKey ?? ''}
            protocol={config.protocol ?? null}
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
          allVisibleModels={allVisibleModels} // ✅ 传递完整模型列表
          apiKey={config.apiKey ?? ''}
          protocol={config.protocol ?? null}
          onPromptSelect={handleWelcomePrompt}
          onOpenSettings={() => handleOpenSettings('profiles')}
          appMode={appMode}
        />
      );
    } else {
      return (
        <StudioView
          {...commonProps}
          messages={messages}
          mode={appMode}
          visibleModels={visibleModels}
          allVisibleModels={allVisibleModels} // ✅ 传递完整模型列表
          initialPrompt={initialPrompt}
          initialAttachments={initialAttachments}
          onDeleteMessage={handleDeleteMessage}
        />
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
  const isAppLoading =
    isAuthLoading || (isAuthenticated && hasActiveProfile === true && isInitLoading);

  // --- Early Return for Loading ---
  if (isAppLoading) {
    return <LoadingSpinner message="正在登录..." showMessage={false} fullscreen />;
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
        sessions={sessions}
        currentSessionId={currentSessionId}
        onNewChat={handleNewChat}
        onSelectSession={setCurrentSessionId}
        onDeleteSession={deleteSession}
        onUpdateSessionTitle={updateSessionTitle}
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
        onOpenCloudStorage={handleOpenCloudStorage}
        appMode={appMode}
        profiles={profiles}
        activeProfileId={activeProfileId}
        onActivateProfile={activateProfile}
        currentUser={user}
        onChangePassword={changePassword}
        onLogout={logout}
        cacheStatus={cacheStatus}
        onRefreshSessions={refreshSessions}
        isPersonaViewOpen={isPersonaViewOpen}
        onOpenPersonaView={handleOpenPersonaView}
        settings={settingsModal}
        showModeNavigation={true}
        setAppMode={handleModeSwitch}
        modeCatalog={modeCatalog}
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
        element={isAuthenticated ? mainAppElement : <Navigate to="/login" replace />}
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

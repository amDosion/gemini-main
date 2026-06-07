import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import { AppMode, Attachment, ChatOptions } from './types/types';
import { llmService } from './services/llmService';
import { initGlobalErrorHandlers, registerGlobalErrorNotifier } from './utils/globalErrorHandler';
import { ConfigProfile } from './services/db'; // ✅ 新增：ConfigProfile 类型

// Cleaner Imports via Barrel Files
import {
  SettingsModal,
  LoadingSpinner,
  ErrorView,
  WelcomeScreen,
} from './components';
import { getErrorMessage } from './utils/errorMessage';

import {
  deleteMessageFromSession,
  submitWelcomePrompt,
  openSettingsPanel,
  openCloudStoragePanel,
  openPersonaPanel,
} from './appHandlers';
import { AppRoutes } from './components/AppRoutes';

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
import { isStudioAppMode } from './utils/appModes';
import { AppShell } from './components/app/AppShell';
import { useWorkspaceModeHandlers } from './hooks/useWorkspaceModeHandlers';

const AppContent: React.FC = () => {
  // --- Router Hooks ---
  const navigate = useNavigate();
  const location = useLocation();
  const { showError } = useToastContext();

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
    retry,
  } = useInitData(shouldLoadInitData);

  // --- UI State ---
  const [isPersonaViewOpen, setIsPersonaViewOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState<'profiles' | 'editor'>('profiles');
  const [isCloudStorageBrowserOpen, setIsCloudStorageBrowserOpen] = useState(false);

  // App Mode State
  const [appMode, setAppMode] = useState<AppMode>('chat');
  const [openWorkspaceModes, setOpenWorkspaceModes] = useState<AppMode[]>(['chat']);
  const [workspaceReloadKeys, setWorkspaceReloadKeys] = useState<Partial<Record<AppMode, number>>>(
    {}
  );
  const [lastStudioMode, setLastStudioMode] = useState<AppMode>('image-gen');
  const [initialAttachments, setInitialAttachments] = useState<Attachment[] | undefined>(undefined);
  const [initialPrompt, setInitialPrompt] = useState<string | undefined>(undefined);

  useEffect(() => {
    setOpenWorkspaceModes((current) =>
      current.includes(appMode) ? current : [...current, appMode]
    );
    if (isStudioAppMode(appMode)) {
      setLastStudioMode(appMode);
    }
  }, [appMode]);

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

  // ✅ C-2: 挂载时激活全局错误兜底，将未处理异常通过 Toast 展示给用户
  useEffect(() => {
    initGlobalErrorHandlers();
    registerGlobalErrorNotifier(showError);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
    selectLatestSessionForMode,
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
          sessionsMode: nonCriticalData.sessionsMode,
          sessionsHasMore: nonCriticalData.sessionsHasMore,
        }
      : undefined
  );

  const { messages, setMessages, loadingState, sendMessage, submitResearchAction, stopGeneration } =
    useChat(currentSessionId, updateSessionMessages, config.apiKey, activeStorageId);

  // --- Wave 2 #36: refs mirror state for stable useCallback handlers ---
  // 模式同 Wave 1 panRef:setter 引用稳定,ref.current 在每次渲染同步,handler 闭包稳定 deps=[]。
  const activePersonaIdRef = useRef(activePersonaId);
  const activeModelConfigRef = useRef(activeModelConfig);
  const currentSessionIdRef = useRef(currentSessionId);
  const messagesRef = useRef(messages);
  activePersonaIdRef.current = activePersonaId;
  activeModelConfigRef.current = activeModelConfig;
  currentSessionIdRef.current = currentSessionId;
  messagesRef.current = messages;

  // --- 消息过滤 ---
  const currentViewMessages = useViewMessages(messages, appMode);
  const chatViewMessages = useViewMessages(messages, 'chat');
  const multiAgentViewMessages = useViewMessages(messages, 'multi-agent');

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

  // Workspace-tab 模式操作 handler 抽离至 ./hooks/useWorkspaceModeHandlers
  const {
    handleWorkspaceModeSelect,
    handleModeNavigationSelect,
    handleWorkspaceModesClose,
    handleWorkspaceModeClose,
    handleWorkspaceModeReload,
  } = useWorkspaceModeHandlers({
    appMode,
    openWorkspaceModes,
    setOpenWorkspaceModes,
    setWorkspaceReloadKeys,
    handleModeSwitch,
    selectLatestSessionForMode,
    refreshSessions,
  });

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
  // Wave 2 #36: useCallback + refs(activePersonaId/activeModelConfig) 保持 deps=[]。
  const handleNewChat = useCallback(() => {
    createNewSession(activePersonaIdRef.current);
    const cfg = activeModelConfigRef.current;
    if (cfg) llmService.startNewChat([], cfg);
    setInitialAttachments(undefined);
    setInitialPrompt(undefined);
  }, [createNewSession]);

  const handleModelSelect = useCallback(
    (id: string) => {
      setCurrentModelId(id);
      setIsModelMenuOpen(false);
      // Let useEffect handle llmService.startNewChat to avoid duplicate calls
    },
    [setCurrentModelId, setIsModelMenuOpen]
  );

  // Wave 2 #36: useCallback + currentSessionIdRef 保持 deps 最小。
  const handlePersonaSelect = useCallback(
    (id: string) => {
      setActivePersonaId(id);

      // ✅ 如果有当前会话，更新会话的 persona
      const sid = currentSessionIdRef.current;
      if (sid) {
        updateSessionPersona(sid, id);
      }
    },
    [setActivePersonaId, updateSessionPersona]
  );

  const onSend = useCallback(
    (
      text: string,
      options: ChatOptions,
      attachments: Attachment[],
      mode: AppMode,
      forcedModelId?: string
    ) => {
      const hasActiveServerProfile = Boolean(activeProfileId || activeProfile);
      // Profile credentials are server-owned and may be redacted from init/settings responses.
      if (!config.apiKey && config.providerId !== 'ollama' && !hasActiveServerProfile) {
        setSettingsInitialTab('profiles');
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
      config.protocol,
      activeProfileId,
      activeProfile,
      currentSessionId,
      sessions,
      showError,
      createNewSession,
      activePersonaId,
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
    setAppMode: handleWorkspaceModeSelect, // ✅ 使用 workspace-aware 切换，确保打开对应 tag
    setCurrentModelId,
    setInitialAttachments,
    setInitialPrompt,
  });

  // 欢迎屏 prompt 选择 — 抽离至 ./appHandlers
  // Wave 2 #36: useCallback 包装,deps 仅为已稳定的 useCallback 引用 (handleModelSelect / handleWorkspaceModeSelect / onSend)。
  const handleWelcomePrompt = useCallback(
    (text: string, mode: AppMode, modelId: string, requiredCap: string) =>
      submitWelcomePrompt(text, mode, modelId, requiredCap, {
        handleModelSelect,
        handleModeSwitch: handleWorkspaceModeSelect,
        onSend,
      }),
    [handleModelSelect, handleWorkspaceModeSelect, onSend]
  );

  // 3 个 open 面板 handler — 抽离至 ./appHandlers（deps 内联，setter 引用稳定无需 useCallback deps）
  const _panelDeps = {
    setIsSettingsOpen,
    setSettingsInitialTab,
    setIsPersonaViewOpen,
    setIsCloudStorageBrowserOpen,
  };
  // Wave 2 #36: useCallback 包装(setter 引用稳定,_panelDeps 仅是 setter 收集器,deps=[] 安全)。
  const handleOpenSettings = useCallback((tab?: string) => openSettingsPanel(tab, _panelDeps), []); // eslint-disable-line react-hooks/exhaustive-deps
  const handleOpenCloudStorage = useCallback(() => openCloudStoragePanel(_panelDeps), []); // eslint-disable-line react-hooks/exhaustive-deps
  const handleOpenPersonaView = useCallback(() => openPersonaPanel(_panelDeps), []); // eslint-disable-line react-hooks/exhaustive-deps

  // 删除单条消息（同时删除对应的用户消息）— 抽离至 ./appHandlers
  // Wave 2 #36: useCallback + refs(currentSessionId/messages) 保持 deps 仅为稳定 setter。
  const handleDeleteMessage = useCallback(
    (messageId: string) =>
      deleteMessageFromSession(messageId, {
        currentSessionId: currentSessionIdRef.current,
        messages: messagesRef.current,
        setMessages,
        updateSessionMessages,
      }),
    [setMessages, updateSessionMessages]
  );

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
  // 外壳（ImageModal + SettingsModal + AppLayout + 工作区）抽离至 ./components/app/AppShell
  const mainAppElement = (
    <AppShell
      previewImage={previewImage}
      setPreviewImage={setPreviewImage}
      allImages={allImages}
      handleNextImage={handleNextImage}
      handlePrevImage={handlePrevImage}
      settingsModal={settingsModal}
      profiles={profiles}
      activeProfileId={activeProfileId}
      activateProfile={activateProfile}
      sessions={sessions}
      currentSessionId={currentSessionId}
      handleNewChat={handleNewChat}
      setCurrentSessionId={setCurrentSessionId}
      deleteSession={deleteSession}
      updateSessionTitle={updateSessionTitle}
      hasMoreSessions={hasMoreSessions}
      isLoadingMore={isLoadingMore}
      loadMoreSessions={loadMoreSessions}
      isModelMenuOpen={isModelMenuOpen}
      setIsModelMenuOpen={setIsModelMenuOpen}
      currentModelId={currentModelId}
      handleOpenSettings={handleOpenSettings}
      handleOpenCloudStorage={handleOpenCloudStorage}
      handleOpenPersonaView={handleOpenPersonaView}
      user={user}
      changePassword={changePassword}
      logout={logout}
      cacheStatus={cacheStatus}
      refreshSessions={refreshSessions}
      modeCatalog={modeCatalog}
      handleModeNavigationSelect={handleModeNavigationSelect}
      openWorkspaceModes={openWorkspaceModes}
      handleWorkspaceModeClose={handleWorkspaceModeClose}
      handleWorkspaceModesClose={handleWorkspaceModesClose}
      handleWorkspaceModeReload={handleWorkspaceModeReload}
      appMode={appMode}
      lastStudioMode={lastStudioMode}
      workspaceReloadKeys={workspaceReloadKeys}
      handleWorkspaceModeSelect={handleWorkspaceModeSelect}
      handleImageClick={handleImageClick}
      loadingState={loadingState}
      onSend={onSend}
      stopGeneration={stopGeneration}
      submitResearchAction={submitResearchAction}
      activeModelConfig={activeModelConfig}
      handleModelSelect={handleModelSelect}
      handleEditImage={handleEditImage}
      handleExpandImage={handleExpandImage}
      config={config}
      personas={personas}
      activePersonaId={activePersonaId}
      handlePersonaSelect={handlePersonaSelect}
      chatViewMessages={chatViewMessages}
      multiAgentViewMessages={multiAgentViewMessages}
      messages={messages}
      isLoadingModels={isLoadingModels}
      visibleModels={visibleModels}
      allVisibleModels={allVisibleModels}
      handleWelcomePrompt={handleWelcomePrompt}
      initialPrompt={initialPrompt}
      initialAttachments={initialAttachments}
      handleDeleteMessage={handleDeleteMessage}
      isCloudStorageBrowserOpen={isCloudStorageBrowserOpen}
      isPersonaViewOpen={isPersonaViewOpen}
      activeStorageId={activeStorageId}
      storageConfigs={storageConfigs}
      setIsCloudStorageBrowserOpen={setIsCloudStorageBrowserOpen}
      createPersona={createPersona}
      updatePersona={updatePersona}
      deletePersona={deletePersona}
      refreshPersonas={refreshPersonas}
      setIsPersonaViewOpen={setIsPersonaViewOpen}
    />
  );

  // 路由分发抽离至 ./components/AppRoutes
  return (
    <AppRoutes
      isAuthenticated={isAuthenticated}
      isAuthLoading={isAuthLoading}
      authError={authError}
      allowRegistration={allowRegistration}
      login={login}
      register={register}
      mainAppElement={mainAppElement}
    />
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

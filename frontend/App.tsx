
import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';

import { AppMode, Attachment, Role } from './types/types';
import { llmService } from './services/llmService';

// Cleaner Imports via Barrel Files
import { 
    AppLayout, 
    ChatView, 
    StudioView, 
    SettingsModal, 
    ImageModal,
    PersonaModal // Ensure this is exported if used, otherwise remove
} from './components';

// Import Auth Components
import { LoginPage, RegisterPage } from './components/auth';

import { 
    useSettings, 
    useModels, 
    useSessions, 
    useChat, 
    usePersonas,
    useAuth
} from './hooks';
import { findAttachmentByUrl, tryFetchCloudUrl } from './hooks/handlers/attachmentUtils';
import { StorageConfig } from './types/storage';
import { db } from './services/db';
import { PdfExtractionService } from './services/pdfExtractionService';

const App: React.FC = () => {
  // --- Router Hooks ---
  const navigate = useNavigate();
  const location = useLocation();

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

  // --- UI State ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false); 
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [settingsInitialTab, setSettingsInitialTab] = useState<'profiles' | 'editor'>('profiles');
  
  // App Mode State
  const [appMode, setAppMode] = useState<AppMode>('chat');
  const [initialAttachments, setInitialAttachments] = useState<Attachment[] | undefined>(undefined);
  const [initialPrompt, setInitialPrompt] = useState<string | undefined>(undefined);
  
  // Track previous session ID to detect actual session switches
  const prevSessionIdRef = useRef<string | null>(null);
  
  // Track previous model config to detect actual model switches
  const prevModelConfigRef = useRef<typeof activeModelConfig>(undefined);
  
  // --- Domain Hooks ---
  const { 
      config, isSettingsOpen, setIsSettingsOpen, 
      profiles, activeProfileId, saveProfile, deleteProfile, activateProfile,
      hiddenModelIds
  } = useSettings();

  const { 
    personas, activePersona, activePersonaId, setActivePersonaId, 
    createPersona, updatePersona, deletePersona, resetPersonas 
  } = usePersonas();

  // --- 云存储状态 ---
  const [storageConfigs, setStorageConfigs] = useState<StorageConfig[]>([]);
  const [activeStorageId, setActiveStorageId] = useState<string | null>(null);
  
  // --- Auth 路由重定向 ---
  useEffect(() => {
    if (isAuthenticated && (location.pathname === '/login' || location.pathname === '/register')) {
      navigate('/', { replace: true });
    } else if (!isAuthenticated && !isAuthLoading && location.pathname !== '/login' && location.pathname !== '/register') {
      navigate('/login', { replace: true });
    }
  }, [isAuthenticated, isAuthLoading, location.pathname, navigate]);

  // --- 加载云存储配置 ---
  useEffect(() => {
    const loadStorageConfigs = async () => {
      try {
        const configs = await db.getStorageConfigs();
        const activeId = await db.getActiveStorageId();
        setStorageConfigs(configs);
        setActiveStorageId(activeId);
      } catch (e) {
        // ✅ 降级到 LocalStorage 不应该报错，只记录日志
        console.warn("加载云存储配置失败（已降级到 LocalStorage）", e);
      }
    };
    
    if (isAuthenticated) {
      loadStorageConfigs();
      // ✅ 用户登录后预加载 PDF 模板（避免首次使用时的延迟）
      PdfExtractionService.preload();
    }
  }, [isAuthenticated]);

  // Get cached models from the active profile for instant loading
  const activeProfile = useMemo(() => profiles.find(p => p.id === activeProfileId), [profiles, activeProfileId]);

  // ✅ 稳定 cachedModels 引用，避免触发不必要的 useEffect
  const cachedModels = useMemo(() => activeProfile?.savedModels, [activeProfile?.savedModels]);

  // Always try to fetch models when provider changes. 
  const { 
    visibleModels, 
    currentModelId, 
    setCurrentModelId, 
    activeModelConfig, 
    isLoadingModels, 
    isModelMenuOpen, 
    setIsModelMenuOpen, 
    refreshModels 
  } = useModels(
      true, 
      hiddenModelIds, 
      config.providerId, 
      cachedModels,  // ✅ 使用稳定的引用
      config.apiKey // Pass apiKey to trigger refresh on profile switch
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
    getSession,
    isLoading: isLoadingSessions,
    // 缓存相关
    cacheStatus,
    refreshSessions,
  } = useSessions();

  // Track sessions in ref to avoid unnecessary useEffect triggers
  const sessionsRef = useRef(sessions);

  const {
    messages,
    setMessages,
    loadingState,
    setLoadingState,
    sendMessage,
    stopGeneration
  } = useChat(currentSessionId, updateSessionMessages, config.apiKey);

  // --- Filter Messages for Current View (Separation Logic) ---
  const currentViewMessages = useMemo(() => {
      return messages.filter(m => {
          // Backward compatibility: If no mode is set, assume it belongs to 'chat'
          const messageMode = m.mode || 'chat';
          return messageMode === appMode;
      });
  }, [messages, appMode]);

  // --- Image Navigation Logic ---
  const { allImages, currentImageIndex } = useMemo(() => {
      if (!previewImage) return { allImages: [], currentImageIndex: -1 };

      // Flatten all image attachments from current view messages
      const images = currentViewMessages.flatMap(m => 
          (m.attachments || [])
             .filter(att => att.mimeType.startsWith('image/') && att.url)
             .map(att => att.url!)
      );

      // Keep array order
      return { 
          allImages: images, 
          currentImageIndex: images.indexOf(previewImage) 
      };
  }, [currentViewMessages, previewImage]);

  // Loop Navigation: Next
  const handleNextImage = () => {
      if (allImages.length <= 1) return;
      const nextIndex = currentImageIndex === allImages.length - 1 ? 0 : currentImageIndex + 1;
      setPreviewImage(allImages[nextIndex]);
  };

  // Loop Navigation: Prev
  const handlePrevImage = () => {
      if (allImages.length <= 1) return;
      const prevIndex = currentImageIndex === 0 ? allImages.length - 1 : currentImageIndex - 1;
      setPreviewImage(allImages[prevIndex]);
  };

  // --- Effects ---
  useEffect(() => {
    if (window.innerWidth >= 1280) setIsRightSidebarOpen(true);
  }, []);

  // ❌ 移除自动创建会话的逻辑
  // 用户应该主动点击"新建聊天"或发送消息时自动创建会话
  // useEffect(() => {
  //   if (isAuthenticated && !isLoadingModels && sessions.length === 0 && currentModelId) {
  //     handleNewChat();
  //   }
  // }, [isAuthenticated, isLoadingModels, currentModelId]);

  // Sync sessions to ref
  useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  useEffect(() => {
    if (currentSessionId) {
      // Use sessionsRef.current instead of getSession to avoid unnecessary triggers
      const session = sessionsRef.current.find(s => s.id === currentSessionId);
      if (session) {
        // Only load messages when session actually switches
        const isSessionSwitch = prevSessionIdRef.current !== currentSessionId;
        if (isSessionSwitch) {
          setMessages(session.messages);
          
          const storedMode = session.mode;
          if (storedMode) {
               setAppMode(storedMode);
          } else {
               const lastMsg = [...session.messages].reverse().find(m => m.mode);
               setAppMode(lastMsg?.mode || 'chat');
          }
          prevSessionIdRef.current = currentSessionId;
        }

        // Only update llmService when session switches or model actually changes
        const isModelSwitch = prevModelConfigRef.current?.id !== activeModelConfig?.id;
        if ((isSessionSwitch || isModelSwitch) && activeModelConfig) {
          llmService.startNewChat(session.messages, activeModelConfig);
          prevModelConfigRef.current = activeModelConfig;
        }
      }
    }
  }, [currentSessionId, activeModelConfig]);

  // --- Handlers ---
  const handleNewChat = () => {
    createNewSession(activePersonaId); // ✅ 传递当前激活的 persona
    if (activeModelConfig) llmService.startNewChat([], activeModelConfig);
    if (window.innerWidth < 768) setIsSidebarOpen(false);
    setAppMode('chat');
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
              if (appMode !== 'image-gen' && appMode !== 'image-edit') {
                  setAppMode('image-gen');
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
        alert("DashScope API Key is required for 'Expand Image'. Please configure it in Settings.");
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
      alert('当前选择的模型不可用，请在模型列表中重新选择后再进行 PDF 提取。');
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

  // ✅ 使用 useCallback 优化，避免每次渲染都创建新函数
  const handleEditImage = useCallback(async (url: string) => {
      setAppMode('image-edit');
      
      // ✅ 尝试从历史消息中查找原附件，复用其 ID（用于后续查询云 URL）
      const found = findAttachmentByUrl(url, messages);
      
      let newAttachment: Attachment;
      
      if (found) {
          // 复用原附件的 ID 和其他信息
          newAttachment = {
              id: found.attachment.id,
              mimeType: found.attachment.mimeType || 'image/png',
              name: found.attachment.name || 'Reference Image',
              url: url,  // ✅ 保留原始 URL 用于显示和匹配
              tempUrl: found.attachment.tempUrl,
              uploadStatus: found.attachment.uploadStatus
          };
          
          // ✅ 如果 uploadStatus 是 pending，查询后端获取云 URL
          if (found.attachment.uploadStatus === 'pending' && currentSessionId) {
              console.log('[handleEditImage] uploadStatus=pending，查询后端获取云 URL');
              const cloudResult = await tryFetchCloudUrl(
                  currentSessionId,
                  found.attachment.id,
                  found.attachment.url,
                  found.attachment.uploadStatus
              );
              if (cloudResult) {
                  console.log('[handleEditImage] ✅ 获取到云 URL:', cloudResult.url.substring(0, 60));
                  // ✅ 修正 (FIX): 云 URL 保存到 url 字段（永久 URL），而不是 tempUrl
                  newAttachment.url = cloudResult.url;
                  newAttachment.uploadStatus = 'completed';
              }
          }
      } else {
          // 未找到原附件，创建新附件
          newAttachment = {
              id: uuidv4(),
              mimeType: 'image/png',
              name: 'Reference Image',
              url: url
          };
      }
      
      console.log('[handleEditImage] 跨模式传递 - 完整附件状态:', {
          foundOriginal: !!found,
          attachmentId: newAttachment.id?.substring(0, 8) + '...',
          url: newAttachment.url?.substring(0, 50) + '...',
          urlType: newAttachment.url?.startsWith('blob:') ? 'Blob' : newAttachment.url?.startsWith('data:') ? 'Base64' : 'HTTP',
          tempUrl: newAttachment.tempUrl?.substring(0, 50) + '...',
          tempUrlType: newAttachment.tempUrl?.startsWith('blob:') ? 'Blob' : newAttachment.tempUrl?.startsWith('data:') ? 'Base64' : newAttachment.tempUrl?.startsWith('http') ? 'HTTP' : 'None',
          uploadStatus: newAttachment.uploadStatus
      });
      
      setInitialAttachments([newAttachment]);
      setInitialPrompt("Make it look like..."); 
      if (activeModelConfig && !activeModelConfig.capabilities.vision) {
          const visionModel = visibleModels.find(m => m.capabilities.vision);
          if (visionModel) setCurrentModelId(visionModel.id);
      }
  }, [messages, currentSessionId, activeModelConfig, visibleModels, setCurrentModelId]);

  // ✅ 使用 useCallback 优化，避免每次渲染都创建新函数
  const handleExpandImage = useCallback(async (url: string) => {
      setAppMode('image-outpainting');
      
      // 根据 URL 类型推断 MIME 类型和扩展名
      let mimeType = 'image/png';
      let extension = 'png';
      
      if (url.startsWith('data:')) {
          // 从 Base64 Data URL 中提取 MIME 类型
          const match = url.match(/^data:([^;]+);/);
          if (match) {
              mimeType = match[1];
              // 根据 MIME 类型确定扩展名
              if (mimeType === 'image/jpeg' || mimeType === 'image/jpg') {
                  extension = 'jpg';
              } else if (mimeType === 'image/webp') {
                  extension = 'webp';
              } else if (mimeType === 'image/gif') {
                  extension = 'gif';
              }
          }
      } else if (url.includes('.jpg') || url.includes('.jpeg')) {
          mimeType = 'image/jpeg';
          extension = 'jpg';
      } else if (url.includes('.webp')) {
          mimeType = 'image/webp';
          extension = 'webp';
      }
      
      // ✅ 尝试从历史消息中查找原附件，复用其 ID（用于后续查询云 URL）
      const found = findAttachmentByUrl(url, messages);
      
      let newAttachment: Attachment;
      
      if (found) {
          // 复用原附件的 ID 和其他信息
          newAttachment = {
              id: found.attachment.id,
              mimeType: found.attachment.mimeType || mimeType,
              name: found.attachment.name || `expand-source-${Date.now()}.${extension}`,
              url: url,  // ✅ 保留原始 URL 用于显示
              tempUrl: found.attachment.tempUrl,
              uploadStatus: found.attachment.uploadStatus
          };
          
          // ✅ 如果 uploadStatus 是 pending，查询后端获取云 URL
          if (found.attachment.uploadStatus === 'pending' && currentSessionId) {
              console.log('[handleExpandImage] uploadStatus=pending，查询后端获取云 URL');
              const cloudResult = await tryFetchCloudUrl(
                  currentSessionId,
                  found.attachment.id,
                  found.attachment.url,
                  found.attachment.uploadStatus
              );
              if (cloudResult) {
                  console.log('[handleExpandImage] ✅ 获取到云 URL:', cloudResult.url.substring(0, 60));
                  // ✅ 修正 (FIX): 云 URL 保存到 url 字段（永久 URL），而不是 tempUrl
                  newAttachment.url = cloudResult.url;
                  newAttachment.uploadStatus = 'completed';
              }
          }
      } else {
          // 未找到原附件，创建新附件
          newAttachment = {
              id: uuidv4(),
              mimeType: mimeType,
              name: `expand-source-${Date.now()}.${extension}`,
              url: url
          };
      }
      
      console.log('[handleExpandImage] 跨模式传递:', {
          foundOriginal: !!found,
          attachmentId: newAttachment.id?.substring(0, 8) + '...',
          urlType: url.startsWith('blob:') ? 'Blob' : url.startsWith('data:') ? 'Base64' : 'HTTP',
          uploadStatus: newAttachment.uploadStatus,
          hasCloudUrl: !!newAttachment.tempUrl && newAttachment.tempUrl.startsWith('http')
      });
      
      setInitialAttachments([newAttachment]);
      setInitialPrompt(undefined); // Clear prompt as outpainting often just needs settings
      // Ensure we stay on a compatible model if possible, but Expand usually uses specific endpoints handled by provider
  }, [messages, currentSessionId]);

  const handleWelcomePrompt = (text: string, mode: AppMode, modelId: string, requiredCap: string) => {
      handleModelSelect(modelId);
      setAppMode(mode);
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

  // --- 云存储处理函数 ---
  const handleSaveStorage = async (config: StorageConfig) => {
    try {
      await db.saveStorageConfig(config);
      const configs = await db.getStorageConfigs();
      setStorageConfigs(configs);
    } catch (e) {
      // ✅ 降级到 LocalStorage 不应该报错
      console.error("保存云存储配置失败", e);
      // ❌ 移除 alert，因为 LocalStorage 保存不应该失败
    }
  };

  const handleDeleteStorage = async (id: string) => {
    try {
      await db.deleteStorageConfig(id);
      const configs = await db.getStorageConfigs();
      setStorageConfigs(configs);
      if (activeStorageId === id) {
        setActiveStorageId(null);
        await db.setActiveStorageId('');
      }
    } catch (e) {
      // ✅ 降级到 LocalStorage 不应该报错
      console.error("删除云存储配置失败", e);
      // ❌ 移除 alert
    }
  };

  const handleActivateStorage = async (id: string) => {
    try {
      await db.setActiveStorageId(id);
      setActiveStorageId(id);
    } catch (e) {
      // ✅ 降级到 LocalStorage 不应该报错
      console.error("激活云存储配置失败", e);
      // ❌ 移除 alert
    }
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

  // ✅ 使用 useCallback 优化，避免每次渲染都创建新函数
  const handleModeSwitch = useCallback((mode: AppMode) => {
    setAppMode(mode);
    if (mode === 'image-gen') {
        let imageModel = visibleModels.find(m => m.id.toLowerCase().includes('imagen'));
        if (!imageModel) {
             imageModel = visibleModels.find(m => m.id === 'gemini-2.5-flash-image') 
             || visibleModels.find(m => m.id.includes('image'))
             || visibleModels.find(m => m.capabilities.vision);
        }
        if (imageModel) setCurrentModelId(imageModel.id);
    } else if (mode === 'image-edit' || mode === 'image-outpainting') {
        const imageModel = visibleModels.find(m => m.capabilities.vision && !m.id.includes('imagen'));
        if (imageModel) setCurrentModelId(imageModel.id);
    } else if (mode === 'video-gen') {
        const videoModel = visibleModels.find(m => m.id.includes('veo'));
        if (videoModel) setCurrentModelId(videoModel.id);
    } else if (mode === 'pdf-extract') {
        // PDF extraction works with most models that support function calling
        // Prefer reasoning-capable models, but allow any compatible model
        const pdfModel = visibleModels.find(m => 
            m.capabilities.reasoning && !m.id.includes('veo') && !m.id.includes('tts')
        ) || visibleModels.find(m => 
            !m.id.includes('veo') && !m.id.includes('tts') && !m.id.includes('wanx')
        );
        
        // Only switch if current model is incompatible (e.g. Veo, TTS, Image Gen)
        if (pdfModel && !visibleModels.find(m => 
            m.id === currentModelId && !m.id.includes('veo') && !m.id.includes('tts')
        )) {
            setCurrentModelId(pdfModel.id);
        }
    }
  }, [visibleModels, setCurrentModelId, currentModelId]);

  // ✅ 使用 useCallback 优化 onImageClick
  const handleImageClick = useCallback((url: string) => setPreviewImage(url), []);

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

      if (appMode === 'chat' || appMode === 'deep-research') {
          return (
            <ChatView 
                {...commonProps}
                isLoadingModels={isLoadingModels}
                visibleModels={visibleModels}
                apiKey={config.apiKey}
                protocol={config.protocol}
                onPromptSelect={handleWelcomePrompt}
                onOpenSettings={() => handleOpenSettings('profiles')}
                appMode={appMode} // ✅ 修复：传递 appMode 给 ChatView
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
      return (
          <div className="fixed inset-0 bg-[#0f172a] flex items-center justify-center">
              <div className="w-10 h-10 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
          </div>
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
            onResetPersonas={resetPersonas}

            settings={isSettingsOpen && (
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
            )}
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

export default App;

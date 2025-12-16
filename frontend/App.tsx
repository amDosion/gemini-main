
import React, { useState, useEffect, useMemo } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { AppMode, Attachment } from '../types';
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

// Import Login Page
import { LoginPage } from './components/auth/LoginPage';

import { 
    useSettings, 
    useModels, 
    useSessions, 
    useChat, 
    usePersonas 
} from './hooks';
import { StorageConfig } from './types/storage';
import { db } from './services/db';

const App: React.FC = () => {
  // --- Auth State ---
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isAuthChecking, setIsAuthChecking] = useState<boolean>(true);

  // --- UI State ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false); 
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [settingsInitialTab, setSettingsInitialTab] = useState<'profiles' | 'editor'>('profiles');
  
  // App Mode State
  const [appMode, setAppMode] = useState<AppMode>('chat');
  const [initialAttachments, setInitialAttachments] = useState<Attachment[] | undefined>(undefined);
  const [initialPrompt, setInitialPrompt] = useState<string | undefined>(undefined);
  
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
  
  // --- Auth Effect ---
  useEffect(() => {
    const checkAuth = () => {
      try {
        const storedAuth = localStorage.getItem('flux_auth_token');
        if (storedAuth) {
          setIsAuthenticated(true);
        }
      } catch (e) {
        console.warn("Auth storage check failed", e);
      } finally {
        setIsAuthChecking(false);
      }
    };
    checkAuth();
  }, []);

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
    }
  }, [isAuthenticated]);

  const handleLogin = () => {
    try {
      localStorage.setItem('flux_auth_token', 'session-' + Date.now());
    } catch (e) {
      console.warn("Failed to save auth token", e);
    }
    setIsAuthenticated(true);
  };

  // Get cached models from the active profile for instant loading
  const activeProfile = useMemo(() => profiles.find(p => p.id === activeProfileId), [profiles, activeProfileId]);

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
      activeProfile?.savedModels,
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
    isLoading: isLoadingSessions
  } = useSessions();

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

  useEffect(() => {
    if (currentSessionId) {
      const session = getSession(currentSessionId);
      if (session) {
        setMessages(session.messages);
        
        // Restore Mode from Session
        const storedMode = session.mode;
        if (storedMode) {
             setAppMode(storedMode);
        } else {
             const lastMsg = [...session.messages].reverse().find(m => m.mode);
             setAppMode(lastMsg?.mode || 'chat');
        }

        if (activeModelConfig) llmService.startNewChat(session.messages, activeModelConfig);
      }
    }
  }, [currentSessionId]);

  // --- Handlers ---
  const handleNewChat = () => {
    createNewSession(activePersonaId); // ✅ 传递当前激活的 persona
    if (activeModelConfig) llmService.startNewChat([], activeModelConfig);
    if (window.innerWidth < 768) setIsSidebarOpen(false);
    setAppMode('chat');
    setInitialAttachments(undefined);
    setInitialPrompt(undefined);
  };

  const handleModelSelect = (id: string) => {
    setCurrentModelId(id);
    setIsModelMenuOpen(false);
    const newModel = visibleModels.find(m => m.id === id);
    if (newModel) llmService.startNewChat(messages, newModel);
  };

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

  const onSend = (text: string, options: any, attachments: Attachment[], mode: AppMode) => {
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
  };

  const handleEditImage = (url: string) => {
      setAppMode('image-edit');
      const newAttachment: Attachment = {
          id: uuidv4(),
          mimeType: 'image/png',
          name: 'Reference Image',
          url: url
      };
      setInitialAttachments([newAttachment]);
      setInitialPrompt("Make it look like..."); 
      if (activeModelConfig && !activeModelConfig.capabilities.vision) {
          const visionModel = visibleModels.find(m => m.capabilities.vision);
          if (visionModel) setCurrentModelId(visionModel.id);
      }
  };

  const handleExpandImage = (url: string) => {
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
      
      const newAttachment: Attachment = {
          id: uuidv4(),
          mimeType: mimeType,
          name: `expand-source-${Date.now()}.${extension}`,  // ✅ 添加正确的扩展名
          url: url
      };
      setInitialAttachments([newAttachment]);
      setInitialPrompt(undefined); // Clear prompt as outpainting often just needs settings
      // Ensure we stay on a compatible model if possible, but Expand usually uses specific endpoints handled by provider
  };

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
  
  const handleModeSwitch = (mode: AppMode) => {
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
  };

  const renderView = () => {
      const commonProps = {
          messages: currentViewMessages,
          setAppMode: handleModeSwitch,
          onImageClick: (url: string) => setPreviewImage(url),
          loadingState,
          onSend,
          onStop: stopGeneration,
          activeModelConfig,
          onEditImage: handleEditImage,
          onExpandImage: handleExpandImage, // Pass the new handler
          providerId: config.providerId,
          sessionId: currentSessionId  // ✅ 传递 sessionId 用于查询附件
      };

      if (appMode === 'chat') {
          return (
            <ChatView 
                {...commonProps}
                isLoadingModels={isLoadingModels}
                visibleModels={visibleModels}
                apiKey={config.apiKey}
                protocol={config.protocol}
                onPromptSelect={handleWelcomePrompt}
                onOpenSettings={() => handleOpenSettings('profiles')}
            />
          );
      } else {
          return (
            <StudioView 
                key={appMode}
                {...commonProps}
                mode={appMode}
                initialPrompt={initialPrompt}
                initialAttachments={initialAttachments}
            />
          );
      }
  };

  // --- Early Return for Auth Check ---
  if (isAuthChecking) {
      return (
          <div className="fixed inset-0 bg-[#0f172a] flex items-center justify-center">
              <div className="w-10 h-10 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
          </div>
      );
  }

  // --- Render Login Page ---
  if (!isAuthenticated) {
      return <LoginPage onLogin={handleLogin} />;
  }

  // --- Render Main App ---
  return (
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
};

export default App;

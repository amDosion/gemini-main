import React from 'react';

import {
  AppMode,
  Attachment,
  ChatOptions,
  ChatSession,
  LoadingState,
  Message,
  ModeCatalogItem,
  ModelConfig,
  Persona,
} from '../../types/types';
import { StorageConfig } from '../../types/storage';
import { ConfigProfile } from '../../services/db';
import type { User, ChangePasswordData } from '../../services/auth';
import { CacheStatusInfo } from '../../hooks/useCacheStatus';
import { AppConfig } from '../../hooks/useSettings';

import { AppLayout, ImageModal } from '../index';
import { WorkspaceTagViews } from '../layout/WorkspaceTagViews';
import { WorkspaceArea } from './WorkspaceArea';

export interface AppShellProps {
  // --- Image preview modal ---
  previewImage: string | null;
  setPreviewImage: (url: string | null) => void;
  allImages: string[];
  handleNextImage: () => void;
  handlePrevImage: () => void;

  // --- Settings modal (built by App.tsx, also used by its early-return path) ---
  settingsModal: React.ReactNode;
  profiles: ConfigProfile[];
  activeProfileId: string | null;
  activateProfile: (id: string) => Promise<void>;

  // --- Layout / header / sessions ---
  sessions: ChatSession[];
  currentSessionId: string | null;
  handleNewChat: () => void;
  setCurrentSessionId: (id: string) => void;
  deleteSession: (id: string) => void;
  updateSessionTitle: (id: string, newTitle: string) => void;
  hasMoreSessions: boolean;
  isLoadingMore: boolean;
  loadMoreSessions: () => void;
  isModelMenuOpen: boolean;
  setIsModelMenuOpen: (open: boolean) => void;
  currentModelId: string;
  handleOpenSettings: (tab?: string) => void;
  handleOpenCloudStorage: () => void;
  handleOpenPersonaView: () => void;
  user: User | null;
  changePassword: (data: ChangePasswordData) => Promise<void>;
  logout: () => void;
  cacheStatus: CacheStatusInfo;
  refreshSessions: () => void;
  modeCatalog: ModeCatalogItem[];
  handleModeNavigationSelect: (mode: AppMode) => void;

  // --- Workspace tabs ---
  openWorkspaceModes: AppMode[];
  handleWorkspaceModeClose: (mode: AppMode) => void;
  handleWorkspaceModesClose: (modes: AppMode[]) => void;
  handleWorkspaceModeReload: (mode: AppMode) => void;

  // --- Workspace area (shared with WorkspaceArea) ---
  appMode: AppMode;
  lastStudioMode: AppMode;
  workspaceReloadKeys: Partial<Record<AppMode, number>>;
  handleWorkspaceModeSelect: (mode: AppMode) => void;
  handleImageClick: (url: string) => void;
  loadingState: LoadingState;
  onSend: (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode,
    forcedModelId?: string
  ) => void;
  stopGeneration: () => void;
  submitResearchAction: (messageId: string, selectedInput: unknown) => Promise<void>;
  activeModelConfig?: ModelConfig;
  handleModelSelect: (id: string) => void;
  handleEditImage: (url: string, attachment?: Attachment) => void;
  handleExpandImage: (url: string, attachment?: Attachment) => void;
  config: AppConfig;
  personas: Persona[];
  activePersonaId: string;
  handlePersonaSelect: (id: string) => void;
  chatViewMessages: Message[];
  multiAgentViewMessages: Message[];
  messages: Message[];
  isLoadingModels: boolean;
  visibleModels: ModelConfig[];
  allVisibleModels: ModelConfig[];
  handleWelcomePrompt: (
    text: string,
    mode: AppMode,
    modelId: string,
    requiredCap: string
  ) => void;
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  handleDeleteMessage: (messageId: string) => void;
  isCloudStorageBrowserOpen: boolean;
  isPersonaViewOpen: boolean;
  activeStorageId: string | null;
  storageConfigs: StorageConfig[];
  setIsCloudStorageBrowserOpen: (open: boolean) => void;
  createPersona: (persona: Omit<Persona, 'id'>) => void;
  updatePersona: (id: string, updates: Partial<Persona>) => void;
  deletePersona: (id: string) => void;
  refreshPersonas: () => void;
  setIsPersonaViewOpen: (open: boolean) => void;
}

/**
 * AppShell — 主应用外壳（图片预览 Modal + 设置 Modal + AppLayout + 工作区）。
 *
 * 1:1 抽离自 `App.tsx` 的 `settingsModal` / `mainAppElement` 组合
 * （< 800 行合规拆分）。纯组合组件：所有状态与副作用仍由 App.tsx 持有，
 * 本组件仅消费 props 并渲染。
 */
export const AppShell: React.FC<AppShellProps> = (props) => {
  const {
    previewImage,
    setPreviewImage,
    allImages,
    handleNextImage,
    handlePrevImage,
    settingsModal,
    profiles,
    activeProfileId,
    activateProfile,
    sessions,
    currentSessionId,
    handleNewChat,
    setCurrentSessionId,
    deleteSession,
    updateSessionTitle,
    hasMoreSessions,
    isLoadingMore,
    loadMoreSessions,
    isModelMenuOpen,
    setIsModelMenuOpen,
    currentModelId,
    handleOpenSettings,
    handleOpenCloudStorage,
    handleOpenPersonaView,
    user,
    changePassword,
    logout,
    cacheStatus,
    refreshSessions,
    modeCatalog,
    handleModeNavigationSelect,
    openWorkspaceModes,
    handleWorkspaceModeClose,
    handleWorkspaceModesClose,
    handleWorkspaceModeReload,
    appMode,
    lastStudioMode,
    workspaceReloadKeys,
    handleWorkspaceModeSelect,
    handleImageClick,
    loadingState,
    onSend,
    stopGeneration,
    submitResearchAction,
    activeModelConfig,
    handleModelSelect,
    handleEditImage,
    handleExpandImage,
    config,
    personas,
    activePersonaId,
    handlePersonaSelect,
    chatViewMessages,
    multiAgentViewMessages,
    messages,
    isLoadingModels,
    visibleModels,
    allVisibleModels,
    handleWelcomePrompt,
    initialPrompt,
    initialAttachments,
    handleDeleteMessage,
    isCloudStorageBrowserOpen,
    isPersonaViewOpen,
    activeStorageId,
    storageConfigs,
    setIsCloudStorageBrowserOpen,
    createPersona,
    updatePersona,
    deletePersona,
    refreshPersonas,
    setIsPersonaViewOpen,
  } = props;

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
        setAppMode={handleModeNavigationSelect}
        modeCatalog={modeCatalog}
        workspaceTabs={
          <WorkspaceTagViews
            activeMode={appMode}
            openModes={openWorkspaceModes}
            modeCatalog={modeCatalog}
            onSelectMode={handleWorkspaceModeSelect}
            onCloseMode={handleWorkspaceModeClose}
            onCloseModes={handleWorkspaceModesClose}
            onReloadMode={handleWorkspaceModeReload}
          />
        }
      >
        <WorkspaceArea
          openWorkspaceModes={openWorkspaceModes}
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
          currentSessionId={currentSessionId}
          chatViewMessages={chatViewMessages}
          multiAgentViewMessages={multiAgentViewMessages}
          messages={messages}
          isLoadingModels={isLoadingModels}
          visibleModels={visibleModels}
          allVisibleModels={allVisibleModels}
          handleWelcomePrompt={handleWelcomePrompt}
          handleOpenSettings={handleOpenSettings}
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
      </AppLayout>
    </>
  );
};

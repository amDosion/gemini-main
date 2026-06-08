import React, { Suspense } from 'react';

import {
  AppMode,
  Attachment,
  ChatOptions,
  LoadingState,
  Message,
  ModelConfig,
  Persona,
} from '../../types/types';
import { StorageConfig } from '../../types/storage';
import { AppConfig } from '../../hooks/useSettings';

import { ChatView, LoadingSpinner } from '../index';
import { GlobalErrorBoundary } from '../common/GlobalErrorBoundary';
import {
  MultiAgentView,
  StudioView,
  CloudStorageView,
  PersonaManagementView,
} from '../../lazyViews';
import { isStudioAppMode } from '../../utils/appModes';

export interface WorkspaceAreaProps {
  // --- Workspace stack composition ---
  openWorkspaceModes: AppMode[];
  appMode: AppMode;
  lastStudioMode: AppMode;
  workspaceReloadKeys: Partial<Record<AppMode, number>>;

  // --- Shared view props (commonProps) ---
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
  currentSessionId: string | null;

  // --- Per-view messages ---
  chatViewMessages: Message[];
  multiAgentViewMessages: Message[];
  messages: Message[];

  // --- Model menu / welcome ---
  isLoadingModels: boolean;
  visibleModels: ModelConfig[];
  allVisibleModels: ModelConfig[];
  handleWelcomePrompt: (text: string, mode: AppMode, modelId: string, requiredCap: string) => void;
  handleOpenSettings: (tab?: string) => void;

  // --- Studio init ---
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  handleDeleteMessage: (messageId: string) => void;

  // --- Overlay views ---
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
 * WorkspaceArea — 工作区视图渲染树。
 *
 * 1:1 抽离自 `App.tsx` 的 `renderWorkspaceViewStack` + `renderView`
 * （< 800 行合规拆分）。封装：
 *   - keep-alive 堆栈：所有 open 的 workspace 模式（chat / multi-agent / studio）
 *     同时挂载，靠 CSS display 切换显隐，而非卸载重建。
 *   - lastStudioMode 记忆：离开 studio 模式后保持其 mode prop 不变。
 *   - overlay 覆盖：打开 cloud storage / persona 面板时，把堆栈包进 `.hidden`
 *     容器并叠加覆盖视图，关闭后恢复堆栈到前台。
 *
 * 所有状态与副作用仍由 App.tsx 持有；本组件为纯渲染（仅消费 props）。
 */
export const WorkspaceArea: React.FC<WorkspaceAreaProps> = (props) => {
  const {
    openWorkspaceModes,
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
    currentSessionId,
    chatViewMessages,
    multiAgentViewMessages,
    messages,
    isLoadingModels,
    visibleModels,
    allVisibleModels,
    handleWelcomePrompt,
    handleOpenSettings,
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

  const renderWorkspaceViewStack = () => {
    const hasChatView = openWorkspaceModes.includes('chat');
    const hasMultiAgentView = openWorkspaceModes.includes('multi-agent');
    const hasStudioView = openWorkspaceModes.some(isStudioAppMode);
    const activeStudioMode = isStudioAppMode(appMode) ? appMode : lastStudioMode;

    const commonProps = {
      setAppMode: handleWorkspaceModeSelect,
      onImageClick: handleImageClick, // ✅ 使用稳定的引用
      loadingState,
      onSend,
      onStop: stopGeneration,
      onSubmitResearchAction: submitResearchAction,
      activeModelConfig,
      onModelSelect: handleModelSelect,
      onEditImage: handleEditImage,
      onExpandImage: handleExpandImage, // Pass the new handler
      providerId: config.providerId,
      personas,
      activePersonaId,
      onSelectPersona: handlePersonaSelect,
      sessionId: currentSessionId, // ✅ 传递 sessionId 用于查询附件
      apiKey: config.apiKey, // ✅ 传递 apiKey 用于调用 API
    };

    // chat / multi-agent 共享的欢迎页 + 模型菜单 props（StudioView 不消费这些）
    const chatLikeProps = {
      isLoadingModels,
      visibleModels,
      allVisibleModels, // ✅ 传递完整模型列表
      apiKey: config.apiKey ?? '',
      protocol: config.protocol ?? null,
      onPromptSelect: handleWelcomePrompt,
      onOpenSettings: () => handleOpenSettings('profiles'),
    };

    return (
      <>
        {hasChatView && (
          <div
            key={`chat-${workspaceReloadKeys.chat || 0}`}
            style={{ display: appMode === 'chat' ? 'contents' : 'none' }}
          >
            <ChatView
              {...commonProps}
              {...chatLikeProps}
              messages={chatViewMessages}
              appMode="chat"
            />
          </div>
        )}

        {hasMultiAgentView && (
          <div
            key={`multi-agent-${workspaceReloadKeys['multi-agent'] || 0}`}
            style={{ display: appMode === 'multi-agent' ? 'contents' : 'none' }}
          >
            <GlobalErrorBoundary>
              <Suspense fallback={<LoadingSpinner fullscreen={false} showMessage={false} />}>
                <MultiAgentView
                  {...commonProps}
                  {...chatLikeProps}
                  messages={multiAgentViewMessages}
                  appMode="multi-agent"
                />
              </Suspense>
            </GlobalErrorBoundary>
          </div>
        )}

        {hasStudioView && (
          <div style={{ display: isStudioAppMode(appMode) ? 'contents' : 'none' }}>
            <StudioView
              {...commonProps}
              messages={messages}
              mode={activeStudioMode}
              modeReloadKeys={workspaceReloadKeys}
              visibleModels={visibleModels}
              allVisibleModels={allVisibleModels} // ✅ 传递完整模型列表
              initialPrompt={initialPrompt}
              initialAttachments={initialAttachments}
              onDeleteMessage={handleDeleteMessage}
            />
          </div>
        )}
      </>
    );
  };

  if (isCloudStorageBrowserOpen || isPersonaViewOpen) {
    return (
      <>
        <div className="hidden">{renderWorkspaceViewStack()}</div>
        {isCloudStorageBrowserOpen && (
          <GlobalErrorBoundary>
            <Suspense fallback={<LoadingSpinner fullscreen={false} showMessage={false} />}>
              <CloudStorageView
                activeStorageId={activeStorageId}
                storageConfigs={storageConfigs}
                onClose={() => setIsCloudStorageBrowserOpen(false)}
              />
            </Suspense>
          </GlobalErrorBoundary>
        )}
        {isPersonaViewOpen && (
          <GlobalErrorBoundary>
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
          </GlobalErrorBoundary>
        )}
      </>
    );
  }

  return renderWorkspaceViewStack();
};

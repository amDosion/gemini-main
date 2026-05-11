/**
 * App.tsx 内部消息处理函数（外部纯函数化，便于测试 + 减小主组件体积）。
 *
 * 1:1 抽离自 `App.tsx` handleDeleteMessage L578-602
 * （< 800 行合规拆分）。
 */

import { AppMode, Attachment, ChatOptions, Message, Role } from './types/types';

export interface DeleteMessageDeps {
  currentSessionId: string | null;
  messages: Message[];
  setMessages: (next: Message[]) => void;
  updateSessionMessages: (sessionId: string, next: Message[]) => void;
}

/**
 * 删除单条消息（如果是 MODEL 消息，同时删除前一条 USER 消息以保持成对）。
 * 无会话或目标消息不存在时直接返回。
 */
export const deleteMessageFromSession = (
  messageId: string,
  { currentSessionId, messages, setMessages, updateSessionMessages }: DeleteMessageDeps
): void => {
  if (!currentSessionId) return;

  const msgToDelete = messages.find((m) => m.id === messageId);
  if (!msgToDelete) return;

  // 如果是 MODEL 消息，同时删除前一条 USER 消息（成对删除）
  const idsToDelete = [messageId];
  if (msgToDelete.role === Role.MODEL) {
    const msgIndex = messages.findIndex((m) => m.id === messageId);
    if (msgIndex > 0) {
      const prevMsg = messages[msgIndex - 1];
      if (prevMsg.role === Role.USER && prevMsg.mode === msgToDelete.mode) {
        idsToDelete.push(prevMsg.id);
      }
    }
  }

  const newMessages = messages.filter((m) => !idsToDelete.includes(m.id));
  setMessages(newMessages);
  updateSessionMessages(currentSessionId, newMessages);
};

export interface WelcomePromptDeps {
  handleModelSelect: (modelId: string) => void;
  handleModeSwitch: (mode: AppMode) => void;
  onSend: (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode,
    forcedModelId?: string
  ) => void;
}

/**
 * 欢迎屏 prompt 选择处理：切模型 → 切模式 → 发起消息（带特定能力 flag）。
 */
export const submitWelcomePrompt = (
  text: string,
  mode: AppMode,
  modelId: string,
  requiredCap: string,
  { handleModelSelect, handleModeSwitch, onSend }: WelcomePromptDeps
): void => {
  handleModelSelect(modelId);
  handleModeSwitch(mode);
  onSend(
    text,
    {
      enableSearch: requiredCap === 'search',
      enableThinking: requiredCap === 'reasoning',
      enableCodeExecution: false,
      imageAspectRatio: '1:1',
      imageResolution: '1K',
      voiceName: 'Puck',
    },
    [],
    mode,
    modelId
  );
};

export interface OpenPanelDeps {
  setIsSettingsOpen: (value: boolean) => void;
  setSettingsInitialTab: (value: 'profiles' | 'editor') => void;
  setIsPersonaViewOpen: (value: boolean) => void;
  setIsCloudStorageBrowserOpen: (value: boolean) => void;
}

/** 打开设置面板（指定 tab；默认 profiles） */
export const openSettingsPanel = (tab: string | undefined, deps: OpenPanelDeps): void => {
  deps.setSettingsInitialTab(tab === 'editor' ? 'editor' : 'profiles');
  deps.setIsSettingsOpen(true);
};

/** 打开云存储浏览器（同时关闭 persona view 防止同屏冲突） */
export const openCloudStoragePanel = (deps: OpenPanelDeps): void => {
  deps.setIsPersonaViewOpen(false);
  deps.setIsCloudStorageBrowserOpen(true);
};

/** 打开 persona 管理视图（同时关闭云存储浏览器） */
export const openPersonaPanel = (deps: OpenPanelDeps): void => {
  deps.setIsCloudStorageBrowserOpen(false);
  deps.setIsPersonaViewOpen(true);
};

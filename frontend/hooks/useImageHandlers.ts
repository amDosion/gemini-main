import { useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { AppMode, Attachment, Message, ModelConfig } from '../types/types';
import { findAttachmentByUrl } from './handlers/attachmentUtils';

interface UseImageHandlersProps {
  messages: Message[];
  visibleModels: ModelConfig[];
  activeModelConfig?: ModelConfig;
  setAppMode: (mode: AppMode) => void;
  setCurrentModelId: (id: string) => void;
  setInitialAttachments: (attachments: Attachment[] | undefined) => void;
  setInitialPrompt: (prompt: string | undefined) => void;
}

interface UseImageHandlersReturn {
  handleEditImage: (url: string, attachment?: Attachment) => Promise<void>;
  handleExpandImage: (url: string, attachment?: Attachment) => Promise<void>;
}

/**
 * 根据 URL 推断 MIME 类型和扩展名（纯函数，组件外）
 *
 * 输入可能是 data: URL 或包含扩展名的 HTTP URL；其他情况回落到 image/png。
 */
const inferImageMimeFromUrl = (url: string): { mimeType: string; extension: string } => {
  if (url.startsWith('data:')) {
    const match = url.match(/^data:([^;]+);/);
    if (match) {
      const mimeType = match[1];
      let extension = 'png';
      if (mimeType === 'image/jpeg' || mimeType === 'image/jpg') extension = 'jpg';
      else if (mimeType === 'image/webp') extension = 'webp';
      else if (mimeType === 'image/gif') extension = 'gif';
      return { mimeType, extension };
    }
  } else if (url.includes('.jpg') || url.includes('.jpeg')) {
    return { mimeType: 'image/jpeg', extension: 'jpg' };
  } else if (url.includes('.webp')) {
    return { mimeType: 'image/webp', extension: 'webp' };
  }
  return { mimeType: 'image/png', extension: 'png' };
};

/**
 * 从 URL 构造 Attachment（纯函数，组件外，三种来源优先级）：
 * 1. 显式传入的 attachment（保留 uploadTaskId 等扩展字段）
 * 2. 历史消息中按 URL 找到的附件
 * 3. 全新生成（仅 url + 默认 mime/name）
 */
const buildAttachmentFromUrl = (
  url: string,
  attachment: Attachment | undefined,
  messages: Message[],
  defaultMimeType: string,
  defaultName: string
): Attachment => {
  if (attachment && attachment.id) {
    return {
      id: attachment.id,
      mimeType: attachment.mimeType || defaultMimeType,
      name: attachment.name || defaultName,
      url,
      tempUrl: attachment.tempUrl,
      uploadStatus: attachment.uploadStatus,
      uploadTaskId: attachment.uploadTaskId,
    };
  }
  const found = findAttachmentByUrl(url, messages);
  if (found) {
    return {
      id: found.attachment.id,
      mimeType: found.attachment.mimeType || defaultMimeType,
      name: found.attachment.name || defaultName,
      url,
      tempUrl: found.attachment.tempUrl,
      uploadStatus: found.attachment.uploadStatus,
    };
  }
  return {
    id: uuidv4(),
    mimeType: defaultMimeType,
    name: defaultName,
    url,
  };
};

/**
 * 图片处理 Handlers Hook
 * 处理图片编辑和扩展的逻辑
 */
export const useImageHandlers = ({
  messages,
  visibleModels,
  activeModelConfig,
  setAppMode,
  setCurrentModelId,
  setInitialAttachments,
  setInitialPrompt,
}: UseImageHandlersProps): UseImageHandlersReturn => {
  const handleEditImage = useCallback(
    async (url: string, attachment?: Attachment) => {
      setAppMode('image-chat-edit'); // 默认使用对话式编辑模式
      const newAttachment = buildAttachmentFromUrl(
        url,
        attachment,
        messages,
        'image/png',
        'Reference Image'
      );
      setInitialAttachments([newAttachment]);
      setInitialPrompt('Make it look like...');
      if (activeModelConfig && !activeModelConfig.capabilities.vision) {
        const visionModel = visibleModels.find((m) => m.capabilities.vision);
        if (visionModel) setCurrentModelId(visionModel.id);
      }
    },
    [
      messages,
      activeModelConfig,
      visibleModels,
      setCurrentModelId,
      setAppMode,
      setInitialAttachments,
      setInitialPrompt,
    ]
  );

  const handleExpandImage = useCallback(
    async (url: string, attachment?: Attachment) => {
      setAppMode('image-outpainting');
      const { mimeType, extension } = inferImageMimeFromUrl(url);
      const newAttachment = buildAttachmentFromUrl(
        url,
        attachment,
        messages,
        mimeType,
        `expand-source-${Date.now()}.${extension}`
      );
      setInitialAttachments([newAttachment]);
      setInitialPrompt(undefined); // Clear prompt as outpainting often just needs settings
    },
    [messages, setAppMode, setInitialAttachments, setInitialPrompt]
  );

  return {
    handleEditImage,
    handleExpandImage,
  };
};

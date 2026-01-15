
import { useCallback, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { AppMode, Attachment, Message, ModelConfig } from '../types/types';
import { findAttachmentByUrl, tryFetchCloudUrl } from './handlers/attachmentUtils';

interface UseImageHandlersProps {
  messages: Message[];
  currentSessionId: string | null;
  visibleModels: ModelConfig[];
  activeModelConfig?: ModelConfig;
  setAppMode: (mode: AppMode) => void;
  setCurrentModelId: (id: string) => void;
  setInitialAttachments: (attachments: Attachment[] | undefined) => void;
  setInitialPrompt: (prompt: string | undefined) => void;
}

interface UseImageHandlersReturn {
  handleEditImage: (url: string) => Promise<void>;
  handleExpandImage: (url: string) => Promise<void>;
}

/**
 * 图片处理 Handlers Hook
 * 处理图片编辑和扩展的逻辑
 */
export const useImageHandlers = ({
  messages,
  currentSessionId,
  visibleModels,
  activeModelConfig,
  setAppMode,
  setCurrentModelId,
  setInitialAttachments,
  setInitialPrompt
}: UseImageHandlersProps): UseImageHandlersReturn => {
  const handleEditImage = useCallback(async (url: string) => {
    setAppMode('image-chat-edit'); // 默认使用对话式编辑模式

    // 尝试从历史消息中查找原附件，复用其 ID（用于后续查询云 URL）
    const found = findAttachmentByUrl(url, messages);

    let newAttachment: Attachment;

    if (found) {
      // 复用原附件的 ID 和其他信息
      newAttachment = {
        id: found.attachment.id,
        mimeType: found.attachment.mimeType || 'image/png',
        name: found.attachment.name || 'Reference Image',
        url: url, // 保留原始 URL 用于显示和匹配
        tempUrl: found.attachment.tempUrl,
        uploadStatus: found.attachment.uploadStatus
      };

      // 如果 uploadStatus 是 pending，查询后端获取云 URL
      if (found.attachment.uploadStatus === 'pending' && currentSessionId) {
        const cloudResult = await tryFetchCloudUrl(
          currentSessionId,
          found.attachment.id,
          found.attachment.url,
          found.attachment.uploadStatus
        );
        if (cloudResult) {
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


    setInitialAttachments([newAttachment]);
    setInitialPrompt("Make it look like...");
    if (activeModelConfig && !activeModelConfig.capabilities.vision) {
      const visionModel = visibleModels.find(m => m.capabilities.vision);
      if (visionModel) setCurrentModelId(visionModel.id);
    }
  }, [messages, currentSessionId, activeModelConfig, visibleModels, setCurrentModelId, setAppMode, setInitialAttachments, setInitialPrompt]);

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

    // 尝试从历史消息中查找原附件，复用其 ID（用于后续查询云 URL）
    const found = findAttachmentByUrl(url, messages);

    let newAttachment: Attachment;

    if (found) {
      // 复用原附件的 ID 和其他信息
      newAttachment = {
        id: found.attachment.id,
        mimeType: found.attachment.mimeType || mimeType,
        name: found.attachment.name || `expand-source-${Date.now()}.${extension}`,
        url: url, // 保留原始 URL 用于显示
        tempUrl: found.attachment.tempUrl,
        uploadStatus: found.attachment.uploadStatus
      };

      // 如果 uploadStatus 是 pending，查询后端获取云 URL
      if (found.attachment.uploadStatus === 'pending' && currentSessionId) {
        const cloudResult = await tryFetchCloudUrl(
          currentSessionId,
          found.attachment.id,
          found.attachment.url,
          found.attachment.uploadStatus
        );
        if (cloudResult) {
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


    setInitialAttachments([newAttachment]);
    setInitialPrompt(undefined); // Clear prompt as outpainting often just needs settings
  }, [messages, currentSessionId, setAppMode, setInitialAttachments, setInitialPrompt]);

  return {
    handleEditImage,
    handleExpandImage
  };
};


import { useCallback, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { AppMode, Attachment, Message, ModelConfig } from '../types/types';
import { findAttachmentByUrl, tryFetchCloudUrl, isHttpUrl } from './handlers/attachmentUtils';

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
  handleEditImage: (url: string, attachment?: Attachment) => Promise<void>;
  handleExpandImage: (url: string, attachment?: Attachment) => Promise<void>;
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
  const handleEditImage = useCallback(async (url: string, attachment?: Attachment) => {
    setAppMode('image-chat-edit'); // 默认使用对话式编辑模式

    let newAttachment: Attachment;

    // ✅ 优先使用传入的 attachment 对象（如果提供），确保 attachmentId 被正确传递
    if (attachment && attachment.id) {
      // 直接使用传入的 attachment，确保 attachmentId 被保留
      newAttachment = {
        id: attachment.id,
        mimeType: attachment.mimeType || 'image/png',
        name: attachment.name || 'Reference Image',
        url: url, // ✅ 优先使用传入的 URL（无论是 Base64 还是 HTTP URL）（🚀 加速显示）
        tempUrl: attachment.tempUrl,
        uploadStatus: attachment.uploadStatus,
        uploadTaskId: attachment.uploadTaskId
      };
    } else {
      // 降级方案：尝试从历史消息中查找原附件，复用其 ID（用于后续查询云 URL）
      const found = findAttachmentByUrl(url, messages);

      if (found) {
        // 复用原附件的 ID 和其他信息
        newAttachment = {
          id: found.attachment.id,
          mimeType: found.attachment.mimeType || 'image/png',
          name: found.attachment.name || 'Reference Image',
          url: url, // ✅ 优先使用传入的 URL（无论是 Base64 还是 HTTP URL）（🚀 加速显示）
          tempUrl: found.attachment.tempUrl,
          uploadStatus: found.attachment.uploadStatus
        };

        // ✅ 优化：只有 HTTP URL 且 pending 时才查询，Base64 URL 直接使用（🔄 避免多次查询）
        // 查询目的：获取永久云存储 URL（如果上传已完成），用于后续 API 调用（🏗️ 有意设计）
        const shouldFetchCloudUrl = found.attachment.uploadStatus === 'pending' && 
                                     currentSessionId && 
                                     isHttpUrl(url);  // ✅ 只对 HTTP URL 查询

        if (shouldFetchCloudUrl) {
          // ✅ 异步查询，但不阻塞显示（🚀 加速显示）
          tryFetchCloudUrl(
            currentSessionId,
            found.attachment.id,
            found.attachment.url,
            found.attachment.uploadStatus
          ).then(cloudResult => {
            if (cloudResult) {
              // 可选：如果查询成功，可以更新 URL（但不影响初始显示）
              // 查询目的是获取永久云存储 URL，用于后续 API 调用
            }
          });
        }
      } else {
        // 未找到原附件，创建新附件
        newAttachment = {
          id: uuidv4(),
          mimeType: 'image/png',
          name: 'Reference Image',
          url: url  // ✅ 直接使用传入的 URL
        };
      }
    }

    // ✅ 立即设置，不等待查询（🚀 加速显示）
    setInitialAttachments([newAttachment]);
    setInitialPrompt("Make it look like...");
    if (activeModelConfig && !activeModelConfig.capabilities.vision) {
      const visionModel = visibleModels.find(m => m.capabilities.vision);
      if (visionModel) setCurrentModelId(visionModel.id);
    }
  }, [messages, currentSessionId, activeModelConfig, visibleModels, setCurrentModelId, setAppMode, setInitialAttachments, setInitialPrompt]);

  const handleExpandImage = useCallback(async (url: string, attachment?: Attachment) => {
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

    let newAttachment: Attachment;

    // ✅ 优先使用传入的 attachment 对象（如果提供），确保 attachmentId 被正确传递
    if (attachment && attachment.id) {
      // 直接使用传入的 attachment，确保 attachmentId 被保留
      newAttachment = {
        id: attachment.id,
        mimeType: attachment.mimeType || mimeType,
        name: attachment.name || `expand-source-${Date.now()}.${extension}`,
        url: url, // ✅ 优先使用传入的 URL（无论是 Base64 还是 HTTP URL）（🚀 加速显示）
        tempUrl: attachment.tempUrl,
        uploadStatus: attachment.uploadStatus,
        uploadTaskId: attachment.uploadTaskId
      };
    } else {
      // 降级方案：尝试从历史消息中查找原附件，复用其 ID（用于后续查询云 URL）
      const found = findAttachmentByUrl(url, messages);

      if (found) {
        // 复用原附件的 ID 和其他信息
        newAttachment = {
          id: found.attachment.id,
          mimeType: found.attachment.mimeType || mimeType,
          name: found.attachment.name || `expand-source-${Date.now()}.${extension}`,
          url: url, // ✅ 优先使用传入的 URL（无论是 Base64 还是 HTTP URL）（🚀 加速显示）
          tempUrl: found.attachment.tempUrl,
          uploadStatus: found.attachment.uploadStatus
        };

        // ✅ 优化：只有 HTTP URL 且 pending 时才查询，Base64 URL 直接使用（🔄 避免多次查询）
        // 查询目的：获取永久云存储 URL（如果上传已完成），用于后续 API 调用（🏗️ 有意设计）
        const shouldFetchCloudUrl = found.attachment.uploadStatus === 'pending' && 
                                     currentSessionId && 
                                     isHttpUrl(url);  // ✅ 只对 HTTP URL 查询

        if (shouldFetchCloudUrl) {
          // ✅ 异步查询，但不阻塞显示（🚀 加速显示）
          tryFetchCloudUrl(
            currentSessionId,
            found.attachment.id,
            found.attachment.url,
            found.attachment.uploadStatus
          ).then(cloudResult => {
            if (cloudResult) {
              // 可选：如果查询成功，可以更新 URL（但不影响初始显示）
              // 查询目的是获取永久云存储 URL，用于后续 API 调用
            }
          });
        }
      } else {
        // 未找到原附件，创建新附件
        newAttachment = {
          id: uuidv4(),
          mimeType: mimeType,
          name: `expand-source-${Date.now()}.${extension}`,
          url: url  // ✅ 直接使用传入的 URL
        };
      }
    }

    // ✅ 立即设置，不等待查询（🚀 加速显示）
    setInitialAttachments([newAttachment]);
    setInitialPrompt(undefined); // Clear prompt as outpainting often just needs settings
  }, [messages, currentSessionId, setAppMode, setInitialAttachments, setInitialPrompt]);

  return {
    handleEditImage,
    handleExpandImage
  };
};

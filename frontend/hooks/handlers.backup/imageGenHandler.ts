/**
 * 图片生成/编辑模式处理器
 * 处理 image-gen 和 image-edit 模式
 */
import { v4 as uuidv4 } from 'uuid';
import { Attachment, AppMode } from '../../../types';
import { llmService } from '../../services/llmService';
import { HandlerContext, HandlerResult, UploadToCloudStorageFn } from './types';

/**
 * 处理图片生成/编辑模式
 */
export const handleImageGen = async (
  text: string,
  attachments: Attachment[],
  mode: AppMode,
  context: HandlerContext,
  uploadToCloudStorage: UploadToCloudStorageFn
): Promise<HandlerResult> => {
  const results = await llmService.generateImage(text, attachments);
  
  // 构建结果数组，添加上传状态标记
  const resultArray: Attachment[] = results.map((res, index) => {
    const attachmentId = uuidv4();
    return {
      id: attachmentId,
      mimeType: res.mimeType,
      name: mode === 'image-edit' 
        ? `edited-${Date.now()}-${index + 1}.png` 
        : `generated-${Date.now()}-${index + 1}.png`,
      url: res.url,           // Base64 Data URL 用于立即显示
      tempUrl: res.url,       // 保留临时 URL
      uploadStatus: 'pending' as const
    };
  });
  
  const finalContent = mode === 'image-edit' 
    ? `Edited image with: "${text}"` 
    : `Generated images for: "${text}"`;
  
  // 异步上传原图到云存储（如果有 File 对象）
  for (const att of attachments) {
    if (att.file) {
      console.log('[imageGenHandler] 上传原图到云存储:', att.name);
      uploadToCloudStorage(
        att.file,
        context.userMessageId,
        att.id,
        context.sessionId,
        att.name
      );
    }
  }
  
  // 异步上传结果图到云存储（不阻塞 UI 显示）
  for (const att of resultArray) {
    console.log('[imageGenHandler] 上传结果图到云存储:', att.name);
    uploadToCloudStorage(
      att.url,
      context.modelMessageId,
      att.id,
      context.sessionId,
      att.name
    );
  }

  return {
    content: finalContent,
    attachments: resultArray
  };
};

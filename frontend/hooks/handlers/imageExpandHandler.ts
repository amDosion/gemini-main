/**
 * 图片扩展模式处理器
 * 处理 image-outpainting 模式
 */
import { v4 as uuidv4 } from 'uuid';
import { Attachment } from '../../../types';
import { llmService } from '../../services/llmService';
import { HandlerContext, HandlerResult, UploadToCloudStorageFn } from './types';
import { isCloudStorageUrl } from './attachmentUtils';

/**
 * 处理图片扩展模式
 */
export const handleImageExpand = async (
  attachments: Attachment[],
  context: HandlerContext,
  uploadToCloudStorage: UploadToCloudStorageFn
): Promise<HandlerResult> => {
  // 获取原图信息
  const originalAttachment = attachments[0];
  const originalAttachmentId = originalAttachment.id;
  const originalUrl = originalAttachment.url || '';
  const isOriginalCloudUrl = isCloudStorageUrl(originalUrl);
  
  console.log('[imageExpandHandler] 原图 URL:', originalUrl.substring(0, 60));
  console.log('[imageExpandHandler] 原图是否已是云存储 URL:', isOriginalCloudUrl);
  
  // 调用扩图 API
  const result = await llmService.outPaintImage(originalAttachment);
  
  // 下载结果图创建 Blob（用于立即显示 + 上传）
  // 只下载一次，避免后端重复下载
  const imageBlob = await fetch(result.url).then(r => r.blob());
  const blobUrl = URL.createObjectURL(imageBlob);
  const resultFilename = `expanded-${Date.now()}.png`;
  const resultFile = new File([imageBlob], resultFilename, { type: 'image/png' });
  
  const resultAttachmentId = uuidv4();
  const resultArray: Attachment[] = [{ 
    id: resultAttachmentId,
    mimeType: result.mimeType,
    name: resultFilename,
    url: blobUrl,      // Blob URL（用于显示）
    tempUrl: blobUrl,
    uploadStatus: 'pending'
  }];
  
  // 异步上传原图到云存储（仅当原图不是云存储 URL 时）
  if (!isOriginalCloudUrl && originalAttachment.file) {
    console.log('[imageExpandHandler] 上传原图到云存储:', {
      file: originalAttachment.file.name,
      userMessageId: context.userMessageId.substring(0, 8) + '...',
      originalAttachmentId: originalAttachmentId.substring(0, 8) + '...'
    });
    // ✅ 使用 await 确保原图任务先创建完成
    await uploadToCloudStorage(
      originalAttachment.file, 
      context.userMessageId, 
      originalAttachmentId, 
      context.sessionId,
      originalAttachment.name
    );
  } else if (isOriginalCloudUrl) {
    console.log('[imageExpandHandler] 原图已是云存储 URL，跳过上传');
  }
  
  // 异步上传结果图到云存储（传 File 对象，不传 URL）
  console.log('[imageExpandHandler] 上传结果图到云存储:', {
    file: resultFilename,
    modelMessageId: context.modelMessageId.substring(0, 8) + '...',
    resultAttachmentId: resultAttachmentId.substring(0, 8) + '...'
  });
  // ✅ 使用 await 确保结果图任务创建完成
  await uploadToCloudStorage(
    resultFile,
    context.modelMessageId, 
    resultAttachmentId, 
    context.sessionId,
    resultFilename
  );

  return {
    content: '扩展后的图片',
    attachments: resultArray
  };
};

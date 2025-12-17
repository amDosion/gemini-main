/**
 * 附件处理工具函数
 */
import { Attachment } from '../../../types';
import { storageUpload } from '../../services/storage/storageUpload';

/**
 * 将 Base64 Data URL 转换为 File 对象
 */
export const base64ToFile = async (base64: string, filename: string): Promise<File> => {
  const response = await fetch(base64);
  const blob = await response.blob();
  return new File([blob], filename, { type: blob.type });
};

/**
 * 清理附件用于数据库存储
 * - 保留云存储 URL（http/https）
 * - 清空 Blob URL 和 Base64 URL（这些是临时 URL，不应保存到数据库）
 * - 清除 File 对象和临时数据（不能序列化）
 * 
 * 注意：正常情况下，附件应该在保存前已经上传到云存储并获得云 URL。
 * 这个函数是最后的安全网，确保不会将临时 URL 保存到数据库。
 * 
 * @param atts 附件数组
 * @param verbose 是否输出详细日志（默认 false）
 */
export const cleanAttachmentsForDb = (atts: Attachment[], verbose: boolean = false): Attachment[] => {
  return atts.map(att => {
    const cleaned = { ...att };
    
    // 如果是云存储 URL，保持不变
    if (cleaned.url && (cleaned.url.startsWith('http://') || cleaned.url.startsWith('https://'))) {
      cleaned.uploadStatus = 'completed';
    }
    // 如果 url 是 Blob URL，设置为空字符串（不应该发生，但作为安全网）
    else if (cleaned.url && cleaned.url.startsWith('blob:')) {
      if (verbose) console.log('[cleanAttachmentsForDb] ⚠️ 发现 Blob URL，清空:', cleaned.url.substring(0, 50));
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    }
    // 如果 url 是 Base64 Data URL，也设置为空字符串（避免数据库存储过大）
    else if (cleaned.url && cleaned.url.startsWith('data:')) {
      if (verbose) console.log('[cleanAttachmentsForDb] ⚠️ 发现 Base64 URL，清空');
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    }
    
    // 清除 File 对象（不能序列化）
    delete cleaned.file;
    // 清除 tempUrl（临时 URL 不需要持久化）
    delete cleaned.tempUrl;
    // 清除 base64Data（仅用于 API 调用，不需要持久化到数据库）
    delete (cleaned as any).base64Data;
    return cleaned;
  });
};

/**
 * 同步上传图片到云存储（等待完成后返回 URL）
 * 
 * @param imageSource 图片来源（File 对象、Base64 URL 或 Blob URL）
 * @param filename 文件名（可选）
 * @returns 云存储 URL，上传失败返回空字符串
 */
export const uploadToCloudStorageSync = async (
  imageSource: string | File,
  filename?: string
): Promise<string> => {
  try {
    const isFile = imageSource instanceof File;
    const isBase64 = typeof imageSource === 'string' && imageSource.startsWith('data:');
    const isBlobUrl = typeof imageSource === 'string' && imageSource.startsWith('blob:');
    
    console.log('[uploadToCloudStorageSync] 开始同步上传:', {
      type: isFile ? 'File' : isBase64 ? 'Base64' : isBlobUrl ? 'Blob URL' : 'Unknown',
      filename: isFile ? (imageSource as File).name : filename
    });

    let file: File;

    if (isFile) {
      file = imageSource as File;
    } else if (isBase64) {
      file = await base64ToFile(imageSource as string, filename || `image-${Date.now()}.png`);
      console.log('[uploadToCloudStorageSync] Base64 已转换为 File:', file.name, file.size);
    } else if (isBlobUrl) {
      // Blob URL 需要先 fetch 再转换
      const response = await fetch(imageSource as string);
      const blob = await response.blob();
      file = new File([blob], filename || `image-${Date.now()}.png`, { type: blob.type });
      console.log('[uploadToCloudStorageSync] Blob URL 已转换为 File:', file.name, file.size);
    } else {
      throw new Error(`不支持的图片来源格式`);
    }

    // 同步上传，等待完成
    const result = await storageUpload.uploadFile(file);
    
    if (result.success && result.url) {
      console.log('[uploadToCloudStorageSync] 上传成功:', result.url);
      return result.url;
    } else {
      console.error('[uploadToCloudStorageSync] 上传失败:', result.error);
      return '';
    }

  } catch (error) {
    console.error('[uploadToCloudStorageSync] 上传失败:', error);
    return '';
  }
};

/**
 * 异步上传图片到云存储（不阻塞前端，用于后台更新数据库）
 * @deprecated 建议使用 uploadToCloudStorageSync 同步上传
 */
export const uploadToCloudStorage = async (
  imageSource: string | File,
  messageId: string,
  attachmentId: string,
  sessionId: string,
  filename?: string
): Promise<void> => {
  try {
    const isFile = imageSource instanceof File;
    const isBase64 = typeof imageSource === 'string' && imageSource.startsWith('data:');
    
    console.log('[uploadToCloudStorage] 提交异步上传任务:', {
      file: isFile ? (imageSource as File).name : isBase64 ? 'Base64' : 'Unknown',
      messageId: messageId.substring(0, 8) + '...',
      attachmentId: attachmentId.substring(0, 8) + '...',
      sessionId: sessionId.substring(0, 8) + '...'
    });

    let file: File;

    if (isFile) {
      file = imageSource as File;
    } else if (isBase64) {
      file = await base64ToFile(imageSource as string, filename || `image-${Date.now()}.png`);
      console.log('[uploadToCloudStorage] Base64 已转换为 File:', file.name, file.type, file.size);
    } else {
      throw new Error(`不支持的图片来源格式`);
    }

    // 提交到后端异步上传队列（不等待完成）
    const result = await storageUpload.uploadFileAsync(file, {
      sessionId,
      messageId,
      attachmentId
    });
    
    console.log('[uploadToCloudStorage] 异步上传任务已提交:', result.taskId);

  } catch (error) {
    console.error('[uploadToCloudStorage] 提交上传任务失败:', error);
  }
};

/**
 * 检查 URL 是否是云存储 URL
 */
export const isCloudStorageUrl = (url: string | undefined): boolean => {
  if (!url) return false;
  return url.startsWith('http://') || url.startsWith('https://');
};

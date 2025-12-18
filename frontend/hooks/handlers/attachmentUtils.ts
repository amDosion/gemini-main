/**
 * 附件处理工具函数
 * 
 * 附件状态说明：
 * - uploadStatus: 'completed' - 已上传到云存储，url 是云存储 URL
 * - uploadStatus: 'pending' - 待上传，url 可能是 Base64/Blob/临时 URL
 * - uploadStatus: 'failed' - 上传失败
 * 
 * URL 类型说明：
 * - 云存储 URL: 我们上传后返回的永久 URL（uploadStatus === 'completed'）
 * - Base64 URL: 内嵌数据 URL（data:image/png;base64,xxx）
 * - Blob URL: 浏览器本地 URL（blob:xxx，页面关闭后失效）
 * - 远程临时 URL: API 返回的临时 URL（会过期）
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
 * 检查附件是否已上传到云存储
 *
 * 判断依据：uploadStatus === 'completed'
 *
 * @param att 附件对象
 * @returns 是否已上传到云存储
 */
export const isUploadedToCloud = (att: Attachment): boolean => {
  return att.uploadStatus === 'completed' && !!att.url && isHttpUrl(att.url);
};

/**
 * 检查 URL 是否是 HTTP/HTTPS URL
 */
export const isHttpUrl = (url: string | undefined): boolean => {
  if (!url) return false;
  return url.startsWith('http://') || url.startsWith('https://');
};

/**
 * 检查 URL 是否是 Blob URL
 */
export const isBlobUrl = (url: string | undefined): boolean => {
  if (!url) return false;
  return url.startsWith('blob:');
};

/**
 * 检查 URL 是否是 Base64 Data URL
 */
export const isBase64Url = (url: string | undefined): boolean => {
  if (!url) return false;
  return url.startsWith('data:');
};

/**
 * 检查 URL 是否是云存储 URL（基于 uploadStatus）
 *
 * @deprecated 此函数已过时且易出错！请使用以下替代方案：
 * - 检查是否已上传：使用 isUploadedToCloud(att)
 * - 检查 URL 格式：使用 isHttpUrl(url)
 *
 * 此函数只检查 URL 格式，无法区分临时 URL 和云存储 URL。
 * 对于完整的云存储判断，应该使用 isUploadedToCloud(attachment)，
 * 因为它会同时检查 uploadStatus 和 URL 格式。
 */
export const isCloudStorageUrl = (url: string | undefined): boolean => {
  // 保持向后兼容：只检查是否是 HTTP URL
  // 真正的云存储判断应该结合 uploadStatus
  return isHttpUrl(url);
};

/**
 * 清理附件用于数据库存储
 * - 保留已上传的云存储 URL（uploadStatus === 'completed'）
 * - 清空 Blob URL 和 Base64 URL（这些是临时 URL，不应保存到数据库）
 * - 清除 File 对象和临时数据（不能序列化）
 * 
 * @param atts 附件数组
 * @param verbose 是否输出详细日志（默认 false）
 */
export const cleanAttachmentsForDb = (atts: Attachment[], verbose: boolean = false): Attachment[] => {
  return atts.map(att => {
    const cleaned = { ...att };
    const url = cleaned.url || '';
    
    // 如果已上传到云存储，保持不变
    if (cleaned.uploadStatus === 'completed' && isHttpUrl(url)) {
      // 已上传，保持不变
    }
    // 如果是 Blob URL，清空（不能持久化）
    else if (isBlobUrl(url)) {
      if (verbose) console.log('[cleanAttachmentsForDb] ⚠️ 发现 Blob URL，清空');
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    }
    // 如果是 Base64 URL，清空（避免数据库存储过大）
    else if (isBase64Url(url)) {
      if (verbose) console.log('[cleanAttachmentsForDb] ⚠️ 发现 Base64 URL，清空');
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    }
    // 其他 HTTP URL（可能是临时 URL），保留但标记为 pending
    else if (isHttpUrl(url) && cleaned.uploadStatus !== 'completed') {
      if (verbose) console.log('[cleanAttachmentsForDb] ⚠️ 发现未完成上传的 HTTP URL');
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
 * 支持的输入类型：
 * - File 对象：直接上传
 * - Base64 URL：转换为 File 后上传
 * - Blob URL：fetch 后转换为 File 上传
 * - HTTP URL（临时 URL）：下载后上传
 * 
 * 注意：调用方应该先检查 uploadStatus，如果已经是 'completed' 则无需调用此函数
 * 
 * @param imageSource 图片来源
 * @param filename 文件名（可选）
 * @returns 云存储 URL，上传失败返回空字符串
 */
export const uploadToCloudStorageSync = async (
  imageSource: string | File,
  filename?: string
): Promise<string> => {
  try {
    // 1. 判断输入类型
    const isFile = imageSource instanceof File;
    const sourceUrl = typeof imageSource === 'string' ? imageSource : '';
    
    const urlType = isFile ? 'File' : 
                    isBase64Url(sourceUrl) ? 'Base64' :
                    isBlobUrl(sourceUrl) ? 'Blob URL' :
                    isHttpUrl(sourceUrl) ? 'HTTP URL' : 'Unknown';
    
    console.log('[uploadToCloudStorageSync] 开始处理:', {
      type: urlType,
      filename: isFile ? (imageSource as File).name : filename
    });

    // 2. 转换为 File 对象
    let file: File;

    if (isFile) {
      file = imageSource as File;
    } 
    else if (isBase64Url(sourceUrl)) {
      file = await base64ToFile(sourceUrl, filename || `image-${Date.now()}.png`);
      console.log('[uploadToCloudStorageSync] Base64 已转换为 File:', file.name, file.size);
    } 
    else if (isBlobUrl(sourceUrl)) {
      const response = await fetch(sourceUrl);
      const blob = await response.blob();
      file = new File([blob], filename || `image-${Date.now()}.png`, { type: blob.type });
      console.log('[uploadToCloudStorageSync] Blob URL 已转换为 File:', file.name, file.size);
    } 
    else if (isHttpUrl(sourceUrl)) {
      // HTTP URL（包括临时 URL 和云存储 URL）- 下载后上传
      console.log('[uploadToCloudStorageSync] 下载远程图片...');
      // 使用后端代理下载图片（解决 CORS 问题）
      const proxyUrl = `/api/storage/download?url=${encodeURIComponent(sourceUrl)}`;
      const response = await fetch(proxyUrl);
      if (!response.ok) {
        throw new Error(`下载远程图片失败: HTTP ${response.status}`);
      }
      const blob = await response.blob();
      file = new File([blob], filename || `image-${Date.now()}.png`, { type: blob.type || 'image/png' });
      console.log('[uploadToCloudStorageSync] 远程图片已下载（通过后端代理）:', file.name, file.size);
    } 
    else {
      throw new Error(`不支持的图片来源格式: ${sourceUrl.substring(0, 30)}...`);
    }

    // 3. 上传到云存储
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
    const sourceUrl = typeof imageSource === 'string' ? imageSource : '';
    
    console.log('[uploadToCloudStorage] 提交异步上传任务:', {
      type: isFile ? 'File' : isBase64Url(sourceUrl) ? 'Base64' : isBlobUrl(sourceUrl) ? 'Blob URL' : 'Unknown',
      messageId: messageId.substring(0, 8) + '...',
      attachmentId: attachmentId.substring(0, 8) + '...',
      sessionId: sessionId.substring(0, 8) + '...'
    });

    let file: File;

    if (isFile) {
      file = imageSource as File;
    } else if (isBase64Url(sourceUrl)) {
      file = await base64ToFile(sourceUrl, filename || `image-${Date.now()}.png`);
      console.log('[uploadToCloudStorage] Base64 已转换为 File:', file.name, file.type, file.size);
    } else if (isBlobUrl(sourceUrl)) {
      const response = await fetch(sourceUrl);
      const blob = await response.blob();
      file = new File([blob], filename || `image-${Date.now()}.png`, { type: blob.type });
      console.log('[uploadToCloudStorage] Blob URL 已转换为 File:', file.name, file.size);
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

/**
 * 图片编辑模式处理器
 * 处理 image-edit 模式
 * 
 * 优化策略（Redis 队列异步上传）：
 * 1. 预处理原图：优先使用本地数据（base64Data/file/blob），只有都没有时才下载
 * 2. 处理结果图：下载远程图片创建本地 Blob URL（用于立即显示）
 * 3. 立即返回显示用附件，不阻塞 UI
 * 4. 提交上传任务到 Redis 队列（不等待上传完成）
 * 5. Worker 池在后台处理上传，完成后自动更新数据库
 */
import { v4 as uuidv4 } from 'uuid';
import { Attachment } from '../../../types';
import { llmService } from '../../services/llmService';
import { HandlerContext, HandlerResult } from './types';
import { isHttpUrl, isUploadedToCloud } from './attachmentUtils';
import { storageUpload } from '../../services/storage/storageUpload';

/**
 * 处理后的附件（内部使用，带有原始云 URL 标记）
 */
interface ProcessedAttachment extends Attachment {
  originalCloudUrl?: string;  // 原始云存储 URL（用于复用，避免重复上传）
}

/**
 * 图片编辑结果类型
 */
export interface ImageEditResult extends HandlerResult {
  dbAttachments?: Attachment[];
  dbUserAttachments?: Attachment[];
  /** 上传任务 Promise，调用方可选择 await 或让其后台执行 */
  uploadTask?: Promise<{ dbAttachments: Attachment[]; dbUserAttachments?: Attachment[] }>;
}

/**
 * 处理图片编辑模式
 */
export const handleImageEdit = async (
  text: string,
  attachments: Attachment[],
  context: HandlerContext
): Promise<ImageEditResult> => {
  // 0. 预处理原图：优先使用本地数据（base64Data/file/blob），只有都没有时才下载
  console.log(`[imageEditHandler] 预处理 ${attachments.length} 张原图`);
  const processedAttachments: ProcessedAttachment[] = await Promise.all(attachments.map(async (att) => {
    const attUrl = att.url || '';
    const base64Data = (att as any).base64Data as string | undefined;

    // 优先级 1：已有 file 对象，直接使用
    if (att.file) {
      console.log(`[imageEditHandler] 已有 File 对象，直接使用: ${att.name}`);
      const isAlreadyUploaded = isUploadedToCloud(att);
      return {
        ...att,
        originalCloudUrl: isAlreadyUploaded ? attUrl : undefined
      };
    }

    // 优先级 2：已有 base64Data，转换为 File 对象（无需下载）
    if (base64Data && base64Data.startsWith('data:')) {
      console.log(`[imageEditHandler] 已有 Base64 数据，直接转换为 File（无需下载）`);
      try {
        const response = await fetch(base64Data);
        const blob = await response.blob();
        const file = new File([blob], att.name || 'reference.png', {
          type: blob.type || 'image/png'
        });
        console.log(`[imageEditHandler] Base64 转 File 完成，大小: ${file.size} bytes`);
        const isAlreadyUploaded = isUploadedToCloud(att);
        return {
          ...att,
          file,
          originalCloudUrl: isAlreadyUploaded ? attUrl : undefined
        };
      } catch (error) {
        console.error('[imageEditHandler] Base64 转 File 失败:', error);
      }
    }

    // 优先级 3：url 是 Base64，转换为 File 对象（无需下载）
    if (attUrl.startsWith('data:')) {
      console.log(`[imageEditHandler] URL 是 Base64，直接转换为 File（无需下载）`);
      try {
        const response = await fetch(attUrl);
        const blob = await response.blob();
        const file = new File([blob], att.name || 'reference.png', {
          type: blob.type || 'image/png'
        });
        console.log(`[imageEditHandler] Base64 URL 转 File 完成，大小: ${file.size} bytes`);
        return { ...att, file };
      } catch (error) {
        console.error('[imageEditHandler] Base64 URL 转 File 失败:', error);
      }
    }

    // 优先级 4：url 是 Blob URL，转换为 File 对象（无需下载）
    if (attUrl.startsWith('blob:')) {
      console.log(`[imageEditHandler] URL 是 Blob，直接转换为 File（无需下载）`);
      try {
        const response = await fetch(attUrl);
        const blob = await response.blob();
        const file = new File([blob], att.name || 'reference.png', {
          type: blob.type || 'image/png'
        });
        console.log(`[imageEditHandler] Blob URL 转 File 完成，大小: ${file.size} bytes`);
        return { ...att, file };
      } catch (error) {
        console.error('[imageEditHandler] Blob URL 转 File 失败:', error);
      }
    }

    // 优先级 5：url 是 HTTP URL，需要通过后端代理下载
    if (isHttpUrl(attUrl)) {
      const isAlreadyUploaded = isUploadedToCloud(att);
      console.log(`[imageEditHandler] 无本地数据，需要从云存储下载: ${attUrl.substring(0, 60)}`);
      try {
        const proxyUrl = `/api/storage/download?url=${encodeURIComponent(attUrl)}`;
        const response = await fetch(proxyUrl);
        const blob = await response.blob();
        const file = new File([blob], att.name || 'reference.png', {
          type: blob.type || 'image/png'
        });
        console.log(`[imageEditHandler] 图片已下载（通过后端代理），大小: ${file.size} bytes`);
        return {
          ...att,
          file,
          originalCloudUrl: isAlreadyUploaded ? attUrl : undefined
        };
      } catch (error) {
        console.error('[imageEditHandler] 下载图片失败:', error);
        return att;
      }
    }

    // 兜底：无法处理，保持原样
    console.warn(`[imageEditHandler] 无法处理附件，保持原样: ${att.name}`);
    return att;
  }));

  // 1. 调用 API 编辑图片（使用处理后的附件）
  const results = await llmService.generateImage(text, processedAttachments);

  // 2. 处理所有结果图（下载远程图片，创建本地显示 URL）
  const processedResults = await Promise.all(results.map(async (res, index) => {
    const attachmentId = uuidv4();
    const filename = `edited-${Date.now()}-${index + 1}.png`;

    let displayUrl = res.url;
    let uploadSource: string | File = res.url;

    // 处理远程临时 URL（如 DashScope 临时链接）
    if (res.url.startsWith('http://') || res.url.startsWith('https://')) {
      console.log(`[imageEditHandler] 检测到远程 URL，下载中...`);
      const proxyUrl = `/api/storage/download?url=${encodeURIComponent(res.url)}`;
      const response = await fetch(proxyUrl);
      const blob = await response.blob();
      displayUrl = URL.createObjectURL(blob);
      uploadSource = new File([blob], filename, { type: blob.type || 'image/png' });
    }

    return {
      id: attachmentId,
      filename,
      displayUrl,
      uploadSource,
      mimeType: res.mimeType
    };
  }));

  console.log(`[imageEditHandler] ${processedResults.length} 张结果图已准备好显示`);

  // 3. 构建显示用附件（本地 URL，立即返回给 UI）
  const displayAttachments: Attachment[] = processedResults.map((r) => ({
    id: r.id,
    mimeType: r.mimeType,
    name: r.filename,
    url: r.displayUrl,
    uploadStatus: 'pending' as const
  }));

  // 4. 构建最终内容文本
  const finalContent = `Edited image with: "${text}"`;


  // 5. 提交上传任务到 Redis 队列（不阻塞，不等待）
  const uploadTask = async (): Promise<{ dbAttachments: Attachment[]; dbUserAttachments?: Attachment[] }> => {
    console.log(`[imageEditHandler] 提交 ${processedResults.length} 张结果图到 Redis 上传队列`);

    // ========== 结果图：提交到 Redis 队列 ==========
    const resultUploadPromises = processedResults.map(async (r) => {
      try {
        // 确保 uploadSource 是 File 对象
        let file: File;
        if (r.uploadSource instanceof File) {
          file = r.uploadSource;
        } else if (typeof r.uploadSource === 'string') {
          const response = await fetch(r.uploadSource);
          const blob = await response.blob();
          file = new File([blob], r.filename, { type: blob.type || 'image/png' });
        } else {
          throw new Error('Invalid upload source type');
        }

        // 调用异步上传 API（提交到 Redis 队列）
        const result = await storageUpload.uploadFileAsync(file, {
          sessionId: context.sessionId,
          messageId: context.modelMessageId,
          attachmentId: r.id
        });

        console.log(`[imageEditHandler] 结果图 ${r.filename} 已提交到队列，任务ID: ${result.taskId}`);

        return {
          id: r.id,
          taskId: result.taskId,
          filename: r.filename,
          mimeType: r.mimeType
        };
      } catch (error) {
        console.error(`[imageEditHandler] 提交结果图上传任务失败 (${r.filename}):`, error);
        return {
          id: r.id,
          taskId: null,
          filename: r.filename,
          mimeType: r.mimeType,
          error: error instanceof Error ? error.message : '提交失败'
        };
      }
    });

    const resultUploadResults = await Promise.all(resultUploadPromises);

    // 构建临时的数据库附件（包含任务ID，实际 URL 由 Worker 更新）
    const dbAttachments: Attachment[] = resultUploadResults.map((result) => ({
      id: result.id,
      mimeType: result.mimeType,
      name: result.filename,
      url: '', // URL 将由 Worker 池上传完成后更新
      uploadStatus: result.taskId ? 'pending' : 'failed',
      uploadTaskId: result.taskId || undefined,
      uploadError: (result as any).error
    }));

    console.log(`[imageEditHandler] 所有结果图已提交到 Redis 队列`);

    // ========== 原图：复用云 URL 或提交到 Redis 队列 ==========
    console.log(`[imageEditHandler] 处理 ${processedAttachments.length} 张原图上传`);

    const userUploadPromises = processedAttachments.map(async (att) => {
      // 优先检查 originalCloudUrl（预处理时标记的原始云 URL）
      if (att.originalCloudUrl) {
        console.log(`[imageEditHandler] 复用原始云存储 URL: ${att.originalCloudUrl.substring(0, 60)}`);
        return {
          ...att,
          url: att.originalCloudUrl,
          uploadStatus: 'completed' as const
        };
      }

      // 检查是否已上传到云存储（基于 uploadStatus）
      if (isUploadedToCloud(att)) {
        console.log(`[imageEditHandler] 原图已上传到云存储，直接复用: ${(att.url || '').substring(0, 60)}`);
        return { ...att };
      }

      // 需要上传：提交到 Redis 队列
      const uploadSource = att.file;
      if (!uploadSource) {
        console.warn(`[imageEditHandler] 原图无可用上传源，跳过`);
        return { ...att, url: '', uploadStatus: 'failed' as const };
      }

      try {
        const result = await storageUpload.uploadFileAsync(uploadSource, {
          sessionId: context.sessionId,
          messageId: context.userMessageId,
          attachmentId: att.id
        });

        console.log(`[imageEditHandler] 原图 ${att.name} 已提交到队列，任务ID: ${result.taskId}`);

        return {
          ...att,
          url: '', // URL 将由 Worker 池上传完成后更新
          uploadStatus: 'pending' as const,
          uploadTaskId: result.taskId
        };
      } catch (error) {
        console.error(`[imageEditHandler] 提交原图上传任务失败 (${att.name}):`, error);
        return {
          ...att,
          url: '',
          uploadStatus: 'failed' as const,
          uploadError: error instanceof Error ? error.message : '提交失败'
        };
      }
    });

    const dbUserAttachments = await Promise.all(userUploadPromises);
    console.log(`[imageEditHandler] 所有原图已处理，Worker 池将在后台处理上传`);

    return { dbAttachments, dbUserAttachments };
  };

  // 6. 立即返回显示用附件，上传任务在后台通过 Redis 队列处理
  return {
    content: finalContent,
    attachments: displayAttachments,
    uploadTask: uploadTask()  // 启动提交任务但不阻塞返回
  };
};

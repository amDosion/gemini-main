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
import { reportError } from '../../utils/globalErrorHandler';
import { v4 as uuidv4 } from 'uuid';
import { Attachment, Message } from '../../types/types';
import { storageUpload } from '../../services/storage/storageUpload';
import { getAccessToken } from '../../services/apiClient';

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
  // 1. Input Validation: Add early return for undefined, null, or non-array inputs.
  if (!atts || !Array.isArray(atts)) {
    return [];
  }

  return atts.map(att => {
    const cleaned = { ...att };
    const url = cleaned.url || '';

    // Blob URL：临时 URL，不能持久化
    if (isBlobUrl(url)) {
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    } 
    // Base64 URL：数据太大，不能保存到数据库
    else if (isBase64Url(url)) {
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    } 
    // HTTP URL：根据状态和特征判断
    else if (isHttpUrl(url)) {
      // 已上传完成：保留云存储 URL
      if (cleaned.uploadStatus === 'completed') {
      }
      // 有上传任务：保留 URL，状态设为 pending
      else if ((cleaned as any).uploadTaskId) {
        cleaned.uploadStatus = 'pending';
      }
      // 临时 URL：清空
      else if (url.includes('/temp/') || url.includes('expires=')) {
        cleaned.url = '';
        cleaned.uploadStatus = 'pending';
      }
      // 其他 HTTP URL：保留但标记为 pending
      else {
        cleaned.uploadStatus = 'pending';
      }
    }

    // Always remove non-serializable File objects and temporary base64 data.
    delete cleaned.file;
    delete (cleaned as any).base64Data;
    
    // tempUrl 清理：只保留有效的非临时 HTTP URL
    // 如果有上传任务，保留 tempUrl（上传中）
    if (cleaned.tempUrl) {
      const isTemporary = !isHttpUrl(cleaned.tempUrl) || 
                         cleaned.tempUrl.includes('/temp/') || 
                         cleaned.tempUrl.includes('expires=');
      
      if (isTemporary && !(cleaned as any).uploadTaskId) {
        delete cleaned.tempUrl;
      }
    }
    
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
    const finalFilename = filename || `image-${Date.now()}.png`;
    
    // 判断输入类型（用于日志）
    const isFile = imageSource instanceof File;
    const sourceUrl = typeof imageSource === 'string' ? imageSource : '';
    const urlType = isFile ? 'File' : 
                    isBase64Url(sourceUrl) ? 'Base64' :
                    isBlobUrl(sourceUrl) ? 'Blob URL' :
                    isHttpUrl(sourceUrl) ? 'HTTP URL' : 'Unknown';
    

    // 使用统一函数转换为 File
    const file = await sourceToFile(imageSource, finalFilename);

    // 上传到云存储
    const result = await storageUpload.uploadFile(file);
    
    if (result.success && result.url) {
      return result.url;
    } else {
      return '';
    }

  } catch (error) {
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
    const finalFilename = filename || `image-${Date.now()}.png`;
    const isFile = imageSource instanceof File;
    const sourceUrl = typeof imageSource === 'string' ? imageSource : '';
    

    // 使用统一函数转换为 File
    const file = await sourceToFile(imageSource, finalFilename);

    // 提交到后端异步上传队列（不等待完成）
    const result = await storageUpload.uploadFileAsync(file, {
      sessionId,
      messageId,
      attachmentId
    });
    

  } catch (err) {
    reportError('附件上传失败', err);
  }
};


// ============================================================
// URL 类型检测与转换工具函数
// ============================================================

/**
 * 将任意来源转换为 File 对象
 * 
 * 支持的输入类型：
 * - File 对象：直接返回
 * - Base64/Blob URL：通过 urlToFile 转换
 * - HTTP URL：使用降级策略下载
 * 
 * HTTP URL 降级策略（按优先级）：
 * 1. 后端代理下载（解决 CORS 问题）
 * 2. 直接下载（绕过代理，适用于同源或允许 CORS 的资源）
 * 3. 使用 urlToFile（最后的备选方案）
 * 
 * @param source 图片来源（File 对象或 URL 字符串）
 * @param filename 目标文件名
 * @param mimeType 可选的 MIME 类型
 * @returns File 对象
 * @throws 如果所有策略都失败，抛出错误
 */
export const sourceToFile = async (
  source: string | File,
  filename: string,
  mimeType?: string
): Promise<File> => {
  // File 对象直接返回
  if (source instanceof File) {
    return source;
  }

  const url = source;

  // 非 HTTP URL（Base64、Blob）直接转换
  if (!isHttpUrl(url)) {
    return await urlToFile(url, filename, mimeType);
  }

  // HTTP URL 使用降级策略
  const strategies = [
    {
      name: '后端代理下载',
      execute: async () => {
        const proxyUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
        const response = await fetch(proxyUrl);
        if (!response.ok) {
          throw new Error(`Proxy failed: HTTP ${response.status}`);
        }
        const blob = await response.blob();
        return new File([blob], filename, { type: mimeType || blob.type || 'image/png' });
      }
    },
    {
      name: '直接下载',
      execute: async () => {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Direct download failed: HTTP ${response.status}`);
        }
        const blob = await response.blob();
        return new File([blob], filename, { type: mimeType || blob.type || 'image/png' });
      }
    },
    {
      name: 'urlToFile 函数',
      execute: async () => {
        return await urlToFile(url, filename, mimeType);
      }
    }
  ];

  // 依次尝试每个策略
  for (let i = 0; i < strategies.length; i++) {
    try {
      const file = await strategies[i].execute();
      return file;
    } catch (error) {
      // 最后一个策略失败时，抛出错误
      if (i === strategies.length - 1) {
        throw new Error(`[sourceToFile] 所有下载策略都失败，URL: ${url.substring(0, 100)}...`);
      }
    }
  }

  // 理论上不会到达这里
  throw new Error(`[sourceToFile] 未知错误`);
};

/**
 * 尝试从后端获取云存储 URL
 * 
 * 功能说明：
 * - 用于 CONTINUITY LOGIC：当本地 URL 不是云存储 URL 时，查询后端获取永久 URL
 * - Base64/Blob URL 直接使用，不查询后端（本地数据无需查询）
 * - 只有 HTTP URL 且状态为 pending 时才查询（避免不必要的请求）
 * 
 * 返回值说明：
 * - 返回的 URL 是永久性的云存储 URL
 * - 调用方应将返回的 URL 保存到附件的 `url` 字段（而非 `tempUrl`）
 * 
 * @param sessionId 会话 ID
 * @param attachmentId 附件 ID
 * @param currentUrl 当前 URL
 * @param currentStatus 当前上传状态
 * @returns 包含永久云存储 URL 和状态的对象，如果无法获取则返回 null
 */
export const tryFetchCloudUrl = async (
  sessionId: string | null,
  attachmentId: string,
  currentUrl: string | undefined,
  currentStatus: string | undefined
): Promise<{ url: string; uploadStatus: string } | null> => {
  // Base64/Blob URL 直接使用，不查询后端
  if (currentUrl) {
    if (isBase64Url(currentUrl) || isBlobUrl(currentUrl)) {
      return null;
    }
  }

  // 只有 HTTP URL 且状态为 pending 时才查询
  const needFetch = sessionId && 
                   currentStatus === 'pending' && 
                   isHttpUrl(currentUrl);

  if (!needFetch) {
    return null;
  }

  const backendData = await fetchAttachmentStatus(sessionId, attachmentId);

  // 验证返回的是有效的云存储 URL
  if (backendData && isHttpUrl(backendData.url) && backendData.uploadStatus === 'completed') {
    return {
      url: backendData.url,
      uploadStatus: 'completed'
    };
  }

  return null;
};

// ============================================================
// URL 转换工具函数
// ============================================================

/**
 * 将任意 URL 转换为 Base64 Data URL
 * 
 * 支持的输入类型：
 * - Base64 URL：直接返回
 * - Blob URL：fetch 后转换为 Base64
 * - HTTP URL：通过后端代理下载后转换为 Base64（解决 CORS）
 * 
 * @param url 源 URL
 * @returns Base64 Data URL
 * @throws 如果 URL 无效或 MIME 类型不支持（仅支持图片类型）
 */
export const urlToBase64 = async (url: string): Promise<string> => {
  if (isBase64Url(url)) {
    return url;
  }

  // HTTP URL 需要通过后端代理下载（解决 CORS）
  let fetchUrl = url;
  if (isHttpUrl(url)) {
    fetchUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
  }

  const response = await fetch(fetchUrl);
  if (!response.ok) {
    throw new Error(`Failed to fetch from ${url}. HTTP status: ${response.status}`);
  }
  
  const blob = await response.blob();

  // 验证 MIME 类型（仅支持图片）
  if (!blob.type) {
  } else if (!blob.type.startsWith('image/')) {
    throw new Error(`[urlToBase64] Unsupported MIME type: ${blob.type}. Only image types are supported.`);
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = (error) => reject(new Error(`[urlToBase64] FileReader failed: ${error}`));
    reader.readAsDataURL(blob);
  });
};

/**
 * 将 File 对象转换为 Base64 Data URL
 * 
 * 特点：
 * - 不依赖 Blob URL，避免因 URL.revokeObjectURL 导致读取失败
 * - 直接使用 FileReader 读取文件内容
 * 
 * @param file File 对象
 * @returns Base64 Data URL
 * @throws 如果 file 为空或读取失败
 */
export const fileToBase64 = async (file: File): Promise<string> => {
  if (!file) {
    throw new Error('[fileToBase64] File is required');
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = (error) => reject(new Error(`[fileToBase64] FileReader failed: ${error}`));
    reader.readAsDataURL(file);
  });
};

/**
 * 将任意 URL 转换为 File 对象
 * 
 * 支持的输入类型：
 * - Base64 URL：fetch 后转换为 File
 * - Blob URL：fetch 后转换为 File
 * - HTTP URL：通过后端代理下载后转换为 File（解决 CORS）
 * 
 * @param url 源 URL
 * @param filename 目标文件名
 * @param mimeType 可选的 MIME 类型
 * @returns File 对象
 * @throws 如果 filename 为空或下载失败
 */
export const urlToFile = async (
  url: string, 
  filename: string, 
  mimeType?: string
): Promise<File> => {
  if (!filename || filename.trim() === '') {
    throw new Error('[urlToFile] Filename cannot be empty');
  }

  // HTTP URL 需要通过后端代理下载（解决 CORS）
  let fetchUrl = url;
  if (isHttpUrl(url)) {
    fetchUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
  }
  
  const response = await fetch(fetchUrl);
  if (!response.ok) {
    throw new Error(`Failed to fetch from ${url}. HTTP status: ${response.status}`);
  }

  const blob = await response.blob();
  if (!blob.type) {
  }

  return new File([blob], filename, { type: mimeType || blob.type || 'image/png' });
};

// ============================================================
// 附件查找与状态查询
// ============================================================

/**
 * 从消息历史中查找匹配 URL 的附件
 * 
 * 功能说明：
 * - 用于 CONTINUITY LOGIC：复用已有附件信息，避免重复上传
 * - 从最新消息开始反向查找，提高查找效率
 * 
 * 匹配策略（按优先级）：
 * 1. 精确匹配：匹配 url 或 tempUrl 字段
 * 2. 兜底策略：对于 Blob URL，如果未精确匹配，查找最近的有效云端图片附件
 * 
 * 注意：此函数只负责在内存中查找，云存储 URL 需要通过 fetchAttachmentStatus 从后端获取
 * 
 * @param targetUrl 目标 URL
 * @param messages 消息历史
 * @returns 匹配的附件和消息 ID，未找到返回 null
 */
export const findAttachmentByUrl = (
  targetUrl: string,
  messages: Message[]
): { attachment: Attachment; messageId: string } | null => {
  if (!targetUrl) {
    return null;
  }

  const urlType = isBase64Url(targetUrl) ? 'Base64' :
                  isBlobUrl(targetUrl) ? 'Blob' :
                  isHttpUrl(targetUrl) ? 'HTTP' : '未知';
  
  
  // 策略 1: 精确匹配 url 或 tempUrl
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    for (const att of msg.attachments || []) {
      if (att.url === targetUrl || att.tempUrl === targetUrl) {
        return { attachment: att, messageId: msg.id };
      }
    }
  }
  
  // 策略 2: Blob URL 兜底策略 - 查找最近的有效云端图片附件
  if (isBlobUrl(targetUrl)) {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      for (const att of msg.attachments || []) {
        // 只返回有效的、已上传的云端图片附件
        if (
          att.mimeType?.startsWith('image/') &&
          att.id &&
          att.uploadStatus === 'completed' &&
          isHttpUrl(att.url)
        ) {
          return { attachment: att, messageId: msg.id };
        }
      }
    }
  }
  
  return null;
};

/**
 * 从后端查询附件的最新状态（包括云存储 URL）
 * 
 * 功能说明：
 * - 用于获取 pending 状态附件的最新云存储 URL
 * - 调用后端 API: /api/attachments/{attachmentId}/cloud-url
 * 
 * @param sessionId 会话 ID
 * @param attachmentId 附件 ID
 * @returns 附件状态信息（url, uploadStatus, taskId, taskStatus），查询失败返回 null
 */
export const fetchAttachmentStatus = async (
  sessionId: string, 
  attachmentId: string
): Promise<{ url: string; uploadStatus: string; taskId?: string; taskStatus?: string } | null> => {
  try {
    const headers: HeadersInit = {};
    const token = getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(`/api/attachments/${attachmentId}/cloud-url`, {
      headers,
    });
    
    if (!response.ok) {
      return null;
    }
    
    return await response.json();
  } catch (error) {
    return null;
  }
};

// ============================================================
// CONTINUITY LOGIC 统一函数
// ============================================================

/**
 * 准备附件供 API 调用（CONTINUITY LOGIC 核心函数）
 * 
 * 功能说明：
 * - 当用户没有上传新附件时，从画布图片（activeImageUrl）中查找或创建附件
 * - 支持复用历史附件，避免重复上传
 * - 优先使用后端 CONTINUITY API，降级到前端查找
 * 
 * URL 字段语义：
 * - `url`: 存储最持久、最权威的资源位置（云存储 URL 或 HTTP URL）
 * - `tempUrl`: 存储临时 URL（Base64、Blob URL）用于查找匹配
 * 
 * 处理流程：
 * 1. 优先调用后端 CONTINUITY API 解析附件
 * 2. 降级到前端查找历史消息中的匹配附件
 * 3. 如果都未找到，根据 URL 类型创建新附件
 * 
 * @param imageUrl 当前画布上的图片 URL
 * @param messages 消息历史（用于查找匹配附件）
 * @param sessionId 当前会话 ID（用于后端 API 调用）
 * @param filePrefix 文件名前缀（如 'canvas', 'expand'）
 * @param skipBase64 是否跳过 base64Data 获取（默认 true，后端会处理）
 * @returns 准备好的 Attachment 对象，失败返回 null
 */
export const prepareAttachmentForApi = async (
  imageUrl: string,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas',
  skipBase64: boolean = true
): Promise<Attachment | null> => {
  const urlType = isBase64Url(imageUrl) ? 'Base64' : isBlobUrl(imageUrl) ? 'Blob' : 'HTTP';
  const urlLength = imageUrl?.length || 0;
  
  // 提取 Base64 的 MIME 类型
  let base64MimeType = 'unknown';
  if (urlType === 'Base64') {
    const mimeMatch = imageUrl.match(/^data:([^;]+);/);
    base64MimeType = mimeMatch ? mimeMatch[1] : 'unknown';
  }
  
  
  // 打印消息历史中的附件信息
  if (messages && messages.length > 0) {
    const messagesWithAttachments = messages.filter(m => m.attachments && m.attachments.length > 0);
    
    // 打印最近3条有附件的消息
    const recentWithAttachments = messagesWithAttachments.slice(-3);
    recentWithAttachments.forEach((msg, idx) => {
    });
  }

  try {
    // 步骤 1: 优先使用后端 CONTINUITY API
    if (sessionId) {
      
      try {
        const headers: HeadersInit = {
          'Content-Type': 'application/json'
        };
        const token = getAccessToken();
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        

        // 构建请求体 - 只发送必要的消息信息，不发送完整的 Base64 数据
        const simplifiedMessages = messages?.map(m => ({
          id: m.id,
          role: m.role,
          attachments: m.attachments?.map(att => ({
            id: att.id,
            url: att.url,
            tempUrl: att.tempUrl,
            uploadStatus: att.uploadStatus,
            mimeType: att.mimeType
          }))
        })) || [];

        const requestBody = {
          activeImageUrl: imageUrl,
          sessionId: sessionId,
          messages: simplifiedMessages
        };
        

        const response = await fetch('/api/attachments/resolve-continuity', {
          method: 'POST',
          headers,
          body: JSON.stringify(requestBody)
        });


        if (response.ok) {
          const resolved = await response.json();
          const hasCloudUrl = resolved.status === 'completed' && resolved.url && isHttpUrl(resolved.url);
          

          const attachment: Attachment = {
            id: resolved.attachmentId,
            mimeType: resolved.mimeType || 'image/png',
            name: resolved.filename || `${filePrefix}-${Date.now()}.png`,
            url: resolved.url,
            uploadStatus: resolved.status as 'pending' | 'uploading' | 'completed' | 'failed',
            uploadTaskId: resolved.taskId,
            // ✅ 新增：保存后端返回的完整元数据
            messageId: resolved.messageId,
            sessionId: resolved.sessionId,
            userId: resolved.userId,
            size: resolved.size,
            cloudUrl: resolved.cloudUrl,
            createdAt: resolved.createdAt
          };

          return attachment;
        } else {
          // 尝试读取错误响应体
          let errorBody = '';
          try {
            errorBody = await response.text();
          } catch (e) {
            errorBody = '无法读取错误响应体';
          }
        }
      } catch (err) {
        reportError('图片重新加载失败', err);
      }
    }

    // 步骤 2: 降级方案 - 前端查找历史附件
    const found = findAttachmentByUrl(imageUrl, messages);

    if (found) {
      const { attachment: existingAttachment, messageId } = found;
      
      
      let finalUrl = existingAttachment.url;
      let finalUploadStatus = existingAttachment.uploadStatus || 'pending';

      // 查询后端获取最新的云存储 URL
      const cloudResult = await tryFetchCloudUrl(
        sessionId,
        existingAttachment.id,
        finalUrl,
        finalUploadStatus
      );
      
      if (cloudResult) {
        finalUrl = cloudResult.url;
        finalUploadStatus = 'completed';
      } else {
      }

      const attachment: Attachment = {
        id: existingAttachment.id,  // ✅ 复用原始附件 ID，避免重复上传
        mimeType: existingAttachment.mimeType || 'image/png',
        name: existingAttachment.name || `${filePrefix}-${Date.now()}.png`,
        url: finalUrl,
        uploadStatus: finalUploadStatus as 'pending' | 'uploading' | 'completed' | 'failed',
        // ✅ 复用原始附件的元数据
        messageId: existingAttachment.messageId,
        sessionId: existingAttachment.sessionId,
        userId: existingAttachment.userId,
        size: existingAttachment.size,
        cloudUrl: existingAttachment.cloudUrl,
        createdAt: existingAttachment.createdAt,
      };
      

      // 对于非 HTTP URL，可选转换为 Base64（如果 skipBase64 为 false）
      if (!skipBase64 && finalUrl && !isHttpUrl(finalUrl)) {
        try {
          const base64Data = await urlToBase64(finalUrl);
          (attachment as any).base64Data = base64Data;
          attachment.tempUrl = base64Data;
        } catch (err) {
          reportError('图片转换失败', err);
        }
      }
      
      return attachment;
    }

    // 步骤 3: 未在历史中找到，根据 URL 类型创建新附件

    const attachmentId = uuidv4();
    const attachmentName = `${filePrefix}-${Date.now()}.png`;

    // Base64 或 Blob URL：转换为 Base64 Data URL
    if (isBase64Url(imageUrl) || isBlobUrl(imageUrl)) {
      const mimeType = imageUrl.match(/^data:([^;]+);/)?.[1] || 'image/png';
      const base64Data = isBase64Url(imageUrl) ? imageUrl : await urlToBase64(imageUrl);
      
      return {
        id: attachmentId,
        mimeType: mimeType,
        name: attachmentName,
        url: '', // 本地数据没有永久 URL
        uploadStatus: 'pending',
        base64Data: base64Data
      } as Attachment;
    }

    // HTTP URL：直接传递 URL，后端会下载
    if (isHttpUrl(imageUrl)) {
      return {
        id: attachmentId,
        mimeType: 'image/png',
        name: attachmentName,
        url: imageUrl,
        uploadStatus: 'completed'
      };
    }

    return null;

  } catch (e) {
    return null;
  }
};

// ============================================================
// View 组件附件处理统一函数
// ============================================================

/**
 * 处理用户上传的附件
 * 
 * 功能说明：
 * - 当用户没有上传新附件时，使用画布图片（CONTINUITY LOGIC）
 * - 当用户上传了附件时，整理附件元数据传递给后端
 * 
 * 前端职责：
 * - 文件选择与预览（创建 Blob URL）
 * - 附件元数据整理
 * - CONTINUITY LOGIC 处理
 * 
 * 后端职责：
 * - 统一处理所有附件（用户上传、AI返回、CONTINUITY）
 * - 统一上传到云存储
 * - 统一管理云 URL
 * 
 * @param attachments 用户上传的附件数组
 * @param activeImageUrl 当前画布上的图片 URL（用于 CONTINUITY LOGIC）
 * @param messages 消息历史（用于查找匹配附件）
 * @param sessionId 当前会话 ID
 * @param filePrefix 文件名前缀（如 'canvas', 'expand'）
 * @returns 处理后的附件数组
 */
export const processUserAttachments = async (
  attachments: Attachment[],
  activeImageUrl: string | null,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas'
): Promise<Attachment[]> => {
  const result: Attachment[] = [];

  // ✅ 1. 如果有画布图片且没有新上传附件，使用画布图片（CONTINUITY LOGIC）
  if (attachments.length === 0 && activeImageUrl) {
    const activeUrlType = activeImageUrl.startsWith('data:') ? 'Base64' : 
                          activeImageUrl.startsWith('blob:') ? 'Blob' : 
                          activeImageUrl.startsWith('http') ? 'HTTP' : 'Other';
    
    // 提取 Base64 的 MIME 类型
    let activeMimeType = 'unknown';
    if (activeUrlType === 'Base64') {
      const mimeMatch = activeImageUrl.match(/^data:([^;]+);/);
      activeMimeType = mimeMatch ? mimeMatch[1] : 'unknown';
    }
    
    
    const prepared = await prepareAttachmentForApi(
      activeImageUrl,
      messages,
      sessionId,
      filePrefix,
      true // skipBase64: 后端会处理所有 URL 类型
    );
    
    if (prepared) {
      result.push(prepared);
    } else {
    }
    return result;
  }

  // ✅ 2. 如果有新上传的附件，处理附件
  if (attachments.length > 0) {
    
    // 格式化 URL 用于日志（Base64 URL 只显示类型和长度）
    const formatUrlForLog = (url: string | undefined): string => {
      if (!url) return 'N/A';
      if (url.startsWith('data:')) {
        return `Base64 Data URL (长度: ${url.length} 字符)`;
      }
      return url.length > 80 ? url.substring(0, 80) + '...' : url;
    };

    // ✅ 统一处理：将 Blob URL 转换为 Base64（确保后端能访问）
    // 原因：JSON.stringify 会忽略 File 对象，Blob URL 无法被后端访问
    const processedAttachments = await Promise.all(attachments.map(async (att, index) => {
      // 日志记录
      const urlInfo = att.url ? formatUrlForLog(att.url) : 'N/A';
      const urlType = att.url?.startsWith('blob:') ? 'Blob' : 
                     att.url?.startsWith('data:') ? 'Base64' : 
                     att.url?.startsWith('http') ? 'HTTP' : 'Other';
      

      // 验证 URL 字段
      if (!att.url && !att.tempUrl) {
      }

      // ✅ 如果有 File 对象且 URL 是 Blob URL，转换为 Base64（与 ChatInputArea 一致）
      if (att.file && isBlobUrl(att.url)) {
        try {
          const base64Url = await fileToBase64(att.file);
          return { 
            ...att, 
            url: base64Url,  // 使用 Base64 URL，后端可以访问
            tempUrl: base64Url,  // 同时更新 tempUrl
            // 保留 File 对象用于上传任务（uploadTask 中会使用）
          };
        } catch (e) {
          return att;
        }
      }

      // 如果 URL 是 HTTP URL，直接使用（后端会自己下载）
      if (isHttpUrl(att.url || '')) {
        return att;
      }

      // 如果 URL 是 Base64，直接使用
      if (isBase64Url(att.url || '')) {
        return att;
      }

      // 如果有 File 对象但 URL 不是 Blob URL，直接返回
      if (att.file) {
        return att;
      }

      // 整理元数据，确保有 URL
      const finalUrl = att.url || att.tempUrl || '';
      return {
        ...att,
        url: finalUrl,
        uploadStatus: att.uploadStatus || 'pending' as const
      };
    }));

    // ✅ 3. 如果同时有画布图片，也添加（支持"附件 + 画布图片"组合）
    // 检查画布图片是否已经在附件中（避免重复）
    if (activeImageUrl) {
      const isCanvasImageInAttachments = processedAttachments.some(att =>
        att.url === activeImageUrl || att.tempUrl === activeImageUrl
      );

      if (!isCanvasImageInAttachments) {
        const canvasAttachment = await prepareAttachmentForApi(
          activeImageUrl,
          messages,
          sessionId,
          filePrefix,
          true
        );
        if (canvasAttachment) {
          // 画布图片放在最前面（图1），用户上传的图片在后面（图2, 图3...）
          return [canvasAttachment, ...processedAttachments];
        }
      }
    }

    return processedAttachments;
  }

  return [];
};

// ============================================================
// Handler 媒体处理统一函数
// ============================================================

/**
 * 处理 AI 返回的媒体结果
 * 
 * 功能说明：
 * - 创建用于 UI 显示的附件（displayAttachment）
 * - 创建异步上传任务（dbAttachmentPromise）
 * - 处理不同 URL 类型的显示逻辑
 * 
 * URL 处理：
 * - Base64 URL：直接使用作为显示 URL
 * - Blob URL：直接使用作为显示 URL
 * - HTTP URL：下载后转换为 Blob URL 用于显示（避免临时 URL 过期）
 * 
 * 字段说明：
 * - `url`: 用于 UI 显示的 URL（可能是 Blob URL 或 Base64 URL）
 * - `tempUrl`: 保存原始 URL，用于跨模式查找匹配附件
 * 
 * @param res AI 返回的媒体结果
 * @param context 执行上下文（sessionId, modelMessageId, storageId）
 * @param filePrefix 文件名前缀
 * @returns displayAttachment 和 dbAttachmentPromise
 */
export const processMediaResult = async (
  res: {
    url: string;
    mimeType: string;
    filename?: string;
    attachmentId?: string;
    messageId?: string;
    sessionId?: string;
    userId?: string;
    uploadStatus?: 'pending' | 'completed' | 'failed';
    taskId?: string;
    cloudUrl?: string;
    size?: number;
    createdAt?: number;
  },
  context: { sessionId: string; modelMessageId: string; storageId?: string },
  filePrefix: string
): Promise<{ 
  displayAttachment: Attachment; 
  dbAttachmentPromise: Promise<Attachment>; 
}> => {
  const attachmentId = res.attachmentId || uuidv4();
  const defaultExtension = filePrefix === 'video' ? 'mp4' : filePrefix === 'audio' ? 'mp3' : 'png';
  const filename = res.filename || `${filePrefix}-${Date.now()}.${defaultExtension}`;
  const originalUrl = res.url;
  let displayUrl = res.url;

  // HTTP URL 需要转换为 Blob URL 用于显示（避免临时 URL 过期）
  if (isHttpUrl(res.url)) {
    const response = await fetch(res.url);
    const blob = await response.blob();
    displayUrl = URL.createObjectURL(blob);
  }

  // 创建用于 UI 显示的附件
  const displayAttachment: Attachment = {
    id: attachmentId,
    mimeType: res.mimeType,
    name: filename,
    url: displayUrl,
    tempUrl: originalUrl, // 保存原始 URL，用于跨模式查找
    uploadStatus: 'pending' as const,
  };

  if (res.attachmentId) {
    return {
      displayAttachment,
      dbAttachmentPromise: Promise.resolve({
        id: attachmentId,
        mimeType: res.mimeType,
        name: filename,
        url: res.cloudUrl || '',
        tempUrl: originalUrl,
        uploadStatus: res.uploadStatus || 'pending',
        uploadTaskId: res.taskId,
        cloudUrl: res.cloudUrl,
        size: res.size,
        messageId: res.messageId,
        sessionId: res.sessionId,
        userId: res.userId,
        createdAt: res.createdAt,
      }),
    };
  }

  // 创建异步上传任务
  const dbAttachmentPromise = (async (): Promise<Attachment> => {
    const file = await sourceToFile(res.url, filename, res.mimeType);
    const result = await storageUpload.uploadFileAsync(file, {
      sessionId: context.sessionId,
      messageId: context.modelMessageId,
      attachmentId: attachmentId,
      storageId: context.storageId,
    });

    return {
      id: attachmentId,
      mimeType: res.mimeType,
      name: filename,
      url: isHttpUrl(originalUrl) ? originalUrl : '', // HTTP URL 作为临时 URL
      tempUrl: isHttpUrl(originalUrl) ? originalUrl : undefined, // 保存用于跨模式查找
      uploadStatus: result.taskId ? ('pending' as const) : ('failed' as const),
      uploadTaskId: result.taskId || undefined,
    };
  })();

  return { displayAttachment, dbAttachmentPromise };
};

/**
 * 通过后端上传图片 URL 到云存储
 * 
 * 功能说明：
 * - 推荐用于远程 URL，后端会下载并上传，避免前端下载
 * - 支持 Base64、Blob URL 和 HTTP URL
 * 
 * @param imageUrl 图片 URL（Base64、Blob 或 HTTP URL）
 * @param filename 文件名
 * @param sessionId 会话 ID
 * @param messageId 消息 ID
 * @param attachmentId 附件 ID
 * @returns 任务 ID，失败返回空字符串
 */
export const submitUploadTaskToBackend = async (
  imageUrl: string,
  filename: string,
  sessionId: string,
  messageId: string,
  attachmentId: string
): Promise<string> => {
  try {
    // Base64 URL：转换为 File 后上传
    if (isBase64Url(imageUrl)) {
      const file = await base64ToFile(imageUrl, filename);
      const result = await storageUpload.uploadFileAsync(file, {
        sessionId,
        messageId,
        attachmentId
      });
      return result.taskId || '';
    }

    // Blob URL：fetch 转换为 File 后上传
    if (isBlobUrl(imageUrl)) {
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      const file = new File([blob], filename, { type: blob.type || 'image/png' });
      const result = await storageUpload.uploadFileAsync(file, {
        sessionId,
        messageId,
        attachmentId
      });
      return result.taskId || '';
    }

    // HTTP URL：通过后端下载并上传
    const result = await storageUpload.uploadFromUrlViaBackend(imageUrl, filename, {
      sessionId,
      messageId,
      attachmentId
    });
    return result.taskId || '';

  } catch (error) {
    return '';
  }
};

/**
 * 获取URL类型（统一函数）
 * 
 * 用于统一判断URL类型，支持所有URL类型包括：
 * - Base64 Data URL (data:image/png;base64,...)
 * - Blob URL (blob:http://localhost:xxx)
 * - 临时代理URL (/api/temp-images/{id})
 * - HTTP/HTTPS URL (http://... 或 https://...)
 * - 空URL ('' 或 undefined)
 * 
 * @param url - URL字符串
 * @param uploadStatus - 上传状态（可选，用于区分云存储URL和HTTP临时URL）
 * @returns URL类型描述字符串
 */
export const getUrlType = (url: string | undefined, uploadStatus?: string): string => {
  if (!url) {
    return '空URL';
  }
  
  if (url.startsWith('data:')) {
    return 'Base64 Data URL (AI原始返回)';
  }
  
  if (url.startsWith('blob:')) {
    return 'Blob URL (处理后的本地URL)';
  }
  
  if (url.startsWith('/api/temp-images/')) {
    return '临时代理URL (后端创建)';
  }
  
  if (url.startsWith('/api/storage/local-files/')) {
    return '本地存储URL (已完成)';
  }
  
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return uploadStatus === 'completed' 
      ? '云存储URL (已上传完成)' 
      : 'HTTP临时URL (AI原始返回)';
  }
  
  return '未知类型';
};

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
import { v4 as uuidv4 } from 'uuid';
import { Attachment, Message } from '../../types/types';
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
    // 清除 base64Data（仅用于 API 调用，不需要持久化到数据库）
    delete (cleaned as any).base64Data;
    
    // 处理 tempUrl：保留 HTTP URL（用于跨模式查找），清空 Base64/Blob
    if (cleaned.tempUrl) {
      if (isBase64Url(cleaned.tempUrl) || isBlobUrl(cleaned.tempUrl)) {
        // Base64/Blob 太大，不能持久化，但保留空字符串作为标记
        // 这样 findAttachmentByUrl 可以通过 url 字段匹配
        delete cleaned.tempUrl;
      }
      // HTTP URL 保留，用于跨模式传递时查找
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
    
    console.log('[uploadToCloudStorageSync] 开始处理:', {
      type: urlType,
      filename: isFile ? (imageSource as File).name : finalFilename
    });

    // 使用统一函数转换为 File
    const file = await sourceToFile(imageSource, finalFilename);
    console.log('[uploadToCloudStorageSync] 已转换为 File:', file.name, file.size);

    // 上传到云存储
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
    const finalFilename = filename || `image-${Date.now()}.png`;
    const isFile = imageSource instanceof File;
    const sourceUrl = typeof imageSource === 'string' ? imageSource : '';
    
    console.log('[uploadToCloudStorage] 提交异步上传任务:', {
      type: isFile ? 'File' : isBase64Url(sourceUrl) ? 'Base64' : isBlobUrl(sourceUrl) ? 'Blob URL' : 'Unknown',
      messageId: messageId.substring(0, 8) + '...',
      attachmentId: attachmentId.substring(0, 8) + '...',
      sessionId: sessionId.substring(0, 8) + '...'
    });

    // 使用统一函数转换为 File
    const file = await sourceToFile(imageSource, finalFilename);
    console.log('[uploadToCloudStorage] 已转换为 File:', file.name, file.type, file.size);

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


// ============================================================
// 核心工具函数：URL 类型检测与转换
// ============================================================

/**
 * 将任意来源转换为 File 对象（统一转换函数）
 * 
 * 支持的输入类型：
 * - File 对象：直接返回
 * - Base64 URL：fetch 后转换
 * - Blob URL：fetch 后转换
 * - HTTP URL：通过后端代理下载后转换
 * 
 * @param source 图片来源（File 或 URL 字符串）
 * @param filename 目标文件名
 * @param mimeType 可选的 MIME 类型
 * @returns File 对象
 */
export const sourceToFile = async (
  source: string | File,
  filename: string,
  mimeType?: string
): Promise<File> => {
  // 如果已经是 File，直接返回
  if (source instanceof File) {
    return source;
  }

  const url = source;
  let fetchUrl = url;

  // HTTP URL 需要通过后端代理下载（解决 CORS）
  if (isHttpUrl(url)) {
    fetchUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
  }

  const response = await fetch(fetchUrl);
  if (!response.ok) {
    throw new Error(`下载失败: HTTP ${response.status}`);
  }
  const blob = await response.blob();
  return new File([blob], filename, { type: mimeType || blob.type || 'image/png' });
};

/**
 * 尝试从后端获取云存储 URL（统一查询函数）
 * 
 * 用于 CONTINUITY LOGIC：当本地 URL 不是云存储 URL 时，查询后端获取
 * 
 * @param sessionId 会话 ID
 * @param attachmentId 附件 ID
 * @param currentUrl 当前 URL
 * @param currentStatus 当前上传状态
 * @returns 云存储 URL 和状态，或 null
 */
export const tryFetchCloudUrl = async (
  sessionId: string | null,
  attachmentId: string,
  currentUrl: string | undefined,
  currentStatus: string | undefined
): Promise<{ url: string; uploadStatus: string } | null> => {
  // 检查是否需要查询后端
  const needFetch = sessionId && (
    currentStatus === 'pending' || 
    !isHttpUrl(currentUrl)
  );

  if (!needFetch) {
    return null;
  }

  console.log('[tryFetchCloudUrl] 查询后端, 原因:', 
    currentStatus === 'pending' ? 'uploadStatus=pending' : 'url不是HTTP URL'
  );

  const backendData = await fetchAttachmentStatus(sessionId, attachmentId);

  if (backendData && isHttpUrl(backendData.url)) {
    console.log('[tryFetchCloudUrl] ✅ 获取到云 URL:', backendData.url.substring(0, 60));
    return {
      url: backendData.url,
      uploadStatus: 'completed'
    };
  }

  console.log('[tryFetchCloudUrl] ⚠️ 后端未返回有效云 URL');
  return null;
};

// ============================================================
// URL 转换工具函数
// ============================================================

/**
 * 将任意 URL 转换为 Base64 Data URL
 * 支持：Base64 URL（直接返回）、Blob URL、HTTP URL（通过后端代理）
 */
export const urlToBase64 = async (url: string): Promise<string> => {
  if (isBase64Url(url)) {
    return url;
  }
  
  let fetchUrl = url;
  if (isHttpUrl(url)) {
    // HTTP URL 需要通过后端代理下载（解决 CORS）
    fetchUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
  }
  
  const response = await fetch(fetchUrl);
  const blob = await response.blob();
  
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
};

/**
 * 将任意 URL 转换为 File 对象
 * 支持：Base64 URL、Blob URL、HTTP URL（通过后端代理）
 */
export const urlToFile = async (
  url: string, 
  filename: string, 
  mimeType?: string
): Promise<File> => {
  let fetchUrl = url;
  if (isHttpUrl(url)) {
    fetchUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
  }
  
  const response = await fetch(fetchUrl);
  const blob = await response.blob();
  return new File([blob], filename, { type: mimeType || blob.type || 'image/png' });
};

// ============================================================
// 新增：附件查找与状态查询
// ============================================================

/**
 * 从消息历史中查找匹配 URL 的附件
 * 用于 CONTINUITY LOGIC：复用已有附件信息，避免重复上传
 * 
 * 匹配策略：
 * 1. 精确匹配 url 或 tempUrl（最可靠）
 * 2. 如果是 Blob URL 且未精确匹配，尝试找最近的图片附件（兜底策略）
 * 
 * 注意：此函数只负责在内存中查找附件 ID，
 * 云存储 URL 需要通过 fetchAttachmentStatus 从后端 upload_tasks 表获取
 */
export const findAttachmentByUrl = (
  targetUrl: string, 
  messages: Message[]
): { attachment: Attachment; messageId: string } | null => {
  const urlType = isBase64Url(targetUrl) ? 'Base64' : 
                  isBlobUrl(targetUrl) ? 'Blob' : 
                  isHttpUrl(targetUrl) ? 'HTTP' : '未知';
  
  console.log('[findAttachmentByUrl] 开始查找, targetUrl 类型:', urlType);
  
  // 遍历消息（从最新到最旧）
  for (const msg of [...messages].reverse()) {
    for (const att of msg.attachments || []) {
      // 策略 1：精确匹配 url 或 tempUrl（最可靠的匹配方式）
      if (att.url === targetUrl || att.tempUrl === targetUrl) {
        console.log('[findAttachmentByUrl] ✅ 精确匹配成功:', {
          id: att.id,
          messageId: msg.id,
          matchedField: att.url === targetUrl ? 'url' : 'tempUrl',
          uploadStatus: att.uploadStatus
        });
        return { attachment: att, messageId: msg.id };
      }
    }
  }
  
  // 策略 4：如果是 Blob URL 且未找到精确匹配，尝试找最近的图片附件
  // 这是一个兜底策略，用于处理 Blob URL 无法精确匹配的情况
  if (isBlobUrl(targetUrl)) {
    console.log('[findAttachmentByUrl] Blob URL 未精确匹配，尝试查找最近的图片附件');
    for (const msg of [...messages].reverse()) {
      for (const att of msg.attachments || []) {
        // 只匹配图片类型的附件
        if (att.mimeType?.startsWith('image/') && att.id) {
          console.log('[findAttachmentByUrl] ✅ 找到最近的图片附件（兜底策略）:', {
            id: att.id,
            messageId: msg.id,
            uploadStatus: att.uploadStatus,
            hasUploadTaskId: !!(att as any).uploadTaskId
          });
          return { attachment: att, messageId: msg.id };
        }
      }
    }
  }
  
  console.log('[findAttachmentByUrl] ❌ 未找到匹配的附件');
  return null;
};

/**
 * 从后端查询附件的最新状态（包括云存储 URL）
 * 用于获取 pending 状态附件的最新 URL
 */
export const fetchAttachmentStatus = async (
  sessionId: string, 
  attachmentId: string
): Promise<{ url: string; uploadStatus: string; taskId?: string; taskStatus?: string } | null> => {
  try {
    console.log('[fetchAttachmentStatus] 开始查询附件:', {
      sessionId: sessionId?.substring(0, 8) + '...',
      attachmentId: attachmentId
    });
    const response = await fetch(`/api/sessions/${sessionId}/attachments/${attachmentId}`);
    if (!response.ok) {
      console.log('[fetchAttachmentStatus] 查询失败:', response.status);
      return null;
    }
    const data = await response.json();
    console.log('[fetchAttachmentStatus] 查询结果:', {
      url: data.url?.substring(0, 80),
      urlIsHttp: isHttpUrl(data.url),
      uploadStatus: data.uploadStatus,
      taskId: data.taskId,
      taskStatus: data.taskStatus,
      hasTask: !!data.taskId
    });
    return data;
  } catch (e) {
    console.error('[fetchAttachmentStatus] 查询异常:', e);
    return null;
  }
};

// ============================================================
// 新增：View 组件 CONTINUITY LOGIC 统一函数
// ============================================================

/**
 * 准备附件供 API 调用（CONTINUITY LOGIC 核心函数）
 * 
 * 当用户没有上传新图片时，自动使用当前画布上的图片作为输入。
 * 处理流程：
 * 1. 先尝试从历史消息中查找已有附件（复用云 URL）
 * 2. 如果找到，检查 uploadStatus，必要时查询后端获取最新 URL
 * 3. 如果未找到，根据 URL 类型直接处理
 * 4. 准备 base64Data 供 API 调用
 * 
 * 注意：
 * - Google 提供商需要 base64Data
 * - Tongyi 提供商可以直接使用云 URL，不需要 base64Data
 * 
 * @param imageUrl 当前画布上的图片 URL
 * @param messages 消息历史
 * @param sessionId 当前会话 ID
 * @param filePrefix 文件名前缀（如 'canvas', 'expand'）
 * @returns 准备好的 Attachment 对象，失败返回 null
 */
export const prepareAttachmentForApi = async (
  imageUrl: string,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas'
): Promise<Attachment | null> => {
  const urlType = isBase64Url(imageUrl) ? 'Base64' : 
                  isBlobUrl(imageUrl) ? 'Blob URL' : 
                  isHttpUrl(imageUrl) ? 'HTTP URL' : '未知';
  
  console.log('[prepareAttachmentForApi] 开始准备附件');
  console.log('[prepareAttachmentForApi] imageUrl 类型:', urlType);

  try {
    // ============================================================
    // 第一步：尝试从历史消息中查找已有附件（复用云 URL）
    // 这对于跨模式传递场景很重要，可以复用已上传的云 URL
    // ============================================================
    const found = findAttachmentByUrl(imageUrl, messages);

    if (found) {
      const { attachment: existingAttachment } = found;
      let finalUrl = existingAttachment.url;
      let finalUploadStatus = existingAttachment.uploadStatus || 'completed';

      console.log('[prepareAttachmentForApi] ✅ 找到历史附件:', {
        id: existingAttachment.id,
        url: finalUrl?.substring(0, 60),
        uploadStatus: finalUploadStatus
      });

      // ============================================================
      // 优化：如果 imageUrl 已是 Base64/Blob，直接使用，无需查询后端
      // ============================================================
      if (isBase64Url(imageUrl)) {
        console.log('[prepareAttachmentForApi] ✅ imageUrl 已是 Base64，直接使用（跳过后端查询）');
        return {
          id: uuidv4(),
          mimeType: existingAttachment.mimeType || 'image/png',
          name: existingAttachment.name || `${filePrefix}-${Date.now()}.png`,
          url: imageUrl,
          uploadStatus: 'completed' as const,
          base64Data: imageUrl
        } as Attachment;
      }

      if (isBlobUrl(imageUrl)) {
        console.log('[prepareAttachmentForApi] ✅ imageUrl 是 Blob，本地转换（跳过后端查询）');
        const base64Data = await urlToBase64(imageUrl);
        return {
          id: uuidv4(),
          mimeType: existingAttachment.mimeType || 'image/png',
          name: existingAttachment.name || `${filePrefix}-${Date.now()}.png`,
          url: imageUrl,
          uploadStatus: existingAttachment.uploadStatus || 'pending' as const,
          base64Data
        } as Attachment;
      }

      // ============================================================
      // 只有当 imageUrl 不是 Base64/Blob 时，才查询后端获取云 URL
      // ============================================================
      const cloudResult = await tryFetchCloudUrl(
        sessionId,
        existingAttachment.id,
        finalUrl,
        finalUploadStatus
      );
      
      if (cloudResult) {
        finalUrl = cloudResult.url;
        finalUploadStatus = cloudResult.uploadStatus as 'pending' | 'uploading' | 'completed' | 'failed';
      }

      // 构建复用的附件对象
      const reusedAttachment: Attachment = {
        id: uuidv4(),
        mimeType: existingAttachment.mimeType || 'image/png',
        name: existingAttachment.name || `${filePrefix}-${Date.now()}.png`,
        url: finalUrl,
        uploadStatus: finalUploadStatus as 'pending' | 'uploading' | 'completed' | 'failed'
      };

      // 获取 Base64 数据供 API 使用（此时 imageUrl 是 HTTP URL）
      try {
        if (finalUrl && isHttpUrl(finalUrl)) {
          (reusedAttachment as any).base64Data = await urlToBase64(finalUrl);
        }
      } catch (base64Error) {
        console.warn('[prepareAttachmentForApi] ⚠️ 获取 base64Data 失败，但仍返回附件:', base64Error);
      }

      console.log('[prepareAttachmentForApi] ✅ 复用历史附件完成:', {
        hasCloudUrl: isHttpUrl(reusedAttachment.url),
        hasBase64: !!(reusedAttachment as any).base64Data
      });
      return reusedAttachment;
    }

    // ============================================================
    // 第二步：未在历史中找到，根据 URL 类型直接处理
    // ============================================================
    console.log('[prepareAttachmentForApi] 未在历史中找到匹配附件，直接处理 URL');

    if (isBase64Url(imageUrl) || isBlobUrl(imageUrl)) {
      // Base64/Blob URL 直接处理
      console.log('[prepareAttachmentForApi] Base64/Blob 直接处理模式');
      const base64Data = await urlToBase64(imageUrl);
      
      // 从 Base64 URL 中提取 MIME 类型
      let mimeType = 'image/png';
      if (isBase64Url(imageUrl)) {
        const match = imageUrl.match(/^data:([^;]+);/);
        if (match) {
          mimeType = match[1];
        }
      }
      
      return {
        id: uuidv4(),
        mimeType: mimeType,
        name: `${filePrefix}-${Date.now()}.png`,
        url: base64Data,
        uploadStatus: 'completed',
        ...({ base64Data } as any)
      };
    }

    if (isHttpUrl(imageUrl)) {
      // HTTP URL 直接处理
      console.log('[prepareAttachmentForApi] 云存储 URL 模式');
      const attachment: Attachment = {
        id: uuidv4(),
        mimeType: 'image/png',
        name: `${filePrefix}-${Date.now()}.png`,
        url: imageUrl,
        uploadStatus: 'completed'
      };
      
      try {
        (attachment as any).base64Data = await urlToBase64(imageUrl);
      } catch (base64Error) {
        console.warn('[prepareAttachmentForApi] ⚠️ 获取 base64Data 失败:', base64Error);
      }
      
      console.log('[prepareAttachmentForApi] ✅ 云存储 URL 模式完成, hasBase64:', !!(attachment as any).base64Data);
      return attachment;
    }

    console.log('[prepareAttachmentForApi] ❌ 无法处理的 URL 类型');
    return null;

  } catch (e) {
    console.error('[prepareAttachmentForApi] ❌ 准备附件失败:', e);
    return null;
  }
};

// ============================================================
// 新增：View 组件 handleSend 统一函数
// ============================================================

/**
 * 处理用户上传的附件（统一函数）
 * 
 * 用于 ImageEditView 和 ImageExpandView 的 handleSend 函数
 * 将重复的附件处理逻辑抽取到此处，避免代码重复
 * 
 * 处理流程：
 * 1. 如果用户没有上传新附件，但画布上有图片 → CONTINUITY LOGIC
 * 2. 如果用户上传了附件 → 处理跨模式传递和 base64Data 准备
 * 
 * @param attachments 用户上传的附件数组
 * @param activeImageUrl 当前画布上的图片 URL
 * @param messages 消息历史
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
  let finalAttachments = [...attachments];

  // ============================================================
  // CONTINUITY LOGIC - 无新上传时使用画布图片
  // ============================================================
  if (finalAttachments.length === 0 && activeImageUrl) {
    console.log(`[processUserAttachments] ✅ 触发 CONTINUITY LOGIC（无新上传）`);
    const prepared = await prepareAttachmentForApi(
      activeImageUrl,
      messages,
      sessionId,
      filePrefix
    );
    if (prepared) {
      finalAttachments = [prepared];
    }
    return finalAttachments;
  }

  // ============================================================
  // 处理用户上传的附件（包括跨模式传递的附件）
  // ============================================================
  if (finalAttachments.length > 0) {
    console.log(`[processUserAttachments] ✅ 处理用户上传的附件, 数量:`, finalAttachments.length);
    const processedAttachments = await Promise.all(
      finalAttachments.map(async (att, index) => {
        // 详细日志：附件原始状态
        const urlType = isBase64Url(att.url || '') ? 'Base64' : 
                        isBlobUrl(att.url || '') ? 'Blob' : 
                        isHttpUrl(att.url || '') ? 'HTTP' : 'Other';
        const tempUrlType = isBase64Url(att.tempUrl || '') ? 'Base64' : 
                           isBlobUrl(att.tempUrl || '') ? 'Blob' : 
                           isHttpUrl(att.tempUrl || '') ? 'HTTP' : 'None';
        
        console.log(`[processUserAttachments] 附件[${index}] 原始状态:`, {
          id: att.id?.substring(0, 8) + '...',
          urlType,
          tempUrlType,
          uploadStatus: att.uploadStatus,
          hasBase64Data: !!(att as any).base64Data
        });

        // 如果已有 base64Data，直接返回
        if ((att as any).base64Data) {
          console.log(`[processUserAttachments] 附件[${index}] 已有 base64Data，直接返回`);
          return att;
        }

        const displayUrl = att.url || '';
        const cloudUrlFromTemp = att.tempUrl && isHttpUrl(att.tempUrl) ? att.tempUrl : null;
        
        console.log(`[processUserAttachments] 附件[${index}] 处理策略:`, {
          displayUrlType: urlType,
          hasCloudUrlInTemp: !!cloudUrlFromTemp,
          uploadStatus: att.uploadStatus
        });

        // ============================================================
        // 情况 1：url 字段已是 Base64（跨模式传递时常见）
        // ✅ 直接使用，无需网络请求
        // ============================================================
        if (isBase64Url(displayUrl)) {
          console.log(`[processUserAttachments] 附件[${index}] ✅ url 已是 Base64，直接使用（无需网络请求）`);
          return {
            ...att,
            uploadStatus: att.uploadStatus || 'completed' as const,
            base64Data: displayUrl
          } as Attachment;
        }

        // ============================================================
        // 情况 2：url 字段是 Blob URL
        // ✅ 本地转换，无需网络请求
        // ============================================================
        if (isBlobUrl(displayUrl)) {
          console.log(`[processUserAttachments] 附件[${index}] ✅ url 是 Blob，本地转换`);
          try {
            const base64Data = await urlToBase64(displayUrl);
            return {
              ...att,
              uploadStatus: att.uploadStatus || 'pending' as const,
              base64Data
            } as Attachment;
          } catch (e) {
            console.warn(`[processUserAttachments] 附件[${index}] ⚠️ Blob 转换失败:`, e);
          }
        }

        // ============================================================
        // 情况 3：url 字段是 HTTP URL（已上传的云 URL）
        // ============================================================
        if (isHttpUrl(displayUrl)) {
          console.log(`[processUserAttachments] 附件[${index}] url 是云 URL，从云 URL 获取 base64`);
          try {
            const base64Data = await urlToBase64(displayUrl);
            return {
              ...att,
              uploadStatus: 'completed' as const,
              base64Data
            } as Attachment;
          } catch (e) {
            console.warn(`[processUserAttachments] 附件[${index}] ⚠️ 从云 URL 获取 base64 失败:`, e);
          }
        }

        // ============================================================
        // 情况 4：tempUrl 中有云 URL（url 字段不可用时的备选）
        // ============================================================
        if (cloudUrlFromTemp) {
          console.log(`[processUserAttachments] 附件[${index}] 使用 tempUrl 中的云 URL`);
          try {
            const base64Data = await urlToBase64(cloudUrlFromTemp);
            return {
              ...att,
              uploadStatus: 'completed' as const,
              base64Data
            } as Attachment;
          } catch (e) {
            console.warn(`[processUserAttachments] 附件[${index}] ⚠️ 从 tempUrl 云 URL 获取 base64 失败:`, e);
          }
        }

        // ============================================================
        // 情况 5：查询后端获取云 URL（最后的备选方案）
        // ============================================================
        if (att.id && sessionId) {
          console.log(`[processUserAttachments] 附件[${index}] 查询后端获取云 URL`);

          const cloudResult = await tryFetchCloudUrl(
            sessionId,
            att.id,
            displayUrl,
            att.uploadStatus
          );

          if (cloudResult) {
            console.log(`[processUserAttachments] 附件[${index}] ✅ 后端返回云 URL`);
            const base64Data = await urlToBase64(cloudResult.url);
            return {
              ...att,
              tempUrl: cloudResult.url,
              uploadStatus: 'completed' as const,
              base64Data
            } as Attachment;
          } else {
            console.log(`[processUserAttachments] 附件[${index}] ⚠️ 后端未返回有效云 URL`);
          }
        }

        console.log(`[processUserAttachments] 附件[${index}] ❌ 无法获取 base64Data`);
        return att;
      })
    );
    finalAttachments = processedAttachments;
  }

  return finalAttachments;
};

// ============================================================
// 新增：Handler 媒体处理统一函数
// ============================================================

/**
 * 处理 AI 返回的媒体结果（Handler 统一函数）
 * 
 * 处理流程：
 * 1. 根据 URL 类型创建 displayUrl（用于 UI 显示）
 * 2. 创建 uploadSource（用于上传到云存储）
 * 3. 返回 displayAttachment 和 dbAttachmentPromise
 * 
 * @param res AI 返回的媒体结果
 * @param context 执行上下文
 * @param filePrefix 文件名前缀
 */
export const processMediaResult = async (
  res: { url: string; mimeType: string; filename?: string },
  context: { sessionId: string; modelMessageId: string },
  filePrefix: string
): Promise<{ 
  displayAttachment: Attachment; 
  dbAttachmentPromise: Promise<Attachment>; 
}> => {
  const attachmentId = uuidv4();
  const filename = res.filename || `${filePrefix}-${Date.now()}.png`;
  let displayUrl = res.url;
  const originalUrl = res.url; // 保存原始 URL，用于跨模式查找

  // 根据 URL 类型处理显示 URL
  if (isHttpUrl(res.url)) {
    // HTTP URL（临时 URL）- 下载后创建 Blob URL 用于显示
    const response = await fetch(res.url);
    const blob = await response.blob();
    displayUrl = URL.createObjectURL(blob);
  }

  // 创建用于 UI 显示的附件
  // tempUrl 保存原始 URL（Base64/Blob/HTTP），用于跨模式传递时查找匹配的附件
  const displayAttachment: Attachment = {
    id: attachmentId,
    mimeType: res.mimeType,
    name: filename,
    url: displayUrl,
    tempUrl: originalUrl, // ✅ 保存原始 URL，用于 findAttachmentByUrl 查找
    uploadStatus: 'pending' as const,
  };

  // 创建异步上传任务
  const dbAttachmentPromise = (async (): Promise<Attachment> => {
    // 使用统一函数转换为 File
    const file = await sourceToFile(res.url, filename, res.mimeType);

    const result = await storageUpload.uploadFileAsync(file, {
      sessionId: context.sessionId,
      messageId: context.modelMessageId,
      attachmentId: attachmentId,
    });

    return {
      id: attachmentId,
      mimeType: res.mimeType,
      name: filename,
      url: '',
      tempUrl: isHttpUrl(originalUrl) ? originalUrl : undefined, // ✅ 保存 HTTP URL 用于跨模式查找
      uploadStatus: result.taskId ? 'pending' : 'failed',
      uploadTaskId: result.taskId || undefined,
    };
  })();

  return { displayAttachment, dbAttachmentPromise };
};

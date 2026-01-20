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
 * 获取访问令牌
 * 参考 UnifiedProviderClient.ts 的实现
 */
function getAccessToken(): string | null {
  return localStorage.getItem('access_token');
}

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
    if (verbose) console.log('[cleanAttachmentsForDb] Input atts is invalid, returning empty array.');
    return [];
  }

  return atts.map(att => {
    const cleaned = { ...att };
    const url = cleaned.url || '';

    // Blob URLs are always temporary and cannot be persisted.
    if (isBlobUrl(url)) {
      if (verbose) console.log('[cleanAttachmentsForDb] ⚠️ Clearing Blob URL.');
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    } 
    // Base64 URLs are too large for the database and must be cleared.
    else if (isBase64Url(url)) {
      if (verbose) console.log('[cleanAttachmentsForDb] ⚠️ Clearing Base64 URL.');
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    } 
    // For HTTP URLs, apply more specific rules.
    else if (isHttpUrl(url)) {
      // 1. If upload is marked 'completed', trust it and preserve. This is a permanent cloud URL.
      if (cleaned.uploadStatus === 'completed') {
        if (verbose) console.log('[cleanAttachmentsForDb] ✅ Preserving completed cloud URL.');
        // Status and URL are correct, no changes needed.
      }
      // 2. If it has an uploadTaskId, it's an in-progress upload. Preserve URL but ensure status is 'pending'.
      else if ((cleaned as any).uploadTaskId) {
        if (verbose) console.log('[cleanAttachmentsForDb] ⏳ Preserving URL for attachment with active upload task.');
        cleaned.uploadStatus = 'pending';
      }
      // 3. If the URL contains temporary patterns, it's an expiring link and must be cleared.
      else if (url.includes('/temp/') || url.includes('expires=')) {
        if (verbose) console.log('[cleanAttachmentsForDb] 🗑️ Clearing temporary HTTP URL:', url);
        cleaned.url = '';
        cleaned.uploadStatus = 'pending'; // Mark for potential re-upload.
      }
      // 4. For any other HTTP URL (e.g., from an external source), preserve it but mark as 'pending' for review or upload.
      else {
        if (verbose) console.log('[cleanAttachmentsForDb] ⚠️ Marking unknown HTTP URL as pending.');
        cleaned.uploadStatus = 'pending';
      }
    }

    // Always remove non-serializable File objects and temporary base64 data.
    delete cleaned.file;
    delete (cleaned as any).base64Data;
    
    // 2. tempUrl Temporary URL Detection:
    // Clean up tempUrl: only preserve it if it's a valid, non-temporary HTTP URL.
    // If uploadTaskId exists, it means the upload is in progress, so preserve the tempUrl.
    if (cleaned.tempUrl) {
      if (!isHttpUrl(cleaned.tempUrl) || (cleaned.tempUrl.includes('/temp/') || cleaned.tempUrl.includes('expires='))) {
        // Only clear tempUrl if there's no active upload task associated with it.
        if ((cleaned as any).uploadTaskId) {
          if (verbose) console.log('[cleanAttachmentsForDb] ⏳ Preserving temporary tempUrl due to active upload task:', cleaned.tempUrl);
          // Do nothing, preserve it
        } else {
          if (verbose) console.log('[cleanAttachmentsForDb] 🗑️ Clearing temporary tempUrl:', cleaned.tempUrl);
          delete cleaned.tempUrl;
        }
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
 * 将任意来源转换为 File 对象（统一转换函数，带降级策略）
 * 
 * 支持的输入类型：
 * - File 对象：直接返回
 * - Base64 URL：fetch 后转换
 * - Blob URL：fetch 后转换
 * - HTTP URL：通过后端代理下载后转换（带 3 层降级策略）
 * 
 * 降级策略（仅针对 HTTP URL）：
 * 1. 策略 1：通过后端代理下载（解决 CORS）
 * 2. 策略 2：直接下载（绕过代理）
 * 3. 策略 3：使用 urlToFile 函数
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

  // 对于非 HTTP URL（Base64, Blob），直接使用 urlToFile
  if (!isHttpUrl(url)) {
    return await urlToFile(url, filename, mimeType);
  }

  // HTTP URL：使用 3 层降级策略
  console.log('[sourceToFile] 开始 HTTP URL 下载，使用降级策略');

  // ============================================================
  // 策略 1：通过后端代理下载（解决 CORS）
  // ============================================================
  try {
    const proxyUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
    console.log('[sourceToFile] 策略 1：尝试后端代理下载');
    const response = await fetch(proxyUrl);
    if (!response.ok) {
      throw new Error(`Proxy failed: HTTP ${response.status} ${response.statusText}`);
    }
    const blob = await response.blob();
    console.log('[sourceToFile] ✅ 策略 1 成功');
    return new File([blob], filename, { type: mimeType || blob.type || 'image/png' });
  } catch (e) {
    console.warn('[sourceToFile] ⚠️ 策略 1（后端代理）失败:', e);
  }

  // ============================================================
  // 策略 2：直接下载（绕过代理）
  // ============================================================
  try {
    console.log('[sourceToFile] 策略 2：尝试直接下载');
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Direct download failed: HTTP ${response.status} ${response.statusText}`);
    }
    const blob = await response.blob();
    console.log('[sourceToFile] ✅ 策略 2 成功');
    return new File([blob], filename, { type: mimeType || blob.type || 'image/png' });
  } catch (e) {
    console.warn('[sourceToFile] ⚠️ 策略 2（直接下载）失败:', e);
  }

  // ============================================================
  // 策略 3：使用 urlToFile 函数（最后的备选方案）
  // ============================================================
  try {
    console.log('[sourceToFile] 策略 3：尝试 urlToFile 函数');
    const file = await urlToFile(url, filename, mimeType);
    console.log('[sourceToFile] ✅ 策略 3 成功');
    return file;
  } catch (e) {
    console.error('[sourceToFile] ❌ 策略 3（urlToFile）失败:', e);
  }

  // ============================================================
  // 所有策略都失败
  // ============================================================
  throw new Error(`[sourceToFile] All strategies failed for URL: ${url.substring(0, 100)}...`);
};

/**
 * 尝试从后端获取云存储 URL（统一查询函数）
 * 
 * 用于 CONTINUITY LOGIC：当本地 URL 不是云存储 URL 时，查询后端获取
 * 
 * 语义约定 (Semantic Contract):
 * - 返回值 (Return Value): 此函数返回的是一个 **永久性** 的云存储 URL。
 * - 调用方责任 (Caller's Responsibility): 调用方 **必须** 将返回的 URL 保存到附件的 `url` 字段，而不是 `tempUrl` 字段。
 * - 理由 (Reason): 将永久 URL 存储在 `url` 字段是确保数据一致性和避免在后续操作中重复上传或下载的关键。
 * 
 * @param sessionId 会话 ID
 * @param attachmentId 附件 ID
 * @param currentUrl 当前 URL
 * @param currentStatus 当前上传状态
 * @returns 包含永久云存储 URL 和状态的对象，如果无法获取则返回 null。
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

  // 修正 (FIX): 确保后端返回的是一个有效的、非临时的 HTTP URL
  if (backendData && isHttpUrl(backendData.url) && backendData.uploadStatus === 'completed') {
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
  if (!response.ok) {
    throw new Error(`Failed to fetch from ${url}. HTTP status: ${response.status} ${response.statusText}`);
  }
  
  const blob = await response.blob();

  // Validate MIME type
  if (!blob.type) {
    console.warn(`[urlToBase64] Blob type is empty for URL: ${url}. Proceeding, but this may indicate an issue.`);
  } else if (!blob.type.startsWith('image/')) {
    // We are more strict here as Base64 conversion is often for image display
    throw new Error(`[urlToBase64] Unsupported MIME type: ${blob.type}. This function currently only supports image types.`);
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    // Enhance error handling with more context
    reader.onerror = (error) => reject(new Error(`[urlToBase64] FileReader failed for URL ${url}: ${error}`));
    reader.readAsDataURL(blob);
  });
};

/**
 * 将 File 对象转换为 Base64 Data URL
 * - 不依赖 Blob URL，避免因 URL.revokeObjectURL 导致读取失败
 */
export const fileToBase64 = async (file: File): Promise<string> => {
  if (!file) {
    throw new Error('[fileToBase64] File is required.');
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = (error) => reject(new Error(`[fileToBase64] FileReader failed for file ${file.name}: ${error}`));
    reader.readAsDataURL(file);
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
  // 1. Validate filename
  if (!filename || filename.trim() === '') {
    throw new Error('[urlToFile] Filename cannot be empty.');
  }

  let fetchUrl = url;
  if (isHttpUrl(url)) {
    fetchUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
  }
  
  const response = await fetch(fetchUrl);
  // 2. Add HTTP error check
  if (!response.ok) {
    throw new Error(`Failed to fetch from ${url}. HTTP status: ${response.status} ${response.statusText}`);
  }

  const blob = await response.blob();

  // 3. Warn if blob type is missing
  if (!blob.type) {
    console.warn(`[urlToFile] Blob type is empty for URL: ${url}. Will use provided mimeType or fallback to 'image/png'.`);
  }

  // 4. Create and return the file
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
  // 1. Edge Case: Add early return if targetUrl is empty or falsy.
  if (!targetUrl) {
    return null;
  }

  const urlType = isBase64Url(targetUrl) ? 'Base64' :
                  isBlobUrl(targetUrl) ? 'Blob' :
                  isHttpUrl(targetUrl) ? 'HTTP' : '未知';
  
  console.log('[findAttachmentByUrl] 开始查找, targetUrl 类型:', urlType);
  
  // 2. Performance: Use a reverse for-loop to avoid copying the array.
  // 策略 1：精确匹配 url 或 tempUrl（最可靠）
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    for (const att of msg.attachments || []) {
      if (att.url === targetUrl || att.tempUrl === targetUrl) {
        const hasCloudUrl = att.uploadStatus === 'completed' && isHttpUrl(att.url);
        console.log('[findAttachmentByUrl] ✅ 精确匹配成功:', {
          id: att.id,
          messageId: msg.id,
          matchedField: att.url === targetUrl ? 'url' : 'tempUrl',
          uploadStatus: att.uploadStatus,
          hasCloudUrl: hasCloudUrl, // ✅ 显示是否有云URL
          cloudUrl: hasCloudUrl ? att.url : null, // ✅ 显示云URL（如果有）
          urlType: att.url ? (isHttpUrl(att.url) ? 'HTTP' : isBase64Url(att.url) ? 'Base64' : '其他') : '无'
        });
        return { attachment: att, messageId: msg.id };
      }
    }
  }
  
  // 策略 2：如果是 Blob URL 且未找到精确匹配，尝试找最近的有效云端图片附件作为兜底
  // 3. Fallback Strategy: Keep the strict fallback, but use the performant loop.
  if (isBlobUrl(targetUrl)) {
    console.log('[findAttachmentByUrl] Blob URL 未精确匹配，尝试查找最近的有效云端图片附件作为兜底');
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      for (const att of msg.attachments || []) {
        // Strict check: Only return valid, uploaded cloud attachments.
        if (
          att.mimeType?.startsWith('image/') &&
          att.id &&
          att.uploadStatus === 'completed' &&
          isHttpUrl(att.url)
        ) {
          console.log('[findAttachmentByUrl] ✅ 找到最近的有效云端图片附件（兜底策略）:', {
            id: att.id,
            messageId: msg.id,
            url: att.url,
            uploadStatus: att.uploadStatus,
            hasCloudUrl: true, // ✅ 显示有云URL（因为已经检查了 isHttpUrl）
            cloudUrl: att.url // ✅ 显示云URL
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
    
    // ✅ 构建请求头，添加 Authorization header（参考 UnifiedProviderClient.ts）
    const headers: HeadersInit = {};
    const token = getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    // ✅ 使用新的统一附件API端点
    const response = await fetch(`/api/attachments/${attachmentId}/cloud-url`, {
      headers,
      credentials: 'include',  // 发送认证 Cookie（向后兼容）
    });
    
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
 * 语义修复 (Semantic Fix):
 * - 原始问题 (Original Issue): 此函数错误地将获取到的永久性云存储 URL 保存到 `tempUrl` 字段，而将临时的本地 URL（如 Base64 或 Blob）保存在 `url` 字段。这与字段的语义完全相反。
 * - 变更 (Change):
 *   1.  **纠正 URL 分配**: 当找到或获取到云存储 URL 时，它现在被正确地赋值给 `url` 字段。
 *   2.  **废弃 tempUrl**: `tempUrl` 字段的使用已被移除或重新定位，以消除混淆。`url` 字段现在是附件的唯一真实来源 (Single Source of Truth)。
 * - 理由 (Reason): `url` 应该始终指向最持久、最权威的资源位置。将云 URL 放在 `url` 字段可确保所有后续 API 调用和数据处理都能依赖于一个稳定、正确的链接，从而避免数据不一致和不必要的转换。
 * 
 * @param imageUrl 当前画布上的图片 URL
 * @param messages 消息历史
 * @param sessionId 当前会话 ID
 * @param filePrefix 文件名前缀（如 'canvas', 'expand'）
 * @param skipBase64 是否跳过 base64Data 获取（默认 true，延迟到 API 调用时）
 * @returns 准备好的 Attachment 对象，失败返回 null
 */
export const prepareAttachmentForApi = async (
  imageUrl: string,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas',
  skipBase64: boolean = true
): Promise<Attachment | null> => {
  console.log('[prepareAttachmentForApi] 开始准备附件, imageUrl 类型:', isBase64Url(imageUrl) ? 'Base64' : isBlobUrl(imageUrl) ? 'Blob' : 'HTTP');

  try {
    // ✅ 步骤 1: 优先使用后端统一CONTINUITY API（如果sessionId可用）
    if (sessionId) {
      try {
        const headers: HeadersInit = {};
        const token = getAccessToken();
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        headers['Content-Type'] = 'application/json';

        const response = await fetch('/api/attachments/resolve-continuity', {
          method: 'POST',
          headers,
          credentials: 'include',
          body: JSON.stringify({
            activeImageUrl: imageUrl,
            sessionId: sessionId,
            messages: messages  // 可选，后端也可以从数据库查询
          })
        });

        if (response.ok) {
          const resolved = await response.json();
          const hasCloudUrl = resolved.status === 'completed' && resolved.url && isHttpUrl(resolved.url);
          console.log('[prepareAttachmentForApi] ✅ 后端CONTINUITY API解析成功:', {
            attachmentId: resolved.attachmentId,
            status: resolved.status,
            hasUrl: !!resolved.url,
            hasCloudUrl: hasCloudUrl, // ✅ 显示是否有云URL
            cloudUrl: hasCloudUrl ? resolved.url : null, // ✅ 显示云URL（如果有）
            urlType: resolved.url ? (isHttpUrl(resolved.url) ? 'HTTP' : '其他') : '无'
          });

          const reusedAttachment: Attachment = {
            id: resolved.attachmentId,
            mimeType: 'image/png', // 默认，可根据需要改进
            name: `${filePrefix}-${Date.now()}.png`,
            url: resolved.url,
            uploadStatus: resolved.status as 'pending' | 'uploading' | 'completed' | 'failed',
            uploadTaskId: resolved.taskId
          };

          // 如果已上传完成，直接返回
          if (resolved.status === 'completed' && resolved.url) {
            console.log('[prepareAttachmentForApi] ✅ 附件已上传完成，使用云URL');
            return reusedAttachment;
          }

          // 如果待上传，返回待上传状态
          console.log('[prepareAttachmentForApi] ✅ 附件待上传，返回待上传状态');
          return reusedAttachment;
        } else {
          console.log('[prepareAttachmentForApi] ⚠️ 后端CONTINUITY API返回错误:', response.status);
        }
      } catch (apiError) {
        console.warn('[prepareAttachmentForApi] ⚠️ 后端CONTINUITY API调用失败，降级到前端查找:', apiError);
      }
    }

    // ✅ 步骤 2: 降级方案 - 前端查找（向后兼容）
    const found = findAttachmentByUrl(imageUrl, messages);

    if (found) {
      console.log('[prepareAttachmentForApi] ✅ 前端查找找到历史附件');
      const { attachment: existingAttachment } = found;
      let finalUrl = existingAttachment.url;
      let finalUploadStatus = existingAttachment.uploadStatus || 'pending';

      // 查询后端获取最新的云 URL
      const cloudResult = await tryFetchCloudUrl(
        sessionId,
        existingAttachment.id,
        finalUrl,
        finalUploadStatus
      );
      
      if (cloudResult) {
        finalUrl = cloudResult.url; // 修正 (FIX): 使用后端返回的权威云 URL
        finalUploadStatus = 'completed';
      }

      const reusedAttachment: Attachment = {
        id: uuidv4(),
        mimeType: existingAttachment.mimeType || 'image/png',
        name: existingAttachment.name || `${filePrefix}-${Date.now()}.png`,
        url: finalUrl, // 修正 (FIX): 权威 URL 存储在 `url` 字段
        uploadStatus: finalUploadStatus as 'pending' | 'uploading' | 'completed' | 'failed',
      };

      // 注意：对于 HTTP URL，不转换为 Base64（避免占用空间）
      // 后端会自己下载 HTTP URL，所以直接传递 URL 即可
      // 只有在没有 HTTP URL 的情况下（如 Blob URL），才需要转换为 Base64
      if (!skipBase64 && finalUrl && !isHttpUrl(finalUrl)) {
        // 只有非 HTTP URL（如 Blob URL）才转换为 Base64
        try {
          const base64Data = await urlToBase64(finalUrl);
          (reusedAttachment as any).base64Data = base64Data;
          reusedAttachment.tempUrl = base64Data;
          console.log('[prepareAttachmentForApi] ✅ 已设置 base64Data（非 HTTP URL）');
        } catch (base64Error) {
          console.warn('[prepareAttachmentForApi] ⚠️ 获取 base64Data 失败:', base64Error);
        }
      } else if (isHttpUrl(finalUrl)) {
        console.log('[prepareAttachmentForApi] ✅ HTTP URL，直接传递（后端会自己下载）');
      }
      
      console.log('[prepareAttachmentForApi] ✅ 复用历史附件完成, Cloud URL:', reusedAttachment.url);
      return reusedAttachment;
    }

    // 步骤 2: 未在历史中找到，根据 URL 类型直接处理
    console.log('[prepareAttachmentForApi] 未在历史中找到匹配附件，直接处理 URL');

    const attachmentId = uuidv4();
    const attachmentName = `${filePrefix}-${Date.now()}.png`;

    if (isBase64Url(imageUrl) || isBlobUrl(imageUrl)) {
        const mimeType = imageUrl.match(/^data:([^;]+);/)?.[1] || 'image/png';
        const base64Data = isBase64Url(imageUrl) ? imageUrl : await urlToBase64(imageUrl);
        // 对于本地数据，url 字段可以留空或设为 base64，但 uploadStatus 必须是 pending
        // 后续处理流程会负责上传并更新 url
        return {
            id: attachmentId,
            mimeType: mimeType,
            name: attachmentName,
            url: '', // 本地数据没有永久 URL
            uploadStatus: 'pending',
            base64Data: base64Data // 提供 base64 数据供立即使用
        } as Attachment;
    }

    if (isHttpUrl(imageUrl)) {
      // 如果是 HTTP URL，直接返回 URL（后端会自己下载，避免 Base64 占用空间）
      const attachment: Attachment = {
        id: attachmentId,
        mimeType: 'image/png', // 假设，可根据需要改进
        name: attachmentName,
        url: imageUrl, // 直接传递 HTTP URL，后端会自己下载
        uploadStatus: 'completed'
      };
      
      // 注意：对于 HTTP URL，不转换为 Base64（避免占用空间）
      // 后端会自己下载 HTTP URL
      console.log('[prepareAttachmentForApi] ✅ HTTP URL，直接传递（后端会自己下载）');
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
 * 2. 如果用户上传了附件 → 处理跨模式传递
 * 
 * 优化说明：
 * - 对于 Base64 URL，直接使用
 * - 对于 Blob URL，本地转换为 base64Data
 * - 对于 HTTP URL（云 URL），下载为 File 对象供 Google Files API 使用
 * 
 * @param attachments 用户上传的附件数组
 * @param activeImageUrl 当前画布上的图片 URL
 * @param messages 消息历史
 * @param sessionId 当前会话 ID
 * @param filePrefix 文件名前缀（如 'canvas', 'expand'）
 * @returns 处理后的附件数组
 */
/**
 * 处理用户上传的附件（简化版 - 后端统一处理架构）
 * 
 * 根据设计文档，前端职责：
 * - 文件选择
 * - 创建预览（Blob URL）
 * - 提交附件元数据给后端
 * 
 * 后端职责：
 * - 统一处理所有附件（用户上传、AI返回、CONTINUITY）
 * - 统一上传到云存储
 * - 统一管理云 URL
 * 
 * 此函数现在只做基本的元数据整理，不再进行：
 * - Base64 转换
 * - Blob URL 转换
 * - 文件上传
 * - URL 类型判断（后端会处理）
 */
export const processUserAttachments = async (
  attachments: Attachment[],
  activeImageUrl: string | null,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas'
): Promise<Attachment[]> => {
  // ============================================================
  // CONTINUITY LOGIC - 无新上传时使用画布图片
  // 调用后端 API 解析 CONTINUITY 附件
  // ============================================================
  if (attachments.length === 0 && activeImageUrl) {
    console.log(`[processUserAttachments] ✅ 触发 CONTINUITY LOGIC（无新上传）`);
    const prepared = await prepareAttachmentForApi(
      activeImageUrl,
      messages,
      sessionId,
      filePrefix,
      true // skipBase64: 后端会处理所有 URL 类型
    );
    if (prepared) {
      return [prepared];
    }
    return [];
  }

  // ============================================================
  // 处理用户上传的附件
  // 简化：只传递元数据，不做转换和上传
  // 后端会统一处理所有 URL 类型（Base64、Blob URL、HTTP URL）
  // ============================================================
  if (attachments.length > 0) {
    console.log(`[processUserAttachments] ✅ 处理用户上传的附件, 数量:`, attachments.length);
    
    // 只做基本的元数据整理，确保附件对象包含必要的字段
    // 后端 modes.py 会调用 AttachmentService 处理上传
    const processedAttachments = attachments.map((att, index) => {
      console.log(`[processUserAttachments] 附件[${index}] 元数据:`, {
        id: att.id?.substring(0, 8) + '...',
        urlType: att.url?.startsWith('blob:') ? 'Blob' : 
                 att.url?.startsWith('data:') ? 'Base64' : 
                 att.url?.startsWith('http') ? 'HTTP' : 'Other',
        uploadStatus: att.uploadStatus,
        hasFile: !!att.file,
        mimeType: att.mimeType,
        name: att.name
      });

      // 如果已有 file 对象，保留它（后端可能需要）
      // 但不再进行 Base64 转换，后端会处理
      if (att.file) {
        console.log(`[processUserAttachments] 附件[${index}] ✅ 保留 File 对象，后端会处理上传`);
        return att;
      }

      // 对于其他情况，直接传递元数据
      // 后端会处理 Base64、Blob URL、HTTP URL 等所有类型
      console.log(`[processUserAttachments] 附件[${index}] ✅ 传递元数据给后端处理`);
      return {
        ...att,
        // 确保有 URL（可能是 Blob URL、Base64 或 HTTP URL）
        url: att.url || att.tempUrl || '',
        // 保持原始状态，后端会处理
        uploadStatus: att.uploadStatus || 'pending' as const
      };
    });

    return processedAttachments;
  }

  return [];
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
  context: { sessionId: string; modelMessageId: string; storageId?: string },
  filePrefix: string
): Promise<{ 
  displayAttachment: Attachment; 
  dbAttachmentPromise: Promise<Attachment>; 
}> => {
  const attachmentId = uuidv4();
  const filename = res.filename || `${filePrefix}-${Date.now()}.png`;
  let displayUrl = res.url;
  const originalUrl = res.url; // 保存原始 URL，用于跨模式查找

  // ✅ 详细日志：记录AI返回的原始URL类型
  const originalUrlType = isBase64Url(originalUrl) ? 'Base64 Data URL (AI原始返回)' :
                         isBlobUrl(originalUrl) ? 'Blob URL' :
                         isHttpUrl(originalUrl) ? 'HTTP临时URL (AI原始返回)' :
                         '未知类型';
  console.log('[processMediaResult] ========== 处理AI返回的媒体结果 ==========');
  console.log('[processMediaResult] AI返回的原始URL:', {
    urlType: originalUrlType,
    url: originalUrl.length > 80 ? originalUrl.substring(0, 80) + '...' : originalUrl,
    mimeType: res.mimeType,
    filename: filename
  });

  // 根据 URL 类型处理显示 URL
  if (isHttpUrl(res.url)) {
    // HTTP URL（临时 URL）- 下载后创建 Blob URL 用于显示
    console.log('[processMediaResult] HTTP URL 检测到，将下载并转换为 Blob URL 用于显示');
    const response = await fetch(res.url);
    const blob = await response.blob();
    displayUrl = URL.createObjectURL(blob);
    console.log('[processMediaResult] ✅ 已创建 Blob URL 用于显示:', displayUrl.substring(0, 50) + '...');
  } else {
    console.log('[processMediaResult] 使用原始URL作为显示URL (Base64或已处理)');
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

  // ✅ 详细日志：记录显示附件使用的URL类型
  const displayUrlType = isBase64Url(displayUrl) ? 'Base64 Data URL' :
                        isBlobUrl(displayUrl) ? 'Blob URL (处理后的本地URL)' :
                        isHttpUrl(displayUrl) ? 'HTTP URL' :
                        '未知类型';
  console.log('[processMediaResult] 显示附件URL类型:', {
    attachmentId: attachmentId.substring(0, 8) + '...',
    displayUrlType: displayUrlType,
    displayUrl: displayUrl.length > 80 ? displayUrl.substring(0, 80) + '...' : displayUrl,
    originalUrl: originalUrl.length > 80 ? originalUrl.substring(0, 80) + '...' : originalUrl,
    source: displayUrlType === 'Base64 Data URL' ? 'AI返回的原始Base64 (直接使用)' :
            displayUrlType === 'Blob URL (处理后的本地URL)' ? '处理后的Blob URL (从HTTP临时URL转换)' :
            '其他类型',
    note: '前端显示将使用 displayUrl，原始URL保存在 tempUrl 中'
  });

  // 创建异步上传任务
  const dbAttachmentPromise = (async (): Promise<Attachment> => {
    // 使用统一函数转换为 File
    const file = await sourceToFile(res.url, filename, res.mimeType);

    const result = await storageUpload.uploadFileAsync(file, {
      sessionId: context.sessionId,
      messageId: context.modelMessageId,
      attachmentId: attachmentId,
      storageId: context.storageId,
    });

    const dbAttachment: Attachment = {
      id: attachmentId,
      mimeType: res.mimeType,
      name: filename,
      url: isHttpUrl(originalUrl) ? originalUrl : '',  // ✅ 保存 AI 临时 URL 作为备选（直到上传完成）
      tempUrl: isHttpUrl(originalUrl) ? originalUrl : undefined, // ✅ 保存 HTTP URL 用于跨模式查找
      uploadStatus: result.taskId ? ('pending' as const) : ('failed' as const),
      uploadTaskId: result.taskId || undefined,
    };

    // ✅ 详细日志：记录数据库附件URL类型
    console.log('[processMediaResult] 数据库附件URL类型:', {
      attachmentId: attachmentId.substring(0, 8) + '...',
      url: dbAttachment.url ? (dbAttachment.url.length > 60 ? dbAttachment.url.substring(0, 60) + '...' : dbAttachment.url) : '空URL',
      urlType: dbAttachment.url ? (isHttpUrl(dbAttachment.url) ? 'HTTP临时URL (AI原始返回，等待上传完成)' : '空URL') : '空URL',
      uploadStatus: dbAttachment.uploadStatus,
      uploadTaskId: dbAttachment.uploadTaskId ? dbAttachment.uploadTaskId.substring(0, 8) + '...' : 'N/A',
      tempUrl: dbAttachment.tempUrl ? (dbAttachment.tempUrl.length > 60 ? dbAttachment.tempUrl.substring(0, 60) + '...' : dbAttachment.tempUrl) : 'N/A',
      note: '上传完成后，url将更新为云存储URL，tempUrl保留原始URL用于查找'
    });
    console.log('[processMediaResult] ============================================');

    return dbAttachment;
  })();

  return { displayAttachment, dbAttachmentPromise };
};

/**
 * 通过后端上传图片 URL 到云存储（推荐用于远程 URL）
 * 后端会下载图片并上传到云存储，避免前端下载
 * 
 * @param imageUrl 图片 URL（远程 URL 或 Base64）
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
    console.log('[submitUploadTaskToBackend] 提交上传任务到后端:', {
      filename,
      sessionId: sessionId.substring(0, 8) + '...',
      messageId: messageId.substring(0, 8) + '...',
      attachmentId: attachmentId.substring(0, 8) + '...',
      urlType: imageUrl.startsWith('data:') ? 'Base64' : imageUrl.startsWith('blob:') ? 'Blob' : 'Remote'
    });

    // 如果是 Base64 URL，需要先转换为 File 再上传
    if (imageUrl.startsWith('data:')) {
      const file = await base64ToFile(imageUrl, filename);
      const result = await storageUpload.uploadFileAsync(file, {
        sessionId,
        messageId,
        attachmentId
      });
      console.log('[submitUploadTaskToBackend] Base64 上传任务已提交:', result.taskId);
      return result.taskId;
    }

    // 如果是 Blob URL，需要先 fetch 转换为 File 再上传
    if (imageUrl.startsWith('blob:')) {
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      const file = new File([blob], filename, { type: blob.type || 'image/png' });
      const result = await storageUpload.uploadFileAsync(file, {
        sessionId,
        messageId,
        attachmentId
      });
      console.log('[submitUploadTaskToBackend] Blob URL 上传任务已提交:', result.taskId);
      return result.taskId;
    }

    // 远程 URL：通过后端下载并上传
    const result = await storageUpload.uploadFromUrlViaBackend(imageUrl, filename, {
      sessionId,
      messageId,
      attachmentId
    });
    console.log('[submitUploadTaskToBackend] 远程 URL 上传任务已提交:', result.taskId);
    return result.taskId;

  } catch (error) {
    console.error('[submitUploadTaskToBackend] 提交上传任务失败:', error);
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
  
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return uploadStatus === 'completed' 
      ? '云存储URL (已上传完成)' 
      : 'HTTP临时URL (AI原始返回)';
  }
  
  return '未知类型';
};

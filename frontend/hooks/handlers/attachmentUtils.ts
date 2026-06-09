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
 * - Blob URL: 浏览器本地 URL（blob:xxx，页面关闭后失效；仅兼容旧附件）
 * - 远程临时 URL: API 返回的临时 URL（会过期）
 */
import { reportError } from '../../utils/globalErrorHandler';
import { v4 as uuidv4 } from 'uuid';
import { Attachment, Message } from '../../types/types';
import { storageUpload } from '../../services/storage/storageUpload';
import { fetchWithTimeout, readJsonResponse } from '../../services/http';
import {
  getPreferredAttachmentUrl,
  getLocalBlobAttachmentId,
  isBlobAttachmentUrl,
  isDataAttachmentUrl,
  isHttpAttachmentUrl,
  isLocalBlobAttachmentUrl,
} from '../../utils/attachmentUrl';

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
  return isHttpAttachmentUrl(url);
};

/**
 * 检查 URL 是否是 Blob URL
 */
export const isBlobUrl = (url: string | undefined): boolean => {
  return isBlobAttachmentUrl(url);
};

/**
 * 检查 URL 是否是 Base64 Data URL
 */
export const isBase64Url = (url: string | undefined): boolean => {
  return isDataAttachmentUrl(url);
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

    // 使用统一函数转换为 File
    const file = await sourceToFile(imageSource, finalFilename);

    // 上传到云存储
    const result = await storageUpload.uploadFile(file);

    if (result.success && result.url) {
      return result.url;
    }
    reportError('上传云存储失败', new Error(result.error || 'upload returned no url'));
    return '';
  } catch (error) {
    reportError('上传云存储异常', error);
    return '';
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
 * - HTTP URL：通过后端代理 /api/storage/download 下载（解决 CORS）
 *
 * @param source 图片来源（File 对象或 URL 字符串）
 * @param filename 目标文件名
 * @param mimeType 可选的 MIME 类型
 * @returns File 对象
 * @throws 如果下载失败，抛出错误
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

  // HTTP URL: 通过后端代理下载(Sprint 2 PR-4: 删除冗余的"直接下载"+"urlToFile"
  // fallback——这两个 strategy 也是 fetch-based,被 CORS block 时与代理同样失败,
  // 所以多层 fallback 提供不了实际韧性。后端代理是 AI provider URL 的唯一可靠路径)
  const proxyUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
  const response = await fetch(proxyUrl);
  if (!response.ok) {
    throw new Error(
      `[sourceToFile] 后端代理下载失败: HTTP ${response.status}, URL: ${url.substring(0, 100)}...`
    );
  }
  const blob = await response.blob();
  return new File([blob], filename, { type: mimeType || blob.type || 'image/png' });
};

// ============================================================
// URL 转换工具函数
// ============================================================

/**
 * 将 Blob/File 对象转换为 Base64 Data URL
 *
 * 特点：
 * - 不依赖 Blob URL，避免因 URL.revokeObjectURL 导致读取失败
 * - 直接使用 FileReader 读取文件内容
 * - 接受 Blob | File（File extends Blob），便于直接传入 fetch().blob() 结果
 *
 * @param input Blob 或 File 对象
 * @returns Base64 Data URL（含 `data:<mime>;base64,` 前缀）
 * @throws 如果 input 为空或读取失败
 */
export const fileToBase64 = async (input: Blob | File): Promise<string> => {
  if (!input) {
    throw new Error('[fileToBase64] Blob/File is required');
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = (error) => reject(new Error(`[fileToBase64] FileReader failed: ${error}`));
    reader.readAsDataURL(input);
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
    const response = await fetchWithTimeout(`/api/attachments/${attachmentId}/cloud-url`, {
      method: 'GET',
      withAuth: true,
      skipAuth: true,
    });

    if (!response.ok) {
      // 401/403 统一提示登录失效，避免成为 token 状态 oracle；HTTP 状态码只入日志
      if (response.status === 401 || response.status === 403) {
        reportError('登录已过期，请重新登录', new Error('auth_expired'));
      }
      return null;
    }

    return await readJsonResponse(response);
  } catch (error) {
    reportError('附件状态查询异常', error);
    return null;
  }
};

/** Backend response shape for /api/attachments/resolve-continuity */
interface ContinuityResolveResponse {
  attachmentId: string;
  mimeType?: string;
  filename?: string;
  url?: string;
  status?: 'pending' | 'uploading' | 'completed' | 'failed';
  taskId?: string;
  messageId?: string;
  sessionId?: string;
  userId?: string;
  size?: number;
  cloudUrl?: string;
  createdAt?: number;
}

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
 * @returns 准备好的 Attachment 对象，失败返回 null
 */
export const prepareAttachmentForApi = async (
  imageUrl: string,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas'
): Promise<Attachment | null> => {
  if (!imageUrl) return null;
  if (isLocalBlobAttachmentUrl(imageUrl)) return null;

  // Sprint 2 PR-2: CONTINUITY 解析完全交给后端权威实现
  // 不再做前端降级查找/转换 — 删除原 ~187 行三层 fallback
  // (后端 API + findAttachmentByUrl + urlToBase64 + 新建)
  try {
    // 简化消息历史,只发后端 lookup 必要字段(避免发送整个 base64 payload)
    const simplifiedMessages =
      messages?.map((m) => ({
        id: m.id,
        role: m.role,
        attachments: m.attachments?.map((att) => ({
          id: att.id,
          url: att.url,
          tempUrl: att.tempUrl,
          uploadStatus: att.uploadStatus,
          mimeType: att.mimeType,
        })),
      })) || [];

    const response = await fetchWithTimeout('/api/attachments/resolve-continuity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      withAuth: true,
      skipAuth: true,
      body: JSON.stringify({
        activeImageUrl: imageUrl,
        sessionId: sessionId,
        messages: simplifiedMessages,
      }),
    });

    if (response.status === 404) {
      // 后端找不到匹配的附件 — 这是正常情况,callers 已处理 null
      return null;
    }
    if (!response.ok) {
      reportError('附件解析失败', new Error(`HTTP ${response.status}`));
      return null;
    }

    const resolved = await readJsonResponse<ContinuityResolveResponse>(response);
    return {
      id: resolved.attachmentId,
      mimeType: resolved.mimeType || 'image/png',
      name: resolved.filename || `${filePrefix}-${Date.now()}.png`,
      url: resolved.url || '',
      uploadStatus: (resolved.status || 'pending') as
        | 'pending'
        | 'uploading'
        | 'completed'
        | 'failed',
      uploadTaskId: resolved.taskId,
      messageId: resolved.messageId,
      sessionId: resolved.sessionId,
      userId: resolved.userId,
      size: resolved.size,
      cloudUrl: resolved.cloudUrl,
      createdAt: resolved.createdAt,
    };
  } catch (err) {
    reportError('准备附件失败', err);
    return null;
  }
};

const findLocalBlobAttachmentInMessages = (
  localBlobUrl: string,
  messages: Message[]
): Attachment | null => {
  const attachmentId = getLocalBlobAttachmentId(localBlobUrl);
  if (!attachmentId) return null;

  for (const message of messages) {
    const attachment = message.attachments?.find((att) => att.id === attachmentId);
    if (attachment) return attachment;
  }

  return null;
};

const normalizeAttachmentForMediaRequest = async (att: Attachment): Promise<Attachment> => {
  const preferredUrl = getPreferredAttachmentUrl(att);
  const file = att.file;
  const shouldInlineFile = file && (!preferredUrl || isBlobUrl(preferredUrl) || isBlobUrl(att.url));

  if (shouldInlineFile) {
    try {
      const base64Url = await fileToBase64(file);
      return {
        ...att,
        url: base64Url,
        tempUrl: base64Url,
      };
    } catch (e) {
      reportError('图片转换失败', e);
      return att;
    }
  }

  if (isHttpUrl(preferredUrl || '')) {
    return { ...att, url: preferredUrl || att.url };
  }

  if (isBase64Url(preferredUrl || '')) {
    return { ...att, url: preferredUrl || att.url };
  }

  if (att.file) {
    return preferredUrl ? { ...att, url: preferredUrl } : att;
  }

  return {
    ...att,
    url: preferredUrl || '',
    uploadStatus: att.uploadStatus || ('pending' as const),
  };
};

const normalizeAttachmentsForMediaRequest = async (
  attachments: Attachment[]
): Promise<Attachment[]> => Promise.all(attachments.map(normalizeAttachmentForMediaRequest));

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
 * - 文件选择与预览（File 交给共享 CachedImage/mediaCache 处理）
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
  if (attachments.length === 0 && activeImageUrl && isLocalBlobAttachmentUrl(activeImageUrl)) {
    const localAttachment = findLocalBlobAttachmentInMessages(activeImageUrl, messages);
    return localAttachment ? normalizeAttachmentsForMediaRequest([localAttachment]) : [];
  }

  // ✅ 1. 如果有画布图片且没有新上传附件，使用画布图片（CONTINUITY LOGIC）
  if (attachments.length === 0 && activeImageUrl) {
    const prepared = await prepareAttachmentForApi(activeImageUrl, messages, sessionId, filePrefix);
    return prepared ? [prepared] : [];
  }

  // ✅ 2. 如果有新上传的附件，处理附件
  if (attachments.length > 0) {
    const processedAttachments = await normalizeAttachmentsForMediaRequest(attachments);

    // ✅ 3. 如果同时有画布图片，也添加（支持"附件 + 画布图片"组合）
    // 检查画布图片是否已经在附件中（避免重复）
    if (activeImageUrl && !isLocalBlobAttachmentUrl(activeImageUrl)) {
      const isCanvasImageInAttachments = processedAttachments.some((att) =>
        [att.url, att.tempUrl, att.cloudUrl, att.fileUri, getPreferredAttachmentUrl(att)].some(
          (url) => url === activeImageUrl
        )
      );

      if (!isCanvasImageInAttachments) {
        const canvasAttachment = await prepareAttachmentForApi(
          activeImageUrl,
          messages,
          sessionId,
          filePrefix
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
 * - HTTP URL：保留 URL 给渲染层加载；若有 cloudUrl 则优先使用稳定地址
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
  const displayUrl = res.cloudUrl || res.url;
  const uploadStatus = res.uploadStatus || (res.cloudUrl ? 'completed' : 'pending');

  // 创建用于 UI 显示的附件
  const displayAttachment: Attachment = {
    id: attachmentId,
    mimeType: res.mimeType,
    name: filename,
    url: displayUrl,
    tempUrl: originalUrl, // 保存原始 URL，用于跨模式查找
    uploadStatus,
    cloudUrl: res.cloudUrl,
    uploadTaskId: res.taskId,
    size: res.size,
    messageId: res.messageId,
    sessionId: res.sessionId,
    userId: res.userId,
    createdAt: res.createdAt,
  };

  // Sprint 2 PR-5: 后端在 image/video/audio mode 已自动创建 attachment 行并触发上传任务。
  // 但后端 modes.py 在 sessionId/messageId 缺失时会 graceful skip 持久化(如用户在
  // useSessions 还没建好 session 时立即发媒体请求),此时响应无 attachmentId。
  // 前端用 client-side uuid 作为 displayAttachment.id(line 727 已 fallback),
  // 只是 dbAttachment 不会真正落库——这是合理的 degraded mode,不该抛错。
  if (!res.attachmentId) {
    console.warn(
      `[processMediaResult] 后端响应缺少 attachmentId（${filePrefix} mode）— 可能是 sessionId/messageId 缺失导致后端 skip 持久化。前端用 client-side uuid 继续渲染,本次结果不会写库。`
    );
  }

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
        attachmentId,
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
        attachmentId,
      });
      return result.taskId || '';
    }

    // HTTP URL：通过后端下载并上传
    const result = await storageUpload.uploadFromUrlViaBackend(imageUrl, filename, {
      sessionId,
      messageId,
      attachmentId,
    });
    return result.taskId || '';
  } catch (error) {
    reportError('提交上传任务失败', error);
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
// getUrlType 抽离至 ./urlClassifier（< 800 行合规）
export { getUrlType } from './urlClassifier';

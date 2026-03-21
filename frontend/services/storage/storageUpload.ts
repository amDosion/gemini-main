/**
 * 云存储上传服务（混合方案）
 * 
 * 优先级：
 * 1. 后端 API（推荐）- 通过后端统一处理上传
 * 2. 前端直连（降级）- 后端不可用时直接调用云存储 API
 * 
 * 支持的存储提供商：
 * - 兰空图床 (Lsky Pro V2)
 * - 阿里云 OSS
 */

import { StorageConfig, StorageUploadResult, LskyConfig, AliyunOSSConfig } from '../../types/storage';
import { fetchWithTimeout, parseHttpError, readJsonResponse, requestJson } from '../http';

const API_BASE = '/api';

const stripTrailingSlash = (value: string): string => value.replace(/\/+$/, '');

/**
 * 云存储上传服务类
 */
export class StorageUploadService {
  private useBackend: boolean | null = null; // null = 未知, true = 可用, false = 不可用
  private uploadLogsSupported: boolean | null = null; // null = 未知, true = 支持, false = 不支持（404）

  /**
   * 检测后端 API 是否可用
   * 优化：如果已经确认后端可用，在短时间内不再重复检测
   */
  private lastCheckTime: number = 0;
  private readonly CHECK_INTERVAL = 30000; // 30秒内不重复检测

  private async checkBackendAvailable(): Promise<boolean> {
    // 如果已经确认后端不可用，直接返回
    if (this.useBackend === false) {
      return false;
    }

    // 如果已经确认后端可用，且在检测间隔内，直接返回 true
    if (this.useBackend === true && Date.now() - this.lastCheckTime < this.CHECK_INTERVAL) {
      return true;
    }

    try {
      const response = await fetchWithTimeout(`${API_BASE}/storage/configs`, {
        method: 'GET',
        withAuth: true,
        credentials: 'include',
      });

      const available = response.ok;

      if (this.useBackend !== available) {
        if (available) {
          console.log('✅ [StorageUpload] 后端 API 可用 - 使用后端上传');
        } else {
          console.warn('⚠️ [StorageUpload] 后端 API 不可用 - 降级到前端直连');
        }
        this.useBackend = available;
      }

      // 记录检测时间
      this.lastCheckTime = Date.now();

      return available;
    } catch (error) {
      // 检测超时或失败时，不永久标记后端不可用
      // 而是保持 null 状态，下次上传时重新检测
      console.warn('⚠️ [StorageUpload] 后端 API 检测失败，将重试');
      console.warn('错误详情:', error);
      // 不设置 this.useBackend = false，保持 null 状态
      return false;
    }
  }

  /**
   * 通过后端 API 上传文件
   */
  private async uploadViaBackend(
    file: File,
    storageId?: string
  ): Promise<StorageUploadResult> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      // ✅ Query 参数使用 camelCase（中间件自动转换为 snake_case）
      const url = storageId
        ? `${API_BASE}/storage/upload?storageId=${storageId}`
        : `${API_BASE}/storage/upload`;

      const response = await fetchWithTimeout(url, {
        method: 'POST',
        withAuth: true,
        credentials: 'include',
        body: formData,
        timeoutMs: 120000,
      });

      if (!response.ok) {
        const error = await parseHttpError(response, `上传失败: HTTP ${response.status}`);
        throw new Error(error.message);
      }

      const result = await readJsonResponse<any>(response);

      return {
        success: result.success,
        url: result.url,
        provider: result.provider,
      };
    } catch (error) {
      console.error('[StorageUpload] 后端上传失败:', error);
      throw error;
    }
  }

  /**
   * 直接上传到兰空图床
   */
  private async uploadToLskyDirect(
    file: File,
    config: LskyConfig
  ): Promise<StorageUploadResult> {
    try {
      console.log('[StorageUpload] 直接上传到兰空图床...');

      const formData = new FormData();
      formData.append('file', file, file.name);

      const uploadUrl = `${stripTrailingSlash(config.domain)}/api/v1/upload`;
      const authToken = config.token.startsWith('Bearer ')
        ? config.token
        : `Bearer ${config.token}`;

      const response = await fetch(uploadUrl, {
        method: 'POST',
        headers: {
          'Authorization': authToken,
          'Accept': 'application/json',
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`兰空图床上传失败: HTTP ${response.status}`);
      }

      const result = await response.json();

      if (result.status && result.data?.links?.url) {
        const imageUrl = result.data.links.url;
        console.log('[StorageUpload] 兰空图床上传成功:', imageUrl);

        return {
          success: true,
          url: imageUrl,
          provider: 'lsky',
        };
      } else {
        const errorMsg = result.message || '未知错误';
        throw new Error(`兰空图床上传失败: ${errorMsg}`);
      }
    } catch (error) {
      console.error('[StorageUpload] 兰空图床上传失败:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : '兰空图床上传失败',
      };
    }
  }

  /**
   * 直接上传到阿里云 OSS（前端直连）
   * 注意：需要配置 CORS 和签名
   */
  private async uploadToAliyunOSSDirect(
    file: File,
    config: AliyunOSSConfig
  ): Promise<StorageUploadResult> {
    try {
      console.log('[StorageUpload] 阿里云 OSS 前端直连暂不支持');
      console.log('[StorageUpload] 建议使用后端 API 或配置 STS 临时凭证');
      
      return {
        success: false,
        error: '阿里云 OSS 前端直连需要配置 STS 临时凭证，请使用后端 API',
      };
    } catch (error) {
      console.error('[StorageUpload] 阿里云 OSS 上传失败:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : '阿里云 OSS 上传失败',
      };
    }
  }

  /**
   * 前端直连上传（降级方案）
   */
  private async uploadDirect(
    file: File,
    config: StorageConfig
  ): Promise<StorageUploadResult> {
    console.log(`[StorageUpload] 使用前端直连上传 (${config.provider})`);

    if (config.provider === 'lsky') {
      return this.uploadToLskyDirect(file, config.config as LskyConfig);
    } else if (config.provider === 'aliyun-oss') {
      return this.uploadToAliyunOSSDirect(file, config.config as AliyunOSSConfig);
    } else {
      return {
        success: false,
        error: `不支持的存储类型: ${config.provider}`,
      };
    }
  }

  /**
   * 上传文件到云存储（混合方案）
   * 
   * @param file 要上传的文件
   * @param storageId 存储配置 ID（可选，不指定则使用当前激活的配置）
   * @returns 上传结果，包含图片 URL
   */
  async uploadFile(
    file: File,
    storageId?: string
  ): Promise<StorageUploadResult> {
    try {
      // 1. 检测后端是否可用
      const backendAvailable = await this.checkBackendAvailable();

      // 2. 如果后端可用，优先使用后端 API
      if (backendAvailable) {
        // 直接使用后端 API 上传，不降级到前端直连
        // 因为前端直连兰空图床会遇到 CORS 问题
        return await this.uploadViaBackend(file, storageId);
      }

      // 3. 后端不可用，返回错误提示
      // 不再降级到前端直连，因为前端直连兰空图床会遇到 CORS 问题
      console.warn('[StorageUpload] 后端 API 不可用，无法上传');
      return {
        success: false,
        error: '后端服务不可用，请确保后端服务正在运行',
      };

    } catch (error) {
      console.error('[StorageUpload] 上传失败:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : '上传失败',
      };
    }
  }

  /**
   * 上传 Blob 到云存储
   * 
   * @param blob Blob 对象
   * @param filename 文件名
   * @param storageId 存储配置 ID（可选）
   * @returns 上传结果
   */
  async uploadBlob(
    blob: Blob,
    filename: string,
    storageId?: string
  ): Promise<StorageUploadResult> {
    const file = new File([blob], filename, { type: blob.type });
    return this.uploadFile(file, storageId);
  }

  /**
   * 上传 Base64 图片到云存储
   * 
   * @param base64 Base64 编码的图片数据
   * @param filename 文件名
   * @param storageId 存储配置 ID（可选）
   * @returns 上传结果
   */
  async uploadBase64(
    base64: string,
    filename: string,
    storageId?: string
  ): Promise<StorageUploadResult> {
    try {
      // 将 Base64 转换为 Blob
      const response = await fetch(base64);
      const blob = await response.blob();
      
      return this.uploadBlob(blob, filename, storageId);
    } catch (error) {
      console.error('[StorageUpload] Base64 转换失败:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Base64 转换失败',
      };
    }
  }

  /**
   * 上传图片 URL 到云存储（先下载再上传）
   * 
   * @param imageUrl 图片 URL
   * @param filename 文件名
   * @param storageId 存储配置 ID（可选）
   * @returns 上传结果
   */
  async uploadFromUrl(
    imageUrl: string,
    filename: string,
    storageId?: string
  ): Promise<StorageUploadResult> {
    try {
      // 如果是 blob: 或 data: URL，直接转换
      if (imageUrl.startsWith('blob:') || imageUrl.startsWith('data:')) {
        return this.uploadBase64(imageUrl, filename, storageId);
      }

      // 如果是 HTTP URL，先下载
      const response = await fetch(imageUrl);
      if (!response.ok) {
        throw new Error(`下载图片失败: HTTP ${response.status}`);
      }

      const blob = await response.blob();
      return this.uploadBlob(blob, filename, storageId);
    } catch (error) {
      console.error('[StorageUpload] 从 URL 上传失败:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : '从 URL 上传失败',
      };
    }
  }

  /**
   * 测试存储配置是否可用
   * 
   * @param config 存储配置
   * @returns 测试结果
   */
  async testConfig(config: StorageConfig): Promise<{
    success: boolean;
    message: string;
  }> {
    try {
      // 创建一个 1x1 的测试图片
      const canvas = document.createElement('canvas');
      canvas.width = 1;
      canvas.height = 1;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, 1, 1);
      }

      const blob = await new Promise<Blob>((resolve) => {
        canvas.toBlob((b) => resolve(b!), 'image/png');
      });

      const testFile = new File([blob], 'test.png', { type: 'image/png' });
      const result = await this.uploadFile(testFile, config.id);

      if (result.success) {
        return {
          success: true,
          message: '配置测试成功！',
        };
      } else {
        return {
          success: false,
          message: result.error || '配置测试失败',
        };
      }
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error ? error.message : '配置测试失败',
      };
    }
  }

  /**
   * 异步上传文件到云存储（不阻塞前端）
   * 
   * 前端提交文件后立即返回，后端在后台处理上传并更新数据库
   * 
   * @param file 要上传的文件
   * @param options 额外选项
   * @returns 上传任务信息
   */
  async uploadFileAsync(
    file: File,
    options: {
      sessionId: string;
      messageId: string;
      attachmentId: string;
      storageId?: string;
    }
  ): Promise<{
    taskId: string;
    attachmentId: string;
    status: 'pending' | 'uploading' | 'completed' | 'failed';
    message?: string;
    enqueued?: boolean;
    enqueueError?: string | null;
    queuePosition?: number;
  }> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const params = new URLSearchParams();
      // ✅ Query 参数使用 camelCase（中间件自动转换为 snake_case）
      params.append('sessionId', options.sessionId);
      params.append('messageId', options.messageId);
      params.append('attachmentId', options.attachmentId);
      if (options.storageId) {
        params.append('storageId', options.storageId);
      }

      const result = await requestJson<any>(`${API_BASE}/storage/upload-async?${params.toString()}`, {
        method: 'POST',
        withAuth: true,
        credentials: 'include',
        body: formData,
        timeoutMs: 120000,
        errorMessage: '创建上传任务失败',
      });
      console.log('[StorageUpload] 异步上传任务已创建:', result.taskId);
      if (result.enqueued === false) {
        console.warn('[StorageUpload] 任务创建成功但 Redis 入队失败，将依赖后端启动补偿/手动补偿:', result.enqueueError);
      }
      
      return {
        taskId: result.taskId,
        attachmentId: result.attachmentId,
        status: result.status,
        message: result.message,
        enqueued: result.enqueued,
        enqueueError: result.enqueueError,
        queuePosition: result.queuePosition
      };
    } catch (error) {
      console.error('[StorageUpload] 创建异步上传任务失败:', error);
      throw error;
    }
  }

  /**
   * 通过后端上传图片 URL（推荐用于扩图）
   * 后端会下载图片并上传到云存储，避免前端下载
   * 
   * @param imageUrl 图片 URL（DashScope 临时 URL）
   * @param filename 文件名
   * @param options 额外选项
   * @returns 上传任务信息
   */
  async uploadFromUrlViaBackend(
    imageUrl: string,
    filename: string,
    options?: {
      sessionId?: string;
      storageId?: string;
      messageId?: string;
      attachmentId?: string;
    }
  ): Promise<{
    taskId: string;
    status: 'pending' | 'uploading' | 'completed' | 'failed';
    message?: string;
    enqueued?: boolean;
    enqueueError?: string | null;
    queuePosition?: number;
  }> {
    try {
      const result = await requestJson<any>(`${API_BASE}/storage/upload-from-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        withAuth: true,
        credentials: 'include',
        timeoutMs: 30000,
        errorMessage: '创建上传任务失败',
        body: JSON.stringify({
          url: imageUrl,
          filename,
          sessionId: options?.sessionId,
          storageId: options?.storageId,
          messageId: options?.messageId,
          attachmentId: options?.attachmentId
        })
      });
      console.log('[StorageUpload] 上传任务已创建:', result.taskId);
      if (result.enqueued === false) {
        console.warn('[StorageUpload] 任务创建成功但 Redis 入队失败，将依赖后端启动补偿/手动补偿:', result.enqueueError);
      }

      return {
        taskId: result.taskId,
        status: result.status,
        message: result.message,
        enqueued: result.enqueued,
        enqueueError: result.enqueueError,
        queuePosition: result.queuePosition
      };
    } catch (error) {
      console.error('[StorageUpload] 创建上传任务失败:', error);
      throw error;
    }
  }

  /**
   * 查询上传任务状态
   * 
   * @param taskId 任务 ID
   * @returns 任务状态信息
   */
  async getUploadTaskStatus(taskId: string): Promise<{
    taskId: string;
    status: 'pending' | 'uploading' | 'completed' | 'failed';
    targetUrl?: string;
    errorMessage?: string;
    createdAt?: number;
    completedAt?: number;
  }> {
    try {
      const result = await requestJson<any>(`${API_BASE}/storage/upload-status/${taskId}`, {
        withAuth: true,
        credentials: 'include',
        errorMessage: '查询上传状态失败',
      });
      
      return {
        taskId: result.id,
        status: result.status,
        targetUrl: result.targetUrl,
        errorMessage: result.errorMessage,
        createdAt: result.createdAt,
        completedAt: result.completedAt
      };
    } catch (error) {
      console.error('[StorageUpload] 查询上传状态失败:', error);
      throw error;
    }
  }

  /**
   * 获取上传任务日志（后端写入 Redis）
   */
  async getUploadTaskLogs(taskId: string, tail: number = 200): Promise<any[]> {
    if (this.uploadLogsSupported === false) {
      return [];
    }
    const response = await fetchWithTimeout(`${API_BASE}/storage/upload-logs/${taskId}?tail=${tail}`, {
      withAuth: true,
      credentials: 'include',
    });
    if (response.status === 404) {
      // 后端未更新/路由未注册：避免在轮询里刷屏
      this.uploadLogsSupported = false;
      console.warn('[StorageUpload] /storage/upload-logs 返回 404：后端可能仍是旧版本，已停止拉取任务日志');
      return [];
    }
    if (!response.ok) {
      const error = await parseHttpError(response, `获取上传日志失败: HTTP ${response.status}`);
      throw new Error(error.message);
    }
    const result = await readJsonResponse<any>(response);
    this.uploadLogsSupported = true;
    return Array.isArray(result.logs) ? result.logs : [];
  }

  /**
   * 轮询上传任务直到完成
   * 
   * @param taskId 任务 ID
   * @param maxRetries 最大重试次数（默认 60 次，即 2 分钟）
   * @param interval 轮询间隔（毫秒，默认 2000ms）
   * @returns 最终的图片 URL
   */
  async pollUploadTask(
    taskId: string,
    maxRetries: number = 60,
    interval: number = 2000
  ): Promise<string> {
    for (let i = 0; i < maxRetries; i++) {
      await new Promise(resolve => setTimeout(resolve, interval));

      try {
        const status = await this.getUploadTaskStatus(taskId);

        if (status.status === 'completed' && status.targetUrl) {
          console.log('[StorageUpload] 上传完成:', status.targetUrl);
          return status.targetUrl;
        } else if (status.status === 'failed') {
          throw new Error(status.errorMessage || '上传失败');
        }

        // 继续轮询
        console.log(`[StorageUpload] 上传中... (${i + 1}/${maxRetries})`);
      } catch (error) {
        console.error('[StorageUpload] 轮询出错:', error);
        throw error;
      }
    }

    throw new Error('上传超时（2分钟）');
  }
}

// 导出单例
export const storageUpload = new StorageUploadService();

// 添加 String.prototype.rstrip 扩展（如果不存在）
declare global {
  interface String {
    rstrip(chars: string): string;
  }
}

if (!String.prototype.rstrip) {
  String.prototype.rstrip = function(chars: string): string {
    let str = this.toString();
    while (str.endsWith(chars)) {
      str = str.slice(0, -chars.length);
    }
    return str;
  };
}

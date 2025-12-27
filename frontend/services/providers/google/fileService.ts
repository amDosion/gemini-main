
import { createGoogleClient } from "./utils";
import { Attachment } from "../../../types/types";

/**
 * Google Files API 缓存条目
 * 用于避免重复上传相同的图片
 */
interface FileCacheEntry {
  googleFileUri: string;
  mimeType: string;
  uploadedAt: number;
  expiresAt: number; // Google 文件 48 小时后过期
}

/**
 * Google Files API 服务
 * 
 * 功能：
 * 1. 上传文件到 Google AI Studio
 * 2. 缓存已上传的文件 URI，避免重复上传
 * 3. 自动处理文件过期
 * 
 * 优势（相比 Base64）：
 * - 减少约 33% 的数据传输量
 * - 降低内存占用
 * - 支持更大的文件（最大 2GB）
 */
export class GoogleFileService {
  // 文件缓存：key 为文件内容的 hash 或 URL
  private fileCache: Map<string, FileCacheEntry> = new Map();
  
  // Google 文件有效期：48 小时
  private readonly FILE_TTL_MS = 48 * 60 * 60 * 1000;
  
  // 缓存清理间隔：1 小时
  private cleanupInterval: ReturnType<typeof setInterval> | null = null;

  constructor() {
    // 启动定期清理过期缓存
    this.startCleanupInterval();
  }

  /**
   * 启动定期清理过期缓存的定时器
   */
  private startCleanupInterval(): void {
    if (this.cleanupInterval) return;
    
    this.cleanupInterval = setInterval(() => {
      this.cleanupExpiredCache();
    }, 60 * 60 * 1000); // 每小时清理一次
  }

  /**
   * 清理过期的缓存条目
   */
  private cleanupExpiredCache(): void {
    const now = Date.now();
    let cleaned = 0;
    
    for (const [key, entry] of this.fileCache.entries()) {
      if (entry.expiresAt < now) {
        this.fileCache.delete(key);
        cleaned++;
      }
    }
    
    if (cleaned > 0) {
      console.log(`[GoogleFileService] 清理了 ${cleaned} 个过期缓存条目`);
    }
  }

  /**
   * 生成缓存 key
   * 优先使用云存储 URL（稳定），其次使用附件 ID
   */
  private getCacheKey(att: Attachment): string {
    // 优先使用云存储 URL 作为 key（最稳定）
    if (att.url && att.url.startsWith('http')) {
      return `url:${att.url}`;
    }
    if (att.tempUrl && att.tempUrl.startsWith('http')) {
      return `url:${att.tempUrl}`;
    }
    // 使用附件 ID
    return `id:${att.id}`;
  }

  /**
   * 检查缓存中是否有有效的 Google 文件 URI
   */
  public getCachedFileUri(att: Attachment): string | null {
    const key = this.getCacheKey(att);
    const entry = this.fileCache.get(key);
    
    if (!entry) return null;
    
    // 检查是否过期（提前 1 小时失效，避免边界情况）
    const safeExpiryTime = entry.expiresAt - 60 * 60 * 1000;
    if (Date.now() > safeExpiryTime) {
      this.fileCache.delete(key);
      console.log(`[GoogleFileService] 缓存已过期: ${key}`);
      return null;
    }
    
    console.log(`[GoogleFileService] ✅ 命中缓存: ${key}`);
    return entry.googleFileUri;
  }

  /**
   * 将文件 URI 添加到缓存
   */
  private setCachedFileUri(att: Attachment, googleFileUri: string, mimeType: string): void {
    const key = this.getCacheKey(att);
    const now = Date.now();
    
    this.fileCache.set(key, {
      googleFileUri,
      mimeType,
      uploadedAt: now,
      expiresAt: now + this.FILE_TTL_MS
    });
    
    console.log(`[GoogleFileService] 已缓存: ${key} -> ${googleFileUri.substring(0, 50)}...`);
  }

  /**
   * Uploads a file to Google AI Studio via the Files API.
   * Handles the upload process and polls for the file to become ACTIVE.
   */
  public async uploadFile(file: File, apiKey: string, baseUrl: string): Promise<string> {
    const ai = createGoogleClient(apiKey, baseUrl);
    
    console.log(`[GoogleFileService] Uploading ${file.name} (${file.type})...`);

    try {
        const response = await ai.files.upload({
          file: file,
          config: { displayName: file.name, mimeType: file.type }
        });
        
        // @ts-ignore - SDK typing might vary between versions, handling both structure
        const fileData = response.file || response;
        const uri = fileData.uri;
        const name = fileData.name; // 'files/...'

        if (!uri) throw new Error("Failed to get file URI from Google API.");

        // Check state. If PROCESSING, poll until ACTIVE or FAILED.
        // Images are usually instant, but PDFs and Videos take time.
        if (fileData.state === 'PROCESSING') {
            console.log(`[GoogleFileService] File ${name} is processing. Polling...`);
            let state = fileData.state;
            let attempts = 0;
            const maxAttempts = 60; // 2 minutes approx

            while (state === 'PROCESSING' && attempts < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 2000));
                const check = await ai.files.get({ name: name });
                // @ts-ignore
                state = check.file?.state || check.state;
                attempts++;
                
                if (state === 'FAILED') {
                    throw new Error("File processing failed on Google servers.");
                }
            }

            if (state !== 'ACTIVE') {
                console.warn(`[GoogleFileService] File ${name} is not ACTIVE after polling (State: ${state}). Usage might fail.`);
            } else {
                console.log(`[GoogleFileService] File ${name} is now ACTIVE.`);
            }
        }

        return uri;
    } catch (error: any) {
        console.error("[GoogleFileService] Upload failed", error);
        throw new Error(`Failed to upload file: ${error.message || 'Unknown error'}`);
    }
  }

  /**
   * 上传附件到 Google Files API（带缓存）
   * 
   * 处理流程：
   * 1. 检查缓存，如果有有效的 URI 直接返回
   * 2. 从附件获取文件数据（Base64/Blob/URL）
   * 3. 上传到 Google Files API
   * 4. 缓存结果
   * 
   * @param att 附件对象
   * @param apiKey Google API Key
   * @param baseUrl API Base URL
   * @returns Google 文件 URI
   */
  public async uploadAttachment(
    att: Attachment, 
    apiKey: string, 
    baseUrl: string
  ): Promise<{ googleFileUri: string; mimeType: string }> {
    // 1. 检查缓存
    const cachedUri = this.getCachedFileUri(att);
    if (cachedUri) {
      return { googleFileUri: cachedUri, mimeType: att.mimeType };
    }

    // 2. 获取文件数据
    const file = await this.attachmentToFile(att);
    if (!file) {
      throw new Error(`无法从附件获取文件数据: ${att.id}`);
    }

    // 3. 上传到 Google
    const googleFileUri = await this.uploadFile(file, apiKey, baseUrl);

    // 4. 缓存结果
    this.setCachedFileUri(att, googleFileUri, file.type);

    return { googleFileUri, mimeType: file.type };
  }

  /**
   * 将附件转换为 File 对象
   * 
   * 支持的数据源（按优先级）：
   * 1. file 字段（原始 File 对象）- 最高效，无需转换
   * 2. base64Data 字段（CONTINUITY LOGIC 预处理）
   * 3. url 字段（Base64 Data URL）
   * 4. url 字段（HTTP URL，需要下载）
   * 5. tempUrl 字段（HTTP URL，备选）
   */
  private async attachmentToFile(att: Attachment): Promise<File | null> {
    const filename = att.name || `image-${Date.now()}.png`;
    const mimeType = att.mimeType || 'image/png';

    // 1. 优先使用原始 File 对象（最高效）
    if (att.file) {
      console.log('[GoogleFileService] ✅ 使用原始 File 对象');
      return att.file;
    }

    // 2. 使用 base64Data
    const base64Data = (att as any).base64Data;
    if (base64Data && base64Data.startsWith('data:')) {
      console.log('[GoogleFileService] 使用 base64Data 转换');
      return this.base64ToFile(base64Data, filename);
    }

    // 3. url 是 Base64 Data URL
    if (att.url && att.url.startsWith('data:')) {
      console.log('[GoogleFileService] 使用 url (Base64) 转换');
      return this.base64ToFile(att.url, filename);
    }

    // 4. url 是 HTTP URL，需要下载
    if (att.url && att.url.startsWith('http')) {
      console.log('[GoogleFileService] 从 HTTP URL 下载');
      return this.downloadToFile(att.url, filename, mimeType);
    }

    // 5. tempUrl 是 HTTP URL
    if (att.tempUrl && att.tempUrl.startsWith('http')) {
      console.log('[GoogleFileService] 从 tempUrl 下载');
      return this.downloadToFile(att.tempUrl, filename, mimeType);
    }

    console.warn('[GoogleFileService] 无法获取文件数据');
    return null;
  }

  /**
   * 将 Base64 Data URL 转换为 File 对象
   */
  private async base64ToFile(base64: string, filename: string): Promise<File> {
    const response = await fetch(base64);
    const blob = await response.blob();
    return new File([blob], filename, { type: blob.type });
  }

  /**
   * 从 HTTP URL 下载并转换为 File 对象
   */
  private async downloadToFile(url: string, filename: string, mimeType: string): Promise<File> {
    // 通过后端代理下载（解决 CORS）
    const proxyUrl = `/api/storage/download?url=${encodeURIComponent(url)}`;
    const response = await fetch(proxyUrl);
    
    if (!response.ok) {
      throw new Error(`下载失败: HTTP ${response.status}`);
    }
    
    const blob = await response.blob();
    return new File([blob], filename, { type: mimeType || blob.type });
  }

  /**
   * 批量上传附件到 Google Files API
   * 
   * @param attachments 附件数组
   * @param apiKey Google API Key
   * @param baseUrl API Base URL
   * @returns 带有 googleFileUri 的附件数组
   */
  public async uploadAttachments(
    attachments: Attachment[],
    apiKey: string,
    baseUrl: string
  ): Promise<Attachment[]> {
    const results = await Promise.all(
      attachments.map(async (att) => {
        try {
          // 只处理图片类型
          if (!att.mimeType?.startsWith('image/')) {
            return att;
          }

          const { googleFileUri, mimeType } = await this.uploadAttachment(att, apiKey, baseUrl);
          
          return {
            ...att,
            googleFileUri,
            googleFileExpiry: Date.now() + this.FILE_TTL_MS,
            mimeType
          };
        } catch (error) {
          console.error(`[GoogleFileService] 上传附件失败: ${att.id}`, error);
          // 上传失败时返回原附件，后续会回退到 Base64 方式
          return att;
        }
      })
    );

    return results;
  }

  /**
   * 获取缓存统计信息
   */
  public getCacheStats(): { size: number; entries: string[] } {
    return {
      size: this.fileCache.size,
      entries: Array.from(this.fileCache.keys())
    };
  }

  /**
   * 清空缓存
   */
  public clearCache(): void {
    this.fileCache.clear();
    console.log('[GoogleFileService] 缓存已清空');
  }
}

export const googleFileService = new GoogleFileService();

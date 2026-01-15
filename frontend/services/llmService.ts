
import { LLMFactory } from "./LLMFactory";
import { Message, ModelConfig, ChatOptions, Attachment, ApiProtocol, AppMode } from "../types/types";
import { StreamUpdate, ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "./providers/interfaces";
import { configService } from "./configurationService";
import { messagePreparer } from "./ai_chat/MessagePreparer";
import { streamManager } from "./stream/StreamManager";
import { UnifiedProviderClient } from "./providers/UnifiedProviderClient";

interface ModelCache {
  models: ModelConfig[];
  timestamp: number;
  providerId: string;
}

const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export class LLMService {
  private apiKey: string = '';
  private baseUrl: string = '';
  private protocol: ApiProtocol | null = null;  // ✅ 移除默认值，由后端配置决定
  private providerId: string = '';  // ✅ 移除默认值，由后端配置决定

  private modelCache = new Map<string, ModelCache>();

  private _cachedHistory: Message[] = [];
  private _cachedModelConfig: ModelConfig | null = null;
  private _cachedOptions: ChatOptions = { 
      enableSearch: false, 
      enableThinking: false, 
      enableCodeExecution: false,
      enableUrlContext: false, // Default false
      googleCacheMode: 'none', // Default No Cache
      imageAspectRatio: '1:1', 
      imageResolution: '1K',
      imageStyle: 'None',
      voiceName: 'Puck'
  };

  public setConfig(apiKey: string, baseUrl: string, protocol: ApiProtocol | null, providerId: string) {
    this.apiKey = apiKey ? apiKey.trim() : '';
    this.baseUrl = baseUrl ? baseUrl.trim().replace(/\/$/, '') : '';
    this.protocol = protocol;
    this.providerId = providerId || '';  // ✅ 不再默认为 'google'
  }

  /**
   * 检查是否已配置 Provider
   */
  public isConfigured(): boolean {
    return !!this.providerId && !!this.protocol;
  }

  private get currentProvider() {
      if (!this.protocol || !this.providerId) {
        throw new Error('Provider not configured. Please configure a provider in Settings → Profiles.');
      }
      return LLMFactory.getProvider(this.protocol, this.providerId);
  }

  public async getAvailableModels(useCache: boolean = true): Promise<ModelConfig[]> {
      // ✅ 如果未配置 Provider，返回空数组而不是发送请求
      if (!this.providerId) {
        console.warn('[LLMService] Provider not configured, returning empty models list');
        return [];
      }
      // ✅ 从后端 API 获取模型列表（后端会从数据库读取 API Key）
      const cacheKey = `${this.providerId}`;
      const now = Date.now();
      const cachedData = this.modelCache.get(cacheKey);

      if (useCache && cachedData && (now - cachedData.timestamp < CACHE_TTL)) {
          console.log(`[LLMService] Returning fresh cached models for ${this.providerId}`);
          return cachedData.models;
      }

      try {
          console.log(`[LLMService] Fetching models from backend API for ${this.providerId}`);

          // ✅ 调用后端 API：/api/models/{provider}
          // 后端会：
          // 1. 从 config_profiles 表读取当前用户激活的配置
          // 2. 获取对应的 API Key 和 BaseURL
          // 3. 调用提供商 API 获取模型列表
          // 4. 返回完整的 ModelConfig 数组
          const response = await fetch(`/api/models/${this.providerId}?useCache=${useCache}`, {
              method: 'GET',
              credentials: 'include', // 携带认证 Cookie
              headers: {
                  'Content-Type': 'application/json'
              }
          });

          if (!response.ok) {
              const errorText = await response.text().catch(() => '');
              throw new Error(`Backend API error: ${response.status} ${errorText}`);
          }

          const data = await response.json();
          const models = data.models || [];

          this.modelCache.set(cacheKey, {
              models: models,
              timestamp: now,
              providerId: this.providerId,
          });

          console.log(`[LLMService] Successfully fetched ${models.length} models from backend`);
          return models;
      } catch (error) {
          if (cachedData) {
              console.warn(`[LLMService] Failed to fetch models for ${this.providerId}. Returning expired cached data as fallback.`, error);
              return cachedData.models;
          }
          console.error(`[LLMService] Failed to fetch models for ${this.providerId} and no cached data available.`, error);
          throw error;
      }
  }

  public clearModelCache() {
      this.modelCache.clear();
      console.log("[LLMService] Model cache cleared.");
  }

  public async uploadFile(file: File): Promise<string> {
      return this.currentProvider.uploadFile(file, this.apiKey, this.baseUrl);
  }

  public startNewChat(history: Message[], modelConfig: ModelConfig, options?: ChatOptions) {
      this._cachedHistory = history;
      this._cachedModelConfig = modelConfig;
      if (options) {
          this._cachedOptions = options;
      }
  }
  
  public async *sendMessageStream(message: string, attachments: Attachment[]): AsyncGenerator<StreamUpdate, void, unknown> {
      if (!this._cachedModelConfig) throw new Error("No model selected");
      const taskId = 'active_chat_stream'; 
      const signal = streamManager.registerTask(taskId);

      try {
          // ✅ 简化：直接使用原始历史，让后端统一处理
          // 后端会负责：过滤、转换、优化
          const stream = this.currentProvider.sendMessageStream(
              this._cachedModelConfig.id,
              this._cachedHistory,  // ✅ 使用原始历史，后端会处理
              message,
              attachments,
              this._cachedOptions,
              this.apiKey,
              this.baseUrl
          );

          for await (const chunk of stream) {
              if (signal.aborted) throw new Error("Stream aborted by user");
              yield chunk;
          }

      } finally {
          streamManager.removeTask(taskId);
      }
  }

  public cancelCurrentStream() {
      streamManager.cancelTask('active_chat_stream', 'User stopped generation');

      // Also stop browser session if Browse was enabled
      this.stopBrowserSession().catch((e) => {
          console.warn('[LLMService] Failed to stop browser session:', e);
      });
  }

  /**
   * Stop the user's browser session on the backend.
   * Called when user stops generation to clean up Selenium resources.
   */
  private async stopBrowserSession(): Promise<void> {
      if (!this.baseUrl) return;

      try {
          const response = await fetch(`${this.baseUrl}/api/chat/browser/stop`, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              credentials: 'include', // Include cookies for user_id
          });

          if (response.ok) {
              console.log('[LLMService] Browser session stopped');
          } else {
              const error = await response.text();
              console.warn('[LLMService] Browser stop response:', error);
          }
      } catch (e) {
          // Silently ignore network errors (browser may not have been active)
          console.debug('[LLMService] Browser stop request failed (may be expected):', e);
      }
  }

  // --- Media Operations (Delegated to MediaFactory) ---

  public async generateImage(prompt: string, referenceImages: Attachment[] = []): Promise<ImageGenerationResult[]> {
      // 调试日志：检查配置
      console.log('[llmService.generateImage] 配置检查:', {
          hasBaseUrl: !!this.baseUrl,
          baseUrl: this.baseUrl?.substring(0, 30) || 'empty',
          providerId: this.providerId
      });
      
      // 直接使用 currentProvider，由 LLMFactory 负责提供商路由
      // 注意：多轮编辑的连续性由前端 ImageEditView 的 CONTINUITY LOGIC 处理
      // 前端会自动将当前画布上的图片转换为 Base64 附件传递，不需要后端维护历史
      // API Key 现在由后端从数据库获取，不再从前端传递
      return this.currentProvider.generateImage(
          this._cachedModelConfig!.id,
          prompt,
          referenceImages,
          this._cachedOptions,
          '', // API Key - now managed by backend
          this.baseUrl
      );
  }

  public async editImage(
      prompt: string, 
      referenceImages: Record<string, Attachment>,
      mode?: AppMode,
      options?: ChatOptions
  ): Promise<ImageGenerationResult[]> {
      // ✅ Check if provider is configured
      if (!this.isConfigured()) {
          throw new Error('Provider not configured. Please configure a provider in Settings → Profiles.');
      }

      // ✅ Check if model is selected
      if (!this._cachedModelConfig) {
          throw new Error('No model selected');
      }

      // ✅ Validate inputs
      if (!prompt || typeof prompt !== 'string' || prompt.trim() === '') {
          throw new Error('Invalid prompt: must be a non-empty string');
      }

      if (!referenceImages || typeof referenceImages !== 'object') {
          throw new Error('Invalid referenceImages: must be an object');
      }

      if (!referenceImages.raw) {
          throw new Error('Raw reference image is required for image editing');
      }

      // 调试日志：检查配置
      console.log('[llmService.editImage] 配置检查:', {
          hasBaseUrl: !!this.baseUrl,
          baseUrl: this.baseUrl?.substring(0, 30) || 'empty',
          providerId: this.providerId,
          modelId: this._cachedModelConfig.id,
          mode: mode || 'auto',
          referenceImageTypes: Object.keys(referenceImages)
      });

      // 路由 1: 对话式编辑模式（image-chat-edit）
      // 注意：对话式编辑由后端 UnifiedProviderClient 处理，直接传递 mode 参数即可
      // 不需要特殊处理，后端会根据 mode='image-chat-edit' 路由到 ConversationalImageEditService

      // 路由 2: Mask 编辑模式（image-mask-edit）- 必须有 mask
      if (mode === 'image-mask-edit') {
          if (!referenceImages.mask) {
              throw new Error('image-mask-edit mode requires a mask in referenceImages');
          }
          if (this.providerId === 'google') {
              const result = await this.callGoogleInpaintAPI(prompt, referenceImages);
              return [result];
          }
      }

      // 路由 3: 自动路由（根据是否有 mask）
      // Route Google inpainting through backend API if mask is provided
      if (this.providerId === 'google' && referenceImages.mask) {
          const result = await this.callGoogleInpaintAPI(prompt, referenceImages);
          return [result];
      }

      // ✅ Call currentProvider.editImage()
      // API Key is retrieved from database by backend, not passed from frontend
      // 对于 UnifiedProviderClient，传递 mode 参数
      // 检查是否是 UnifiedProviderClient（通过检查是否有 id 属性，这是 UnifiedProviderClient 的特征）
      const provider = this.currentProvider;
      // 合并 options（如果提供了）
      const finalOptions = options ? { ...this._cachedOptions, ...options } : this._cachedOptions;
      
      if ('id' in provider && typeof (provider as any).id === 'string') {
          // 这是 UnifiedProviderClient，它有 editImage 方法支持 mode 参数
          return (provider as UnifiedProviderClient).editImage(
              this._cachedModelConfig.id,
              prompt,
              referenceImages,
              finalOptions,  // 使用合并后的 options
              this.baseUrl,
              mode  // 传递模式参数
          );
      }
      
      // 其他提供者（保持向后兼容，不支持 mode 参数）
      return provider.editImage(
          this._cachedModelConfig.id,
          prompt,
          referenceImages,
          finalOptions,  // 使用合并后的 options
          this.baseUrl
      );
  }

  public async generateVideo(prompt: string, referenceImages: Attachment[] = []): Promise<VideoGenerationResult> {
      // 直接使用 currentProvider，由 LLMFactory 负责提供商路由
      return this.currentProvider.generateVideo(
          prompt,
          referenceImages,
          this._cachedOptions,
          this.apiKey,
          this.baseUrl
      );
  }

  public async generateSpeech(text: string): Promise<AudioGenerationResult> {
      // 直接使用 currentProvider，由 LLMFactory 负责提供商路由
      return this.currentProvider.generateSpeech(
          text,
          this._cachedOptions.voiceName || 'Puck',
          this.apiKey,
          this.baseUrl
      );
  }

  public async outPaintImage(referenceImage: Attachment): Promise<ImageGenerationResult> {
      // Route Google provider through backend API
      if (this.providerId === 'google') {
          return this.callGoogleOutpaintAPI(referenceImage);
      }
      
      // For other providers, use existing logic
      if (this.currentProvider.outPaintImage) {
          return this.currentProvider.outPaintImage(referenceImage, this._cachedOptions, this.apiKey, this.baseUrl);
      }
      
      // Fallback: If current provider doesn't support outpainting,
      // check if we have a DashScope key configured and use the Tongyi provider (via UnifiedProviderClient) for this specific task.
      // ✅ 新架构: 使用 UnifiedProviderClient('tongyi')，通过 executeMode('image-outpainting', ...) 统一处理
      const dashscopeKey = await configService.getDashScopeKey();
      if (dashscopeKey) {
           const tongyiProvider = LLMFactory.getProvider('openai', 'tongyi'); // 返回 UnifiedProviderClient('tongyi')
           if (tongyiProvider.outPaintImage) {
               // Resolve correct DashScope URL from config if available, otherwise default standard
               const profiles = await configService.getProfiles();
               const tongyiProfile = profiles.find(p => p.providerId === 'tongyi');
               
               // Use profile URL if exists, BUT if it is undefined, resolveDashUrl in api.ts will handle the default proxy path.
               // We avoid defaulting to the absolute 'https://dashscope...' URL here because it breaks CORS in browsers.
               const dsUrl = tongyiProfile?.baseUrl;

               return tongyiProvider.outPaintImage(referenceImage, this._cachedOptions, dashscopeKey, dsUrl);
           }
      }
      throw new Error("Out-Painting not supported by current provider.");
  }

  public async virtualTryOn(prompt: string, attachments: Attachment[]): Promise<ImageGenerationResult[]> {
      // ✅ 新架构: 使用 UnifiedProviderClient.executeMode('virtual-try-on', ...) 统一处理
      if (this.currentProvider && 'executeMode' in this.currentProvider) {
          const unifiedProvider = this.currentProvider as any;
          const result = await unifiedProvider.executeMode(
              'virtual-try-on',
              this._cachedOptions.modelId || '',
              prompt,
              attachments,
              this._cachedOptions,
              {}
          );
          return Array.isArray(result) ? result : [result];
      }
      
      // 回退到旧方法（仅用于兼容性，应该尽快迁移）
      if (this.providerId === 'google') {
          const result = await this.callGoogleVirtualTryonAPI(prompt, attachments);
          return [result];
      }
      
      throw new Error("Virtual Try-On not supported by current provider.");
  }

  private async callGoogleOutpaintAPI(referenceImage: Attachment): Promise<ImageGenerationResult> {
      try {
          // Convert attachment to base64 if needed
          let imageData = referenceImage.url;
          if (referenceImage.url.startsWith('blob:')) {
              const response = await fetch(referenceImage.url);
              const blob = await response.blob();
              const base64 = await new Promise<string>((resolve) => {
                  const reader = new FileReader();
                  reader.onloadend = () => resolve(reader.result as string);
                  reader.readAsDataURL(blob);
              });
              imageData = base64;
          }

          const response = await fetch('/api/google/outpaint', {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              credentials: 'include',
              body: JSON.stringify({
                  image: imageData,
                  prompt: this._cachedOptions.prompt || 'Extend the image naturally',
                  model: this._cachedOptions.modelId || 'imagen-3.0-generate-001',
                  aspectRatio: this._cachedOptions.outPainting?.aspectRatio,
                  platform: this._cachedOptions.outPainting?.platform,
              }),
          });

          if (!response.ok) {
              const error = await response.json().catch(() => ({ detail: response.statusText }));
              throw new Error(error.detail || `HTTP ${response.status}`);
          }

          const result = await response.json();
          
          // Convert backend response to ImageGenerationResult format
          return {
              url: result.images[0], // Backend returns base64 in images array
              mimeType: 'image/png',
              filename: 'outpainted.png',
          };
      } catch (error) {
          console.error('[LLMService] Google outpaint API error:', error);
          throw error;
      }
  }

  /**
   * @deprecated 使用 UnifiedProviderClient.executeMode('virtual-try-on', ...) 代替
   * 旧 API 路由: /api/google/virtual-tryon
   * 新 API 路由: /api/modes/google/virtual-try-on
   */
  private async callGoogleVirtualTryonAPI(prompt: string, attachments: Attachment[]): Promise<ImageGenerationResult> {
      try {
          if (!attachments || attachments.length < 2) {
              throw new Error('Virtual try-on requires 2 images: person and garment');
          }

          // Convert attachments to base64
          const convertToBase64 = async (attachment: Attachment): Promise<string> => {
              if (attachment.url.startsWith('data:')) {
                  return attachment.url;
              }
              if (attachment.url.startsWith('blob:')) {
                  const response = await fetch(attachment.url);
                  const blob = await response.blob();
                  return await new Promise<string>((resolve) => {
                      const reader = new FileReader();
                      reader.onloadend = () => resolve(reader.result as string);
                      reader.readAsDataURL(blob);
                  });
              }
              return attachment.url;
          };

          const personImage = await convertToBase64(attachments[0]);
          const garmentImage = await convertToBase64(attachments[1]);

          const response = await fetch('/api/google/virtual-tryon', {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              credentials: 'include',
              body: JSON.stringify({
                  personImage,
                  garmentImage,
                  model: this._cachedOptions.modelId || 'imagen-3.0-generate-001',
                  platform: this._cachedOptions.platform,
              }),
          });

          if (!response.ok) {
              const error = await response.json().catch(() => ({ detail: response.statusText }));
              throw new Error(error.detail || `HTTP ${response.status}`);
          }

          const result = await response.json();
          
          // Convert backend response to ImageGenerationResult format
          return {
              url: result.images[0], // Backend returns base64 in images array
              mimeType: 'image/png',
              filename: 'virtual-tryon.png',
          };
      } catch (error) {
          console.error('[LLMService] Google virtual try-on API error:', error);
          throw error;
      }
  }

  private async callGoogleInpaintAPI(prompt: string, referenceImages: Record<string, Attachment>): Promise<ImageGenerationResult> {
      try {
          // Convert attachments to base64
          const convertToBase64 = async (attachment: Attachment): Promise<string> => {
              if (attachment.url.startsWith('data:')) {
                  return attachment.url;
              }
              if (attachment.url.startsWith('blob:')) {
                  const response = await fetch(attachment.url);
                  const blob = await response.blob();
                  return await new Promise<string>((resolve) => {
                      const reader = new FileReader();
                      reader.onloadend = () => resolve(reader.result as string);
                      reader.readAsDataURL(blob);
                  });
              }
              return attachment.url;
          };

          const image = await convertToBase64(referenceImages.raw);
          const mask = await convertToBase64(referenceImages.mask);

          const response = await fetch('/api/google/inpaint', {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              credentials: 'include',
              body: JSON.stringify({
                  image,
                  mask,
                  prompt,
                  model: this._cachedOptions.modelId || 'imagen-3.0-generate-001',
                  platform: this._cachedOptions.platform,
              }),
          });

          if (!response.ok) {
              const error = await response.json().catch(() => ({ detail: response.statusText }));
              throw new Error(error.detail || `HTTP ${response.status}`);
          }

          const result = await response.json();
          
          // Convert backend response to ImageGenerationResult format
          return {
              url: result.images[0], // Backend returns base64 in images array
              mimeType: 'image/png',
              filename: 'inpainted.png',
          };
      } catch (error) {
          console.error('[LLMService] Google inpaint API error:', error);
          throw error;
      }
  }
}

export const llmService = new LLMService();

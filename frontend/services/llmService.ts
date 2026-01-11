
import { LLMFactory } from "./LLMFactory";
import { Message, ModelConfig, ChatOptions, Attachment, ApiProtocol } from "../types/types";
import { StreamUpdate, ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "./providers/interfaces";
import { configService } from "./configurationService";
import { messagePreparer } from "./ai_chat/MessagePreparer";
import { streamManager } from "./stream/StreamManager";

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
          this.baseUrl
      );
  }

  public async editImage(prompt: string, referenceImages: Record<string, Attachment>): Promise<ImageGenerationResult[]> {
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
          referenceImageTypes: Object.keys(referenceImages)
      });

      // ✅ Call currentProvider.editImage()
      // API Key is retrieved from database by backend, not passed from frontend
      return this.currentProvider.editImage(
          this._cachedModelConfig.id,
          prompt,
          referenceImages,
          this._cachedOptions,
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
      if (this.currentProvider.outPaintImage) {
          return this.currentProvider.outPaintImage(referenceImage, this._cachedOptions, this.apiKey, this.baseUrl);
      }
      
      // Fallback: If current provider (e.g. Google) doesn't support outpainting,
      // check if we have a DashScope key configured and use the DashScope provider for this specific task.
      const dashscopeKey = await configService.getDashScopeKey();
      if (dashscopeKey) {
           const dashscopeProvider = LLMFactory.getProvider('openai', 'tongyi');
           if (dashscopeProvider.outPaintImage) {
               // Resolve correct DashScope URL from config if available, otherwise default standard
               const profiles = await configService.getProfiles();
               const tongyiProfile = profiles.find(p => p.providerId === 'tongyi');
               
               // Use profile URL if exists, BUT if it is undefined, resolveDashUrl in api.ts will handle the default proxy path.
               // We avoid defaulting to the absolute 'https://dashscope...' URL here because it breaks CORS in browsers.
               const dsUrl = tongyiProfile?.baseUrl;

               return dashscopeProvider.outPaintImage(referenceImage, this._cachedOptions, dashscopeKey, dsUrl);
           }
      }
      throw new Error("Out-Painting not supported by current provider.");
  }
}

export const llmService = new LLMService();

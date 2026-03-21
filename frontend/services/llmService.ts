
import { LLMFactory } from "./LLMFactory";
import { Message, ModelConfig, ChatOptions, Attachment, ApiProtocol, AppMode, ModeCatalogItem } from "../types/types";
import { StreamUpdate, ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "./providers/interfaces";
import { configService } from "./configurationService";
import { messagePreparer } from "./ai_chat/MessagePreparer";
import { streamManager } from "./stream/StreamManager";
import { UnifiedProviderClient } from "./providers/UnifiedProviderClient";
import mcpConfigService from "./mcpConfigService";
import { fetchWithTimeout, parseHttpError, readJsonResponse } from "./http";

export interface ModelsApiResponse {
  models: ModelConfig[];
  defaultModelId: string | null;
  modeCatalog: ModeCatalogItem[];
  filteredByMode?: string | null;
  cached?: boolean;
  provider?: string;
}

interface ModelCache {
  payload: ModelsApiResponse;
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

  public getProviderId(): string {
    return this.providerId;
  }

  public getProtocol(): ApiProtocol | null {
    return this.protocol;
  }

  private get currentProvider() {
      if (!this.protocol || !this.providerId) {
        throw new Error('Provider not configured. Please configure a provider in Settings → Profiles.');
      }
      return LLMFactory.getProvider(this.protocol, this.providerId);
  }

  private isVerboseLoggingEnabled(): boolean {
      if (!import.meta.env.DEV || typeof window === 'undefined') {
          return false;
      }
      try {
          return window.localStorage.getItem('llm.verbose') === '1';
      } catch {
          return false;
      }
  }

  private debugLog(...args: unknown[]): void {
      if (this.isVerboseLoggingEnabled()) {
          console.log(...args);
      }
  }

  public async getAvailableModelsPayload(
    useCache: boolean = true,
    mode?: AppMode | string
  ): Promise<ModelsApiResponse> {
      // ✅ 如果未配置 Provider，返回空数组而不是发送请求
      if (!this.providerId) {
        console.warn('[LLMService] Provider not configured, returning empty payload');
        return { models: [], defaultModelId: null, modeCatalog: [] };
      }
      // ✅ 从后端 API 获取模型列表（后端会从数据库读取 API Key）
      // 缓存策略：仅缓存 provider 级完整模型列表；mode 请求始终单独获取。
      const cacheKey = `${this.providerId}`;
      const now = Date.now();
      const cachedData = this.modelCache.get(cacheKey);

      // ✅ 如果传递了 mode，不使用缓存（因为缓存的是完整列表）
      // 如果未传递 mode，可以使用缓存
      if (useCache && !mode && cachedData && (now - cachedData.timestamp < CACHE_TTL)) {
          console.log(`[LLMService] Returning fresh cached payload for ${this.providerId}`);
          return cachedData.payload;
      }

      try {
          console.log(`[LLMService] Fetching models from backend API for ${this.providerId}${mode ? ` (mode: ${mode})` : ''}`);

          // ✅ 调用后端 API：/api/models/{provider}?mode={mode}
          // 后端会：
          // 1. 从 config_profiles / vertex_ai_config 读取 provider 模型集合
          // 2. 计算 provider 级 modeCatalog
          // 3. 按 mode 返回对应模型列表（若未传 mode 则返回完整列表）
          const params = new URLSearchParams();
          // ✅ Query 参数使用 camelCase（中间件自动转换为 snake_case）
          params.append('useCache', String(useCache));
          if (mode) {
              params.append('mode', mode);
          }
          
          const response = await fetchWithTimeout(`/api/models/${this.providerId}?${params.toString()}`, {
              method: 'GET',
              cache: 'no-store',
              credentials: 'include', // 携带认证 Cookie
              headers: {
                  'Content-Type': 'application/json'
              },
              withAuth: true,
              timeoutMs: 30000,
          });

          if (!response.ok) {
              const parsedError = await parseHttpError(response, '');
              const suffix = parsedError.message ? ` ${parsedError.message}` : '';
              throw new Error(`Backend API error: ${response.status}${suffix}`);
          }

          const data = await readJsonResponse<any>(response);
          const payload: ModelsApiResponse = {
              models: Array.isArray(data.models) ? data.models : [],
              defaultModelId: typeof data.defaultModelId === 'string' ? data.defaultModelId : null,
              modeCatalog: Array.isArray(data.modeCatalog) ? data.modeCatalog : [],
              filteredByMode: typeof data.filteredByMode === 'string' ? data.filteredByMode : null,
              cached: Boolean(data.cached),
              provider: typeof data.provider === 'string' ? data.provider : this.providerId,
          };

          // ✅ 只有未传递 mode 时才缓存（缓存完整列表）
          // 如果传递了 mode，不缓存（因为不同 mode 需要不同的过滤结果）
          if (!mode) {
              this.modelCache.set(cacheKey, {
                  payload,
                  timestamp: now,
                  providerId: this.providerId,
              });
          }

          console.log(`[LLMService] Successfully fetched ${payload.models.length} models from backend${payload.filteredByMode ? ` (filtered by mode: ${payload.filteredByMode})` : ''}`);
          return payload;
      } catch (error) {
          console.error(`[LLMService] Failed to fetch models for ${this.providerId}.`, error);
          throw error;
      }
  }

  public async getAvailableModels(useCache: boolean = true, mode?: AppMode | string): Promise<ModelConfig[]> {
      const payload = await this.getAvailableModelsPayload(useCache, mode);
      return payload.models;
  }

  public clearModelCache() {
      this.modelCache.clear();
      console.log("[LLMService] Model cache cleared.");
  }

  public startNewChat(history: Message[], modelConfig: ModelConfig, options?: ChatOptions) {
      this._cachedHistory = history;
      this._cachedModelConfig = modelConfig;
      if (options) {
          // ✅ 详细日志：记录 image-gen 模式下设置的 options
          if (options.imageAspectRatio || options.numberOfImages || options.imageResolution) {
              this.debugLog('========== [llmService.startNewChat] 设置图片生成参数 ==========');
              this.debugLog('[startNewChat] Model:', modelConfig.id);
              this.debugLog('[startNewChat] 传入的 Options:', {
                  numberOfImages: options.numberOfImages,
                  imageAspectRatio: options.imageAspectRatio,
                  imageResolution: options.imageResolution,
                  imageStyle: options.imageStyle,
                  negativePrompt: options.negativePrompt,
                  seed: options.seed,
                  // guidanceScale removed - not officially documented by Google Imagen
                  outputMimeType: options.outputMimeType,
                  outputCompressionQuality: options.outputCompressionQuality,
                  enhancePrompt: options.enhancePrompt,
              });
              this.debugLog('[startNewChat] 完整 Options 对象:', JSON.stringify(options, null, 2));
              this.debugLog('========== [llmService.startNewChat] 参数设置结束 ==========');
          }
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
              this.baseUrl,
              signal
          );

          for await (const chunk of stream) {
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

      // Also stop MCP session if MCP was enabled for current chat
      this.stopMcpSession().catch((e) => {
          console.warn('[LLMService] Failed to stop MCP session:', e);
      });
  }

  /**
   * Stop the user's browser session on the backend.
   * Called when user stops generation to clean up Selenium resources.
   */
  private async stopBrowserSession(): Promise<void> {
      try {
          const response = await fetchWithTimeout(`/api/browser/stop`, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              credentials: 'include', // Include cookies for user_id
              withAuth: true,
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

  /**
   * Stop current MCP chat session on the backend.
   * Called when user clicks stop to proactively terminate in-flight MCP execution.
   */
  private async stopMcpSession(): Promise<void> {
      const mcpServerKey = this._cachedOptions?.mcpServerKey;
      if (!mcpServerKey) return;

      try {
          const result = await mcpConfigService.stopSessions(mcpServerKey);
          console.log('[LLMService] MCP sessions stopped:', {
              mcpServerKey,
              closedCount: result.closedCount
          });
      } catch (e) {
          console.debug('[LLMService] MCP stop request failed (may be expected):', e);
      }
  }

  // --- Media Operations (通过 UnifiedProviderClient 处理) ---

  public async generateImage(
    prompt: string, 
    referenceImages: Attachment[] = [],
    options?: Partial<ChatOptions>  // ✅ 新增：接收 options（包含 sessionId 和 messageId）
  ): Promise<ImageGenerationResult[]> {
      // ✅ 详细日志：记录图片生成请求的参数
      this.debugLog('========== [llmService.generateImage] 图片生成请求开始 ==========');
      this.debugLog('[llmService.generateImage] Provider ID:', this.providerId);
      this.debugLog('[llmService.generateImage] Model ID:', this._cachedModelConfig?.id);
      this.debugLog('[llmService.generateImage] Prompt:', prompt.substring(0, 100) + (prompt.length > 100 ? '...' : ''));
      this.debugLog('[llmService.generateImage] 附件数量:', referenceImages.length);
      this.debugLog('[llmService.generateImage] 传递给 Provider 的 Options (_cachedOptions):', {
        numberOfImages: this._cachedOptions.numberOfImages,
        imageAspectRatio: this._cachedOptions.imageAspectRatio,
        imageResolution: this._cachedOptions.imageResolution,
        imageStyle: this._cachedOptions.imageStyle,
        negativePrompt: this._cachedOptions.negativePrompt,
        seed: this._cachedOptions.seed,
        // guidanceScale removed - not officially documented by Google Imagen
        outputMimeType: this._cachedOptions.outputMimeType,
        outputCompressionQuality: this._cachedOptions.outputCompressionQuality,
        enhancePrompt: this._cachedOptions.enhancePrompt,
        enableSearch: this._cachedOptions.enableSearch,
        enableThinking: this._cachedOptions.enableThinking,
        enableCodeExecution: this._cachedOptions.enableCodeExecution,
        enableUrlContext: this._cachedOptions.enableUrlContext,
        enableBrowser: this._cachedOptions.enableBrowser,
        enableEnhancedRetrieval: this._cachedOptions.enableEnhancedRetrieval,
        enableDeepResearch: this._cachedOptions.enableDeepResearch,
        googleCacheMode: this._cachedOptions.googleCacheMode,
        baseUrl: this.baseUrl,
      });
      this.debugLog('[llmService.generateImage] 完整 _cachedOptions 对象:', JSON.stringify(this._cachedOptions, null, 2));
      this.debugLog('========== [llmService.generateImage] 图片生成请求参数结束 ==========');
      
      // 直接使用 currentProvider，由 LLMFactory 负责提供商路由
      // 注意：多轮编辑的连续性由前端 ImageEditView 的 CONTINUITY LOGIC 处理
      // 前端会自动将当前画布上的图片转换为 Base64 附件传递，不需要后端维护历史
      // API Key 现在由后端从数据库获取，不再从前端传递
      // ✅ 合并传入的 options（包含 sessionId 和 messageId）和缓存的 options
      const mergedOptions = {
        ...this._cachedOptions,
        ...options  // 传入的 options 优先（包含 sessionId 和 messageId）
      };
      
      return this.currentProvider.generateImage(
          this._cachedModelConfig!.id,
          prompt,
          referenceImages,
          mergedOptions,  // ✅ 使用合并后的 options
          '', // API Key - now managed by backend
          this.baseUrl
      );
  }

  public async editImage(
      prompt: string,
      referenceImages: Record<string, Attachment | Attachment[]>,  // ✅ 支持多图：raw 可以是数组
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
      this.debugLog('[llmService.editImage] 配置检查:', {
          hasBaseUrl: !!this.baseUrl,
          baseUrl: this.baseUrl?.substring(0, 30) || 'empty',
          providerId: this.providerId,
          modelId: this._cachedModelConfig.id,
          mode: mode || 'auto',
          referenceImageTypes: Object.keys(referenceImages)
      });

      // ✅ 统一路由：所有编辑模式都通过 UnifiedProviderClient → 后端 /api/modes/{provider}/{mode} 处理
      // 包括：image-chat-edit, image-mask-edit, image-inpainting, image-background-edit, image-recontext 等
      // 后端会根据 mode 分发到对应的子服务（ConversationalImageEditService, MaskEditService 等）

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

  public async generateVideo(
    prompt: string,
    referenceImages: Attachment[] = [],
    options?: Partial<ChatOptions>
  ): Promise<VideoGenerationResult> {
      const finalOptions = options ? { ...this._cachedOptions, ...options } : this._cachedOptions;

      return this.currentProvider.generateVideo(
          this._cachedModelConfig.id,
          prompt,
          referenceImages,
          finalOptions,
          this.apiKey,
          this.baseUrl
      );
  }

  public async generateSpeech(text: string): Promise<AudioGenerationResult> {
      // 直接使用 currentProvider，由 LLMFactory 负责提供商路由
      return this.currentProvider.generateSpeech(
          this._cachedModelConfig.id,
          text,
          this._cachedOptions.voiceName || 'Puck',
          this.apiKey,
          this.baseUrl
      );
  }

  /**
   * Out-Painting（图片扩展）
   *
   * 与 GEN 模式保持一致：传递 sessionId 和 messageId 到后端，
   * 后端会通过 AttachmentService 创建数据库附件记录和上传任务。
   *
   * @param referenceImage 参考图片
   * @param options 选项（包含 sessionId、messageId 等）
   */
  public async outPaintImage(
    referenceImage: Attachment,
    options?: Partial<ChatOptions>
  ): Promise<ImageGenerationResult[]> {  // ✅ 修复：返回数组而不是单个结果
      // ✅ 与 ImageGenHandler 保持一致：合并 options，确保传递 sessionId 和 messageId
      const mergedOptions = {
        ...this._cachedOptions,
        ...options,  // ✅ Handler 传入的 options 优先（包含 sessionId、messageId）
      };

      // ✅ 根据 outpaintMode 选择正确的模型
      // - upscale 模式：必须使用 imagen-4.0-upscale-preview
      // - ratio/scale/offset 模式：使用 imagen-3.0-capability-001 或 imagen-4.0-ingredients-preview
      const outpaintMode = (mergedOptions as any).outpaintMode || 'ratio';
      let selectedModelId = mergedOptions.modelId;
      
      if (outpaintMode === 'upscale') {
          // ✅ upscale 模式必须使用放大专用模型
          if (!selectedModelId || !selectedModelId.toLowerCase().includes('upscale')) {
              selectedModelId = 'imagen-4.0-upscale-preview';
              this.debugLog('[outPaintImage] ✅ upscale 模式：自动切换到放大模型', selectedModelId);
          }
      } else {
          // ✅ ratio/scale/offset 模式使用编辑模型
          if (!selectedModelId || selectedModelId.toLowerCase().includes('upscale')) {
              selectedModelId = 'imagen-3.0-capability-001';
              this.debugLog('[outPaintImage] ✅ 扩图模式：自动切换到编辑模型', selectedModelId);
          }
      }

      // ✅ 详细日志：记录 image-outpainting 模式下传递的参数
      this.debugLog('========== [llmService.outPaintImage] 参数传递 ==========');
      this.debugLog('[outPaintImage] Provider:', this.providerId);
      this.debugLog('[outPaintImage] sessionId:', mergedOptions.sessionId || mergedOptions.frontendSessionId || 'N/A');
      this.debugLog('[outPaintImage] messageId:', (mergedOptions as any).messageId || 'N/A');
      this.debugLog('[outPaintImage] outpaintMode:', outpaintMode);
      this.debugLog('[outPaintImage] selectedModelId:', selectedModelId);
      this.debugLog('[outPaintImage] outPainting options:', mergedOptions.outPainting);
      this.debugLog('========== [llmService.outPaintImage] 参数传递结束 ==========');

      // ✅ 新架构: 使用 UnifiedProviderClient.executeMode('image-outpainting', ...) 统一处理
      // 路由: /api/modes/{provider}/image-outpainting → modes.py → GoogleService.expand_image() → ExpandService
      if (this.currentProvider && 'executeMode' in this.currentProvider) {
          const unifiedProvider = this.currentProvider as any;
          const prompt = mergedOptions.prompt || 'Extend the image naturally';

          const result = await unifiedProvider.executeMode(
              'image-outpainting',
              selectedModelId,  // ✅ 使用根据 outpaintMode 选择的模型
              prompt,
              [referenceImage],
              mergedOptions,  // ✅ 使用合并后的 options（包含 sessionId、message_id、outPainting）
              {}
          );
          return Array.isArray(result) ? result : [result];  // ✅ 修复：返回数组
      }

      // 回退到旧方法（仅用于兼容性，应该尽快迁移）
      // For other providers, use existing logic
      if (this.currentProvider.outPaintImage) {
          const result = await this.currentProvider.outPaintImage(referenceImage, mergedOptions, this.apiKey, this.baseUrl);
          return Array.isArray(result) ? result : [result];  // ✅ 确保返回数组
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

               const result = await tongyiProvider.outPaintImage(referenceImage, mergedOptions, dashscopeKey, dsUrl);
               return Array.isArray(result) ? result : [result];  // ✅ 确保返回数组
           }
      }
      throw new Error("Out-Painting not supported by current provider.");
  }

  /**
   * Virtual Try-On（虚拟试衣）
   *
   * 与 GEN 模式保持一致：传递 sessionId 和 messageId 到后端，
   * 后端会通过 AttachmentService 创建数据库附件记录和上传任务。
   *
   * @param prompt 提示词（暂不支持）
   * @param attachments 附件（人物图 + 服装图）
   * @param options 选项（包含 sessionId、messageId 等）
   */
  public async virtualTryOn(
    prompt: string,
    attachments: Attachment[],
    options?: Partial<ChatOptions>
  ): Promise<ImageGenerationResult[]> {
      // ✅ 与 ImageGenHandler 保持一致：合并 options，确保传递 sessionId 和 messageId
      const mergedOptions = {
        ...this._cachedOptions,
        ...options,  // ✅ Handler 传入的 options 优先（包含 sessionId、messageId）
      };

      // ✅ 详细日志：记录 virtual-try-on 模式下传递的参数
      this.debugLog('========== [llmService.virtualTryOn] 参数传递 ==========');
      this.debugLog('[virtualTryOn] sessionId:', mergedOptions.sessionId || mergedOptions.frontendSessionId || 'N/A');
      this.debugLog('[virtualTryOn] messageId:', (mergedOptions as any).messageId || 'N/A');
      this.debugLog('[virtualTryOn] numberOfImages:', mergedOptions.numberOfImages);
      this.debugLog('[virtualTryOn] attachments:', attachments.length);
      this.debugLog('========== [llmService.virtualTryOn] 参数传递结束 ==========');

      // ✅ 新架构: 使用 UnifiedProviderClient.executeMode('virtual-try-on', ...) 统一处理
      if (this.currentProvider && 'executeMode' in this.currentProvider) {
          const unifiedProvider = this.currentProvider as any;
          const result = await unifiedProvider.executeMode(
              'virtual-try-on',
              mergedOptions.modelId || '',
              prompt,
              attachments,
              mergedOptions,  // ✅ 使用合并后的 options（包含 sessionId、messageId）
              {}
          );
          return Array.isArray(result) ? result : [result];
      }
      
      throw new Error("Virtual Try-On not supported by current provider.");
  }

}

export const llmService = new LLMService();

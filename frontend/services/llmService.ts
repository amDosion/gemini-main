
import { LLMFactory } from "./LLMFactory";
import { Message, ModelConfig, ChatOptions, Attachment, ApiProtocol } from "../../types";
import { StreamUpdate, ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "./providers/interfaces";
import { configService } from "./configurationService";
import { messagePreparer } from "./ai_chat/MessagePreparer";
import { streamManager } from "./stream/StreamManager";
import { MediaFactory } from "./media/MediaFactory";

export class LLMService {
  private apiKey: string = '';
  private baseUrl: string = '';
  private protocol: ApiProtocol = 'google';
  private providerId: string = 'google';

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

  public setConfig(apiKey: string, baseUrl: string, protocol: ApiProtocol, providerId: string) {
    this.apiKey = apiKey ? apiKey.trim() : '';
    this.baseUrl = baseUrl ? baseUrl.trim().replace(/\/$/, '') : '';
    this.protocol = protocol;
    this.providerId = providerId || 'google';
  }

  private get currentProvider() {
      return LLMFactory.getProvider(this.protocol, this.providerId);
  }

  public async getAvailableModels(): Promise<ModelConfig[]> {
      return this.currentProvider.getAvailableModels(this.apiKey, this.baseUrl);
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
          // Prepare Messages
          await messagePreparer.prepare(
              this._cachedHistory,
              message,
              attachments,
              this._cachedOptions,
              this._cachedModelConfig
          );

          // Execute via Provider
          const stream = this.currentProvider.sendMessageStream(
              this._cachedModelConfig.id,
              this._cachedHistory, 
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
      // Use the Media Factory to find the strategy for the current provider
      const strategy = MediaFactory.getStrategy(this.providerId);
      
      // If strategy exists, use it. Otherwise fallback to old provider method (Migration phase)
      // 注意：多轮编辑的连续性由前端 ImageEditView 的 CONTINUITY LOGIC 处理
      // 前端会自动将当前画布上的图片转换为 Base64 附件传递，不需要后端维护历史
      if (strategy && this.providerId.includes('google')) {
          return strategy.generateImage(
              this._cachedModelConfig!.id,
              prompt,
              referenceImages,
              this._cachedOptions,
              this.apiKey,
              this.baseUrl
          );
      }
      
      // Fallback for providers not yet migrated to MediaFactory strategies (like TongYi/OpenAI temporarily)
      return this.currentProvider.generateImage(
          this._cachedModelConfig!.id,
          prompt,
          referenceImages,
          this._cachedOptions,
          this.apiKey,
          this.baseUrl
      );
  }

  public async generateVideo(prompt: string, referenceImages: Attachment[] = []): Promise<VideoGenerationResult> {
      const strategy = MediaFactory.getStrategy(this.providerId);
      
      if (strategy && this.providerId.includes('google')) {
          return strategy.generateVideo(
              prompt,
              referenceImages,
              this._cachedOptions,
              this.apiKey,
              this.baseUrl
          );
      }

      return this.currentProvider.generateVideo(
          prompt,
          referenceImages,
          this._cachedOptions,
          this.apiKey,
          this.baseUrl
      );
  }

  public async generateSpeech(text: string): Promise<AudioGenerationResult> {
      const strategy = MediaFactory.getStrategy(this.providerId);

      if (strategy && this.providerId.includes('google')) {
          return strategy.generateSpeech(
              text,
              this._cachedOptions.voiceName || 'Puck',
              this.apiKey,
              this.baseUrl
          );
      }

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

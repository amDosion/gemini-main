/**
 * @deprecated 此 Provider 已废弃，请使用 UnifiedProviderClient('openai') 代替
 * 
 * OpenAI Provider - 已统一到 UnifiedProviderClient
 * 
 * 新架构: 所有 Provider 统一使用 UnifiedProviderClient，通过后端统一路由处理
 * - Chat: /api/modes/openai/chat
 * - Modes: /api/modes/openai/{mode}
 * 
 * 特殊说明:
 * - 上下文优化功能 (contextManager.optimizeContext) 已集成到 UnifiedProviderClient
 * - 所有功能都通过后端统一处理，无需前端直接调用 OpenAI API
 * 
 * 迁移指南:
 * - 使用 UnifiedProviderClient('openai') 代替 new OpenAIProvider()
 * - LLMFactory 会自动使用 UnifiedProviderClient
 */

import { ILLMProvider, StreamUpdate, ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "../interfaces";
import { ModelConfig, Message, Attachment, ChatOptions } from "../../../types/types";
import { UnifiedProviderClient } from "../UnifiedProviderClient";

/**
 * OpenAI Provider - 委托给 UnifiedProviderClient
 * 
 * 此类的所有方法都委托给 UnifiedProviderClient，保持向后兼容
 */
export class OpenAIProvider implements ILLMProvider {
  public id = 'openai';
  
  // ✅ 内部使用 UnifiedProviderClient 处理所有请求
  private unifiedClient: UnifiedProviderClient;

  constructor() {
    this.unifiedClient = new UnifiedProviderClient('openai');
  }

  public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    // ✅ 委托给 UnifiedProviderClient
    return await this.unifiedClient.getAvailableModels(apiKey, baseUrl);
  }

  public async uploadFile(file: File, apiKey: string, baseUrl: string): Promise<string> {
    // ✅ 委托给 UnifiedProviderClient
    return await this.unifiedClient.uploadFile(file, apiKey, baseUrl);
  }

  public async *sendMessageStream(
    modelId: string,
    history: Message[],
    message: string,
    attachments: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): AsyncGenerator<StreamUpdate, void, unknown> {
    // ✅ 委托给 UnifiedProviderClient
    yield* this.unifiedClient.sendMessageStream(
      modelId,
      history,
      message,
      attachments,
      options,
      apiKey,
      baseUrl
    );
  }

  public async generateImage(
      modelId: string, 
      prompt: string, 
      referenceImages: Attachment[], 
      options: ChatOptions, 
      apiKey: string, 
      baseUrl: string
  ): Promise<ImageGenerationResult[]> {
    // ✅ 委托给 UnifiedProviderClient
    return await this.unifiedClient.generateImage(
      modelId,
      prompt,
      referenceImages,
      options,
      apiKey,
      baseUrl
    );
  }

  public async editImage(
      modelId: string,
      prompt: string,
      referenceImages: Record<string, any>,
      options: ChatOptions,
      baseUrl: string
  ): Promise<ImageGenerationResult[]> {
    // ✅ 委托给 UnifiedProviderClient
    return await this.unifiedClient.editImage(
      modelId,
      prompt,
      referenceImages,
      options,
      baseUrl
    );
  }

  public async generateVideo(
      prompt: string, 
      referenceImages: Attachment[], 
      options: ChatOptions, 
      apiKey: string, 
      baseUrl: string
  ): Promise<VideoGenerationResult> {
    // ✅ 委托给 UnifiedProviderClient
    return await this.unifiedClient.generateVideo(
      prompt,
      referenceImages,
      options,
      apiKey,
      baseUrl
    );
  }

  public async generateSpeech(
      text: string, 
      voiceName: string, 
      apiKey: string, 
      baseUrl: string
  ): Promise<AudioGenerationResult> {
    // ✅ 委托给 UnifiedProviderClient
    return await this.unifiedClient.generateSpeech(
      text,
      voiceName,
      apiKey,
      baseUrl
    );
  }
}

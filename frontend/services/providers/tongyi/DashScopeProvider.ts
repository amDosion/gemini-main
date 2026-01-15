/**
 * @deprecated 此 Provider 已废弃，请使用 UnifiedProviderClient('tongyi') 代替
 * 
 * DashScope Provider - 通义千问服务提供者
 *
 * 新架构: 所有提供商统一使用 UnifiedProviderClient，通过后端统一路由处理
 * - Chat: /api/modes/tongyi/chat
 * - Modes: /api/modes/tongyi/{mode}
 *
 * 认证方式:
 * - 使用 JWT Token (Authorization: Bearer <token>)
 * - API Key 由后端从数据库获取（更安全）
 */

import { ILLMProvider, StreamUpdate, ImageGenerationResult } from "../interfaces";
import { ModelConfig, Message, Attachment, ChatOptions } from "../../../types/types";
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { generateDashScopeImage } from "./image-gen";
import { editWanxImage } from "./image-edit";
import { outPaintWanxImage } from "./image-expand";
import { getAccessToken } from "../../auth";

export class DashScopeProvider extends OpenAIProvider implements ILLMProvider {
  public id = 'tongyi';

  public async getAvailableModels(_apiKey: string, _baseUrl: string): Promise<ModelConfig[]> {
    // 使用 JWT Token 认证
    const token = getAccessToken();
    if (!token) {
      throw new Error('未登录，请先登录');
    }

    const response = await fetch('/api/models/tongyi', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `API error (${response.status})`);
    }
    const data = await response.json();
    return data.models;
  }

  public async *sendMessageStream(
    modelId: string,
    history: Message[],
    message: string,
    attachments: Attachment[],
    options: ChatOptions,
    _apiKey: string,
    _baseUrl: string
  ): AsyncGenerator<StreamUpdate, void, unknown> {
    // 使用 JWT Token 认证
    const token = getAccessToken();
    if (!token) {
      throw new Error('未登录，请先登录');
    }

    const response = await fetch('/api/chat/tongyi', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        modelId,
        messages: history.map(msg => ({
          role: msg.role,
          content: msg.content,
          isError: msg.isError || false,
          attachments: msg.attachments?.map(att => ({
            id: att.id,
            mimeType: att.mimeType,
            name: att.name,
            url: att.url,
            tempUrl: att.tempUrl,
            fileUri: att.fileUri,
          })),
        })),
        message,
        attachments: attachments?.map(att => ({
          id: att.id,
          mimeType: att.mimeType,
          name: att.name,
          url: att.url,
          tempUrl: att.tempUrl,
          fileUri: att.fileUri,
        })),
        options: {
          enableSearch: options.enableSearch || false,
          enableThinking: options.enableThinking || false,
          temperature: 1.0,
          maxTokens: null,
        },
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `API error (${response.status})`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6)) as StreamUpdate;
          } catch {}
        }
      }
    }
  }

  // --- Image Generation (Qwen/Wanx) ---
  public async generateImage(
    modelId: string,
    prompt: string,
    referenceImages: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): Promise<ImageGenerationResult[]> {
    if (referenceImages && referenceImages.length > 0) {
      return [await editWanxImage(modelId, prompt, referenceImages[0], options)];
    }
    return generateDashScopeImage(modelId, prompt, options, apiKey, baseUrl);
  }

  // --- Image Editing ---
  public async editImage(
    _modelId: string,
    _prompt: string,
    _referenceImages: Record<string, any>,
    _options: ChatOptions,
    _baseUrl: string
  ): Promise<ImageGenerationResult[]> {
    throw new Error("Image editing not supported for Tongyi provider. Please use Google provider with Vertex AI configuration.");
  }

  // --- Out-Painting ---
  public async outPaintImage(
    referenceImage: Attachment,
    options: ChatOptions,
    _apiKey: string,
    _baseUrl?: string
  ): Promise<ImageGenerationResult> {
    return outPaintWanxImage(referenceImage, options);
  }

  // --- File Upload (已弃用 - 后端处理文件上传) ---
  public async uploadFile(_file: File, _apiKey: string, _baseUrl: string): Promise<string> {
    throw new Error("Direct file upload is deprecated. Backend handles file uploads via JWT authentication.");
  }
}

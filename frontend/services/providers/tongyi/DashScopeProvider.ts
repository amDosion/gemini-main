import { ILLMProvider, StreamUpdate, ImageGenerationResult } from "../interfaces";
import { ModelConfig, Message, Attachment, ChatOptions } from "../../../types/types";
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { generateDashScopeImage } from "./image-gen";
import { editWanxImage } from "./image-edit";
import { outPaintWanxImage } from "./image-expand";
import { uploadDashScopeFile } from "./api";

export class DashScopeProvider extends OpenAIProvider implements ILLMProvider {
  public id = 'tongyi'; 
  
  public async getAvailableModels(apiKey: string, _baseUrl: string): Promise<ModelConfig[]> {
    const response = await fetch(`/api/models/tongyi?apiKey=${encodeURIComponent(apiKey)}`);
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
    apiKey: string,
    _baseUrl: string
  ): AsyncGenerator<StreamUpdate, void, unknown> {
    // 统一使用后端 API（包括视觉模型）
    const response = await fetch('/api/chat/tongyi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
        apiKey,
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
      return [await editWanxImage(modelId, prompt, referenceImages[0], options, apiKey, baseUrl)];
    }
    return generateDashScopeImage(modelId, prompt, options, apiKey, baseUrl);
  }

  // --- Out-Painting ---
  public async outPaintImage(
    referenceImage: Attachment,
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string
  ): Promise<ImageGenerationResult> {
    return outPaintWanxImage(referenceImage, options, apiKey, baseUrl);
  }

  // --- File Upload ---
  public async uploadFile(file: File, apiKey: string, baseUrl: string): Promise<string> {
    return uploadDashScopeFile(file, apiKey, baseUrl);
  }
}

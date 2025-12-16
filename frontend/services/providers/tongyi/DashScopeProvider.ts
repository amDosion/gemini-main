
import { ILLMProvider, StreamUpdate, ImageGenerationResult, VideoGenerationResult, AudioGenerationResult } from "../interfaces";
import { ModelConfig, Message, Attachment, ChatOptions } from "../../../../types";
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { getTongYiModels } from "./models";
import { streamNativeDashScope } from "./chat";
import { generateDashScopeImage } from "./image-gen";
import { editWanxImage } from "./image-edit";
import { outPaintWanxImage } from "./image-expand";
import { uploadDashScopeFile } from "./api";

export class DashScopeProvider extends OpenAIProvider implements ILLMProvider {
  public id = 'tongyi'; 
  
  public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
      return getTongYiModels(apiKey, baseUrl);
  }

  // --- Chat / Streaming (Native Support) ---
  public async *sendMessageStream(
    modelId: string,
    history: Message[],
    message: string,
    attachments: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): AsyncGenerator<StreamUpdate, void, unknown> {
      // Models that support Native API features
      const isNativeCandidate = 
          modelId === 'qwen-deep-research' || 
          modelId.includes('qwq') || 
          modelId.includes('qwen-max') || 
          modelId.includes('qwen-plus') || 
          modelId.includes('qwen-turbo') ||
          (options.enableSearch || options.enableThinking);

      // 1. Try Native API (if applicable)
      if (isNativeCandidate && !modelId.includes('vl')) {
          try {
              yield* streamNativeDashScope(modelId, history, message, attachments, options, apiKey, baseUrl);
              return;
          } catch (e: any) {
              console.warn("Native DashScope call failed:", e);
              const isNetworkError = e.message.includes('Network Error') || e.message.includes('Failed to fetch') || e.message.includes('CORS');
              const reason = isNetworkError ? "Network/CORS restriction" : (e.message || "Unknown error");
              yield { text: `\n\n> ⚠️ **System Notice**: Native mode unavailable (${reason}). Switching to compatibility mode (Search/Thinking may be disabled).\n\n` };
          }
      }

      // 2. Fallback: OpenAI Compatibility Layer
      try {
          yield* super.sendMessageStream(modelId, history, message, attachments, options, apiKey, baseUrl);
      } catch (e: any) {
          console.error("DashScope Fallback Error:", e);
          yield { text: `\n\n❌ **Error**: Connection failed.\n\nCould not connect to DashScope via Native or Compatibility modes.\n\n**Troubleshooting:**\n- Check your API Key.\n- If using a custom proxy, verify the Base URL.\n- If running in a browser without a proxy, CORS may be blocking requests.\n\nDetails: ${e.message}` };
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
      
      // If we have a reference image, it's Editing (Image-to-Image)
      if (referenceImages && referenceImages.length > 0) {
          // Pass full options to support LoRA/Seed in editing
          return [await editWanxImage(modelId, prompt, referenceImages[0], options, apiKey, baseUrl)];
      }

      // Otherwise, Text-to-Image (using new Logic)
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

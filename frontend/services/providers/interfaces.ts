
import { ModelConfig, Message, Attachment, ChatOptions } from '../../../types';

export interface StreamUpdate {
  text: string;
  attachments?: Attachment[];
  groundingMetadata?: any;
  urlContextMetadata?: any; // Added URL Context Metadata
  browserOperationId?: string; // Added: Browser tool operation ID
}

export interface ImageGenerationResult {
  url: string;
  mimeType: string;
}

export interface VideoGenerationResult {
  url: string;
  mimeType: string;
}

export interface AudioGenerationResult {
  url: string;
  mimeType: string;
}

export interface ILLMProvider {
  id: string;
  
  getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]>;
  
  sendMessageStream(
    modelId: string,
    history: Message[],
    message: string,
    attachments: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): AsyncGenerator<StreamUpdate, void, unknown>;

  // Updated to accept array of attachments for reference
  generateImage(
    modelId: string,
    prompt: string,
    referenceImages: Attachment[], 
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): Promise<ImageGenerationResult[]>;

  generateVideo(
    prompt: string,
    referenceImages: Attachment[], // Changed from single Attachment | undefined to Attachment[]
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
  ): Promise<VideoGenerationResult>;

  generateSpeech(
    text: string,
    voiceName: string,
    apiKey: string,
    baseUrl: string
  ): Promise<AudioGenerationResult>;

  // New: Outpainting (Keep single for now as it's usually canvas based, but return array for consistency)
  outPaintImage?(
    referenceImage: Attachment,
    options: ChatOptions,
    apiKey: string, // Specifically the DashScope Key
    baseUrl?: string // Added baseUrl
  ): Promise<ImageGenerationResult>;

  uploadFile(file: File, apiKey: string, baseUrl: string): Promise<string>;
}

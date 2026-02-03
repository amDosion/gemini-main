
import { ModelConfig, Message, Attachment, ChatOptions } from '../../types/types';

export interface ToolCall {
  name: string;
  args: Record<string, any>;
}

export interface ToolResult {
  name: string;
  result: string;
  screenshot?: string; // Base64 encoded PNG screenshot (fallback)
  screenshotUrl?: string; // URL of uploaded screenshot (preferred)
}

export interface StreamUpdate {
  text: string;
  attachments?: Attachment[];
  groundingMetadata?: any;
  urlContextMetadata?: any; // Added URL Context Metadata
  browserOperationId?: string; // Added: Browser tool operation ID
  toolCall?: ToolCall; // Browser tool call (function calling)
  toolResult?: ToolResult; // Browser tool result
}

export interface ImageGenerationResult {
  url: string;  // 显示URL（Base64 Data URL 或 HTTP URL）
  mimeType: string;
  filename?: string; // Optional filename for generated images
  // ✅ 附件元数据（后端统一附件处理）
  attachmentId?: string;  // 附件ID
  messageId?: string;  // 消息ID
  sessionId?: string;  // 会话ID
  userId?: string;  // 用户ID
  uploadStatus?: 'pending' | 'completed' | 'failed';  // 上传状态
  taskId?: string;  // 上传任务ID
  cloudUrl?: string;  // 云存储URL（如果已上传完成）
  size?: number;  // 文件大小（bytes）
  createdAt?: number;  // 创建时间戳
  // ✅ AI 响应元数据
  thoughts?: Array<{ type: 'text' | 'image'; content: string }>; // 思考过程（thoughts）
  text?: string; // 文本响应
  enhancedPrompt?: string; // 增强后的提示词（当启用 enhance_prompt 时返回）
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
  
  // API Key is now managed by backend for UnifiedProviderClient
  // Other providers may still require apiKey parameter
  /**
   * Get available models for this provider
   * @param apiKey - Optional API key (for verification/testing)
   * @param baseUrl - Optional base URL
   * @param useCache - Whether to use cached models (default: true)
   */
  getAvailableModels(apiKey?: string, baseUrl?: string, useCache?: boolean): Promise<ModelConfig[]>;
  
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

  // New: Image editing (Google Imagen edit_image API)
  editImage(
    modelId: string,
    prompt: string,
    referenceImages: Record<string, any>, // Dictionary of reference images (raw, mask, control, style, subject, content)
    options: ChatOptions,
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

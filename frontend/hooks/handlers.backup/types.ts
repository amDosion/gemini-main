/**
 * 模式处理器的公共类型定义
 */
import { Message, Attachment, ChatOptions, ModelConfig, AppMode } from '../../../types';

/**
 * 处理器上下文 - 包含处理器需要的所有依赖
 */
export interface HandlerContext {
  sessionId: string;
  userMessageId: string;
  modelMessageId: string;
  apiKey?: string;
  currentModel: ModelConfig;
  options: ChatOptions;
  protocol: 'google' | 'openai';
}

/**
 * 处理器结果
 */
export interface HandlerResult {
  content: string;
  attachments: Attachment[];
  groundingMetadata?: any;
  urlContextMetadata?: any;
  browserOperationId?: string;
  isError?: boolean;
}

/**
 * 流式更新回调
 */
export type StreamUpdateCallback = (partial: Partial<HandlerResult>) => void;

/**
 * 上传到云存储的函数类型
 */
export type UploadToCloudStorageFn = (
  imageSource: string | File,
  messageId: string,
  attachmentId: string,
  sessionId: string,
  filename?: string
) => Promise<void>;

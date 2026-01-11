/**
 * 旧的 Handler 类型定义（兼容层）
 * 
 * 这些类型用于桥接新的基于类的 Handler 和旧的函数式 handler
 */

import { Attachment, ChatOptions, ModelConfig } from '../../types/types';

/**
 * 旧的 HandlerContext 接口（用于现有的函数式 handler）
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
 * 旧的 HandlerResult 接口（用于现有的函数式 handler）
 */
export interface HandlerResult {
  content: string;
  attachments: Attachment[];
  groundingMetadata?: any;
  urlContextMetadata?: any;
  browserOperationId?: string;
}

/**
 * 流式更新回调类型
 */
export type StreamUpdateCallback = (update: {
  content?: string;
  attachments?: Attachment[];
  groundingMetadata?: any;
  urlContextMetadata?: any;
  browserOperationId?: string;
}) => void;

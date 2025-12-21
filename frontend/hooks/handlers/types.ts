/**
 * 核心接口和类型定义
 * 
 * 本文件定义了 useChat 重构所需的所有核心接口和类型。
 * 这些接口遵循 SOLID 原则，特别是依赖倒置原则（DIP）。
 */

import { Attachment, AppMode, ChatOptions, ModelConfig, GroundingMetadata, UrlContextMetadata } from '../../types/types';
import { llmService } from '../../services/llmService';
import { storageUpload } from '../../services/storage/storageUpload';

/**
 * 流式更新的类型定义
 */
export interface StreamUpdate {
  content?: string;
  attachments?: Attachment[];
  groundingMetadata?: GroundingMetadata;
  urlContextMetadata?: UrlContextMetadata;
  browserOperationId?: string;
}

/**
 * 进度更新的类型定义
 */
export interface ProgressUpdate {
  attachmentId?: string;
  status?: 'pending' | 'uploading' | 'completed' | 'failed';
  progress?: number;  // 0-100
  message?: string;
}

/**
 * 上传状态接口
 */
export interface UploadStatus {
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  progress?: number;
  error?: string;
  result?: any;
  targetUrl?: string;
  errorMessage?: string;
}

/**
 * 轮询配置接口
 */
export interface PollingConfig {
  /**
   * 轮询间隔（毫秒）
   */
  interval: number;
  
  /**
   * 最大轮询次数
   */
  maxAttempts: number;
  
  /**
   * 超时时间（毫秒）
   */
  timeout?: number;
  
  /**
   * 状态检查回调
   */
  onStatusCheck: (taskId: string) => Promise<UploadStatus>;
  
  /**
   * 成功回调
   */
  onSuccess?: (taskId: string, result: any) => void;
  
  /**
   * 失败回调
   */
  onFailure?: (taskId: string, error: Error) => void;
}

/**
 * 轮询任务接口
 */
export interface PollingTask {
  taskId: string;
  config: PollingConfig;
  attempts: number;
  timerId?: number;
  delayTimerId?: number;  // 延迟启动的定时器 ID（修复问题8）
  startTime: number;
}

/**
 * 轮询管理器接口
 */
export interface IPollingManager {
  startPolling(taskId: string, config: PollingConfig): Promise<void>;
  stopPolling(taskId: string): void;
  cleanup(): void;
}

/**
 * 执行上下文接口
 * 传递给 Handler 的执行上下文，包含所有必需的信息和服务实例
 */
export interface ExecutionContext {
  // 基础信息（必填）
  sessionId: string;
  userMessageId: string;
  modelMessageId: string;
  mode: AppMode;
  
  // 输入数据（必填）
  text: string;
  attachments: Attachment[];
  
  // 配置（必填）
  currentModel: ModelConfig;
  options: ChatOptions;
  protocol: 'google' | 'openai';
  
  // 可选配置
  apiKey?: string;
  timeout?: number;  // 超时时间（毫秒），默认 30000
  
  // 回调函数（可选）
  onStreamUpdate?: (update: StreamUpdate) => void;
  onProgressUpdate?: (progress: ProgressUpdate) => void;
  
  // 服务实例（必填）
  llmService: typeof llmService;
  storageService: typeof storageUpload;
  
  // 轮询管理器（必填）- 全局单例，由 useChat Hook 创建并传递（修复问题1）
  pollingManager: IPollingManager;
}

/**
 * 失败操作记录
 */
export interface FailedOperation {
  operation: string;
  error: Error;
  recoverable?: boolean;
}

/**
 * 上传任务结果类型
 */
export interface UploadTaskResult {
  dbAttachments: Attachment[];
  dbUserAttachments?: Attachment[];
}

/**
 * Handler 执行结果接口
 * 使用 Readonly 类型确保不可变性（修复问题3）
 */
export interface HandlerResult {
  // 基础结果（必填）
  readonly content: string;
  readonly attachments: ReadonlyArray<Attachment>;
  
  // 可选的元数据（使用正确的类型定义）
  readonly groundingMetadata?: GroundingMetadata;
  readonly urlContextMetadata?: UrlContextMetadata;
  readonly browserOperationId?: string;
  
  // 上传任务（用于异步上传）
  readonly uploadTask?: Promise<UploadTaskResult>;
  
  // 数据库保存用的附件（如果与显示附件不同）
  readonly dbAttachments?: ReadonlyArray<Attachment>;
  readonly dbUserAttachments?: ReadonlyArray<Attachment>;
  
  // 部分失败支持（修复问题6）
  readonly partialSuccess?: boolean;
  readonly failedOperations?: ReadonlyArray<FailedOperation>;
}

/**
 * Handler 错误接口
 * 扩展标准 Error 类型，添加错误码和上下文信息（修复问题4）
 */
export interface HandlerError extends Error {
  /**
   * 错误码，可以是字符串或数字
   * 例如：'INVALID_INPUT', 429, 'RESOURCE_EXHAUSTED'
   */
  code: string | number;
  
  /**
   * 错误状态（可选）
   * 例如：'INVALID_ARGUMENT', 'RESOURCE_EXHAUSTED', 'INTERNAL'
   */
  status?: string;
  
  /**
   * 错误上下文信息（可选）
   * 包含发生错误时的相关信息，用于调试和日志记录
   */
  context?: {
    mode: AppMode;
    sessionId: string;
    [key: string]: any;
  };
}

/**
 * HandlerError 类实现
 * 统一所有 Handler 的错误类型（修复问题4）
 */
export class HandlerErrorImpl extends Error implements HandlerError {
  code: string | number;
  status?: string;
  context?: {
    mode: AppMode;
    sessionId: string;
    [key: string]: any;
  };
  
  constructor(
    message: string,
    code: string | number,
    status?: string,
    context?: {
      mode: AppMode;
      sessionId: string;
      [key: string]: any;
    }
  ) {
    super(message);
    this.name = 'HandlerError';
    this.code = code;
    this.status = status;
    this.context = context;
    
    // 保持正确的原型链
    Object.setPrototypeOf(this, HandlerErrorImpl.prototype);
  }
}

/**
 * ModeHandler 接口
 * 所有 Handler 必须实现的核心接口
 */
export interface ModeHandler {
  /**
   * 执行 Handler 的核心逻辑
   * @param context 执行上下文
   * @returns Handler 执行结果
   */
  execute(context: ExecutionContext): Promise<HandlerResult>;

  /**
   * Handler 开始执行时的钩子（可选）
   * 
   * **调用时机：** 在 execute() 方法调用之前，由协调者同步调用
   * **用途：** 初始化资源、记录日志、更新 UI 状态
   * **注意：** 此钩子应该是同步的，不应包含耗时操作
   * **错误处理：** 如果此钩子抛出错误，execute() 将不会被调用
   */
  onStart?(): void;

  /**
   * Handler 执行完成时的钩子（可选）
   * 
   * **调用时机：** 在 execute() 成功返回后，由协调者同步调用
   * **用途：** 清理资源、记录日志、触发后续操作
   * **注意：** 此钩子应该是同步的，不应包含耗时操作
   * **错误处理：** 如果此钩子抛出错误，不会影响 execute() 的结果，但会被记录
   * 
   * @param result 执行结果
   */
  onComplete?(result: HandlerResult): void;

  /**
   * Handler 执行失败时的钩子（可选）
   * 
   * **调用时机：** 在 execute() 抛出错误后，由协调者同步调用
   * **用途：** 清理资源、记录错误日志、触发错误恢复逻辑
   * **注意：** 此钩子不应该重新抛出错误，应该静默处理
   * **错误处理：** 如果此钩子抛出错误，会被记录但不会向上传播
   * 
   * @param error 错误对象
   */
  onError?(error: Error): void;

  /**
   * Handler 被取消时的钩子（可选）
   * 
   * **调用时机：** 当用户取消操作时，由协调者同步调用
   * **用途：** 取消正在进行的请求、清理资源、更新 UI 状态
   * **注意：** 此钩子应该尽快完成，避免阻塞 UI
   * **错误处理：** 如果此钩子抛出错误，会被记录但不会向上传播
   */
  onCancel?(): void;
}

/**
 * 前置处理器接口
 * 用于在 Handler 执行前处理特定的逻辑（如 Google 文件上传）
 */
export interface Preprocessor {
  /**
   * 优先级（可选）
   * 数字越小优先级越高，默认为 999（修复问题2）
   */
  priority?: number;
  
  /**
   * 判断是否可以处理当前上下文
   * @param context 执行上下文
   * @returns 是否可以处理
   */
  canHandle(context: ExecutionContext): boolean;
  
  /**
   * 处理上下文，返回修改后的上下文
   * @param context 执行上下文
   * @returns 修改后的执行上下文
   */
  process(context: ExecutionContext): Promise<ExecutionContext>;
}

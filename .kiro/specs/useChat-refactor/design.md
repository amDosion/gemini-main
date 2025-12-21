# Design Document

## Overview

本设计文档描述了如何将 `useChat.ts` 重构为基于策略模式的协调者架构。核心思想是将当前的巨大 `if-else` 链替换为可扩展的策略映射系统，使 `useChat` 成为一个纯粹的协调者，而将具体的业务逻辑委托给各个 Handler。

## Architecture

### 高层架构

```
┌─────────────────────────────────────────────────────────────┐
│                        useChat Hook                          │
│                      (Coordinator)                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  1. 初始化上下文                                        │ │
│  │  2. 处理文件上传（Google 特定）                         │ │
│  │  3. 创建用户消息                                        │ │
│  │  4. 创建模型消息占位符                                  │ │
│  │  5. 通过 StrategyRegistry 选择 Handler                 │ │
│  │  6. 执行 Handler                                        │ │
│  │  7. 统一错误处理                                        │ │
│  │  8. 统一状态管理                                        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    StrategyRegistry                          │
│                   (Strategy Selector)                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Map<AppMode, ModeHandler>                             │ │
│  │  - chat         → ChatHandler                          │ │
│  │  - image-gen    → ImageGenHandler                      │ │
│  │  - image-edit   → ImageEditHandler                     │ │
│  │  - image-outpainting → ImageOutpaintingHandler         │ │
│  │  - virtual-try-on → VirtualTryOnHandler                │ │
│  │  - video-gen    → VideoGenHandler                      │ │
│  │  - audio-gen    → AudioGenHandler                      │ │
│  │  - pdf-extract  → PdfExtractHandler                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      ModeHandler                             │
│                   (Strategy Interface)                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  execute(context): Promise<HandlerResult>              │ │
│  │  onStart?(): void                                      │ │
│  │  onComplete?(result): void                             │ │
│  │  onError?(error): void                                 │ │
│  │  onCancel?(): void                                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Concrete Handlers                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ ChatHandler  │  │ImageGenHandler│ │ImageEditHandler│     │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │VideoGenHandler│ │AudioGenHandler│ │PdfExtractHandler│    │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

```
用户输入
   │
   ▼
useChat.sendMessage()
   │
   ├─→ 1. 构建 ExecutionContext
   │
   ├─→ 2. 处理文件上传（如需要）
   │
   ├─→ 3. 创建用户消息 + 模型消息占位符
   │
   ├─→ 4. StrategyRegistry.getHandler(mode)
   │      │
   │      ▼
   │   返回对应的 ModeHandler
   │
   ├─→ 5. handler.execute(context)
   │      │
   │      ├─→ 调用具体业务逻辑
   │      │
   │      ├─→ 通过回调更新 UI
   │      │
   │      └─→ 返回 HandlerResult
   │
   ├─→ 6. 处理结果
   │      │
   │      ├─→ 更新前端显示（本地 URL）
   │      │
   │      └─→ 保存到数据库（云存储 URL）
   │
   └─→ 7. 错误处理 + 状态管理
```

## Components and Interfaces

### 1. ModeHandler Interface

所有 Handler 必须实现的核心接口：

```typescript
interface ModeHandler {
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
```

### 2. ExecutionContext

传递给 Handler 的执行上下文：

```typescript
interface ExecutionContext {
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
  
  // 轮询管理器（必填）- 全局单例，由 useChat Hook 创建并传递
  pollingManager: PollingManager;
}

/**
 * 流式更新的类型定义
 */
interface StreamUpdate {
  content?: string;
  attachments?: Attachment[];
  groundingMetadata?: any;
  urlContextMetadata?: any;
}

/**
 * 进度更新的类型定义
 */
interface ProgressUpdate {
  attachmentId?: string;
  status?: 'pending' | 'uploading' | 'completed' | 'failed';
  progress?: number;  // 0-100
  message?: string;
}
```

### 3. HandlerResult

Handler 执行后返回的标准化结果：

```typescript
interface HandlerResult {
  // 基础结果（必填）
  readonly content: string;
  readonly attachments: ReadonlyArray<Attachment>;
  
  // 可选的元数据
  readonly groundingMetadata?: Readonly<any>;
  readonly urlContextMetadata?: Readonly<any>;
  readonly browserOperationId?: string;
  
  // 上传任务（用于异步上传）
  readonly uploadTask?: Promise<UploadTaskResult>;
  
  // 数据库保存用的附件（如果与显示附件不同）
  readonly dbAttachments?: ReadonlyArray<Attachment>;
  readonly dbUserAttachments?: ReadonlyArray<Attachment>;
  
  // 部分失败支持
  readonly partialSuccess?: boolean;
  readonly failedOperations?: ReadonlyArray<FailedOperation>;
}

/**
 * 上传任务结果类型
 */
interface UploadTaskResult {
  dbAttachments: Attachment[];
  dbUserAttachments?: Attachment[];
}

/**
 * 失败操作记录
 */
interface FailedOperation {
  operation: string;
  error: Error;
  recoverable?: boolean;
}
```

**不可变性约定：**
- `HandlerResult` 应该是不可变的，使用 `Readonly` 类型约束
- Handler 返回新对象，不共享引用
- 协调者如需修改结果，应创建新对象

### 4. HandlerError

标准化的错误类型，用于 Handler 抛出的错误：

```typescript
/**
 * Handler 错误接口
 * 扩展标准 Error 类型，添加错误码和上下文信息
 */
interface HandlerError extends Error {
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
 */
class HandlerErrorImpl extends Error implements HandlerError {
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
```

### 5. StrategyRegistry

策略注册表，负责管理和选择 Handler：

```typescript
class StrategyRegistry {
  private strategies: Map<AppMode, ModeHandler>;
  private finalized: boolean = false;
  
  constructor() {
    this.strategies = new Map();
  }
  
  /**
   * 注册一个 Handler
   * @param mode 应用模式
   * @param handler Handler 实例
   * @throws Error 如果注册表已经被锁定
   */
  register(mode: AppMode, handler: ModeHandler): void {
    if (this.finalized) {
      throw new Error('Cannot register handler after registry is finalized');
    }
    this.strategies.set(mode, handler);
  }
  
  /**
   * 锁定注册表，防止运行时动态注册
   * 应该在模块加载完成后调用
   */
  finalize(): void {
    this.finalized = true;
  }
  
  /**
   * 获取指定模式的 Handler
   * @param mode 应用模式
   * @returns Handler 实例
   * @throws HandlerError 如果找不到对应的 Handler
   */
  getHandler(mode: AppMode): ModeHandler {
    const handler = this.strategies.get(mode);
    if (!handler) {
      throw new HandlerErrorImpl(
        `No handler registered for mode: ${mode}`,
        'HANDLER_NOT_FOUND',
        'INVALID_ARGUMENT',
        { mode }
      );
    }
    return handler;
  }
  
  /**
   * 检查是否注册了指定模式的 Handler
   * @param mode 应用模式
   * @returns 是否已注册
   */
  hasHandler(mode: AppMode): boolean {
    return this.strategies.has(mode);
  }
}
```

### 6. PollingManager

轮询管理器，负责管理上传任务的状态轮询：

```typescript
/**
 * 轮询配置接口
 */
interface PollingConfig {
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
interface PollingTask {
  taskId: string;
  config: PollingConfig;
  attempts: number;
  timerId?: number;
  delayTimerId?: number;  // 延迟启动的定时器 ID
  startTime: number;
}

/**
 * 上传状态接口
 */
interface UploadStatus {
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  progress?: number;
  error?: string;
  result?: any;
}

/**
 * 轮询管理器类
 */
class PollingManager {
  private tasks: Map<string, PollingTask> = new Map();
  private maxConcurrent: number = 5;
  private activeTasks: number = 0;
  
  /**
   * 启动轮询任务
   * @param taskId 任务 ID
   * @param config 轮询配置
   * @returns Promise，在任务完成或失败时 resolve
   */
  startPolling(taskId: string, config: PollingConfig): Promise<void> {
    return new Promise((resolve, reject) => {
      const task: PollingTask = {
        taskId,
        config,
        attempts: 0,
        startTime: Date.now()
      };
      
      this.tasks.set(taskId, task);
      
      // 如果达到并发上限，等待
      if (this.activeTasks >= this.maxConcurrent) {
        // 追踪延迟定时器
        task.delayTimerId = window.setTimeout(() => {
          task.delayTimerId = undefined;
          this.pollOnce(task, resolve, reject);
        }, config.interval);
      } else {
        this.pollOnce(task, resolve, reject);
      }
    });
  }
  
  /**
   * 执行一次轮询
   */
  private async pollOnce(
    task: PollingTask,
    resolve: () => void,
    reject: (error: Error) => void
  ): Promise<void> {
    this.activeTasks++;
    task.attempts++;
    
    try {
      const status = await task.config.onStatusCheck(task.taskId);
      
      if (status.status === 'completed') {
        task.config.onSuccess?.(task.taskId, status.result);
        this.cleanup(task.taskId);
        this.activeTasks--;
        resolve();
        return;
      }
      
      if (status.status === 'failed') {
        const error = new Error(status.error || 'Upload failed');
        task.config.onFailure?.(task.taskId, error);
        this.cleanup(task.taskId);
        this.activeTasks--;
        reject(error);
        return;
      }
      
      // 检查是否超时
      if (task.config.timeout && Date.now() - task.startTime > task.config.timeout) {
        const error = new Error('Polling timeout');
        task.config.onFailure?.(task.taskId, error);
        this.cleanup(task.taskId);
        this.activeTasks--;
        reject(error);
        return;
      }
      
      // 检查是否达到最大尝试次数
      if (task.attempts >= task.config.maxAttempts) {
        const error = new Error('Max polling attempts reached');
        task.config.onFailure?.(task.taskId, error);
        this.cleanup(task.taskId);
        this.activeTasks--;
        reject(error);
        return;
      }
      
      // 继续轮询
      task.timerId = window.setTimeout(() => {
        this.pollOnce(task, resolve, reject);
      }, task.config.interval);
      
    } catch (error) {
      task.config.onFailure?.(task.taskId, error as Error);
      this.cleanup(task.taskId);
      this.activeTasks--;
      reject(error as Error);
    }
  }
  
  /**
   * 停止轮询任务
   * @param taskId 任务 ID
   */
  stopPolling(taskId: string): void {
    const task = this.tasks.get(taskId);
    if (task) {
      // 清理轮询定时器
      if (task.timerId) {
        clearTimeout(task.timerId);
        this.activeTasks--;
      }
      // 清理延迟定时器
      if (task.delayTimerId) {
        clearTimeout(task.delayTimerId);
      }
    }
    this.cleanup(taskId);
  }
  
  /**
   * 清理所有轮询任务
   */
  cleanup(): void {
    this.tasks.forEach((task) => {
      if (task.timerId) {
        clearTimeout(task.timerId);
      }
    });
    this.tasks.clear();
    this.activeTasks = 0;
  }
  
  /**
   * 清理单个任务
   */
  private cleanup(taskId: string): void {
    this.tasks.delete(taskId);
  }
}
```

### 8. Preprocessor System

前置处理器系统，用于在 Handler 执行前处理特定的逻辑（如 Google 文件上传）：

```typescript
/**
 * 前置处理器接口
 */
interface Preprocessor {
  /**
   * 优先级（可选）
   * 数字越小优先级越高，默认为 999
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

/**
 * 前置处理器注册表
 */
class PreprocessorRegistry {
  private preprocessors: Preprocessor[] = [];
  
  /**
   * 注册前置处理器
   * @param preprocessor 前置处理器实例
   */
  register(preprocessor: Preprocessor): void {
    this.preprocessors.push(preprocessor);
    // 按优先级排序（数字越小优先级越高）
    this.preprocessors.sort((a, b) => 
      (a.priority || 999) - (b.priority || 999)
    );
  }
  
  /**
   * 执行所有适用的前置处理器
   * @param context 执行上下文
   * @returns 处理后的执行上下文
   * @throws HandlerError 如果任何 preprocessor 失败，错误会向上传播，中断整个链路
   */
  async process(context: ExecutionContext): Promise<ExecutionContext> {
    let processedContext = context;
    
    for (const preprocessor of this.preprocessors) {
      if (preprocessor.canHandle(processedContext)) {
        processedContext = await preprocessor.process(processedContext);
      }
    }
    
    return processedContext;
  }
}

/**
 * Google 文件上传前置处理器
 */
class GoogleFileUploadPreprocessor implements Preprocessor {
  priority = 10; // 高优先级，确保在其他 preprocessor 之前执行
  
  canHandle(context: ExecutionContext): boolean {
    return (
      context.protocol === 'google' &&
      context.mode === 'chat' &&
      context.attachments.some(att => att.file && !att.fileUri)
    );
  }
  
  async process(context: ExecutionContext): Promise<ExecutionContext> {
    // 使用深拷贝确保不可变性
    const clonedContext = this.deepClone(context);
    
    // 处理文件上传逻辑
    const uploadedAttachments = await this.uploadFiles(clonedContext.attachments, clonedContext);
    
    return {
      ...clonedContext,
      attachments: uploadedAttachments
    };
  }
  
  private async uploadFiles(
    attachments: Attachment[],
    context: ExecutionContext
  ): Promise<Attachment[]> {
    // 使用 Promise.allSettled 并行上传，支持部分失败
    const results = await Promise.allSettled(
      attachments.map(att => this.uploadFile(att, context))
    );
    
    const successfulAttachments = results
      .filter(r => r.status === 'fulfilled')
      .map(r => (r as PromiseFulfilledResult<Attachment>).value);
    
    const failedAttachments = results
      .filter(r => r.status === 'rejected')
      .map((r, index) => ({
        attachment: attachments[index],
        error: (r as PromiseRejectedResult).reason
      }));
    
    // 如果有失败的上传，抛出错误
    if (failedAttachments.length > 0) {
      throw new HandlerErrorImpl(
        `Failed to upload ${failedAttachments.length} files`,
        'FILE_UPLOAD_FAILED',
        'INTERNAL',
        {
          mode: context.mode,
          sessionId: context.sessionId,
          failedAttachments
        }
      );
    }
    
    return successfulAttachments;
  }
  
  private async uploadFile(
    attachment: Attachment,
    context: ExecutionContext
  ): Promise<Attachment> {
    // 实现单个文件上传逻辑
    // 调用 context.storageService.uploadFile()
    // 返回包含 fileUri 的附件
    return attachment; // 简化示例
  }
  
  /**
   * 深拷贝对象，确保不可变性
   * 使用 structuredClone() 而不是 JSON.parse/stringify
   * 优势：支持 Date、Set、Map、RegExp、ArrayBuffer 等复杂类型
   * 性能：比 JSON 方法更快
   * 浏览器支持：Chrome 98+, Firefox 94+, Safari 15.4+
   */
  private deepClone<T>(obj: T): T {
    return structuredClone(obj);
  }
}
```

### 9. BaseHandler (抽象基类)

提供通用功能的抽象基类，减少代码重复：

```typescript
abstract class BaseHandler implements ModeHandler {
  /**
   * 使用模板方法模式，强制子类调用验证方法
   * 此方法为 final，不允许子类覆盖
   */
  async execute(context: ExecutionContext): Promise<HandlerResult> {
    // 自动调用验证
    this.validateContext(context);
    this.validateAttachments(context.attachments, context);
    
    // 调用子类实现
    return await this.doExecute(context);
  }
  
  /**
   * 子类必须实现此方法
   * @param context 执行上下文
   * @returns Handler 执行结果
   */
  protected abstract doExecute(context: ExecutionContext): Promise<HandlerResult>;
  
  /**
   * 验证执行上下文
   * @param context 执行上下文
   * @throws HandlerError 如果验证失败
   */
  protected validateContext(context: ExecutionContext): void {
    if (!context.sessionId) {
      throw new HandlerErrorImpl(
        'sessionId is required',
        'INVALID_CONTEXT',
        'INVALID_ARGUMENT',
        { mode: context.mode, sessionId: context.sessionId }
      );
    }
    
    if (!context.userMessageId) {
      throw new HandlerErrorImpl(
        'userMessageId is required',
        'INVALID_CONTEXT',
        'INVALID_ARGUMENT',
        { mode: context.mode, sessionId: context.sessionId }
      );
    }
    
    if (!context.modelMessageId) {
      throw new HandlerErrorImpl(
        'modelMessageId is required',
        'INVALID_CONTEXT',
        'INVALID_ARGUMENT',
        { mode: context.mode, sessionId: context.sessionId }
      );
    }
    
    if (!context.mode) {
      throw new HandlerErrorImpl(
        'mode is required',
        'INVALID_CONTEXT',
        'INVALID_ARGUMENT',
        { mode: context.mode, sessionId: context.sessionId }
      );
    }
    
    if (!context.currentModel) {
      throw new HandlerErrorImpl(
        'currentModel is required',
        'INVALID_CONTEXT',
        'INVALID_ARGUMENT',
        { mode: context.mode, sessionId: context.sessionId }
      );
    }
  }
  
  /**
   * 验证附件
   * @param attachments 附件数组
   * @param context 执行上下文
   * @throws HandlerError 如果验证失败
   */
  protected validateAttachments(
    attachments: Attachment[],
    context: ExecutionContext
  ): void {
    for (const attachment of attachments) {
      if (!attachment.id) {
        throw new HandlerErrorImpl(
          'Attachment id is required',
          'INVALID_ATTACHMENT',
          'INVALID_ARGUMENT',
          { mode: context.mode, sessionId: context.sessionId, attachmentId: attachment.id }
        );
      }
      
      if (!attachment.type) {
        throw new HandlerErrorImpl(
          'Attachment type is required',
          'INVALID_ATTACHMENT',
          'INVALID_ARGUMENT',
          { mode: context.mode, sessionId: context.sessionId, attachmentId: attachment.id }
        );
      }
      
      if (!attachment.url && !attachment.file && !attachment.fileUri) {
        throw new HandlerErrorImpl(
          'Attachment must have url, file, or fileUri',
          'INVALID_ATTACHMENT',
          'INVALID_ARGUMENT',
          { mode: context.mode, sessionId: context.sessionId, attachmentId: attachment.id }
        );
      }
    }
  }
  
  /**
   * 处理上传任务并启动后台轮询
   * @param attachments 需要上传的附件
   * @param context 执行上下文
   * @returns 上传任务 Promise
   */
  protected async handleUploadWithPolling(
    attachments: Attachment[],
    context: ExecutionContext
  ): Promise<{ dbAttachments: Attachment[] }> {
    // 提交上传任务（不等待完成）
    const dbAttachments = await this.submitUploadTasks(attachments, context);
    
    // 启动后台轮询（使用全局 pollingManager）
    this.startUploadPolling(dbAttachments, context);
    
    return { dbAttachments };
  }
  
  /**
   * 提交上传任务到后端
   */
  protected async submitUploadTasks(
    attachments: Attachment[],
    context: ExecutionContext
  ): Promise<Attachment[]> {
    // 实现上传任务提交逻辑
    // ...
  }
  
  /**
   * 启动上传状态轮询
   * 使用全局 PollingManager 管理轮询任务
   */
  protected startUploadPolling(
    attachments: Attachment[],
    context: ExecutionContext
  ): void {
    attachments.forEach((attachment) => {
      if (attachment.uploadTaskId) {
        // 使用全局 pollingManager（从 context 获取）
        context.pollingManager.startPolling(attachment.uploadTaskId, {
          interval: 2000, // 2秒轮询一次
          maxAttempts: 30, // 最多30次（60秒）
          timeout: 60000, // 60秒超时
          onStatusCheck: async (taskId) => {
            // 调用后端 API 检查上传状态
            const status = await context.storageService.checkUploadStatus(taskId);
            return status;
          },
          onSuccess: (taskId, result) => {
            // 更新附件状态
            context.onProgressUpdate?.({
              attachmentId: attachment.id,
              status: 'completed',
              progress: 100
            });
          },
          onFailure: (taskId, error) => {
            // 更新附件状态为失败
            context.onProgressUpdate?.({
              attachmentId: attachment.id,
              status: 'failed',
              message: error.message
            });
          }
        }).catch((error) => {
          // 捕获 Promise rejection，记录错误但不影响主流程
          console.error(`[PollingManager] Failed to start polling for ${attachment.uploadTaskId}:`, error);
        });
      }
    });
  }
  
  /**
   * 标准化错误处理
   */
  protected handleError(error: any): never {
    // 实现错误转换逻辑
    throw error;
  }
}
```

### 6. Concrete Handlers

#### ChatHandler

```typescript
class ChatHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const { text, attachments, onStreamUpdate } = context;
    
    // 调用现有的 handleChat 函数
    const result = await handleChat(
      text,
      attachments,
      this.buildHandlerContext(context),
      onStreamUpdate
    );
    
    return {
      content: result.content,
      attachments: result.attachments,
      groundingMetadata: result.groundingMetadata,
      urlContextMetadata: result.urlContextMetadata,
      browserOperationId: result.browserOperationId
    };
  }
  
  private buildHandlerContext(context: ExecutionContext): HandlerContext {
    return {
      sessionId: context.sessionId,
      userMessageId: context.userMessageId,
      modelMessageId: context.modelMessageId,
      apiKey: context.apiKey,
      currentModel: context.currentModel,
      options: context.options,
      protocol: context.protocol
    };
  }
}
```

#### ImageGenHandler

```typescript
class ImageGenHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const { text, attachments } = context;
    
    // 调用现有的 handleImageGen 函数
    const result = await handleImageGen(
      text,
      attachments,
      this.buildHandlerContext(context)
    );
    
    // 处理上传任务
    const uploadTask = result.uploadTask
      ? this.wrapUploadTask(result.uploadTask, context)
      : undefined;
    
    return {
      content: result.content,
      attachments: result.attachments,
      uploadTask
    };
  }
  
  private async wrapUploadTask(
    originalTask: Promise<any>,
    context: ExecutionContext
  ): Promise<{ dbAttachments: Attachment[] }> {
    const { dbAttachments } = await originalTask;
    
    // 启动后台轮询
    this.startUploadPolling(dbAttachments, context);
    
    return { dbAttachments };
  }
}
```

## Data Models

### AppMode (已存在)

```typescript
type AppMode = 
  | 'chat'
  | 'image-gen'
  | 'image-edit'
  | 'image-outpainting'
  | 'virtual-try-on'
  | 'video-gen'
  | 'audio-gen'
  | 'pdf-extract';
```

### Message (已存在)

```typescript
interface Message {
  id: string;
  role: Role;
  content: string;
  attachments: Attachment[];
  timestamp: number;
  mode?: AppMode;
  groundingMetadata?: any;
  urlContextMetadata?: any;
  browserOperationId?: string;
  isError?: boolean;
}
```

### Attachment (已存在)

```typescript
interface Attachment {
  id: string;
  type: 'image' | 'video' | 'audio' | 'pdf' | 'file';
  url?: string;
  file?: File;
  fileUri?: string;
  uploadStatus?: 'pending' | 'uploading' | 'completed' | 'failed';
  uploadError?: string;
  uploadTaskId?: string;
  // ... 其他字段
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: 策略注册完整性
*For any* 预定义的 AppMode，StrategyRegistry 应该包含对应的 Handler 注册
**Validates: Requirements 1.4**

### Property 2: 策略委托正确性
*For any* AppMode 和对应的输入，useChat 应该调用正确 Handler 的 execute 方法，而不是直接执行业务逻辑
**Validates: Requirements 1.2**

### Property 3: 代码封装性
*For any* Handler 实现，其内部不应包含其他模式的业务逻辑代码
**Validates: Requirements 1.3**

### Property 4: 无条件分支
*For any* 代码路径，sendMessage 函数不应包含基于 mode 的 if-else 或 switch 语句
**Validates: Requirements 2.1**

### Property 5: 接口一致性
*For any* Handler 实现，都应该实现 ModeHandler 接口的 execute 方法
**Validates: Requirements 2.3**

### Property 6: 错误处理集中性
*For any* Handler 抛出的错误，都应该被 useChat 的统一错误处理逻辑捕获和处理
**Validates: Requirements 2.4**

### Property 7: 状态管理集中性
*For any* 状态更新操作（setMessages、setLoadingState），都应该在 useChat 中执行，而不是在 Handler 中
**Validates: Requirements 2.5**

### Property 8: Handler 职责单一性
*For any* Handler，应该只处理一种 AppMode 的业务逻辑
**Validates: Requirements 3.2**

### Property 9: 回调通信机制
*For any* Handler 需要更新 UI 时，应该通过 ExecutionContext 提供的回调函数，而不是直接操作状态
**Validates: Requirements 3.3**

### Property 10: 返回值标准化
*For any* Handler 的 execute 方法，返回值应该符合 HandlerResult 接口定义
**Validates: Requirements 3.4**

### Property 11: 错误对象标准化
*For any* Handler 抛出的错误，应该包含 message 和 code 等标准字段
**Validates: Requirements 3.5**

### Property 12: 行为向后兼容
*For any* 现有的 AppMode 和输入组合，重构后的行为应该与原始实现产生相同的结果
**Validates: Requirements 4.1**

### Property 13: 消息格式兼容
*For any* 生成的 Message 对象，其结构应该与原始实现相同
**Validates: Requirements 4.3**

### Property 14: 状态更新时序一致
*For any* 执行路径，状态更新的顺序应该与原始实现相同
**Validates: Requirements 4.4**

### Property 15: 附件处理兼容
*For any* 附件处理场景，上传、转换、存储的逻辑应该与原始实现相同
**Validates: Requirements 4.5**

### Property 16: 类型注解完整性
*For any* 函数、变量、接口，都应该有明确的 TypeScript 类型注解，不使用 any
**Validates: Requirements 5.4**

### Property 17: 代码复用性
*For any* 在多个 Handler 中出现的相同逻辑（如上传、轮询），应该提取到 BaseHandler 或工具模块中
**Validates: Requirements 6.1, 6.2, 6.3**

### Property 18: 回调接口统一性
*For any* Handler 更新消息时，应该使用统一的回调接口（如 onStreamUpdate）
**Validates: Requirements 6.4**

### Property 19: 生命周期钩子调用
*For any* 定义了生命周期钩子的 Handler，对应的钩子应该在正确的时机被调用（onStart 在 execute 前，onComplete 在成功后，onError 在失败时）
**Validates: Requirements 7.1, 7.2, 7.3**

### Property 20: Handler 可组合性
*For any* Handler 的输出（HandlerResult），应该可以作为另一个 Handler 的输入
**Validates: Requirements 8.1**

### Property 21: 策略查找性能
*For any* AppMode 查找操作，StrategyRegistry.getHandler() 的时间复杂度应该是 O(1)
**Validates: Requirements 1.4**

### Property 22: Handler 实例复用
*For any* Handler 实例，应该在模块加载时创建并在整个应用生命周期中复用，不应该在每次调用时创建新实例
**Validates: Requirements 1.4**

### Property 23: 并发轮询限制
*For any* 时刻，PollingManager 中活跃的轮询任务数量不应超过 maxConcurrent 限制
**Validates: Requirements 6.3**

### Property 24: 资源清理完整性
*For any* 组件卸载事件，所有正在进行的轮询任务、上传任务、定时器都应该被清理
**Validates: Requirements 7.5**

### Property 25: HandlerResult 不可变性
*For any* HandlerResult 对象，协调者不应该修改其内部状态，如需修改应创建新对象
**Validates: Requirements 3.4**

## Error Handling

### 错误处理策略

1. **Handler 层错误**
   - Handler 应该捕获和转换特定于模式的错误
   - 使用 BaseHandler.handleError() 进行标准化
   - 抛出 HandlerError 类型的错误对象，包含 message、code、status、context

2. **协调者层错误**
   - useChat 统一捕获所有 Handler 错误
   - 根据错误类型进行分类处理：
     - 429/RESOURCE_EXHAUSTED → 配额超限提示
     - 400/INVALID_ARGUMENT → 无效请求提示
     - 503/500 → 服务过载提示
   - 更新消息状态为错误状态（isError: true）
   - 调用 cleanupOnError() 进行错误恢复

3. **用户取消**
   - 特殊处理 "Stream aborted by user" 错误
   - 在消息末尾添加 "[Stopped]" 标记
   - 调用 Handler 的 onCancel 钩子（如果定义）
   - 取消所有正在进行的上传任务

### 错误恢复流程

```typescript
/**
 * 错误恢复函数
 * 在 Handler 执行失败时调用，清理中间状态
 */
function cleanupOnError(
  context: ExecutionContext,
  error: HandlerError
): void {
  // 1. 重置加载状态
  setLoadingState('idle');
  
  // 2. 取消正在进行的上传任务
  if (context.uploadTasks) {
    context.uploadTasks.forEach(task => {
      task.cancel?.();
    });
  }
  
  // 3. 清理轮询任务
  pollingManager.cleanup();
  
  // 4. 回滚乐观更新（如果有）
  if (context.optimisticUpdates) {
    rollbackOptimisticUpdates(context.optimisticUpdates);
  }
  
  // 5. 更新错误消息
  setMessages(prev => prev.map(msg => {
    if (msg.id === context.modelMessageId) {
      return {
        ...msg,
        content: error.message,
        isError: true
      };
    }
    return msg;
  }));
  
  // 6. 记录错误日志
  console.error('[useChat] Handler execution failed:', {
    mode: context.mode,
    sessionId: context.sessionId,
    error: {
      message: error.message,
      code: error.code,
      status: error.status,
      context: error.context
    }
  });
}

/**
 * 回滚乐观更新
 */
function rollbackOptimisticUpdates(updates: OptimisticUpdate[]): void {
  updates.forEach(update => {
    if (update.type === 'message') {
      // 移除乐观创建的消息
      setMessages(prev => prev.filter(msg => msg.id !== update.id));
    } else if (update.type === 'attachment') {
      // 移除乐观添加的附件
      setMessages(prev => prev.map(msg => {
        if (msg.id === update.messageId) {
          return {
            ...msg,
            attachments: msg.attachments.filter(att => att.id !== update.id)
          };
        }
        return msg;
      }));
    }
  });
}
```

### 错误恢复保证

- 错误发生后，loadingState 应该重置为 'idle'
- 所有正在进行的异步任务应该被取消
- 所有轮询任务应该被清理
- 乐观更新应该被回滚
- 错误消息应该保留在消息列表中，供用户查看
- 用户可以重新发送消息进行重试

## Testing Strategy

### 属性测试库选择

本项目使用 **fast-check** 作为属性测试库。fast-check 是一个成熟的 TypeScript 属性测试库，提供：
- 丰富的内置生成器（arbitraries）
- 自动缩小（shrinking）失败的测试用例
- 优秀的 TypeScript 类型支持
- 与 Jest/Vitest 无缝集成

安装：
```bash
npm install --save-dev fast-check
```

### 测试数据生成器

```typescript
import * as fc from 'fast-check';

/**
 * AppMode 生成器
 */
const appModeArbitrary = fc.constantFrom(
  'chat',
  'image-gen',
  'image-edit',
  'image-outpainting',
  'virtual-try-on',
  'video-gen',
  'audio-gen',
  'pdf-extract'
);

/**
 * Attachment 生成器
 */
const attachmentArbitrary = fc.record({
  id: fc.uuid(),
  type: fc.constantFrom('image', 'video', 'audio', 'pdf', 'file'),
  url: fc.option(fc.webUrl(), { nil: undefined }),
  file: fc.option(fc.constant(new File([], 'test.txt')), { nil: undefined }),
  fileUri: fc.option(fc.string(), { nil: undefined }),
  uploadStatus: fc.option(
    fc.constantFrom('pending', 'uploading', 'completed', 'failed'),
    { nil: undefined }
  )
});

/**
 * ExecutionContext 生成器
 */
const executionContextArbitrary = fc.record({
  sessionId: fc.uuid(),
  userMessageId: fc.uuid(),
  modelMessageId: fc.uuid(),
  mode: appModeArbitrary,
  text: fc.string({ minLength: 1, maxLength: 1000 }),
  attachments: fc.array(attachmentArbitrary, { maxLength: 5 }),
  currentModel: fc.record({
    id: fc.string(),
    name: fc.string(),
    provider: fc.constantFrom('google', 'openai')
  }),
  options: fc.record({
    temperature: fc.float({ min: 0, max: 2 }),
    maxTokens: fc.integer({ min: 1, max: 4096 })
  }),
  protocol: fc.constantFrom('google', 'openai'),
  apiKey: fc.option(fc.string(), { nil: undefined }),
  timeout: fc.option(fc.integer({ min: 1000, max: 60000 }), { nil: undefined })
});

/**
 * HandlerResult 生成器
 */
const handlerResultArbitrary = fc.record({
  content: fc.string(),
  attachments: fc.array(attachmentArbitrary, { maxLength: 5 }),
  groundingMetadata: fc.option(fc.object(), { nil: undefined }),
  urlContextMetadata: fc.option(fc.object(), { nil: undefined }),
  browserOperationId: fc.option(fc.uuid(), { nil: undefined }),
  partialSuccess: fc.option(fc.boolean(), { nil: undefined }),
  failedOperations: fc.option(
    fc.array(
      fc.record({
        operation: fc.string(),
        error: fc.constant(new Error('Test error')),
        recoverable: fc.option(fc.boolean(), { nil: undefined })
      }),
      { maxLength: 3 }
    ),
    { nil: undefined }
  )
});
```

### 消息比较函数

```typescript
/**
 * 比较两个消息是否相等（忽略非确定性字段）
 * @param msg1 消息 1
 * @param msg2 消息 2
 * @returns 是否相等
 */
function compareMessages(msg1: Message, msg2: Message): boolean {
  // 忽略 id 和 timestamp（非确定性字段）
  return (
    msg1.role === msg2.role &&
    msg1.content === msg2.content &&
    msg1.mode === msg2.mode &&
    msg1.isError === msg2.isError &&
    compareAttachments(msg1.attachments, msg2.attachments) &&
    compareMetadata(msg1.groundingMetadata, msg2.groundingMetadata) &&
    compareMetadata(msg1.urlContextMetadata, msg2.urlContextMetadata)
  );
}

/**
 * 比较两个附件数组是否相等
 */
function compareAttachments(
  atts1: Attachment[],
  atts2: Attachment[]
): boolean {
  if (atts1.length !== atts2.length) return false;
  
  return atts1.every((att1, index) => {
    const att2 = atts2[index];
    return (
      att1.type === att2.type &&
      att1.url === att2.url &&
      att1.uploadStatus === att2.uploadStatus
    );
  });
}

/**
 * 比较两个元数据对象是否相等
 */
function compareMetadata(meta1: any, meta2: any): boolean {
  if (meta1 === meta2) return true;
  if (!meta1 || !meta2) return false;
  
  // 深度比较（简化版）
  return JSON.stringify(meta1) === JSON.stringify(meta2);
}
```

### 单元测试

1. **StrategyRegistry 测试**
   - 测试 register() 方法正确注册 Handler
   - 测试 getHandler() 方法返回正确的 Handler
   - 测试 getHandler() 在找不到 Handler 时抛出错误
   - 测试 hasHandler() 方法正确判断注册状态

2. **BaseHandler 测试**
   - 测试 handleUploadWithPolling() 正确提交上传任务
   - 测试 startUploadPolling() 正确启动轮询
   - 测试 handleError() 正确转换错误对象

3. **Concrete Handler 测试**
   - 为每个 Handler 编写单元测试
   - 测试 execute() 方法的正常流程
   - 测试错误处理
   - 测试生命周期钩子调用

4. **useChat Hook 测试**
   - 测试 sendMessage() 正确选择 Handler
   - 测试状态管理逻辑
   - 测试错误处理逻辑
   - 测试文件上传逻辑

### 属性测试

使用 fast-check 库进行属性测试，每个测试运行至少 100 次迭代。

1. **策略注册完整性测试**
```typescript
import * as fc from 'fast-check';

test('Property 1: 策略注册完整性', () => {
  fc.assert(
    fc.property(appModeArbitrary, (mode) => {
      // 验证每个 AppMode 都有对应的 Handler 注册
      expect(registry.hasHandler(mode)).toBe(true);
    }),
    { numRuns: 100 }
  );
});
```

2. **接口一致性测试**
```typescript
test('Property 5: 接口一致性', () => {
  fc.assert(
    fc.property(appModeArbitrary, (mode) => {
      const handler = registry.getHandler(mode);
      // 验证 Handler 实现了 execute 方法
      expect(typeof handler.execute).toBe('function');
      // 验证 execute 返回 Promise
      expect(handler.execute).toHaveLength(1); // 接受 1 个参数
    }),
    { numRuns: 100 }
  );
});
```

3. **返回值标准化测试**
```typescript
test('Property 10: 返回值标准化', async () => {
  await fc.assert(
    fc.asyncProperty(
      appModeArbitrary,
      executionContextArbitrary,
      async (mode, context) => {
        const handler = registry.getHandler(mode);
        const result = await handler.execute({ ...context, mode });
        
        // 验证返回值符合 HandlerResult 接口
        expect(result).toHaveProperty('content');
        expect(result).toHaveProperty('attachments');
        expect(typeof result.content).toBe('string');
        expect(Array.isArray(result.attachments)).toBe(true);
      }
    ),
    { numRuns: 100 }
  );
});
```

4. **行为兼容性测试**
```typescript
test('Property 12: 行为向后兼容', async () => {
  await fc.assert(
    fc.asyncProperty(
      appModeArbitrary,
      fc.string({ minLength: 1 }),
      fc.array(attachmentArbitrary, { maxLength: 3 }),
      async (mode, text, attachments) => {
        // 调用重构后的实现
        const newResult = await newImplementation(mode, text, attachments);
        
        // 调用原始实现
        const oldResult = await oldImplementation(mode, text, attachments);
        
        // 使用 compareMessages 比较结果
        expect(compareMessages(newResult, oldResult)).toBe(true);
      }
    ),
    { numRuns: 100 }
  );
});
```

5. **代码封装性测试**
```typescript
import * as ts from 'typescript';

test('Property 4: 无条件分支', () => {
  const sourceFile = ts.createSourceFile(
    'useChat.ts',
    fs.readFileSync('useChat.ts', 'utf-8'),
    ts.ScriptTarget.Latest
  );
  
  let hasModeBranch = false;
  
  function visit(node: ts.Node) {
    if (ts.isIfStatement(node) || ts.isSwitchStatement(node)) {
      const text = node.getText();
      if (text.includes('mode')) {
        hasModeBranch = true;
      }
    }
    ts.forEachChild(node, visit);
  }
  
  visit(sourceFile);
  expect(hasModeBranch).toBe(false);
});
```

6. **类型注解完整性测试**
```typescript
test('Property 16: 类型注解完整性', () => {
  const program = ts.createProgram(['useChat.ts'], {});
  const checker = program.getTypeChecker();
  const sourceFile = program.getSourceFile('useChat.ts');
  
  let hasAnyType = false;
  
  function visit(node: ts.Node) {
    if (ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node)) {
      const signature = checker.getSignatureFromDeclaration(node);
      if (signature) {
        const returnType = checker.getReturnTypeOfSignature(signature);
        if (returnType.flags & ts.TypeFlags.Any) {
          hasAnyType = true;
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  
  visit(sourceFile!);
  expect(hasAnyType).toBe(false);
});
```

### 集成测试

1. **端到端流程测试**
   - 模拟用户发送消息
   - 验证完整的执行流程
   - 验证消息正确保存到数据库

2. **文件上传测试**
   - 测试 Google 协议的文件上传
   - 测试上传任务提交和轮询
   - 验证附件 URL 正确更新

3. **错误场景测试**
   - 模拟各种错误情况（429、400、503）
   - 验证错误消息正确显示
   - 验证状态正确恢复

### 回归测试

1. **功能回归测试**
   - 为每个现有模式创建测试用例
   - 验证重构后功能完全一致

2. **性能回归测试**
   - 对比重构前后的性能指标
   - 确保没有性能退化

## Implementation Notes

### 迁移策略

1. **阶段 1：创建新架构**
   - 实现 ModeHandler 接口
   - 实现 StrategyRegistry
   - 实现 BaseHandler

2. **阶段 2：迁移 Handler**
   - 逐个创建 Concrete Handler
   - 包装现有的 handler 函数
   - 保持原有逻辑不变

3. **阶段 3：重构 useChat**
   - 替换 if-else 链为策略调用
   - 保持其他逻辑不变
   - 确保向后兼容

4. **阶段 4：优化和清理**
   - 提取共享逻辑到 BaseHandler
   - 优化错误处理
   - 添加文档注释

### 文件结构

```
frontend/hooks/
├── useChat.ts                    # 重构后的协调者
├── handlers/
│   ├── index.ts                  # 导出所有 Handler
│   ├── types.ts                  # 接口定义
│   ├── base/
│   │   ├── ModeHandler.ts        # Handler 接口
│   │   ├── BaseHandler.ts        # 抽象基类
│   │   ├── StrategyRegistry.ts   # 策略注册表
│   │   ├── PollingManager.ts     # 轮询管理器
│   │   └── HandlerError.ts       # 错误类型定义
│   ├── preprocessors/
│   │   ├── Preprocessor.ts       # 前置处理器接口
│   │   ├── PreprocessorRegistry.ts  # 前置处理器注册表
│   │   └── GoogleFileUploadPreprocessor.ts  # Google 文件上传前置处理器
│   ├── concrete/
│   │   ├── ChatHandler.ts
│   │   ├── ImageGenHandler.ts
│   │   ├── ImageEditHandler.ts
│   │   ├── ImageOutpaintingHandler.ts
│   │   ├── VirtualTryOnHandler.ts
│   │   ├── VideoGenHandler.ts
│   │   ├── AudioGenHandler.ts
│   │   └── PdfExtractHandler.ts
│   ├── utils/
│   │   ├── uploadUtils.ts        # 上传工具函数
│   │   ├── pollingUtils.ts       # 轮询工具函数
│   │   └── errorUtils.ts         # 错误处理工具
│   └── config/
│       └── strategyConfig.ts     # Handler 注册配置
```

### 数据库保存策略

为了提高用户体验，采用"先保存 pending，后更新"的策略：

1. **立即保存 pending 状态**
   ```typescript
   // Handler 返回结果后，立即保存到数据库
   await saveMessageToDatabase({
     ...modelMessage,
     content: result.content,
     attachments: result.dbAttachments || result.attachments,
     uploadStatus: 'pending' // 标记为 pending
   });
   ```

2. **后台轮询更新**
   ```typescript
   // PollingManager 在上传完成后更新数据库
   pollingManager.startPolling(taskId, {
     onSuccess: async (taskId, uploadResult) => {
       await updateMessageInDatabase({
         messageId: modelMessage.id,
         attachments: uploadResult.attachments,
         uploadStatus: 'completed'
       });
     }
   });
   ```

3. **优点**
   - 用户立即看到结果（本地 URL）
   - 数据库立即有记录（pending 状态）
   - 后台异步更新云存储 URL
   - 即使上传失败，用户也能看到结果

### 内存泄漏保护

使用 React 的 useEffect 清理机制防止内存泄漏：

```typescript
useEffect(() => {
  // 创建全局 PollingManager 实例
  const pollingManager = new PollingManager();
  
  // 组件卸载时清理所有轮询任务
  return () => {
    pollingManager.cleanup();
  };
}, []);
```

**关键保护措施：**
1. 所有 setTimeout/setInterval 都通过 PollingManager 管理
2. 组件卸载时自动清理所有任务
3. 错误发生时清理相关任务
4. 用户取消时清理相关任务
│   └── config/
│       └── strategyConfig.ts     # Handler 注册配置
```

### 性能考虑

1. **策略查找性能**
   - 使用 Map 数据结构，O(1) 查找时间
   - 在模块加载时完成注册，避免运行时开销

2. **内存占用**
   - Handler 实例在注册时创建，整个应用生命周期复用
   - 避免在每次调用时创建新实例

3. **异步处理**
   - 保持原有的异步处理逻辑
   - 上传和轮询在后台执行，不阻塞 UI

### 扩展性考虑

1. **添加新模式**
   - 创建新的 Handler 类
   - 在 strategyConfig.ts 中注册
   - 无需修改 useChat 核心逻辑

2. **修改现有模式**
   - 只需修改对应的 Handler
   - 不影响其他模式

3. **添加新功能**
   - 可以通过扩展 BaseHandler 添加共享功能
   - 可以通过扩展 ExecutionContext 添加新的上下文信息
   - 可以通过扩展 HandlerResult 添加新的返回字段

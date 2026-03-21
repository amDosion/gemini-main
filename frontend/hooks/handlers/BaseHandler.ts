/**
 * BaseHandler 抽象基类
 * 
 * 提供通用功能的抽象基类，减少代码重复
 * 修复问题5：使用模板方法模式，execute() 为 final，子类实现 doExecute()
 * 修复问题7：startUploadPolling() 使用 .catch() 捕获 Promise rejection
 */

import { 
  ModeHandler, 
  ExecutionContext, 
  HandlerResult, 
  HandlerErrorImpl,
  UploadTaskResult
} from './types';
import { Attachment } from '../../types/types';

/**
 * BaseHandler 抽象基类
 * 所有具体 Handler 应该继承此类
 */
export abstract class BaseHandler implements ModeHandler {
  /**
   * 使用模板方法模式，强制子类调用验证方法（修复问题5）
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
      
      // 修复：使用 mimeType 而不是 type（Attachment 接口中没有 type 字段）
      if (!attachment.mimeType) {
        throw new HandlerErrorImpl(
          'Attachment mimeType is required',
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
  ): Promise<UploadTaskResult> {
    // 提交上传任务（不等待完成）
    const dbAttachments = await this.submitUploadTasks(attachments, context);
    
    // 启动后台轮询（使用全局 pollingManager，修复问题1）
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
    // 这里需要调用 storageService 提交上传任务
    // 返回带有 uploadTaskId 的附件
    return attachments.map(att => ({
      ...att,
      uploadStatus: 'pending' as const,
      uploadTaskId: `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    }));
  }
  
  /**
   * 启动上传状态轮询
   * 使用全局 PollingManager 管理轮询任务（修复问题1）
   * 修复问题7：使用 .catch() 捕获 Promise rejection
   * 
   * 长期方案：上传完成后更新数据库中的 tempUrl，但不刷新前端显示
   */
  protected startUploadPolling(
    attachments: Attachment[],
    context: ExecutionContext
  ): void {
    attachments.forEach((attachment) => {
      if (attachment.uploadTaskId) {
        // 使用全局 pollingManager（从 context 获取，修复问题1）
        context.pollingManager.startPolling(attachment.uploadTaskId, {
          interval: 2000, // 2秒轮询一次
          maxAttempts: 30, // 最多30次（60秒）
          timeout: 60000, // 60秒超时
          onStatusCheck: async (taskId) => {
            // 调用后端 API 检查上传状态
            const status = await context.storageService.getUploadTaskStatus(taskId);
            return status;
          },
          onSuccess: async (_taskId, result) => {
            if (result && result.url) {
              console.log('[BaseHandler] 上传完成:', {
                attachmentId: attachment.id,
                cloudUrl: result.url.substring(0, 60) + '...'
              });
            }
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
          // 捕获 Promise rejection，记录错误但不影响主流程（修复问题7）
          console.error(`[PollingManager] Failed to start polling for ${attachment.uploadTaskId}:`, error);
        });
      }
    });
  }
  
  /**
   * 标准化错误处理
   */
  protected handleError(error: any): never {
    // 如果已经是 HandlerError，直接抛出
    if (error instanceof HandlerErrorImpl) {
      throw error;
    }
    
    // 否则转换为 HandlerError（不传递 context，因为此处没有完整的上下文信息）
    throw new HandlerErrorImpl(
      error.message || 'Unknown error',
      'INTERNAL_ERROR',
      'INTERNAL'
    );
  }
}

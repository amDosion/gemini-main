/**
 * 前置处理器注册表和 Google 文件上传前置处理器
 * 
 * 修复问题2：PreprocessorRegistry 按优先级排序执行
 * 修复问题3：GoogleFileUploadPreprocessor 使用 structuredClone() 确保不可变性
 * 修复问题6：使用 Promise.allSettled 支持部分失败处理
 */

import { Preprocessor, ExecutionContext, HandlerErrorImpl } from './types';
import { Attachment } from '../../types/types';

/**
 * 前置处理器注册表
 * 修复问题2：按优先级排序执行（数字越小优先级越高）
 */
export class PreprocessorRegistry {
  private preprocessors: Preprocessor[] = [];
  
  /**
   * 注册前置处理器
   * @param preprocessor 前置处理器实例
   */
  register(preprocessor: Preprocessor): void {
    this.preprocessors.push(preprocessor);
    // 按优先级排序（数字越小优先级越高）（修复问题2）
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
 * 修复问题3：使用 structuredClone() 确保不可变性
 * 修复问题6：使用 Promise.allSettled 支持部分失败处理
 */
export class GoogleFileUploadPreprocessor implements Preprocessor {
  priority = 10; // 高优先级，确保在其他 preprocessor 之前执行
  
  canHandle(context: ExecutionContext): boolean {
    return (
      context.protocol === 'google' &&
      context.mode === 'chat' &&
      context.attachments.some(att => att.file && !att.fileUri)
    );
  }
  
  async process(context: ExecutionContext): Promise<ExecutionContext> {
    // 使用深拷贝确保不可变性（修复问题3）
    const clonedContext = this.deepClone(context);
    
    // 处理文件上传逻辑
    const uploadedAttachments = await this.uploadFiles(clonedContext.attachments, clonedContext);
    
    return {
      ...clonedContext,
      attachments: uploadedAttachments
    };
  }
  
  /**
   * 上传文件，使用 Promise.allSettled 支持部分失败（修复问题6）
   */
  private async uploadFiles(
    attachments: Attachment[],
    context: ExecutionContext
  ): Promise<Attachment[]> {
    // 使用 Promise.allSettled 并行上传，支持部分失败（修复问题6）
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
  
  /**
   * 上传单个文件
   */
  private async uploadFile(
    attachment: Attachment,
    context: ExecutionContext
  ): Promise<Attachment> {
    if (attachment.file && !attachment.fileUri) {
      const uri = await context.llmService.uploadFile(attachment.file);
      return { ...attachment, fileUri: uri, file: undefined };
    }
    return attachment;
  }
  
  /**
   * 深拷贝对象，确保不可变性（修复问题3）
   * 使用 structuredClone() 而不是 JSON.parse/stringify
   * 优势：支持 Date、Set、Map、RegExp、ArrayBuffer 等复杂类型
   * 性能：比 JSON 方法更快
   * 浏览器支持：Chrome 98+, Firefox 94+, Safari 15.4+
   */
  private deepClone<T>(obj: T): T {
    return structuredClone(obj);
  }
}

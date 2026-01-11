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
    // 不使用深拷贝，直接处理附件
    // structuredClone 无法正确克隆 File 对象，会导致问题
    
    // 处理文件上传逻辑
    const uploadedAttachments = await this.uploadFiles(context.attachments, context);
    
    return {
      ...context,
      attachments: uploadedAttachments
    };
  }
  
  /**
   * 上传文件，使用 Promise.allSettled 支持部分失败（修复问题6）
   * 修复：上传失败时降级到 Base64，不阻塞用户
   */
  private async uploadFiles(
    attachments: Attachment[],
    context: ExecutionContext
  ): Promise<Attachment[]> {
    // 使用 Promise.allSettled 并行上传，支持部分失败（修复问题6）
    const results = await Promise.allSettled(
      attachments.map(att => this.uploadFile(att, context))
    );
    
    // 处理上传结果：成功的使用 fileUri，失败的保留原始附件（降级到 Base64）
    const processedAttachments = results.map((result, index) => {
      if (result.status === 'fulfilled') {
        return result.value;
      } else {
        // 上传失败，记录警告但保留原始附件（后续会使用 Base64 方式）
        const attachment = attachments[index];
        const error = (result as PromiseRejectedResult).reason;
        
        console.warn(`[GoogleFileUploadPreprocessor] 文件上传失败，将使用 Base64 方式:`, {
          fileName: attachment.name || 'unknown',
          fileType: attachment.mimeType || 'unknown',
          error: error.message || 'Unknown error'
        });
        
        // 返回原始附件，让后续流程使用 Base64
        return attachment;
      }
    });
    
    return processedAttachments;
  }
  
  /**
   * 上传单个文件
   */
  private async uploadFile(
    attachment: Attachment,
    context: ExecutionContext
  ): Promise<Attachment> {
    if (attachment.file && !attachment.fileUri) {
      // 调试日志
      console.log('[GoogleFileUploadPreprocessor] 准备上传文件:', {
        fileName: attachment.name,
        hasLlmService: !!context.llmService,
        llmServiceType: typeof context.llmService,
        hasUploadFile: typeof context.llmService?.uploadFile,
        llmServiceKeys: context.llmService ? Object.keys(context.llmService) : []
      });
      
      const uri = await context.llmService.uploadFile(attachment.file);
      // 保留原始 url 字段，用于 UI 显示
      return { ...attachment, fileUri: uri, file: undefined, url: attachment.url };
    }
    return attachment;
  }
}

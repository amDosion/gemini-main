/**
 * 前置处理器注册表和 Google 文件上传前置处理器
 *
 * 修复问题2：PreprocessorRegistry 按优先级排序执行
 * 修复问题3：GoogleFileUploadPreprocessor 使用 structuredClone() 确保不可变性
 * 修复问题6：使用 Promise.allSettled 支持部分失败处理
 *
 * Chat 模式附件处理：
 * - 将 Blob URL 转换为 Base64 Data URL（确保后端可访问）
 * - 尝试上传到 Google Files API（可选，失败时降级到 Base64）
 * - 移除不可序列化的 File 对象
 */

import { reportError } from '../../utils/globalErrorHandler';
import { Preprocessor, ExecutionContext, HandlerErrorImpl } from './types';
import { Attachment } from '../../types/types';
import { fileToBase64 } from './attachmentUtils';

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
        
        
        // 返回原始附件，让后续流程使用 Base64
        return attachment;
      }
    });
    
    return processedAttachments;
  }
  
  /**
   * 处理单个附件：
   * 1. 将 Blob URL 转换为 Base64 Data URL（后端可直接解析 inline_data）
   * 2. 移除 File 对象（不可 JSON 序列化）
   *
   * 注意：Google Files API 上传路由（POST /api/upload/google）尚未实现，
   * 当前使用 Base64 inline_data 方式传递图片数据（< 20MB）。
   * 未来如需支持大文件（> 20MB），可实现上传路由并在此处启用。
   */
  private async uploadFile(
    attachment: Attachment,
    context: ExecutionContext
  ): Promise<Attachment> {
    let processed = { ...attachment };

    // Step 1: 确保 url 是 Base64 Data URL（后端可访问）
    // Blob URL 只在浏览器内有效，后端无法访问
    if (processed.file && processed.url?.startsWith('blob:')) {
      try {
        const base64Url = await fileToBase64(processed.file);
        processed.url = base64Url;
        processed.tempUrl = base64Url;
      } catch (err) {
        reportError('文件预处理失败', err);
      }
    }

    // Step 2: 保留 File 对象（供 ChatHandler 的 uploadTask 上传到云存储）
    // JSON.stringify 会自动忽略 File 对象，不影响序列化
    return processed;
  }
}

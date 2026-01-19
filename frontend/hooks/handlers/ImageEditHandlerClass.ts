import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { ImageGenerationResult } from '../../services/providers/interfaces';
import { llmService } from '../../services/llmService';
import { isHttpUrl } from './attachmentUtils';
import { storageUpload } from '../../services/storage/storageUpload';
import { v4 as uuidv4 } from 'uuid';

export class ImageEditHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    // ✅ 根据设计文档，前端只负责传递附件元数据，后端统一处理
    // 不再进行 Base64 转换，后端会处理所有 URL 类型（Base64、Blob URL、HTTP URL）
    const referenceImages: Record<string, Attachment> = {};
    
    // 处理第一个附件作为 raw（基础图片）
    if (context.attachments.length > 0) {
      const rawAttachment = context.attachments[0];
      
      // ✅ 直接传递附件元数据，后端会处理：
      // - HTTP URL → 后端自己下载
      // - Base64 URL → 后端创建临时代理 URL
      // - Blob URL → 后端会通过其他方式处理（如果需要）
      // - File 对象 → 前端上传到后端，后端统一处理
      console.log('[ImageEditHandler] ✅ 传递附件元数据给后端处理:', {
        urlType: rawAttachment.url?.startsWith('blob:') ? 'Blob' : 
                 rawAttachment.url?.startsWith('data:') ? 'Base64' : 
                 rawAttachment.url?.startsWith('http') ? 'HTTP' : 'Other',
        hasFile: !!rawAttachment.file,
        uploadStatus: rawAttachment.uploadStatus
      });
      
      referenceImages.raw = rawAttachment;
    }
    
    // 检查是否有 mask（第二个附件可能是 mask）
    if (context.attachments.length > 1) {
      // 简单判断：如果模式是 image-mask-edit，第二个附件作为 mask
      if (context.mode === 'image-mask-edit') {
        referenceImages.mask = context.attachments[1];
      }
    }
    
    // 传递模式参数、sessionId 和 messageId（用于对话式编辑和附件保存）
    // 将 sessionId 和 messageId 添加到 options 中，以便后端使用
    const editOptions = {
      ...context.options,
      frontend_session_id: context.sessionId,  // 传递前端会话 ID
      sessionId: context.sessionId,  // 向后兼容
      message_id: context.modelMessageId  // ✅ 新增：后端需要 messageId 来创建附件记录
    };
    
    const results = await llmService.editImage(
      context.text, 
      referenceImages,
      context.mode,  // 传递模式参数
      editOptions  // 传递包含 sessionId 的 options
    );

    // 提取 thoughts 和 text（从第一个结果中，因为所有图片共享相同的 thoughts）
    const firstResult = results[0];
    const thoughts = firstResult?.thoughts || [];
    const textResponse = firstResult?.text;

    // ✅ 后端已处理图片（返回 attachmentId, uploadStatus, taskId）
    // 直接使用后端返回的结果，不需要再次处理
    const displayAttachments: Attachment[] = results.map((res: ImageGenerationResult) => ({
      id: res.attachmentId || uuidv4(),  // 使用后端返回的 attachmentId
      mimeType: res.mimeType || 'image/png',
      name: res.filename || `edited-${Date.now()}.png`,
      url: res.url,  // 显示URL（可能是 /api/temp-images/{attachment_id} 或 HTTP URL）
      uploadStatus: res.uploadStatus || 'pending',
      uploadTaskId: res.taskId
    } as Attachment));
    
    // 构建内容：包含 thoughts 和 text（如果有）
    let content = `Edited images for: "${context.text}"`;
    if (thoughts.length > 0 || textResponse) {
      const thoughtTexts = thoughts
        .filter(t => t.type === 'text')
        .map(t => t.content)
        .join('\n\n');
      if (thoughtTexts) {
        content += `\n\n**思考过程：**\n${thoughtTexts}`;
      }
      if (textResponse) {
        content += `\n\n**AI 响应：**\n${textResponse}`;
      }
    }

    const uploadTask = async () => {
      // ✅ 后端已创建附件记录和上传任务（AI 返回的图片）
      const dbAttachments = displayAttachments;
      
      // ✅ 处理用户上传的附件
      // 注意：用户上传的文件仍然需要前端通过 FormData 上传到后端
      // 但后端现在使用 AttachmentService.process_user_upload() 统一处理
      const dbUserAttachments = await Promise.all(
        context.attachments.map(async (att) => {
          // 如果已经上传到云存储，直接返回
          if (att.uploadStatus === 'completed' && att.url?.startsWith('http')) {
            return att;
          }
          
          // ✅ 如果有 File 对象，上传到后端（后端会统一处理）
          // 后端 /api/storage/upload-async 现在使用 AttachmentService.process_user_upload()
          if (att.file) {
            try {
              const result = await storageUpload.uploadFileAsync(att.file, {
                sessionId: context.sessionId,
                messageId: context.userMessageId,
                attachmentId: att.id || uuidv4(),
                storageId: context.storageId,
              });
              
              console.log('[ImageEditHandler] ✅ 用户附件已提交到后端统一处理:', {
                attachmentId: result.attachmentId || att.id,
                taskId: result.taskId
              });
              
              return {
                ...att,
                id: result.attachmentId || att.id,  // 使用后端返回的 attachmentId
                uploadStatus: result.taskId ? 'pending' : 'failed',
                uploadTaskId: result.taskId || undefined,
              } as Attachment;
            } catch (error) {
              console.error('[ImageEditHandler] 用户附件上传失败:', error);
              return { ...att, uploadStatus: 'failed' as const };
            }
          }
          
          // ✅ 其他情况（URL 类型），后端 modes.py 会处理
          // 不需要前端转换，直接传递元数据
          return att;
        })
      );
      
      return { dbAttachments, dbUserAttachments };
    };

    return {
      content: content,
      attachments: displayAttachments,
      uploadTask: uploadTask(),
      // 将 thoughts 存储在自定义字段中（用于前端显示）
      thoughts: thoughts,
      textResponse: textResponse
    };
  }
}

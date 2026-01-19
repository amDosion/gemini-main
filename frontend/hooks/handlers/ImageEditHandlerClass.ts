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
    // 将 attachments 数组转换为 referenceImages 字典格式
    // 注意：如果有 File 对象且有 HTTP URL，直接传递 URL（后端会自己下载，避免 Base64 占用空间）
    // 如果没有 HTTP URL 但有 File 对象，才需要转换为 Base64
    const referenceImages: Record<string, Attachment> = {};
    
    // 处理第一个附件作为 raw（基础图片）
    if (context.attachments.length > 0) {
      let rawAttachment = context.attachments[0];
      
      // 如果有 File 对象，优先使用 HTTP URL（后端会自己下载）
      // 只有在没有 HTTP URL 的情况下，才转换为 Base64
      if (rawAttachment.file && !isHttpUrl(rawAttachment.url)) {
        // 如果没有 HTTP URL，但有 File 对象，需要转换为 Base64
        // 这种情况通常发生在 Blob URL 或 Base64 URL 的场景
        if (!(rawAttachment as any).base64Data) {
          try {
            const { fileToBase64 } = await import('./attachmentUtils');
            const base64Data = await fileToBase64(rawAttachment.file);
            rawAttachment = {
              ...rawAttachment,
              url: rawAttachment.url || base64Data,
              base64Data: base64Data
            } as Attachment & { base64Data: string };
            console.log('[ImageEditHandler] ✅ 已将 File 对象转换为 Base64 Data URL（无 HTTP URL）');
          } catch (error) {
            console.warn('[ImageEditHandler] ⚠️ File 转 Base64 失败:', error);
          }
        }
      } else if (isHttpUrl(rawAttachment.url)) {
        // 有 HTTP URL，直接传递 URL（后端会自己下载）
        console.log('[ImageEditHandler] ✅ 使用 HTTP URL，后端将自行下载:', rawAttachment.url.substring(0, 60));
      }
      
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
      // ✅ 后端已创建附件记录和上传任务，直接返回
      const dbAttachments = displayAttachments;
      
      // 处理用户上传的附件（上传到云存储）
      const dbUserAttachments = await Promise.all(
        context.attachments.map(async (att) => {
          // 如果已经上传到云存储，直接返回
          if (att.uploadStatus === 'completed' && att.url?.startsWith('http')) {
            return att;
          }
          
          // 如果有 File 对象，上传到云存储
          if (att.file) {
            try {
              const result = await storageUpload.uploadFileAsync(att.file, {
                sessionId: context.sessionId,
                messageId: context.userMessageId,
                attachmentId: att.id || uuidv4(),
                storageId: context.storageId,
              });
              
              return {
                ...att,
                uploadStatus: result.taskId ? 'pending' : 'failed',
                uploadTaskId: result.taskId || undefined,
              } as Attachment;
            } catch (error) {
              console.error('[ImageEditHandler] 用户附件上传失败:', error);
              return { ...att, uploadStatus: 'failed' as const };
            }
          }
          
          // 其他情况，保持原样
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

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
    const referenceImages: Record<string, Attachment | Attachment[]> = {};

    // ✅ 格式化 URL 用于日志（避免输出完整 BASE64）
    const formatUrlForLog = (url: string | undefined): string => {
      if (!url) return 'N/A';
      if (url.startsWith('data:')) {
        return `Base64 Data URL (长度: ${url.length} 字符)`;
      }
      return url.length > 80 ? url.substring(0, 80) + '...' : url;
    };

    // ✅ 直接传递附件元数据，后端会处理：
    // - HTTP URL → 后端自己下载
    // - Base64 URL → 后端创建临时代理 URL
    // - Blob URL → 后端会通过其他方式处理（如果需要）
    // - File 对象 → 前端上传到后端，后端统一处理

    // 处理附件：根据模式和附件数量决定如何传递
    if (context.attachments.length > 0) {
      // ✅ image-mask-edit 模式：第一个附件是 raw，第二个是 mask
      if (context.mode === 'image-mask-edit') {
        const rawAttachment = context.attachments[0];
        console.log('[ImageEditHandler] ✅ image-mask-edit 模式 - raw 附件:', {
          id: rawAttachment.id || 'N/A',
          urlType: rawAttachment.url?.startsWith('blob:') ? 'Blob' :
                   rawAttachment.url?.startsWith('data:') ? 'Base64' :
                   rawAttachment.url?.startsWith('http') ? 'HTTP' : 'Other',
          url: formatUrlForLog(rawAttachment.url),
          hasFile: !!rawAttachment.file,
          uploadStatus: rawAttachment.uploadStatus
        });
        referenceImages.raw = rawAttachment;

        if (context.attachments.length > 1) {
          referenceImages.mask = context.attachments[1];
          console.log('[ImageEditHandler] ✅ image-mask-edit 模式 - mask 附件:', {
            id: context.attachments[1].id || 'N/A'
          });
        }
      }
      // ✅ image-chat-edit 模式：支持多图编辑
      else if (context.mode === 'image-chat-edit') {
        if (context.attachments.length === 1) {
          // 单图：保持向后兼容，raw 是单个附件
          const rawAttachment = context.attachments[0];
          console.log('[ImageEditHandler] ✅ image-chat-edit 单图模式:', {
            id: rawAttachment.id || 'N/A',
            urlType: rawAttachment.url?.startsWith('blob:') ? 'Blob' :
                     rawAttachment.url?.startsWith('data:') ? 'Base64' :
                     rawAttachment.url?.startsWith('http') ? 'HTTP' : 'Other',
            url: formatUrlForLog(rawAttachment.url),
            hasFile: !!rawAttachment.file,
            uploadStatus: rawAttachment.uploadStatus
          });
          referenceImages.raw = rawAttachment;
        } else {
          // ✅ 多图：raw 是附件数组
          console.log(`[ImageEditHandler] ✅ image-chat-edit 多图模式，附件数量: ${context.attachments.length}`);
          context.attachments.forEach((att, idx) => {
            console.log(`[ImageEditHandler] 附件[${idx}]:`, {
              id: att.id || 'N/A',
              urlType: att.url?.startsWith('blob:') ? 'Blob' :
                       att.url?.startsWith('data:') ? 'Base64' :
                       att.url?.startsWith('http') ? 'HTTP' : 'Other',
              url: formatUrlForLog(att.url),
              hasFile: !!att.file,
              uploadStatus: att.uploadStatus
            });
          });
          referenceImages.raw = context.attachments;  // ✅ 传递附件数组
        }
      }
      // ✅ 其他模式：只使用第一个附件
      else {
        const rawAttachment = context.attachments[0];
        console.log('[ImageEditHandler] ✅ 传递附件元数据给后端处理:', {
          mode: context.mode,
          id: rawAttachment.id || 'N/A',
          urlType: rawAttachment.url?.startsWith('blob:') ? 'Blob' :
                   rawAttachment.url?.startsWith('data:') ? 'Base64' :
                   rawAttachment.url?.startsWith('http') ? 'HTTP' : 'Other',
          url: formatUrlForLog(rawAttachment.url),
          urlLength: rawAttachment.url ? rawAttachment.url.length : 0,
          hasFile: !!rawAttachment.file,
          uploadStatus: rawAttachment.uploadStatus,
          mimeType: rawAttachment.mimeType,
          name: rawAttachment.name
        });
        referenceImages.raw = rawAttachment;
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

    // ✅ 提取增强后的提示词（如果有）- 同一批次所有图片共享相同的 enhancedPrompt
    const enhancedPrompt = results.find((res: ImageGenerationResult) => res.enhancedPrompt)?.enhancedPrompt;

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
    
    // ✅ 构建显示内容：只保存原始提示词
    // enhancedPrompt 作为单独字段存储，在前端单独显示
    // thoughts 和 textResponse 通过 ThinkingBlock 单独显示
    const content = context.text;

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
              
              // ✅ 修复：保留原始 Blob URL 到 tempUrl，用于当前会话显示
              // 注意：这个返回的附件会保存到数据库（cleanAttachmentsForDb 会清空 Blob URL）
              // 但当前会话的 messages 状态会保留原始 Blob URL（因为 setMessages 在 updateSessionMessages 之前调用）
              const originalUrl = att.url || att.tempUrl;
              const isBlobUrl = originalUrl?.startsWith('blob:');
              
              return {
                ...att,
                id: result.attachmentId || att.id,  // 使用后端返回的 attachmentId
                // ✅ 保留原始 URL 到 tempUrl，用于当前会话显示
                // url 字段保留 Blob URL（如果存在），cleanAttachmentsForDb 会在保存到数据库时清空
                url: originalUrl || '',
                tempUrl: originalUrl || att.tempUrl, // 保留原始 URL 用于显示
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
      // 将 thoughts、textResponse、enhancedPrompt 存储在自定义字段中（用于前端显示和数据库持久化）
      thoughts: thoughts,
      textResponse: textResponse,
      enhancedPrompt: enhancedPrompt
    };
  }
}

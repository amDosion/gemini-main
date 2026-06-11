import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { ImageGenerationResult } from '../../services/providers/interfaces';
import { llmService } from '../../services/llmService';
import { storageUpload } from '../../services/storage/storageUpload';
import { v4 as uuidv4 } from 'uuid';
import { getPreferredAttachmentUrl, isTemporaryAttachmentUrl } from '../../utils/attachmentUrl';

export class ImageEditHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    // ✅ 根据设计文档，前端只负责传递附件元数据，后端统一处理
    // 不再进行 Base64 转换，后端会处理所有 URL 类型（Base64、Blob URL、HTTP URL）
    const referenceImages: Record<string, Attachment | Attachment[]> = {};

    // ✅ 直接传递附件元数据，后端会处理：
    // - HTTP URL → 后端自己下载
    // - Base64 URL → 后端创建临时代理 URL
    // - Blob URL → 后端会通过其他方式处理（如果需要）
    // - File 对象 → 前端上传到后端，后端统一处理

    // 处理附件：根据模式和附件数量决定如何传递
    if (context.attachments.length > 0) {
      // ✅ image-mask-edit 模式：第一个附件是 raw，第二个是 mask
      if (context.mode === 'image-mask-edit') {
        referenceImages.raw = context.attachments[0];

        if (context.attachments.length > 1) {
          referenceImages.mask = {
            ...context.attachments[1],
            role: 'mask',
            name: context.attachments[1].name || 'mask.png',
            mimeType: context.attachments[1].mimeType || 'image/png',
          };
        }
      }
      // ✅ image-chat-edit 多图模式：raw 是附件数组
      else if (context.mode === 'image-chat-edit' && context.attachments.length > 1) {
        referenceImages.raw = context.attachments;
      }
      // ✅ 单图（image-chat-edit 向后兼容）/其他模式：只使用第一个附件
      else {
        referenceImages.raw = context.attachments[0];
      }
    }

    // 传递模式参数、sessionId 和 messageId（用于对话式编辑和附件保存）
    // 将 sessionId 和 messageId 添加到 options 中，以便后端使用
    const editOptions = {
      ...context.options,
      frontendSessionId: context.sessionId, // 传递前端会话 ID
      sessionId: context.sessionId, // 向后兼容
      messageId: context.modelMessageId, // ✅ 新增：后端需要 messageId 来创建附件记录
    };

    const results = await llmService.editImage(
      context.text,
      referenceImages,
      context.mode, // 传递模式参数
      editOptions // 传递包含 sessionId 的 options
    );

    // 提取 thoughts 和 text（从第一个结果中，因为所有图片共享相同的 thoughts）
    const firstResult = results[0];
    const thoughts = firstResult?.thoughts || [];
    const textResponse = firstResult?.text;

    // ✅ 提取增强后的提示词（如果有）- 同一批次所有图片共享相同的 enhancedPrompt
    const enhancedPrompt = results.find(
      (res: ImageGenerationResult) => res.enhancedPrompt
    )?.enhancedPrompt;

    // ✅ 后端已处理图片（返回完整的附件元数据）
    // 直接使用后端返回的结果，不需要再次处理
    const displayAttachments: Attachment[] = results.map((res: ImageGenerationResult) => {
      return {
        id: res.attachmentId || uuidv4(), // 使用后端返回的 attachmentId
        mimeType: res.mimeType || 'image/png',
        name: res.filename || `edited-${Date.now()}.png`,
        url: res.url, // 显示URL（Base64 Data URL 或 HTTP URL）
        uploadStatus: res.uploadStatus || 'pending',
        uploadTaskId: res.taskId,
        // ✅ 新增：保存后端返回的额外元数据
        size: res.size, // 文件大小（bytes）
        cloudUrl: res.cloudUrl, // 云存储 URL（如果已上传）
        messageId: res.messageId, // 消息 ID
        sessionId: res.sessionId, // 会话 ID
        userId: res.userId, // 用户 ID
        createdAt: res.createdAt, // 创建时间戳
        openaiResponseId: res.openaiResponseId,
      } as Attachment;
    });

    const uploadTask = async () => {
      // ✅ 处理用户上传的附件
      // 注意：用户上传的文件仍然需要前端通过 FormData 上传到后端
      // 但后端现在使用 AttachmentService.process_user_upload() 统一处理
      const dbUserAttachments = await Promise.all(
        context.attachments.map(async (att) => {
          const preferredUrl = getPreferredAttachmentUrl(att);
          // 如果已经上传到云存储，直接返回
          if (
            att.uploadStatus === 'completed' &&
            preferredUrl &&
            !isTemporaryAttachmentUrl(preferredUrl)
          ) {
            return {
              ...att,
              url: preferredUrl,
              cloudUrl: att.cloudUrl || preferredUrl,
              uploadStatus: 'completed' as const,
            };
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

              // ✅ 修复：保留原始 Blob URL 到 tempUrl，用于当前会话显示
              // 注意：这个返回的附件会保存到数据库（后端 PR-1 b0bd8ee 在 upsert 时
              // 权威清洗 Blob URL,落库时 url=""+status="pending"）。
              // 但当前会话的 messages 状态会保留原始 Blob URL（因为 setMessages 在 updateSessionMessages 之前调用）
              const originalUrl = preferredUrl || att.url || att.tempUrl;

              return {
                ...att,
                id: result.attachmentId || att.id, // 使用后端返回的 attachmentId
                // ✅ 保留原始 URL 到 tempUrl，用于当前会话显示
                // url 字段保留 Blob URL（如果存在），后端 upsert 路径会落库时清空
                url: originalUrl || '',
                tempUrl: originalUrl || att.tempUrl, // 保留原始 URL 用于显示
                uploadStatus: result.taskId ? 'pending' : 'failed',
                uploadTaskId: result.taskId || undefined,
              } as Attachment;
            } catch {
              return { ...att, uploadStatus: 'failed' as const };
            }
          }

          // ✅ 其他情况（URL 类型），后端 modes.py 会处理
          // 不需要前端转换，直接传递元数据
          return att;
        })
      );

      // ✅ 后端已创建附件记录和上传任务（AI 返回的图片），dbAttachments 直接复用 displayAttachments
      return { dbAttachments: displayAttachments, dbUserAttachments };
    };

    return {
      // ✅ 显示内容只保存原始提示词；enhancedPrompt / thoughts / textResponse 单独存储显示
      content: context.text,
      attachments: displayAttachments,
      uploadTask: uploadTask(),
      // 将 thoughts、textResponse、enhancedPrompt 存储在自定义字段中（用于前端显示和数据库持久化）
      thoughts,
      textResponse,
      enhancedPrompt,
    };
  }
}

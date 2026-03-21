import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { llmService } from '../../services/llmService';
import { processMediaResult } from './attachmentUtils';
// ✅ 改为静态导入，避免与其他文件的静态导入冲突
import { storageUpload } from '../../services/storage/storageUpload';
import { v4 as uuidv4 } from 'uuid';

// --- Handler Classes ---

export class ImageOutpaintingHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    if (!context.attachments || context.attachments.length === 0) {
      throw new Error('ImageOutpaintingHandler requires an attachment.');
    }

    // ✅ 与 VirtualTryOnHandler 保持一致：传递 sessionId 和 messageId 到 options
    // 后端需要这些信息来保存附件到数据库
    const outpaintOptions = {
      ...context.options,
      frontendSessionId: context.sessionId,
      sessionId: context.sessionId,  // 向后兼容
      messageId: context.modelMessageId  // ✅ 后端需要 messageId 来创建附件记录
    };

    // ✅ 修复：outPaintImage 现在返回数组，不需要再包装
    const results = await llmService.outPaintImage(
      context.attachments[0],
      outpaintOptions  // ✅ 传递包含 sessionId 和 messageId 的 options
    );

    // ✅ 后端已处理图片（返回 attachmentId, uploadStatus, taskId）
    // 直接使用后端返回的结果，与 VirtualTryOnHandler 一致
    const displayAttachments: Attachment[] = results.map((res: {
      url: string;
      mimeType: string;
      filename?: string;
      attachmentId?: string;
      uploadStatus?: string;
      taskId?: string;
    }) => ({
      id: res.attachmentId || `outpaint-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      mimeType: res.mimeType || 'image/png',
      name: res.filename || `outpainted-${Date.now()}.png`,
      url: res.url,
      uploadStatus: (res.uploadStatus || 'pending') as 'pending' | 'uploading' | 'completed' | 'failed',
      uploadTaskId: res.taskId
    } as Attachment));

    // ✅ 后端已创建附件记录和上传任务（AI 返回的结果图片）
    const uploadTask = async () => ({
      dbAttachments: displayAttachments,
      dbUserAttachments: context.attachments
    });

    return {
      content: 'Image expanded.',
      attachments: displayAttachments,
      uploadTask: uploadTask(),
    };
  }
}


export class VirtualTryOnHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    if (!context.attachments || context.attachments.length < 2) {
      throw new Error('Virtual try-on requires 2 images: person and garment');
    }

    // ✅ 与 ImageEditHandler 保持一致：传递 sessionId 和 messageId 到 options
    // 后端需要这些信息来保存附件到数据库
    const tryOnOptions = {
      ...context.options,
      frontendSessionId: context.sessionId,
      sessionId: context.sessionId,  // 向后兼容
      messageId: context.modelMessageId  // ✅ 后端需要 messageId 来创建附件记录
    };

    const results = await llmService.virtualTryOn(
      context.text, 
      context.attachments,
      tryOnOptions  // ✅ 传递包含 sessionId 和 messageId 的 options
    );

    // ✅ 后端已处理图片（返回 attachmentId, uploadStatus, taskId）
    // 直接使用后端返回的结果，与 ImageEditHandler 一致
    const displayAttachments: Attachment[] = results.map((res: { 
      url: string; 
      mimeType: string; 
      filename?: string;
      attachmentId?: string;
      uploadStatus?: string;
      taskId?: string;
    }) => ({
      id: res.attachmentId || `vto-${Date.now()}`,
      mimeType: res.mimeType || 'image/png',
      name: res.filename || `tryon-${Date.now()}.png`,
      url: res.url,
      uploadStatus: (res.uploadStatus || 'pending') as 'pending' | 'uploading' | 'completed' | 'failed',
      uploadTaskId: res.taskId
    } as Attachment));

    // ✅ 与 ImageEditHandler 保持一致：处理用户上传的附件（人物图、服装图）
    const uploadTask = async () => {
      // ✅ 后端已创建附件记录和上传任务（AI 返回的结果图片）
      const dbAttachments = displayAttachments;
      
      // ✅ 处理用户上传的附件（人物图、服装图）
      // 注意：用户上传的文件需要前端通过 FormData 上传到后端
      // 后端使用 AttachmentService.process_user_upload() 统一处理
      const dbUserAttachments = await Promise.all(
        context.attachments.map(async (att) => {
          // 如果已经上传到云存储，直接返回
          if (att.uploadStatus === 'completed' && att.url?.startsWith('http')) {
            return att;
          }
          
          // ✅ 如果有 File 对象，上传到后端（后端会统一处理）
          if (att.file) {
            try {
              const result = await storageUpload.uploadFileAsync(att.file, {
                sessionId: context.sessionId,
                messageId: context.userMessageId,
                attachmentId: att.id || uuidv4(),
                storageId: context.storageId,
              });
              
              console.log('[VirtualTryOnHandler] ✅ 用户附件已提交到后端统一处理:', {
                attachmentId: result.attachmentId || att.id,
                taskId: result.taskId
              });
              
              return {
                ...att,
                id: result.attachmentId || att.id,
                uploadStatus: result.taskId ? 'pending' : 'failed',
                uploadTaskId: result.taskId || undefined,
              } as Attachment;
            } catch (error) {
              console.error('[VirtualTryOnHandler] 用户附件上传失败:', error);
              return { ...att, uploadStatus: 'failed' as const };
            }
          }
          
          // ✅ 对于 Base64/Blob URL，需要转换为 File 对象并上传
          // 这是 Virtual Try-On 特有的逻辑，因为人物图/服装图通常是本地上传的
          if (att.url && (att.url.startsWith('data:') || att.url.startsWith('blob:'))) {
            try {
              // 将 Base64/Blob URL 转换为 File 对象
              const response = await fetch(att.url);
              const blob = await response.blob();
              const filename = att.name || `tryon-input-${Date.now()}.png`;
              const file = new File([blob], filename, { type: blob.type || 'image/png' });
              
              const result = await storageUpload.uploadFileAsync(file, {
                sessionId: context.sessionId,
                messageId: context.userMessageId,
                attachmentId: att.id || uuidv4(),
                storageId: context.storageId,
              });
              
              console.log('[VirtualTryOnHandler] ✅ Base64/Blob 附件已上传:', {
                attachmentId: result.attachmentId || att.id,
                taskId: result.taskId
              });
              
              return {
                ...att,
                id: result.attachmentId || att.id,
                uploadStatus: result.taskId ? 'pending' : 'failed',
                uploadTaskId: result.taskId || undefined,
              } as Attachment;
            } catch (error) {
              console.error('[VirtualTryOnHandler] Base64/Blob 附件上传失败:', error);
              return { ...att, uploadStatus: 'failed' as const };
            }
          }
          
          // 其他情况，直接返回
          return att;
        })
      );
      
      return { dbAttachments, dbUserAttachments };
    };

    return {
      content: `Virtual try-on result for: "${context.text}"`,
      attachments: displayAttachments,
      uploadTask: uploadTask(),
    };
  }
}

export class VideoGenHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const videoOptions = {
      ...context.options,
      frontendSessionId: context.sessionId,
      sessionId: context.sessionId,
      messageId: context.modelMessageId,
    };

    const result = await llmService.generateVideo(context.text, context.attachments, videoOptions);
    const enhancedPrompt = result.enhancedPrompt?.trim();
    const displayContent = enhancedPrompt
      ? `📝 ${context.text}\n✨ ${enhancedPrompt}`
      : context.text;
    const videoGenerationMeta = {
      ...(result.continuationStrategy ? { continuationStrategy: result.continuationStrategy } : {}),
      ...(typeof result.videoExtensionCount === 'number' ? { videoExtensionCount: result.videoExtensionCount } : {}),
      ...(typeof result.videoExtensionApplied === 'number' ? { videoExtensionApplied: result.videoExtensionApplied } : {}),
      ...(typeof result.totalDurationSeconds === 'number' ? { totalDurationSeconds: result.totalDurationSeconds } : {}),
      ...(result.continuedFromVideo ? { continuedFromVideo: true } : {}),
      ...(typeof result.storyboardShotSeconds === 'number' ? { storyboardShotSeconds: result.storyboardShotSeconds } : {}),
      ...(typeof result.generateAudio === 'boolean' ? { generateAudio: result.generateAudio } : {}),
      ...(result.personGeneration ? { personGeneration: result.personGeneration } : {}),
      ...(result.subtitleMode ? { subtitleMode: result.subtitleMode } : {}),
      ...(result.subtitleLanguage ? { subtitleLanguage: result.subtitleLanguage } : {}),
      ...(result.trackedFeature ? { trackedFeature: result.trackedFeature } : {}),
      ...(result.trackingOverlayText ? { trackingOverlayText: result.trackingOverlayText } : {}),
    };

    if (result.attachmentId || result.uploadStatus || result.taskId) {
      const displayAttachments: Attachment[] = [{
        id: result.attachmentId || uuidv4(),
        mimeType: result.mimeType || 'video/mp4',
        name: result.filename || `generated-${Date.now()}.mp4`,
        url: result.url,
        fileUri: result.gcsUri || result.providerFileUri || result.providerFileName || result.fileUri,
        uploadStatus: (result.uploadStatus || 'pending') as 'pending' | 'uploading' | 'completed' | 'failed',
        uploadTaskId: result.taskId,
        cloudUrl: result.cloudUrl,
        messageId: result.messageId,
        sessionId: result.sessionId,
        userId: result.userId,
        createdAt: result.createdAt,
        enhancedPrompt,
      }];
      for (const sidecar of result.sidecarFiles || []) {
        displayAttachments.push({
          id: sidecar.attachmentId || uuidv4(),
          mimeType: sidecar.mimeType,
          name: sidecar.filename || `subtitle-${Date.now()}`,
          url: sidecar.url,
          uploadStatus: (sidecar.uploadStatus || 'pending') as 'pending' | 'uploading' | 'completed' | 'failed',
          uploadTaskId: sidecar.taskId,
          cloudUrl: sidecar.cloudUrl,
          messageId: sidecar.messageId,
          sessionId: sidecar.sessionId,
          userId: sidecar.userId,
          language: sidecar.language,
          kind: sidecar.kind || 'subtitle',
        });
      }
      const subtitleAttachmentIds = displayAttachments
        .filter((attachment) => attachment.kind === 'subtitle' || attachment.mimeType === 'text/vtt' || attachment.mimeType === 'application/x-subrip')
        .map((attachment) => attachment.id)
        .filter((value): value is string => typeof value === 'string' && value.length > 0);

      return {
        content: displayContent,
        attachments: displayAttachments,
        uploadTask: Promise.resolve({ dbAttachments: displayAttachments }),
        ...(subtitleAttachmentIds.length > 0 ? { subtitleAttachmentIds } : {}),
        ...videoGenerationMeta,
      };
    }

    const processed = await processMediaResult(result, context, 'video');
    if (enhancedPrompt) {
      processed.displayAttachment.enhancedPrompt = enhancedPrompt;
    }
    const displayAttachments = [processed.displayAttachment];
    const uploadTask = async () => ({
      dbAttachments: [await processed.dbAttachmentPromise]
    });
    
    return {
      content: displayContent,
      attachments: displayAttachments,
      uploadTask: uploadTask(),
      ...videoGenerationMeta,
    };
  }
}

export class AudioGenHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const result = await llmService.generateSpeech(context.text);
    const results = [result];
    
    const processed = await Promise.all(
      results.map(res => processMediaResult({ ...res, filename: 'speech.mp3' }, context, 'audio'))
    );

    const displayAttachments = processed.map(p => p.displayAttachment);
    const uploadTask = async () => ({
      dbAttachments: await Promise.all(processed.map(p => p.dbAttachmentPromise))
    });

    return {
      content: `Speech generated for: "${context.text}"`,
      attachments: displayAttachments,
      uploadTask: uploadTask(),
    };
  }
}

export class PdfExtractHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    // Simplified PDF extraction - returns text content
    return {
      content: `PDF extraction completed for ${context.attachments.length} file(s)`,
      attachments: [],
    };
  }
}

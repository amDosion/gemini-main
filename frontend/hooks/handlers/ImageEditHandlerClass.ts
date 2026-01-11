import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { llmService } from '../../services/llmService';
import { processMediaResult } from './attachmentUtils';
import { storageUpload } from '../../services/storage/storageUpload';
import { v4 as uuidv4 } from 'uuid';

export class ImageEditHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const results = await llmService.editImage(context.text, context.attachments);

    // 使用统一的媒体处理函数
    const processed = await Promise.all(
      results.map(res => processMediaResult(res, context, 'edited'))
    );

    const displayAttachments: Attachment[] = processed.map(p => p.displayAttachment);

    const uploadTask = async () => {
      // 处理 AI 生成的图片
      const dbAttachments = await Promise.all(processed.map(p => p.dbAttachmentPromise));
      
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
      content: `Edited images for: "${context.text}"`,
      attachments: displayAttachments,
      uploadTask: uploadTask()
    };
  }
}

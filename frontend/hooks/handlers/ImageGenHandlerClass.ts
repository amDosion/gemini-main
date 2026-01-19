import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { ImageGenerationResult } from '../../services/providers/interfaces';
import { llmService } from '../../services/llmService';
import { v4 as uuidv4 } from 'uuid';

export class ImageGenHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    try {
      // ✅ 传递 sessionId 和 messageId 到 options（后端需要这些信息来保存附件）
      const genOptions = {
        ...context.options,
        frontend_session_id: context.sessionId,
        sessionId: context.sessionId,  // 向后兼容
        message_id: context.modelMessageId  // ✅ 新增：后端需要 messageId 来创建附件记录
      };
      
      const results = await llmService.generateImage(
        context.text, 
        context.attachments,
        genOptions  // ✅ 传递包含 sessionId 和 messageId 的 options
      );

      // ✅ 后端已处理图片（返回 attachmentId, uploadStatus, taskId）
      // 直接使用后端返回的结果，不需要再次处理
      const displayAttachments: Attachment[] = results.map((res: ImageGenerationResult) => ({
        id: res.attachmentId || uuidv4(),  // 使用后端返回的 attachmentId
        mimeType: res.mimeType || 'image/png',
        name: res.filename || `generated-${Date.now()}.png`,
        url: res.url,  // 显示URL（可能是 /api/temp-images/{attachment_id} 或 HTTP URL）
        uploadStatus: res.uploadStatus || 'pending',
        uploadTaskId: res.taskId
      } as Attachment));

      // ✅ 后端已处理上传任务，不需要前端再次上传
      const uploadTask = async () => {
        // 后端已创建附件记录和上传任务，直接返回
        return { dbAttachments: displayAttachments };
      };

      return {
        content: `Generated images for: "${context.text}"`,
        attachments: displayAttachments,
        uploadTask: uploadTask()
      };
    } catch (error: any) {
      // Handle 401 authentication errors specifically
      if (error.message && error.message.includes('401')) {
        throw new Error('Authentication failed. Please log in again to generate images.');
      }
      
      // Handle other authentication-related errors
      if (error.message && (
        error.message.includes('Authentication failed') ||
        error.message.includes('API Key not found') ||
        error.message.includes('Unauthorized')
      )) {
        throw new Error('Unable to authenticate. Please check your provider settings or log in again.');
      }
      
      // Re-throw other errors
      throw error;
    }
  }
}

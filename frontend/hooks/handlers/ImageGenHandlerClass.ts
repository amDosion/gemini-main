import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { ImageGenerationResult } from '../../services/providers/interfaces';
import { llmService } from '../../services/llmService';
import { v4 as uuidv4 } from 'uuid';

export class ImageGenHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    try {
      // 后端需要 sessionId / messageId 来创建附件记录；sessionId 字段保留向后兼容
      const genOptions = {
        ...context.options,
        frontendSessionId: context.sessionId,
        sessionId: context.sessionId,
        messageId: context.modelMessageId,
      };

      const results = await llmService.generateImage(context.text, context.attachments, genOptions);

      // 后端已完成图片处理与上传任务创建，直接映射返回结果
      const displayAttachments: Attachment[] = results.map((res: ImageGenerationResult) => ({
        id: res.attachmentId || uuidv4(),
        mimeType: res.mimeType || 'image/png',
        name: res.filename || `generated-${Date.now()}.png`,
        url: res.url,
        uploadStatus: res.uploadStatus || 'pending',
        uploadTaskId: res.taskId,
        cloudUrl: res.cloudUrl,
        sessionId: res.sessionId,
        messageId: res.messageId,
        userId: res.userId,
        size: res.size,
        enhancedPrompt: res.enhancedPrompt,
        openaiResponseId: res.openaiResponseId,
      }));

      // 同一批次所有图片共享相同的 enhancedPrompt / thoughts / text
      const enhancedPrompt = results.find((res) => res.enhancedPrompt)?.enhancedPrompt;
      const firstResult = results[0];
      const thoughts = firstResult?.thoughts || [];
      const textResponse = firstResult?.text;

      const displayContent = enhancedPrompt
        ? `📝 ${context.text}\n✨ ${enhancedPrompt}`
        : context.text;

      return {
        content: displayContent,
        attachments: displayAttachments,
        // 后端已创建附件记录和上传任务，前端无需再次上传
        uploadTask: Promise.resolve({ dbAttachments: displayAttachments }),
        thoughts: thoughts.length > 0 ? thoughts : undefined,
        textResponse,
        enhancedPrompt,
      };
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '';
      // Handle 401 authentication errors specifically
      if (message.includes('401')) {
        throw new Error('Authentication failed. Please log in again to generate images.');
      }

      // Handle other authentication-related errors
      if (
        message.includes('Authentication failed') ||
        message.includes('API Key not found') ||
        message.includes('Unauthorized')
      ) {
        throw new Error(
          'Unable to authenticate. Please check your provider settings or log in again.'
        );
      }

      // Re-throw other errors
      throw error;
    }
  }
}

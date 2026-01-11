import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { llmService } from '../../services/llmService';
import { processMediaResult } from './attachmentUtils';

export class ImageGenHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    try {
      const results = await llmService.generateImage(context.text, context.attachments);

      // 使用统一的媒体处理函数
      const processed = await Promise.all(
        results.map(res => processMediaResult(res, context, 'generated'))
      );

      const displayAttachments: Attachment[] = processed.map(p => p.displayAttachment);

      const uploadTask = async () => {
        const dbAttachments = await Promise.all(processed.map(p => p.dbAttachmentPromise));
        return { dbAttachments };
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

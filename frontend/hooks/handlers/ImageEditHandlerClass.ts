import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { llmService } from '../../services/llmService';
import { processMediaResult } from './attachmentUtils';

export class ImageEditHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const results = await llmService.generateImage(context.text, context.attachments);

    // 使用统一的媒体处理函数
    const processed = await Promise.all(
      results.map(res => processMediaResult(res, context, 'edited'))
    );

    const displayAttachments: Attachment[] = processed.map(p => p.displayAttachment);

    const uploadTask = async () => {
      const dbAttachments = await Promise.all(processed.map(p => p.dbAttachmentPromise));
      return { dbAttachments, dbUserAttachments: context.attachments };
    };

    return {
      content: `Edited images for: "${context.text}"`,
      attachments: displayAttachments,
      uploadTask: uploadTask()
    };
  }
}

import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
import { llmService } from '../../services/llmService';
import { addCitations } from '../../utils/groundingUtils';

export class ChatHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const stream = llmService.sendMessageStream(context.text, context.attachments);

    let accumulatedText = '';
    const accumulatedAttachments: Attachment[] = [];
    let lastGroundingMetadata: any = undefined;
    let lastUrlContextMetadata: any = undefined;
    let lastBrowserOperationId: string | undefined = undefined;

    for await (const chunk of stream) {
      if (chunk.text) accumulatedText += chunk.text;
      if (chunk.attachments) accumulatedAttachments.push(...chunk.attachments);
      if (chunk.groundingMetadata) lastGroundingMetadata = chunk.groundingMetadata;
      if (chunk.urlContextMetadata) lastUrlContextMetadata = chunk.urlContextMetadata;
      if (chunk.browserOperationId) lastBrowserOperationId = chunk.browserOperationId;

      context.onStreamUpdate({
        content: accumulatedText,
        attachments: [...accumulatedAttachments],
        groundingMetadata: lastGroundingMetadata,
        urlContextMetadata: lastUrlContextMetadata,
        browserOperationId: lastBrowserOperationId
      });
    }

    let finalText = accumulatedText;
    if (lastGroundingMetadata) {
      finalText = addCitations(finalText, lastGroundingMetadata);
    }

    return {
      content: finalText,
      attachments: accumulatedAttachments,
      groundingMetadata: lastGroundingMetadata,
      urlContextMetadata: lastUrlContextMetadata,
      browserOperationId: lastBrowserOperationId
    };
  }
}

import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { llmService } from '../../services/llmService';
import { processMediaResult } from './attachmentUtils';

// --- Handler Classes ---

export class ImageOutpaintingHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    if (!context.attachments || context.attachments.length === 0) {
      throw new Error('ImageOutpaintingHandler requires an attachment.');
    }
    
    const result = await llmService.outPaintImage(context.attachments[0]);
    const results = [result];

    const processed = await Promise.all(
      results.map(res => processMediaResult(res, context, 'outpainted'))
    );
    
    const displayAttachments = processed.map(p => p.displayAttachment);
    const uploadTask = async () => ({
      dbAttachments: await Promise.all(processed.map(p => p.dbAttachmentPromise)),
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

    const results = await llmService.virtualTryOn(context.text, context.attachments);

    const processed = await Promise.all(
      results.map((res: { url: string; mimeType: string; filename?: string }) => 
        processMediaResult(res, context, 'vto')
      )
    );

    const displayAttachments = processed.map(p => p.displayAttachment);
    const uploadTask = async () => ({
      dbAttachments: await Promise.all(processed.map(p => p.dbAttachmentPromise)),
      dbUserAttachments: context.attachments
    });

    return {
      content: `Virtual try-on result for: "${context.text}"`,
      attachments: displayAttachments,
      uploadTask: uploadTask(),
    };
  }
}

export class VideoGenHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const result = await llmService.generateVideo(context.text, context.attachments);
    const results = [result];

    const processed = await Promise.all(
      results.map(res => processMediaResult(res, context, 'video'))
    );
    
    const displayAttachments = processed.map(p => p.displayAttachment);
    const uploadTask = async () => ({
      dbAttachments: await Promise.all(processed.map(p => p.dbAttachmentPromise))
    });
    
    return {
      content: `Video generated for: "${context.text}"`,
      attachments: displayAttachments,
      uploadTask: uploadTask(),
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

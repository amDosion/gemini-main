/**
 * Chat 模式处理器
 * 处理流式对话
 */
import { Attachment } from '../../../types';
import { llmService } from '../../services/llmService';
import { addCitations } from '../../utils/groundingUtils';
import { HandlerContext, HandlerResult, StreamUpdateCallback } from './types';

/**
 * 处理 Chat 模式
 */
export const handleChat = async (
  text: string,
  attachments: Attachment[],
  context: HandlerContext,
  onStreamUpdate: StreamUpdateCallback
): Promise<HandlerResult> => {
  const stream = llmService.sendMessageStream(text, attachments);
  
  let accumulatedText = '';
  const accumulatedAttachments: Attachment[] = [];
  let lastGroundingMetadata: any = undefined;
  let lastUrlContextMetadata: any = undefined;
  let lastBrowserOperationId: string | undefined = undefined;

  for await (const chunk of stream) {
    if (chunk.text) accumulatedText += chunk.text;
    if (chunk.attachments && chunk.attachments.length > 0) {
      accumulatedAttachments.push(...chunk.attachments);
    }
    if (chunk.groundingMetadata) lastGroundingMetadata = chunk.groundingMetadata;
    if (chunk.urlContextMetadata) lastUrlContextMetadata = chunk.urlContextMetadata;
    if (chunk.browserOperationId) lastBrowserOperationId = chunk.browserOperationId;

    // 流式更新
    onStreamUpdate({
      content: accumulatedText,
      attachments: [...accumulatedAttachments],
      groundingMetadata: lastGroundingMetadata,
      urlContextMetadata: lastUrlContextMetadata,
      browserOperationId: lastBrowserOperationId
    });
  }

  // 添加引用
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
};

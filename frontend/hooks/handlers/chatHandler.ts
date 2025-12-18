/**
 * Chat 模式处理器
 * 处理流式对话
 */
import { Attachment } from '../../../types';
import { llmService } from '../../services/llmService';
import { addCitations } from '../../utils/groundingUtils';
import { HandlerContext, HandlerResult, StreamUpdateCallback } from './types';

/**
 * 处理 Chat 模式（流式对话）
 * 
 * @param text - 用户输入的消息
 * @param attachments - 附件列表
 * @param context - 处理器上下文
 * @param onStreamUpdate - 流式更新回调，每次收到新内容时调用
 * @returns 最终结果（包含完整内容和元数据）
 */
export const handleChat = async (
  text: string,
  attachments: Attachment[],
  context: HandlerContext,
  onStreamUpdate: StreamUpdateCallback
): Promise<HandlerResult> => {
  console.log('[chatHandler] 开始流式对话:', {
    textLength: text.length,
    attachmentsCount: attachments.length,
    model: context.currentModel?.id || 'unknown'
  });

  const stream = llmService.sendMessageStream(text, attachments);
  
  let accumulatedText = '';
  const accumulatedAttachments: Attachment[] = [];
  let lastGroundingMetadata: any = undefined;
  let lastUrlContextMetadata: any = undefined;
  let lastBrowserOperationId: string | undefined = undefined;
  let chunkCount = 0;

  for await (const chunk of stream) {
    chunkCount++;
    
    // 累积文本
    if (chunk.text) {
      accumulatedText += chunk.text;
    }
    
    // 累积附件
    if (chunk.attachments && chunk.attachments.length > 0) {
      accumulatedAttachments.push(...chunk.attachments);
    }
    
    // 更新元数据
    if (chunk.groundingMetadata) {
      lastGroundingMetadata = chunk.groundingMetadata;
    }
    if (chunk.urlContextMetadata) {
      lastUrlContextMetadata = chunk.urlContextMetadata;
    }
    if (chunk.browserOperationId) {
      lastBrowserOperationId = chunk.browserOperationId;
    }

    // 流式更新回调
    onStreamUpdate({
      content: accumulatedText,
      attachments: [...accumulatedAttachments],
      groundingMetadata: lastGroundingMetadata,
      urlContextMetadata: lastUrlContextMetadata,
      browserOperationId: lastBrowserOperationId
    });
  }

  // 添加引用（如果有 grounding 元数据）
  let finalText = accumulatedText;
  if (lastGroundingMetadata) {
    finalText = addCitations(finalText, lastGroundingMetadata);
    console.log('[chatHandler] 已添加引用');
  }

  console.log('[chatHandler] 流式对话完成:', {
    chunkCount,
    finalTextLength: finalText.length,
    attachmentsCount: accumulatedAttachments.length,
    hasGrounding: !!lastGroundingMetadata,
    hasUrlContext: !!lastUrlContextMetadata,
    hasBrowserOp: !!lastBrowserOperationId
  });

  return {
    content: finalText,
    attachments: accumulatedAttachments,
    groundingMetadata: lastGroundingMetadata,
    urlContextMetadata: lastUrlContextMetadata,
    browserOperationId: lastBrowserOperationId
  };
};

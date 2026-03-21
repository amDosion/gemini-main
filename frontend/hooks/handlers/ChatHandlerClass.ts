import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment, ToolCall, ToolResult, GroundingMetadata, UrlContextMetadata } from '../../types/types';
import { llmService } from '../../services/llmService';
import { addCitations } from '../../utils/groundingUtils';
import { storageUpload } from '../../services/storage/storageUpload';
import { v4 as uuidv4 } from 'uuid';

// 打字效果配置
const TYPING_CONFIG = {
  CHAR_BATCH_SIZE: 5,      // 每批字符数
  ANIMATION_DELAY: 16,     // 动画间隔（约 60fps）
  CHUNK_THRESHOLD: 20,     // 触发分批的文本长度阈值
};

// 延迟函数
const delay = (ms: number) => new Promise(r => setTimeout(r, ms));

export class ChatHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    // 增强检索的搜索增强逻辑已经在 useChat 中处理：
    // enableEnhancedRetrieval=true 时强制 enableSearch=true。
    
    const stream = llmService.sendMessageStream(context.text, context.attachments);

    let accumulatedText = '';
    const accumulatedThoughts: Array<{ type: 'text' | 'image'; content: string }> = [];
    const accumulatedAttachments: Attachment[] = [];
    const accumulatedToolCalls: ToolCall[] = [];
    const accumulatedToolResults: ToolResult[] = [];
    let lastGroundingMetadata: GroundingMetadata | undefined = undefined;
    let lastUrlContextMetadata: UrlContextMetadata | undefined = undefined;
    let lastBrowserOperationId: string | undefined = undefined;

    // 辅助函数：发送流更新
    const sendUpdate = () => {
      context.onStreamUpdate({
        content: accumulatedText,
        attachments: [...accumulatedAttachments],
        groundingMetadata: lastGroundingMetadata,
        urlContextMetadata: lastUrlContextMetadata,
        browserOperationId: lastBrowserOperationId,
        toolCalls: [...accumulatedToolCalls],
        toolResults: [...accumulatedToolResults],
        thoughts: accumulatedThoughts.length > 0 ? [...accumulatedThoughts] : undefined,
      });
    };

    for await (const chunk of stream) {
      if (chunk.thoughts && chunk.thoughts.length > 0) {
        accumulatedThoughts.push(...chunk.thoughts);
        sendUpdate();
        continue;
      }

      if (chunk.chunkType === 'reasoning' && chunk.text) {
        accumulatedThoughts.push({ type: 'text', content: chunk.text });
        sendUpdate();
        continue;
      }

      // 处理附件和元数据（立即更新）
      if (chunk.attachments) accumulatedAttachments.push(...chunk.attachments);
      if (chunk.groundingMetadata) lastGroundingMetadata = chunk.groundingMetadata;
      if (chunk.urlContextMetadata) lastUrlContextMetadata = chunk.urlContextMetadata;
      if (chunk.browserOperationId) lastBrowserOperationId = chunk.browserOperationId;

      // 处理 Browser 工具调用 (tool_call)
      if (chunk.toolCall) {
        const callId = chunk.toolCall.id || `tool_call_${Date.now()}_${accumulatedToolCalls.length + 1}`;
        const normalizedCall: ToolCall = {
          id: callId,
          type: chunk.toolCall.type || 'function_call',
          name: chunk.toolCall.name,
          arguments: chunk.toolCall.arguments || {}
        };
        const existingIndex = accumulatedToolCalls.findIndex((call) => call.id === callId);
        if (existingIndex >= 0) {
          accumulatedToolCalls[existingIndex] = normalizedCall;
        } else {
          accumulatedToolCalls.push(normalizedCall);
        }
        sendUpdate();
        continue;
      }

      // 处理 Browser 工具结果 (tool_result)
      if (chunk.toolResult) {
        let callId = chunk.toolResult.callId;
        if (!callId) {
          const unresolved = [...accumulatedToolCalls].reverse().find((call) => {
            if (call.name !== chunk.toolResult?.name) return false;
            return !accumulatedToolResults.some((result) => result.callId === call.id);
          });
          callId = unresolved?.id || `tool_result_${Date.now()}_${accumulatedToolResults.length + 1}`;
        }

        const normalizedResult: ToolResult = {
          name: chunk.toolResult.name,
          callId,
          result: chunk.toolResult.result,
          error: chunk.toolResult.error || undefined,
          screenshot: chunk.toolResult.screenshot || undefined,
          screenshotUrl: chunk.toolResult.screenshotUrl || undefined,
        };

        const existingResultIndex = accumulatedToolResults.findIndex((result) => result.callId === callId);
        if (existingResultIndex >= 0) {
          accumulatedToolResults[existingResultIndex] = normalizedResult;
        } else {
          accumulatedToolResults.push(normalizedResult);
        }

        sendUpdate();
        continue;
      }

      // 处理文本内容
      if (chunk.text && chunk.chunkType !== 'reasoning') {
        const text = chunk.text;

        // 如果文本块较大，分批更新以实现统一的打字效果
        // 这解决了不同提供商 yield 频率不同导致的打字效果不一致问题
        if (text.length > TYPING_CONFIG.CHUNK_THRESHOLD) {
          for (let i = 0; i < text.length; i += TYPING_CONFIG.CHAR_BATCH_SIZE) {
            accumulatedText += text.slice(i, i + TYPING_CONFIG.CHAR_BATCH_SIZE);
            sendUpdate();
            await delay(TYPING_CONFIG.ANIMATION_DELAY);
          }
        } else {
          // 短文本直接更新，不影响已经高频 yield 的提供商（如 DeepSeek）
          accumulatedText += text;
          sendUpdate();
        }
      } else if (chunk.attachments || chunk.groundingMetadata || chunk.urlContextMetadata || chunk.browserOperationId) {
        // 非文本更新也需要触发 UI 刷新
        sendUpdate();
      }
    }

    let finalText = accumulatedText;
    if (lastGroundingMetadata) {
      finalText = addCitations(finalText, lastGroundingMetadata);
    }

    // 检查用户附件是否有 File 对象需要上传到云存储
    const userAttachmentsWithFile = context.attachments.filter(att => att.file);

    if (userAttachmentsWithFile.length > 0) {
      // 有用户附件需要上传到云存储（与 ImageEditHandler 模式一致）
      const uploadTask = async () => {
        const dbUserAttachments = await Promise.all(
          context.attachments.map(async (att) => {
            // 已上传到云存储的附件直接返回
            if (att.uploadStatus === 'completed' && att.url?.startsWith('http')) {
              return att;
            }

            // 有 File 对象的附件，上传到后端云存储
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
                  id: result.attachmentId || att.id,
                  file: undefined, // 移除 File 对象（不可序列化到数据库）
                  uploadStatus: result.taskId ? 'pending' as const : 'failed' as const,
                  uploadTaskId: result.taskId || undefined,
                } as Attachment;
              } catch (error) {
                return { ...att, file: undefined, uploadStatus: 'failed' as const } as Attachment;
              }
            }

            // 无 File 对象的附件，移除不可序列化的数据
            return { ...att, file: undefined } as Attachment;
          })
        );

        // 启动后台轮询，上传完成后更新本地数据库中的云 URL
        // （与 BaseHandler.startUploadPolling 一致）
        this.startUploadPolling(
          dbUserAttachments.filter(att => att.uploadTaskId),
          context
        );

        return {
          dbAttachments: accumulatedAttachments, // AI 返回的附件（chat 模式通常为空）
          dbUserAttachments
        };
      };

      return {
        content: finalText,
        attachments: accumulatedAttachments,
        groundingMetadata: lastGroundingMetadata,
        urlContextMetadata: lastUrlContextMetadata,
        browserOperationId: lastBrowserOperationId,
        toolCalls: accumulatedToolCalls,
        toolResults: accumulatedToolResults,
        uploadTask: uploadTask()
      };
    }

    // 无用户附件需要上传，直接返回（原有逻辑）
    return {
      content: finalText,
      attachments: accumulatedAttachments,
      groundingMetadata: lastGroundingMetadata,
      urlContextMetadata: lastUrlContextMetadata,
      browserOperationId: lastBrowserOperationId,
      toolCalls: accumulatedToolCalls,
      toolResults: accumulatedToolResults,
      thoughts: accumulatedThoughts.length > 0 ? accumulatedThoughts : undefined,
    };
  }
}

import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { Attachment } from '../../types/types';
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
    // 如果启用了 Research，强制启用 Search 以提供增强的研究功能
    // 注意：options 已经在 useChat 中通过 startNewChat 设置到 llmService 中
    // 这里我们只需要确保 enableResearch 时 enableSearch 也被启用
    // 实际的 options 传递在 useChat 的 sendMessage 中已经完成
    
    const stream = llmService.sendMessageStream(context.text, context.attachments);

    let accumulatedText = '';
    const accumulatedAttachments: Attachment[] = [];
    let lastGroundingMetadata: any = undefined;
    let lastUrlContextMetadata: any = undefined;
    let lastBrowserOperationId: string | undefined = undefined;

    // 辅助函数：发送流更新
    const sendUpdate = () => {
      context.onStreamUpdate({
        content: accumulatedText,
        attachments: [...accumulatedAttachments],
        groundingMetadata: lastGroundingMetadata,
        urlContextMetadata: lastUrlContextMetadata,
        browserOperationId: lastBrowserOperationId
      });
    };

    for await (const chunk of stream) {
      // 处理附件和元数据（立即更新）
      if (chunk.attachments) accumulatedAttachments.push(...chunk.attachments);
      if (chunk.groundingMetadata) lastGroundingMetadata = chunk.groundingMetadata;
      if (chunk.urlContextMetadata) lastUrlContextMetadata = chunk.urlContextMetadata;
      if (chunk.browserOperationId) lastBrowserOperationId = chunk.browserOperationId;

      // 处理 Browser 工具调用 (tool_call)
      if (chunk.toolCall) {
        const toolText = `\n\n> **Calling tool:** \`${chunk.toolCall.name}\`\n> **Args:** \`${JSON.stringify(chunk.toolCall.args)}\`\n\n`;
        accumulatedText += toolText;
        sendUpdate();
        continue;
      }

      // 处理 Browser 工具结果 (tool_result)
      if (chunk.toolResult) {
        const resultPreview = chunk.toolResult.result.length > 200
          ? chunk.toolResult.result.substring(0, 200) + '...'
          : chunk.toolResult.result;
        let toolText = `\n\n> **Tool result** (\`${chunk.toolResult.name}\`):\n> \`\`\`\n> ${resultPreview.split('\n').join('\n> ')}\n> \`\`\`\n`;

        // 如果有截图，显示为内联图片（优先使用 URL，回退到 base64）
        if (chunk.toolResult.screenshotUrl) {
          toolText += `\n\n**Screenshot:**\n\n![Browser Screenshot](${chunk.toolResult.screenshotUrl})\n\n`;
        } else if (chunk.toolResult.screenshot) {
          toolText += `\n\n**Screenshot:**\n\n![Browser Screenshot](data:image/png;base64,${chunk.toolResult.screenshot})\n\n`;
        } else {
          toolText += '\n\n';
        }

        accumulatedText += toolText;
        sendUpdate();
        continue;
      }

      // 处理文本内容
      if (chunk.text) {
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

                console.log('[ChatHandler] 用户附件已提交云存储上传:', {
                  attachmentId: result.attachmentId || att.id,
                  taskId: result.taskId
                });

                return {
                  ...att,
                  id: result.attachmentId || att.id,
                  file: undefined, // 移除 File 对象（不可序列化到数据库）
                  uploadStatus: result.taskId ? 'pending' as const : 'failed' as const,
                  uploadTaskId: result.taskId || undefined,
                } as Attachment;
              } catch (error) {
                console.error('[ChatHandler] 用户附件上传失败:', error);
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
        uploadTask: uploadTask()
      };
    }

    // 无用户附件需要上传，直接返回（原有逻辑）
    return {
      content: finalText,
      attachments: accumulatedAttachments,
      groundingMetadata: lastGroundingMetadata,
      urlContextMetadata: lastUrlContextMetadata,
      browserOperationId: lastBrowserOperationId
    };
  }
}

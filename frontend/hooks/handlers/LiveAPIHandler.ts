import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';

export class LiveAPIHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const { text, onStreamUpdate } = context;

    // 从 options 中获取 agent_id
    const agentId = context.options?.liveAPIConfig?.agentId;

    onStreamUpdate?.({
      content: '💬 正在处理实时交互...\n\n',
    });

    try {
      const token = localStorage.getItem('access_token');
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      // 使用流式查询（SSE）
      const response = await fetch('/api/live/stream-query', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          input: text,
          agent_id: agentId
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Live API 查询失败: ${errorText}`);
      }

      // 使用 EventSource 接收 SSE 流
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = '';

      if (!reader) {
        throw new Error('无法读取响应流');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.content) {
                accumulatedText += data.content;
                onStreamUpdate?.({
                  content: accumulatedText,
                });
              } else if (data.error) {
                throw new Error(data.error);
              }
            } catch (e) {
              // 忽略 JSON 解析错误
            }
          }
        }
      }

      return {
        content: accumulatedText || '实时交互完成。',
        attachments: [],
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      onStreamUpdate?.({
        content: `❌ 实时交互失败: ${errorMessage}`,
      });
      throw error;
    }
  }
}

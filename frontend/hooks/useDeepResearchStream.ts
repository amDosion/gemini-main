import { useState, useCallback, useRef } from 'react';

// --- Interfaces and Types ---

export interface ResearchStreamStatus {
  isStreaming: boolean;
  progress: string[];
  researchResult: string;
  error?: string;
  reconnectCount?: number;
}

export interface ResearchOptions {
  format?: 'technical report' | 'market analysis' | 'literature review' | string;
  documentIds?: string[];
  language?: string;
  tone?: 'professional' | 'casual' | 'technical';
}

export interface UseDeepResearchStreamReturn {
  status: ResearchStreamStatus;
  startStreamingResearch: (prompt: string, options?: ResearchOptions) => Promise<void>;
  stopStreaming: () => void;
}

interface StreamEvent {
  eventType: 'interaction.start' | 'content.delta' | 'interaction.complete' | 'error';
  eventId?: string;
  delta?: ContentDelta;
  interaction?: {
    id: string;
  };
  error?: {
    message: string;
  };
}

interface ContentDelta {
  type: string;
  text?: string;
  content?: {
    text?: string;
  };
}

export const buildPrompt = (prompt: string, options: ResearchOptions = {}): string => {
  let fullPrompt = prompt;
  const additions: string[] = [];

  if (options.format) {
    additions.push(`Please format the output as a ${options.format}.`);
  }
  if (options.language) {
    additions.push(`Please write the report in ${options.language}.`);
  }
  if (options.tone) {
    additions.push(`Please use a ${options.tone} tone.`);
  }

  if (additions.length > 0) {
    fullPrompt += '\n\n' + additions.join('\n');
  }

  return fullPrompt;
};

export const formatTime = (totalSeconds: number): string => {
  if (isNaN(totalSeconds) || totalSeconds < 0) {
    return '00:00';
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
};

export const useDeepResearchStream = (): UseDeepResearchStreamReturn => {
  const [status, setStatus] = useState<ResearchStreamStatus>({
    isStreaming: false,
    progress: [],
    researchResult: '',
    reconnectCount: 0,
  });
  const abortControllerRef = useRef<AbortController | null>(null);
  const interactionIdRef = useRef<string | null>(null);
  const lastEventIdRef = useRef<string>('');
  const reconnectCountRef = useRef<number>(0);
  const maxReconnects = 5;

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStatus(prev => ({
      ...prev,
      isStreaming: false,
    }));
  }, []);

  const connectSSE = useCallback(
    async (onComplete: () => void) => {
      if (!interactionIdRef.current) {
        console.error('No interaction ID available');
        return;
      }

      // ✅ Query 参数使用 camelCase（中间件自动转换为 snake_case）
      const authParam = encodeURIComponent(`Bearer ${import.meta.env.VITE_GEMINI_API_KEY}`);
      const url = `/api/research/stream/${interactionIdRef.current}?lastEventId=${lastEventIdRef.current}&authorization=${authParam}`;
      const eventSource = new EventSource(url);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as StreamEvent;

          // 保存 event_id
          if (data.eventId) {
            lastEventIdRef.current = data.eventId;
          }

          switch (data.eventType) {
            case 'interaction.start':
              setStatus(prev => ({
                ...prev,
                progress: [...prev.progress, `研究任务已开始 (ID: ${data.interaction?.id})`],
              }));
              break;
            case 'content.delta':
              const text = data.delta?.text ?? data.delta?.content?.text ?? '';
              if (data.delta?.type === 'thinking' || data.delta?.type === 'thought_summary') {
                setStatus(prev => ({ ...prev, progress: [...prev.progress, text] }));
              } else if (text) {
                setStatus(prev => ({ ...prev, researchResult: prev.researchResult + text }));
              }
              break;
            case 'interaction.complete':
              setStatus(prev => ({ ...prev, isStreaming: false, progress: [...prev.progress, '研究完成。'] }));
              eventSource.close();
              onComplete();
              return;
            case 'error':
              throw new Error(data.error?.message || '未知流错误');
          }
        } catch (e: any) {
          console.error('无法解析或处理流事件:', e.message, 'Data:', `"${event.data}"`);
        }
      };

      eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        eventSource.close();

        // 尝试重连
        if (reconnectCountRef.current < maxReconnects) {
          reconnectCountRef.current += 1;
          const delay = 2000 * Math.pow(2, reconnectCountRef.current - 1); // 指数退避

          setStatus(prev => ({
            ...prev,
            progress: [...prev.progress, `连接中断，${delay / 1000}秒后重连 (${reconnectCountRef.current}/${maxReconnects})...`],
            reconnectCount: reconnectCountRef.current,
          }));

          setTimeout(() => {
            console.log(`Attempting to reconnect... (${reconnectCountRef.current}/${maxReconnects})`);
            connectSSE(onComplete);
          }, delay);
        } else {
          setStatus(prev => ({
            ...prev,
            isStreaming: false,
            error: `连接失败，已重试 ${maxReconnects} 次`,
          }));
        }
      };
    },
    []
  );

  const startStreamingResearch = useCallback(
    async (prompt: string, options: ResearchOptions = {}) => {
      if (status.isStreaming) {
        console.warn('Streaming is already in progress.');
        return;
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;
      reconnectCountRef.current = 0;
      lastEventIdRef.current = '';

      setStatus({
        isStreaming: true,
        progress: ['正在开始研究...'],
        researchResult: '',
        error: undefined,
        reconnectCount: 0,
      });

      const fullPrompt = buildPrompt(prompt, options);

      const requestBody = {
        prompt: fullPrompt,
        agent: "deep-research-pro-preview-12-2025",
        background: true,
        stream: true,
        agentConfig: {
          thinkingSummaries: 'auto'
        },
        tools: (options.documentIds && options.documentIds.length > 0)
          ? [{ type: 'file_search', docIds: options.documentIds }]
          : undefined,
      };

      try {
        const response = await fetch('/api/research/stream/start', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${import.meta.env.VITE_GEMINI_API_KEY}`,
          },
          body: JSON.stringify(requestBody),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`API 请求失败，状态码: ${response.status}, 信息: ${errorText}`);
        }

        const data = await response.json();
        interactionIdRef.current = data.interactionId;

        setStatus(prev => ({
          ...prev,
          progress: [...prev.progress, `已获取 interaction_id: ${data.interactionId}`],
        }));

        // 连接 SSE 流
        await connectSSE(() => {
          stopStreaming();
        });

      } catch (err: any) {
        if (err.name === 'AbortError') {
          setStatus(prev => ({ ...prev, isStreaming: false, error: '研究已取消。' }));
        } else {
          console.error('流式研究时发生错误:', err);
          setStatus(prev => ({
            ...prev,
            isStreaming: false,
            error: `研究请求失败: ${err.message}`,
          }));
        }
      }
    },
    [status.isStreaming, stopStreaming, connectSSE]
  );

  return { status, startStreamingResearch, stopStreaming };
};
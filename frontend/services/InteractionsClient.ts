/**
 * Interactions API TypeScript 客户端
 * 
 * 提供统一的接口用于调用 Interactions API
 */

export interface CreateInteractionParams {
  model?: string;
  agent?: string;
  input: string | Content[];
  previousInteractionId?: string;
  tools?: Tool[];
  stream?: boolean;
  background?: boolean;
  generationConfig?: GenerationConfig;
  systemInstruction?: string;
  responseFormat?: Record<string, any>;
  store?: boolean;
}

export interface Content {
  type: string;
  text?: string;
  data?: string;
  mimeType?: string;
  uri?: string;
}

export interface Tool {
  type: string;
  name?: string;
  [key: string]: any;
}

export interface GenerationConfig {
  temperature?: number;
  maxOutputTokens?: number;
  thinkingLevel?: 'minimal' | 'low' | 'medium' | 'high';
  topP?: number;
  topK?: number;
}

export interface Interaction {
  id: string;
  model?: string;
  agent?: string;
  status: string;
  outputs: Content[];
  usage?: Usage;
  createdAt?: string;
}

export interface Usage {
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
}

export interface StreamChunk {
  eventType: string;
  eventId?: string;
  delta?: {
    type: string;
    text?: string;
    content?: {
      text: string;
    };
  };
  interaction?: {
    id: string;
    status: string;
  };
}

export class InteractionsClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  /**
   * 创建新的交互
   */
  async createInteraction(params: CreateInteractionParams): Promise<Interaction> {
    const response = await fetch(`${this.baseUrl}/api/interactions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`
      },
      body: JSON.stringify(params)
    });

    if (!response.ok) {
      throw await this.handleError(response);
    }

    return await response.json();
  }

  /**
   * 获取交互状态
   */
  async getInteraction(interactionId: string): Promise<Interaction> {
    const response = await fetch(
      `${this.baseUrl}/api/interactions/${interactionId}`,
      {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`
        }
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }

    return await response.json();
  }

  /**
   * 流式获取交互
   */
  streamInteraction(
    interactionId: string,
    onChunk: (chunk: StreamChunk) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): EventSource {
    const url = new URL(
      `${this.baseUrl}/api/interactions/${interactionId}/stream`
    );
    url.searchParams.set('authorization', `Bearer ${this.apiKey}`);

    const eventSource = new EventSource(url.toString());

    eventSource.onmessage = (event) => {
      const chunk = JSON.parse(event.data);

      if (chunk.eventType === 'interaction.complete') {
        onComplete();
        eventSource.close();
      } else {
        onChunk(chunk);
      }
    };

    eventSource.onerror = (error) => {
      onError(new Error('Stream error'));
      eventSource.close();
    };

    return eventSource;
  }

  /**
   * 删除交互
   */
  async deleteInteraction(interactionId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/interactions/${interactionId}`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`
        }
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }
  }

  private async handleError(response: Response): Promise<Error> {
    const error = await response.json();
    return new Error(error.detail || 'Unknown error');
  }
}

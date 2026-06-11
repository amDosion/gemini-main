import { Message, ChatOptions, Attachment, Role, ModelConfig } from '../../types/types';
import { contextManager } from '../ai_tools/ContextManager';

export interface PreparedPayload {
  messages: Array<{ role: string; content: string }>;
  contextWindow: number;
}

const DEFAULT_CONTEXT_WINDOW = 128000;

/**
 * MessagePreparer
 * Responsible for assembling the final payload for the AI Provider.
 * Layers:
 * 1. Persona/System Prompt — resolved by backend single source; no frontend fallback injected.
 * 2. History Flattening & Formatting
 * 3. Context Window Optimization (Truncation)
 */
export class MessagePreparer {
  public async prepare(
    history: Message[],
    currentInput: string,
    attachments: Attachment[],
    options: ChatOptions,
    modelConfig: ModelConfig
  ): Promise<PreparedPayload> {
    // History processing: drop errors and empty states. Internal roles map to
    // 'assistant' (the de-facto standard); specific providers map back if needed.
    const pipelineMessages: Array<{ role: string; content: string }> = [];
    for (const msg of history) {
      if (msg.isError) continue;
      if (!msg.content && (!msg.attachments || msg.attachments.length === 0)) continue;
      pipelineMessages.push({
        role: msg.role === Role.USER ? 'user' : 'assistant',
        content: msg.content,
      });
    }

    // Context window: trust backend-provided model metadata, keep a safe fallback.
    const configuredWindow = Number(modelConfig.contextWindow);
    const contextWindow =
      Number.isFinite(configuredWindow) && configuredWindow > 0
        ? Math.floor(configuredWindow)
        : DEFAULT_CONTEXT_WINDOW;

    // The current user message is passed to providers separately; only the
    // history is optimized here, so the new message always fits.
    return {
      messages: contextManager.optimizeContext(pipelineMessages, contextWindow),
      contextWindow,
    };
  }
}

export const messagePreparer = new MessagePreparer();


import { Message, ChatOptions, Attachment, Role, ModelConfig } from "../../../types";
import { contextManager } from "../ai_tools/ContextManager";

export interface PreparedPayload {
    messages: any[];
    contextWindow: number;
}

/**
 * MessagePreparer
 * Responsible for assembling the final payload for the AI Provider.
 * Layers:
 * 1. Persona/System Prompt Injection
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
        
        let pipelineMessages: any[] = [];

        // 1. System Prompt (Persona) Injection
        // Strategy: Always put system prompt first.
        if (options.persona) {
            pipelineMessages.push({ 
                role: 'system', 
                content: options.persona.systemPrompt 
            });
        } else {
            pipelineMessages.push({ 
                role: 'system', 
                content: "You are a helpful AI assistant. Use Markdown for formatting." 
            });
        }

        // 2. History Processing
        // Filter out errors or empty states
        for (const msg of history) {
            if (msg.isError) continue;
            if (!msg.content && (!msg.attachments || msg.attachments.length === 0)) continue;

            // Map internal roles to provider-friendly roles
            // Note: Some models support 'model', others need 'assistant'. We standardize on 'assistant' here
            // and let specific Providers map back if needed, but 'assistant' is the de-facto standard.
            const role = msg.role === Role.USER ? "user" : "assistant";
            
            // For context estimation, we use a simplified structure. 
            // Real providers might need complex objects (multimodal), but for Token Counting, string rep is usually enough.
            // However, we preserve the object structure for the final payload.
            pipelineMessages.push({ 
                role: role, 
                content: msg.content,
                // We don't deep-process attachments here for *context counting* yet, 
                // but we pass them through if the provider needs history with images.
                // Current robust implementation: Most providers only look at text history or last N images.
                // We keep it simple for text-based context optimization.
            }); 
        }

        // 3. Append Current User Message (Optimistic)
        // We add this *before* optimization to ensure it fits, or *after*?
        // Strategy: The current message MUST fit. We optimize the *history* to make room for it.
        // So we don't add it to `pipelineMessages` yet for truncation calculation, 
        // OR we add it and mark it as "protected".
        
        // Let's optimize the history first.
        
        // 4. Context Window Estimation
        let contextWindow = 128000; // Default safe buffer
        
        // Heuristics based on Model ID (Mimicking backend configuration)
        const lowerId = modelConfig.id.toLowerCase();
        if (lowerId.includes('flash')) contextWindow = 1000000;
        else if (lowerId.includes('pro')) contextWindow = 2000000;
        else if (lowerId.includes('gpt-4')) contextWindow = 128000;
        else if (lowerId.includes('8k')) contextWindow = 8192;
        else if (lowerId.includes('32k')) contextWindow = 32768;

        // 5. Execution: Optimize Context
        // This delegates to the ContextManager (which we created in previous steps)
        const optimizedHistory = contextManager.optimizeContext(pipelineMessages, contextWindow);

        // 6. Final Assembly
        // The provider expects a clean list. The `sendMessageStream` in providers usually
        // takes (history, currentMessage) separately. 
        // So we return the optimized history.
        
        return {
            messages: optimizedHistory,
            contextWindow: contextWindow
        };
    }
}

export const messagePreparer = new MessagePreparer();

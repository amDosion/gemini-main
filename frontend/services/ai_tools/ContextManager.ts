
import { Message, Role } from "../../../types";

export class ContextManager {
  // Conservative estimate: 1 token ~= 4 characters for English, ~1-2 chars for CJK
  private static CHARS_PER_TOKEN = 3.5;

  /**
   * Estimates the token count for a list of messages.
   */
  public estimateTokens(messages: any[]): number {
    let total = 0;
    for (const msg of messages) {
      const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);
      total += content.length / ContextManager.CHARS_PER_TOKEN;
      
      // Add overhead for role definitions
      total += 4; 
    }
    return Math.ceil(total);
  }

  /**
   * Smartly truncates messages to fit within the context window.
   * Strategy:
   * 1. ALWAYS preserve the System Prompt (first message if role is system).
   * 2. ALWAYS preserve the most recent N messages (conversation flow).
   * 3. Remove messages from the middle (oldest context) until it fits.
   */
  public optimizeContext(
    messages: any[], 
    maxContextTokens: number = 128000, 
    preserveRecentCount: number = 10
  ): any[] {
    const estimatedTotal = this.estimateTokens(messages);
    
    // If we are within limits (with 10% buffer), return original
    if (estimatedTotal < maxContextTokens * 0.9) {
      return messages;
    }

    console.log(`[ContextManager] Context limit exceeded (${estimatedTotal} > ${maxContextTokens}). Truncating...`);

    // Separate System Prompt
    let systemMessage = null;
    let chatMessages = [...messages];
    
    if (chatMessages.length > 0 && chatMessages[0].role === 'system') {
      systemMessage = chatMessages.shift();
    }

    // If we have fewer messages than the preserve count, we can't delete anything meaningful 
    // without breaking the immediate flow. We might just have to cut the oldest or fail.
    if (chatMessages.length <= preserveRecentCount) {
        // Fallback: Return as is, or maybe just last few.
        return systemMessage ? [systemMessage, ...chatMessages] : chatMessages;
    }

    // Keep the recent buffer
    const recentMessages = chatMessages.slice(-preserveRecentCount);
    const olderMessages = chatMessages.slice(0, -preserveRecentCount);

    // Calculate tokens used by essential parts
    const systemTokens = systemMessage ? this.estimateTokens([systemMessage]) : 0;
    const recentTokens = this.estimateTokens(recentMessages);
    let availableTokens = (maxContextTokens * 0.9) - systemTokens - recentTokens;

    // Add older messages back as long as they fit
    const keptOlderMessages: any[] = [];
    
    // We iterate from the END of older messages (newest of the old) to keep context closer to now
    for (let i = olderMessages.length - 1; i >= 0; i--) {
      const msg = olderMessages[i];
      const msgTokens = this.estimateTokens([msg]);
      
      if (availableTokens - msgTokens > 0) {
        keptOlderMessages.unshift(msg);
        availableTokens -= msgTokens;
      } else {
        // Stop adding once we run out of space
        break; 
      }
    }

    // Reconstruct
    const result = [];
    if (systemMessage) result.push(systemMessage);
    result.push(...keptOlderMessages);
    result.push(...recentMessages);

    console.log(`[ContextManager] Optimized from ${messages.length} to ${result.length} messages.`);
    return result;
  }
}

export const contextManager = new ContextManager();

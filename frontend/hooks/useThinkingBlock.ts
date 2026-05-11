import { useEffect, useState } from 'react';
import type { Message } from '../types/types';

/**
 * 流式思考块 hook（typewriter effect）。
 *
 * 替代 6 个 image view 中完全相同的 18-21 行 typewriter useEffect
 * （见 JIRA-frontend-hook-utility-extraction.md A.1.1）。
 *
 * 行为（按 ImageGenView.tsx:142-182 抽离）：
 * - 拿 messages 最后一条 model 消息的 thoughts + textResponse 拼接
 * - text thought 保留原文；image thought → `[图片思考过程]` placeholder
 * - textResponse 前置 `\n\n💬 AI 响应：\n` 分隔符
 * - loadingState === 'idle' → 一次性 snap 到 fullContent
 * - 否则按 chunkSize 步进每 delayMs 推进 displayedContent
 * - 卸载或依赖变更时 clearTimeout 防泄漏
 */

export interface UseThinkingBlockOptions {
  /** 每次步进字符数。默认 5。 */
  chunkSize?: number;
  /** 每步延迟（毫秒）。默认 30。 */
  delayMs?: number;
  /** 初始是否展开思考块。默认 true。 */
  autoOpen?: boolean;
}

export interface UseThinkingBlockResult {
  /** 思考块是否展开，由调用方控制 UI */
  isOpen: boolean;
  setIsOpen: React.Dispatch<React.SetStateAction<boolean>>;
  /** 当前打字效果显示的内容（流式增长） */
  displayedContent: string;
  /** 完整的拼接内容（thoughts + textResponse），用于和 displayedContent 对比 */
  fullContent: string;
  /** 是否正在流式输出（displayedContent.length < fullContent.length） */
  isStreaming: boolean;
}

const DEFAULT_CHUNK_SIZE = 5;
const DEFAULT_DELAY_MS = 30;
const IMAGE_THOUGHT_PLACEHOLDER = '[图片思考过程]';
const TEXT_RESPONSE_PREFIX = '\n\n💬 AI 响应：\n';

function buildFullContent(messages: readonly Message[]): string {
  const lastMsg = messages.length > 0 ? messages[messages.length - 1] : null;
  if (!lastMsg || lastMsg.role !== 'model') {
    return '';
  }
  const thoughts = lastMsg.thoughts ?? [];
  const textResponse = lastMsg.textResponse;
  const parts: string[] = [];
  for (const thought of thoughts) {
    if (thought.type === 'text') {
      parts.push(thought.content);
    } else {
      parts.push(IMAGE_THOUGHT_PLACEHOLDER);
    }
  }
  if (textResponse) {
    parts.push(`${TEXT_RESPONSE_PREFIX}${textResponse}`);
  }
  return parts.join('\n\n');
}

export function useThinkingBlock(
  messages: readonly Message[],
  loadingState: string,
  options?: UseThinkingBlockOptions
): UseThinkingBlockResult {
  const chunkSize = options?.chunkSize ?? DEFAULT_CHUNK_SIZE;
  const delayMs = options?.delayMs ?? DEFAULT_DELAY_MS;
  const autoOpen = options?.autoOpen ?? true;

  const [isOpen, setIsOpen] = useState<boolean>(autoOpen);
  const [displayedContent, setDisplayedContent] = useState<string>('');

  const fullContent = buildFullContent(messages);

  useEffect(() => {
    if (!fullContent) {
      setDisplayedContent('');
      return;
    }
    if (loadingState === 'idle') {
      setDisplayedContent(fullContent);
      return;
    }
    const targetLength = fullContent.length;
    const currentLength = displayedContent.length;
    if (currentLength < targetLength) {
      const nextLength = Math.min(currentLength + chunkSize, targetLength);
      const timer = setTimeout(() => {
        setDisplayedContent(fullContent.substring(0, nextLength));
      }, delayMs);
      return () => clearTimeout(timer);
    }
    if (fullContent !== displayedContent) {
      // currentLength >= targetLength 但内容不一致：流式过程中 fullContent 被截短，直接同步
      setDisplayedContent(fullContent);
    }
    return undefined;
  }, [fullContent, loadingState, displayedContent, chunkSize, delayMs]);

  return {
    isOpen,
    setIsOpen,
    displayedContent,
    fullContent,
    isStreaming: displayedContent.length < fullContent.length,
  };
}

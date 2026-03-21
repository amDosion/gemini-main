
import { useMemo, useState, useEffect } from 'react';
import { Message, Role } from '../types/types';

export const useMessageProcessor = (message: Message) => {
  const isUser = message.role === Role.USER;
  const [isThinkingOpen, setIsThinkingOpen] = useState(true);
  const structuredThinkingContent = useMemo(() => {
    if (!Array.isArray(message.thoughts) || message.thoughts.length === 0) {
      return null;
    }
    const texts = message.thoughts
      .filter((thought) => thought?.type === 'text')
      .map((thought) => String(thought.content || '').trim())
      .filter(Boolean);
    return texts.length > 0 ? texts.join('\n\n') : null;
  }, [message.thoughts]);

  // Auto-open thinking if it is still streaming.
  useEffect(() => {
    if (isUser) return;
    const structuredStreaming =
      !!structuredThinkingContent &&
      !!message.researchStatus &&
      !['completed', 'failed', 'cancelled'].includes(message.researchStatus.status);
    if (structuredStreaming) {
      setIsThinkingOpen(true);
    }
  }, [message.content, isUser, structuredThinkingContent, message.researchStatus]);

  const { displayContent, thinkingContent } = useMemo(() => {
    if (isUser) {
      return { displayContent: message.content, thinkingContent: null };
    }
    if (structuredThinkingContent) {
      return {
        displayContent: message.content || '',
        thinkingContent: structuredThinkingContent,
      };
    }
    return {
      displayContent: message.content || '',
      thinkingContent: null,
    };
  }, [message.content, isUser, structuredThinkingContent]);

  // Grounding / Search Logic
  const hasGroundingChunks = message.groundingMetadata?.groundingChunks && message.groundingMetadata.groundingChunks.length > 0;
  const hasUrlContext = !!message.urlContextMetadata;
  
  const searchQueries = message.groundingMetadata?.webSearchQueries || [];
  const searchEntryPoint = message.groundingMetadata?.searchEntryPoint?.renderedContent;
  const showSearch = searchQueries.length > 0 || hasGroundingChunks || !!searchEntryPoint;
  const isThinkingComplete = !(
    !!thinkingContent &&
    !!message.researchStatus &&
    !['completed', 'failed', 'cancelled'].includes(message.researchStatus.status)
  );

  return {
    isUser,
    displayContent,
    thinkingContent,
    isThinkingOpen,
    setIsThinkingOpen,
    isThinkingComplete,
    showSearch,
    searchQueries,
    searchEntryPoint,
    hasGroundingChunks,
    groundingChunks: message.groundingMetadata?.groundingChunks,
    hasUrlContext,
    urlContextMetadata: message.urlContextMetadata
  };
};

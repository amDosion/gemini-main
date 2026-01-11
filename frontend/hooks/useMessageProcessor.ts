
import { useMemo, useState, useEffect } from 'react';
import { Message, Role } from '../types/types';

export const useMessageProcessor = (message: Message) => {
  const isUser = message.role === Role.USER;
  const [isThinkingOpen, setIsThinkingOpen] = useState(true);

  // Auto-open thinking if it's streaming (incomplete tag)
  useEffect(() => {
    if (!isUser && message.content.includes('<thinking>') && !message.content.includes('</thinking>')) {
        setIsThinkingOpen(true);
    }
  }, [message.content, isUser]);

  const { displayContent, thinkingContent } = useMemo(() => {
    if (isUser || !message.content) return { displayContent: message.content, thinkingContent: null };

    const startTag = '<thinking>';
    const endTag = '</thinking>';
    const startIndex = message.content.indexOf(startTag);

    if (startIndex === -1) {
        return { displayContent: message.content, thinkingContent: null };
    }

    const endIndex = message.content.indexOf(endTag);

    if (endIndex !== -1) {
        // Complete thinking block
        const thinking = message.content.substring(startIndex + startTag.length, endIndex).trim();
        const before = message.content.substring(0, startIndex);
        const after = message.content.substring(endIndex + endTag.length);
        return { 
            thinkingContent: thinking, 
            displayContent: (before + after).trim() 
        };
    }

    // Incomplete thinking block (streaming)
    const thinking = message.content.substring(startIndex + startTag.length).trim();
    const before = message.content.substring(0, startIndex).trim();
    
    return {
        thinkingContent: thinking,
        displayContent: before
    };
  }, [message.content, isUser]);

  // Grounding / Search Logic
  const hasGroundingChunks = message.groundingMetadata?.groundingChunks && message.groundingMetadata.groundingChunks.length > 0;
  const hasUrlContext = !!message.urlContextMetadata;
  
  const searchQueries = message.groundingMetadata?.webSearchQueries || [];
  const searchEntryPoint = message.groundingMetadata?.searchEntryPoint?.renderedContent;
  const showSearch = searchQueries.length > 0 || hasGroundingChunks || !!searchEntryPoint;
  const isThinkingComplete = message.content.includes('</thinking>');

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

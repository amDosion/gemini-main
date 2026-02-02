
import React, { useState } from 'react';
import { Message, Role, ToolCall, ToolResult } from '../../types/types';
import MarkdownRenderer from './MarkdownRenderer';
import { injectCursorToContent } from '../../utils/cursorUtils';
import { Bot, User, AlertCircle, Copy, Check, Download } from 'lucide-react';
import { useMessageProcessor } from '../../hooks/useMessageProcessor';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { SearchProcess } from '../message/SearchProcess';
import { GroundingSources } from '../message/GroundingSources';
import { UrlContextStatus } from '../message/UrlContextStatus';
import { AttachmentGrid } from '../message/AttachmentGrid';
import { BrowserProgressIndicator } from '../message/BrowserProgressIndicator';
import ToolCallDisplay from './ToolCallDisplay';

interface MessageItemProps {
  message: Message;
  onImageClick?: (url: string) => void;
  onEditImage?: (url: string) => void;
  isStreaming?: boolean;
}

const MessageItem: React.FC<MessageItemProps> = ({ message, onImageClick, onEditImage, isStreaming }) => {
  const {
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
    groundingChunks,
    hasUrlContext,
    urlContextMetadata
  } = useMessageProcessor(message);

  const [isCopied, setIsCopied] = useState(false);
  const [isDownloaded, setIsDownloaded] = useState(false);

  const handleCopy = () => {
    // Only copy the main display content (excluding thinking blocks)
    if (!displayContent) return;
    navigator.clipboard.writeText(displayContent);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!displayContent) return;
    
    try {
      const blob = new Blob([displayContent], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      
      // Create a filename based on timestamp or ID
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      link.href = url;
      link.download = `message-${timestamp}.md`;
      
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setIsDownloaded(true);
      setTimeout(() => setIsDownloaded(false), 2000);
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  // If streaming and NOT thinking (or thinking is done), show cursor in main content
  const showMainCursor = isStreaming && (isThinkingComplete || !thinkingContent);

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6 group`}>
      <div className={`flex max-w-[95%] md:max-w-[85%] lg:max-w-[75%] gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        
        {/* Avatar */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? 'bg-indigo-600' : 'bg-emerald-600'
        } shadow-lg mt-1`}>
          {isUser ? (
            <User size={16} className="text-white" />
          ) : (
            <Bot size={16} className="text-white" />
          )}
        </div>

        {/* Bubble */}
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} w-full min-w-0`}>
          <div className={`px-4 py-3 rounded-2xl shadow-md border overflow-hidden w-full ${
            isUser 
              ? 'bg-indigo-600 border-indigo-500 text-white rounded-tr-none' 
              : 'bg-slate-800 border-slate-700 text-slate-100 rounded-tl-none'
          } ${message.isError ? 'border-red-500 bg-red-900/20' : ''}`}>
            
            {message.isError ? (
              <div className="flex items-center gap-2 text-red-400">
                <AlertCircle size={16} />
                <span>{message.content}</span>
              </div>
            ) : (
               <div className="flex flex-col gap-3">
                 
                 {/* 1. Search Logic */}
                 {!isUser && showSearch && (
                    <SearchProcess 
                        queries={searchQueries} 
                        entryPoint={searchEntryPoint} 
                        isThinking={!message.content && !hasGroundingChunks} 
                    />
                 )}

                 {/* 2. Thinking Process */}
                 {thinkingContent && (
                    <ThinkingBlock 
                        content={thinkingContent}
                        isOpen={isThinkingOpen}
                        onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                        isComplete={isThinkingComplete}
                    />
                 )}

                 {/* 3. Browser Tool Progress */}
                 {!isUser && message.browserOperationId && (
                    <BrowserProgressIndicator operationId={message.browserOperationId} />
                 )}

                 {/* 4. Main Text Content with Cursor */}
                 {(displayContent || showMainCursor) && (
                    <div className="min-w-0">
                      <MarkdownRenderer
                        content={injectCursorToContent(displayContent, showMainCursor)}
                      />
                    </div>
                 )}

                 {/* 5. Tool Calls */}
                 {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
                     <div className="flex flex-col gap-2">
                         {message.toolCalls.map((toolCall) => {
                             const toolResult = message.toolResults?.find(
                                 (result) => result.callId === toolCall.id
                             );
                             const isToolExecuting = !toolResult && isStreaming;

                             return (
                                 <ToolCallDisplay
                                     key={toolCall.id}
                                     toolCall={toolCall}
                                     toolResult={toolResult}
                                     isExecuting={isToolExecuting}
                                 />
                             );
                         })}
                     </div>
                 )}

                 {/* 6. Grounding / Sources */}
                 {!isUser && hasGroundingChunks && (
                    <GroundingSources chunks={groundingChunks} />
                 )}

                 {/* 7. URL Context Status */}
                 {!isUser && hasUrlContext && (
                    <UrlContextStatus metadata={urlContextMetadata} />
                 )}
                 
                 {/* 8. Attachments (Images, Videos, Files) */}
                 {message.attachments && message.attachments.length > 0 && (
                    <AttachmentGrid 
                        attachments={message.attachments} 
                        onImageClick={onImageClick} 
                        onEditImage={onEditImage}
                    />
                 )}

               </div>
            )}
          </div>
          
          <div className={`flex items-center gap-2 mt-1 px-1 opacity-0 group-hover:opacity-100 transition-opacity ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            <span className="text-xs text-slate-500">
                {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            
            {/* Actions: Copy & Download */}
            {!message.isError && displayContent && (
              <>
                <button 
                    onClick={handleCopy}
                    className="p-1 text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 rounded transition-colors flex items-center gap-1"
                    title="Copy text"
                >
                    {isCopied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                    {isCopied && <span className="text-[10px] text-emerald-500">Copied</span>}
                </button>

                <button 
                    onClick={handleDownload}
                    className="p-1 text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 rounded transition-colors flex items-center gap-1"
                    title="Download as Markdown"
                >
                    {isDownloaded ? <Check size={12} className="text-emerald-500" /> : <Download size={12} />}
                    {isDownloaded && <span className="text-[10px] text-emerald-500">Saved</span>}
                </button>
              </>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default MessageItem;

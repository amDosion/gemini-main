
import React, { useRef, useEffect, useState } from 'react';
import { Paperclip, StopCircle, Send, Youtube, Link as LinkIcon, X, Check } from 'lucide-react';
import { AppMode } from '../../../../types';

interface PromptInputProps {
  input: string;
  setInput: (v: string) => void;
  handleSend: () => void;
  isLoading: boolean;
  onStop?: () => void;
  mode: AppMode;
  hasActiveContext?: boolean;
  hasAttachments: boolean;
  isMissingImage: boolean;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onAddLink?: (url: string) => void;
}

export const PromptInput: React.FC<PromptInputProps> = ({
  input, setInput, handleSend, isLoading, onStop, mode, hasActiveContext, hasAttachments, isMissingImage, onFileSelect, onAddLink
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Track focused state to handle transparent text logic
  const [isFocused, setIsFocused] = useState(false);
  
  // Link Input State
  const [showLinkInput, setShowLinkInput] = useState(false);
  const [linkValue, setLinkValue] = useState('');

  // Sync scroll between textarea and backdrop
  const handleScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
      if (backdropRef.current) {
          backdropRef.current.scrollTop = e.currentTarget.scrollTop;
      }
  };

  // Auto-resize logic (Disabled if user manually resizes)
  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (textarea && textarea.scrollHeight < 200) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  };

  useEffect(() => {
    adjustHeight();
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleLinkSubmit = () => {
      if (linkValue && onAddLink) {
          onAddLink(linkValue);
          setLinkValue('');
          setShowLinkInput(false);
      }
  };

  // Highlighting Logic: Render HTML with spans for [brackets]
  const renderHighlights = (text: string) => {
      const regex = /(\[.*?\])/g;
      const parts = text.split(regex);
      
      return parts.map((part, i) => {
          if (part.match(regex)) {
              return <span key={i} className="bg-indigo-500/30 text-indigo-300 font-medium rounded-sm shadow-[0_0_0_1px_rgba(99,102,241,0.4)]">{part}</span>;
          }
          return <span key={i}>{part}</span>;
      });
  };

  // 扩图模式禁用输入框
  const isOutPaintingMode = mode === 'image-outpainting';
  
  // Determine placeholder text
  const placeholderText = mode === 'chat' ? "Message Gemini... (Attach PDFs, Images, etc.)" :
      mode === 'image-gen' ? "Describe the image you want to generate..." :
      mode === 'image-edit' ? (hasActiveContext ? "Enter instructions to edit the image..." : "Attach an image to edit...") :
      mode === 'image-outpainting' ? "扩图模式无需输入提示词" :
      mode === 'video-gen' ? "Describe the video you want to generate..." :
      "Enter text...";
  
  // 发送按钮禁用逻辑：扩图模式只需要有图片即可
  const isSendDisabled = isOutPaintingMode 
      ? (!hasAttachments && !hasActiveContext)  // 扩图模式：只需要有图片
      : (!input.trim() && !hasAttachments && !hasActiveContext);  // 其他模式：需要输入或附件

  return (
    <div className={`relative flex items-end gap-2 bg-slate-800/80 backdrop-blur-xl border rounded-3xl p-2 shadow-2xl transition-all duration-300 ${
        isMissingImage 
          ? 'border-orange-500/50 ring-2 ring-orange-500/20' 
          : 'border-slate-700 ring-1 ring-white/5'
    }`}>
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={onFileSelect} 
        className="hidden" 
        multiple={mode === 'chat' || mode === 'image-edit'} 
        // Expanded accept list for document processing
        accept={mode !== 'chat' ? "image/*,video/*,audio/*" : "image/*,video/*,audio/*,application/pdf,text/plain,text/csv,text/html,application/json"} 
      />
      <button 
          onClick={() => fileInputRef.current?.click()}
          className={`p-3 rounded-full transition-all duration-300 mb-0.5 ${isMissingImage ? 'text-orange-400 bg-orange-500/10 hover:bg-orange-500/20 animate-pulse' : 'text-slate-400 hover:text-white hover:bg-slate-700'}`}
          title="Attach File (Image, Video, Audio, PDF, Text)"
      >
          <Paperclip size={20} />
      </button>

      {onAddLink && (
        <div className="relative flex items-center">
            {showLinkInput ? (
                <div className="absolute bottom-0 left-0 flex items-center gap-1 bg-slate-900 border border-slate-600 p-1 rounded-full shadow-xl animate-[fadeIn_0.2s_ease-out] z-20 w-64">
                    <div className="pl-3 pr-2 text-slate-400"><LinkIcon size={14} /></div>
                    <input 
                        type="text" 
                        value={linkValue}
                        onChange={(e) => setLinkValue(e.target.value)}
                        placeholder="Paste YouTube URL..."
                        className="flex-1 bg-transparent border-none outline-none text-xs text-white placeholder-slate-500 h-8 min-w-0"
                        autoFocus
                        onKeyDown={(e) => e.key === 'Enter' && handleLinkSubmit()}
                    />
                    <button onClick={handleLinkSubmit} className="p-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full">
                        <Check size={12} />
                    </button>
                    <button onClick={() => setShowLinkInput(false)} className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-full">
                        <X size={12} />
                    </button>
                </div>
            ) : (
                <button 
                    onClick={() => setShowLinkInput(true)}
                    className="p-3 rounded-full transition-all duration-300 mb-0.5 text-slate-400 hover:text-white hover:bg-slate-700"
                    title="Add YouTube Link"
                >
                    <Youtube size={20} />
                </button>
            )}
        </div>
      )}

      {/* Input Container */}
      <div className="relative flex-1 min-w-0">
          
          {/* Backdrop for Highlighting */}
          <div 
              ref={backdropRef}
              className="absolute inset-0 w-full h-full p-3 text-sm font-sans leading-relaxed whitespace-pre-wrap break-words overflow-hidden pointer-events-none text-slate-200"
              aria-hidden="true"
          >
              {renderHighlights(input)}
              {input.endsWith('\n') && <br />}
          </div>

          <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onScroll={handleScroll}
              onKeyDown={handleKeyDown}
              placeholder={placeholderText}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              disabled={isOutPaintingMode}
              className={`relative z-10 w-full bg-transparent border-none resize-y min-h-[44px] max-h-[400px] p-3 text-sm font-sans leading-relaxed focus:ring-0 scrollbar-hide outline-none text-transparent caret-white selection:bg-indigo-500/30 selection:text-white placeholder:text-slate-500 ${
                  isOutPaintingMode ? 'cursor-not-allowed opacity-60' : ''
              }`}
              rows={1}
              style={{ 
                  color: input ? 'transparent' : undefined, 
              }}
              spellCheck={false}
          />
      </div>

      {isLoading ? (
          <button 
              onClick={onStop}
              className="p-3 rounded-full bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all hover:scale-105 active:scale-95 mb-0.5"
          >
              <StopCircle size={20} />
          </button>
      ) : (
           <button 
              onClick={handleSend}
              disabled={isSendDisabled}
              className={`p-3 rounded-full transition-all duration-300 shadow-lg mb-0.5 ${
                  isSendDisabled
                  ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white hover:shadow-indigo-500/25 hover:scale-105 active:scale-95'
              }`}
          >
              <Send size={20} />
          </button>
      )}
    </div>
  );
};

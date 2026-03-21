import React, { useState, useEffect, useMemo, useRef } from 'react';
import { ChatOptions, ModelConfig, Attachment, AppMode, Persona } from '../../types/types';
import { v4 as uuidv4 } from 'uuid';
import { fileToBase64, isBlobUrl } from '../../hooks/handlers/attachmentUtils';
import { Paperclip, StopCircle, Send, Youtube, Link as LinkIcon, X, Check, Upload } from 'lucide-react';
import { useDragDrop } from '../../hooks/useDragDrop';
import { isThinkingCapableModel } from '../../utils/modelSuitability';

// Sub-components
import { AttachmentPreview } from './input/AttachmentPreview';

// Chat 专用控件
import { ChatControls } from '../../controls/modes';
import { useControlsState } from '../../hooks/useControlsState';

interface ChatInputAreaProps {
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  isLoading: boolean;
  onStop?: () => void;
  currentModel?: ModelConfig;
  visibleModels?: ModelConfig[];
  mode: AppMode;
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  activeAttachments?: Attachment[];
  onAttachmentsChange?: (attachments: Attachment[]) => void;
  hasActiveContext?: boolean;
  providerId?: string;
  personas?: Persona[];
  activePersonaId?: string;
  onSelectPersona?: (id: string) => void;
  // ✅ 生成参数（来自控制面板）
  temperature?: number;
  maxTokens?: number;
  topP?: number;
  topK?: number;
}

const ChatInputArea: React.FC<ChatInputAreaProps> = ({
  onSend, isLoading, onStop, currentModel,
  visibleModels = [],
  mode, initialPrompt, initialAttachments,
  activeAttachments, onAttachmentsChange, hasActiveContext,
  personas = [],
  activePersonaId = '',
  onSelectPersona,
  // 生成参数
  temperature = 0.7,
  maxTokens = 8192,
  topP = 0.95,
  topK = 40,
}) => {
  const [input, setInput] = useState('');
  const [localAttachments, setLocalAttachments] = useState<Attachment[]>([]);
  
  // Refs for input components
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Link Input State
  const [showLinkInput, setShowLinkInput] = useState(false);
  const [linkValue, setLinkValue] = useState('');

  // Controlled vs Local State for Attachments
  const attachments = activeAttachments !== undefined ? activeAttachments : localAttachments;
  const updateAttachments = (newAtts: Attachment[]) => {
    if (onAttachmentsChange) {
      onAttachmentsChange(newAtts);
    } else {
      setLocalAttachments(newAtts);
    }
  };

  // Use centralized controls state hook
  const controls = useControlsState(mode, currentModel);

  const deepResearchModelCandidates = useMemo(
    () => visibleModels.filter(isThinkingCapableModel),
    [visibleModels]
  );

  // Refs & Effects
  const attachmentsRef = useRef<Attachment[]>(attachments);
  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  useEffect(() => {
    if (initialPrompt) setInput(initialPrompt);
  }, [initialPrompt]);

  useEffect(() => {
    if (initialAttachments !== undefined) {
      updateAttachments(initialAttachments);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAttachments]);

  // File handling
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newAttachments: Attachment[] = [];
    for (const file of Array.from(files)) {
      const blobUrl = URL.createObjectURL(file);
      const attachmentId = uuidv4();
      const attachment: Attachment = {
        id: attachmentId,
        file: file,
        mimeType: file.type,
        name: file.name,
        url: blobUrl,
        tempUrl: blobUrl,
        uploadStatus: 'pending'
      };
      newAttachments.push(attachment);
    }

    updateAttachments([...attachments, ...newAttachments]);
    if (e.target) e.target.value = '';
  };

  // 拖放功能
  const handleFilesDropped = (files: File[]) => {
    const dataTransfer = new DataTransfer();
    files.forEach(file => dataTransfer.items.add(file));
    
    const event = {
      target: {
        files: dataTransfer.files,
        value: ''
      }
    } as React.ChangeEvent<HTMLInputElement>;
    
    handleFileSelect(event);
  };

  const dragDrop = useDragDrop({
    mode: 'chat',
    currentAttachmentCount: attachments.length,
    onFilesDropped: handleFilesDropped,
    disabled: isLoading
  });

  // Auto-resize textarea
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

  // Sync scroll between textarea and backdrop
  const handleScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
    if (backdropRef.current) {
      backdropRef.current.scrollTop = e.currentTarget.scrollTop;
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

  const handleLinkSubmit = () => {
    if (linkValue && handleAddLink) {
      handleAddLink(linkValue);
      setLinkValue('');
      setShowLinkInput(false);
    }
  };

  const handleAddLink = (url: string) => {
    if (url) {
      const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
      const newAttachment: Attachment = {
        id: uuidv4(),
        mimeType: isYouTube ? 'video/external' : 'text/link',
        fileUri: url,
        name: isYouTube ? 'YouTube Video' : 'Link',
        url: url
      };
      updateAttachments([...attachments, newAttachment]);

      if (!isYouTube && !controls.enableUrlContext) {
        controls.setEnableUrlContext(true);
      }
    }
  };

  const removeAttachment = (id: string) => {
    const attachmentToRemove = attachments.find(att => att.id === id);
    if (attachmentToRemove?.tempUrl) {
      URL.revokeObjectURL(attachmentToRemove.tempUrl);
    }
    updateAttachments(attachments.filter(att => att.id !== id));
  };

  // Cleanup Blob URLs when component unmounts
  useEffect(() => {
    return () => {
      attachments.forEach(att => {
        if (att.tempUrl) {
          URL.revokeObjectURL(att.tempUrl);
        }
      });
    };
  }, [attachments]);

  const handleSend = async () => {
    if (isLoading && !onStop) return;
    if (!input.trim() && attachments.length === 0 && !hasActiveContext) return;

    // 在发送前将 Blob URL 转换为 Base64 Data URL
    const processedAttachments = await Promise.all(
      attachments.map(async (att) => {
        if (att.file && isBlobUrl(att.url)) {
          try {
            const base64Url = await fileToBase64(att.file);
            return { ...att, url: base64Url, tempUrl: base64Url };
          } catch (e) {
            console.warn('[ChatInputArea] File 转 Base64 失败:', e);
            return att;
          }
        }
        return att;
      })
    );

    // 构建 ChatOptions 对象 - 只包含 chat 模式需要的选项
    const chatOptions: ChatOptions = {
      enableSearch: controls.enableSearch,
      enableThinking: controls.enableThinking,
      enableCodeExecution: controls.enableCodeExecution,
      enableUrlContext: controls.enableUrlContext,
      enableBrowser: controls.enableBrowser,
      enableEnhancedRetrieval: controls.enableEnhancedRetrieval,
      enableDeepResearch: controls.enableDeepResearch,
      enableAutoDeepResearch: controls.enableAutoDeepResearch,
      deepResearchAgentId: controls.deepResearchAgentId || undefined,
      googleCacheMode: controls.googleCacheMode,
      mcpServerKey: controls.selectedMcpServerKey || undefined,
      // ✅ 生成参数（来自控制面板）
      temperature,
      maxTokens,
      topP,
      topK,
      // 以下为必填但 chat 模式不使用的默认值
      imageAspectRatio: '1:1',
      imageResolution: '1024x1024',
      numberOfImages: 1,
    };
    
    onSend(input, chatOptions, processedAttachments, mode);

    setInput('');
    updateAttachments([]);
  };

  return (
    <div className="w-full max-w-[98%] 2xl:max-w-[1400px] mx-auto px-4 pb-6 pt-2 space-y-2 transition-all duration-300">
      {/* 工具栏 - 居中显示 */}
      <div className="flex justify-center">
        <ChatControls
        currentModel={currentModel}
        enableSearch={controls.enableSearch}
        setEnableSearch={controls.setEnableSearch}
        enableThinking={controls.enableThinking}
        setEnableThinking={controls.setEnableThinking}
        enableCodeExecution={controls.enableCodeExecution}
        setEnableCodeExecution={controls.setEnableCodeExecution}
        enableUrlContext={controls.enableUrlContext}
        setEnableUrlContext={controls.setEnableUrlContext}
        enableBrowser={controls.enableBrowser}
        setEnableBrowser={controls.setEnableBrowser}
        enableRAG={controls.enableRAG}
        setEnableRAG={controls.setEnableRAG}
        enableEnhancedRetrieval={controls.enableEnhancedRetrieval}
        setEnableEnhancedRetrieval={controls.setEnableEnhancedRetrieval}
        enableDeepResearch={controls.enableDeepResearch}
        setEnableDeepResearch={controls.setEnableDeepResearch}
        enableAutoDeepResearch={controls.enableAutoDeepResearch}
        setEnableAutoDeepResearch={controls.setEnableAutoDeepResearch}
        deepResearchAgentId={controls.deepResearchAgentId}
        setDeepResearchAgentId={controls.setDeepResearchAgentId}
        deepResearchModelCandidates={deepResearchModelCandidates}
        googleCacheMode={controls.googleCacheMode}
        setGoogleCacheMode={controls.setGoogleCacheMode}
        personas={personas}
        activePersonaId={activePersonaId}
        onSelectPersona={onSelectPersona}
        selectedMcpServerKey={controls.selectedMcpServerKey}
        setSelectedMcpServerKey={controls.setSelectedMcpServerKey}
      />
      </div>

      {/* 附件预览 */}
      <AttachmentPreview
        attachments={attachments}
        removeAttachment={removeAttachment}
      />

      {/* 输入框 - Chat 专用实现 */}
      <div 
        className={`relative flex items-end gap-2 bg-slate-800/80 backdrop-blur-xl border rounded-3xl p-2 shadow-2xl transition-all duration-300 ${
          dragDrop.isDragging
            ? dragDrop.isValidDrop
              ? 'border-blue-500 ring-2 ring-blue-500/30 bg-blue-500/5'
              : 'border-red-500 ring-2 ring-red-500/30 bg-red-500/5'
            : 'border-slate-700 ring-1 ring-white/5'
        }`}
        onDragEnter={dragDrop.handleDragEnter}
        onDragOver={dragDrop.handleDragOver}
        onDragLeave={dragDrop.handleDragLeave}
        onDrop={dragDrop.handleDrop}
        aria-label="输入区域，支持拖放文件上传"
        role="region"
      >
        {/* 拖放提示层 */}
        {dragDrop.isDragging && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm rounded-3xl z-30 pointer-events-none">
            <div className="flex flex-col items-center gap-2">
              <Upload 
                size={32} 
                className={dragDrop.isValidDrop ? 'text-blue-400' : 'text-red-400'} 
              />
              <p className={`text-sm font-medium ${dragDrop.isValidDrop ? 'text-blue-300' : 'text-red-300'}`}>
                {dragDrop.isValidDrop ? '释放文件以上传' : dragDrop.errorMessage}
              </p>
            </div>
          </div>
        )}

        <input 
          type="file" 
          id="chat-file-input"
          name="chat-file-input"
          ref={fileInputRef} 
          onChange={handleFileSelect} 
          className="hidden" 
          multiple={true}
          accept="image/*,video/*,audio/*,application/pdf,text/plain,text/csv,text/html,application/json"
        />
        
        <button 
          onClick={() => fileInputRef.current?.click()}
          className="p-3 rounded-full transition-all duration-300 mb-0.5 text-slate-400 hover:text-white hover:bg-slate-700"
          title="Attach File (Image, Video, Audio, PDF, Text)"
        >
          <Paperclip size={20} />
        </button>

        {/* YouTube Link Input */}
        <div className="relative flex items-center">
          {showLinkInput ? (
            <div className="absolute bottom-0 left-0 flex items-center gap-1 bg-slate-900 border border-slate-600 p-1 rounded-full shadow-xl animate-[fadeIn_0.2s_ease-out] z-20 w-64">
              <div className="pl-3 pr-2 text-slate-400"><LinkIcon size={14} /></div>
              <input 
                type="text" 
                id="youtube-link-input"
                name="youtube-link-input"
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
            id="chat-textarea"
            name="chat-textarea"
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onScroll={handleScroll}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Message Gemini... (Attach PDFs, Images, etc.)"
            className="relative z-10 w-full bg-transparent border-none resize-y min-h-[44px] max-h-[400px] p-3 text-sm font-sans leading-relaxed focus:ring-0 scrollbar-hide outline-none text-transparent caret-white selection:bg-indigo-500/30 selection:text-white placeholder:text-slate-500"
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
            disabled={!input.trim() && attachments.length === 0 && !hasActiveContext}
            className={`p-3 rounded-full transition-all duration-300 shadow-lg mb-0.5 ${
              (!input.trim() && attachments.length === 0 && !hasActiveContext)
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white hover:shadow-indigo-500/25 hover:scale-105 active:scale-95'
            }`}
          >
            <Send size={20} />
          </button>
        )}
      </div>
    </div>
  );
};

export default ChatInputArea;

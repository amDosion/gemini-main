
import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Sparkles, AlertCircle, Layers, User, Bot, SlidersHorizontal, RotateCcw } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';

interface ImageRecontextViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];
    allVisibleModels?: ModelConfig[];  // 新增：完整模型列表
    initialPrompt?: string;
    initialAttachments?: Attachment[];
    onExpandImage?: (url: string) => void;
    providerId?: string;
    sessionId?: string | null;
}

// 复用 ImageEditView 的比较函数
const arePropsEqual = (prevProps: ImageRecontextViewProps, nextProps: ImageRecontextViewProps) => {
    if (prevProps.activeModelConfig?.id !== nextProps.activeModelConfig?.id) {
        return false;
    }
    if (prevProps.loadingState !== nextProps.loadingState) return false;
    if (prevProps.messages !== nextProps.messages) return false;
    if (prevProps.sessionId !== nextProps.sessionId) return false;
    if (prevProps.providerId !== nextProps.providerId) return false;
    return true;
};

// 复用 ImageEditMainCanvas 组件（从 ImageEditView 导入或复制）
type ImageEditMainCanvasProps = {
    loadingState: string;
    isCompareMode: boolean;
    activeAttachments: Attachment[];
    activeImageUrl: string | null;
    originalImageUrl: string | null;
    zoom: number;
    isDragging: boolean;
    canvasStyle: React.CSSProperties;
    onWheel: (e: React.WheelEvent) => void;
    onMouseDown: (e: React.MouseEvent) => void;
    onMouseMove: (e: React.MouseEvent) => void;
    onMouseUp: () => void;
    onZoomIn: (e?: React.MouseEvent) => void;
    onZoomOut: (e?: React.MouseEvent) => void;
    onReset: (e?: React.MouseEvent) => void;
    onFullscreen?: () => void;
    onExpand?: () => void;
    onToggleCompare?: () => void;
};

const ImageEditMainCanvas = memo(({
    loadingState,
    isCompareMode,
    activeAttachments,
    activeImageUrl,
    originalImageUrl,
    zoom,
    isDragging,
    canvasStyle,
    onWheel,
    onMouseDown,
    onMouseMove,
    onMouseUp,
    onZoomIn,
    onZoomOut,
    onReset,
    onFullscreen,
    onExpand,
    onToggleCompare,
}: ImageEditMainCanvasProps) => {
    const cursor =
        isCompareMode ? 'default' : isDragging ? 'grabbing' : activeImageUrl ? 'grab' : 'default';

    return (
        <div
            className="flex-1 w-full h-full select-none flex flex-col relative"
            onWheel={isCompareMode ? undefined : onWheel}
            onMouseDown={isCompareMode ? undefined : onMouseDown}
            onMouseMove={isCompareMode ? undefined : onMouseMove}
            onMouseUp={isCompareMode ? undefined : onMouseUp}
            onMouseLeave={isCompareMode ? undefined : onMouseUp}
            style={{ cursor }}
        >
            {/* Checkerboard Background */}
            <div
                className="absolute inset-0 opacity-20 pointer-events-none"
                style={{
                    backgroundImage: `
                               linear-gradient(45deg, #334155 25%, transparent 25%), 
                               linear-gradient(-45deg, #334155 25%, transparent 25%), 
                               linear-gradient(45deg, transparent 75%, #334155 75%), 
                               linear-gradient(-45deg, transparent 75%, #334155 75%)
                           `,
                    backgroundSize: '20px 20px',
                    backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
                }}
            />

            {/* Canvas Header */}
            <div className="absolute top-4 left-4 z-10 pointer-events-none">
                <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
                    <Sparkles size={12} className="text-yellow-400" />
                    {isCompareMode
                        ? '对比模式'
                        : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url
                            ? 'Source Preview'
                            : 'Recontext Editor'}
                    <span className="opacity-50">|</span>
                    <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
                </div>
            </div>

            {/* Main Image Display */}
            <div className="flex-1 flex items-center justify-center p-0 w-full h-full">
                {loadingState !== 'idle' ? (() => {
                    let statusText = 'Processing Image...';
                    if (loadingState === 'uploading') {
                        statusText = '上传图片中...';
                    } else if (loadingState === 'loading') {
                        statusText = '重新上下文处理中，正在调整图片上下文...';
                    } else if (loadingState === 'streaming') {
                        statusText = '流式处理中...';
                    }
                    
                    return (
                        <div className="flex flex-col items-center gap-4 pointer-events-none">
                            <div className="relative">
                                <div className="w-20 h-20 border-4 border-yellow-500/30 border-t-yellow-500 rounded-full animate-spin"></div>
                            </div>
                            <p className="text-slate-400 animate-pulse">{statusText}</p>
                        </div>
                    );
                })() : isCompareMode && originalImageUrl && activeImageUrl ? (
                    <div className="relative shadow-2xl transition-transform duration-75 ease-out" style={canvasStyle}>
                        <ImageCompare
                            beforeImage={originalImageUrl}
                            afterImage={activeImageUrl}
                            beforeLabel="原图"
                            afterLabel="重上下文结果"
                            accentColor="orange"
                            className="max-w-none rounded-lg border border-slate-800"
                            style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                        />
                    </div>
                ) : activeImageUrl ? (
                    <div
                        className="relative shadow-2xl group transition-transform duration-75 ease-out"
                        style={canvasStyle}
                    >
                        <img
                            src={activeImageUrl}
                            className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
                            style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                            alt="Main Canvas"
                        />
                    </div>
                ) : (
                    <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                        <Sparkles size={48} className="opacity-20" />
                        <div>
                            <h3 className="text-xl font-bold text-slate-500 mb-2">Recontext Editor</h3>
                            <p className="text-sm opacity-60">
                                上传图片并调整其上下文环境
                            </p>
                        </div>
                    </div>
                )}
            </div>

            {/* Floating Controls */}
            {activeImageUrl && (
                <div className="absolute bottom-6 right-6 z-20">
                    <ImageCanvasControls
                        zoom={zoom}
                        onZoomIn={onZoomIn}
                        onZoomOut={onZoomOut}
                        onReset={onReset}
                        onFullscreen={onFullscreen}
                        downloadUrl={activeImageUrl}
                        onExpand={onExpand}
                        onToggleCompare={onToggleCompare}
                        isCompareMode={isCompareMode}
                        accentColor="orange"
                    />
                </div>
            )}
        </div>
    );
});

ImageEditMainCanvas.displayName = 'ImageEditMainCanvas';

export const ImageRecontextView = memo(({
    messages,
    setAppMode,
    onImageClick,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    visibleModels = [],
    allVisibleModels = [],
    initialPrompt,
    initialAttachments,
    onExpandImage,
    providerId,
    sessionId: currentSessionId
}: ImageRecontextViewProps) => {
    const { showError } = useToastContext();
    const scrollRef = useRef<HTMLDivElement>(null);

    // State for reference image
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
    
    // 固定使用 image-recontext 模式
    const editMode: AppMode = 'image-recontext';
    
    // ✅ 参数面板状态
    const controls = useControlsState(editMode, activeModelConfig);

    // 重置参数
    const resetParams = useCallback(() => {
        controls.setAspectRatio('1:1');
        controls.setResolution('1K');
        controls.setNegativePrompt('');
        controls.setSeed(-1);
    }, [controls]);
    
    // State for thinking block
    const [isThinkingOpen, setIsThinkingOpen] = useState(true);
    const [displayedThinkingContent, setDisplayedThinkingContent] = useState('');

    // Stable canvas URL
    const canvasObjectUrlRef = useRef<string | null>(null);
    const canvasObjectUrlFileRef = useRef<File | null>(null);

    const getStableCanvasUrlFromAttachment = useCallback((att: Attachment) => {
        if (att.file) {
            const file = att.file;
            if (!canvasObjectUrlRef.current || canvasObjectUrlFileRef.current !== file) {
                if (canvasObjectUrlRef.current) URL.revokeObjectURL(canvasObjectUrlRef.current);
                canvasObjectUrlRef.current = URL.createObjectURL(file);
                canvasObjectUrlFileRef.current = file;
            }
            return canvasObjectUrlRef.current;
        }
        return att.url || att.tempUrl || null;
    }, []);

    useEffect(() => {
        return () => {
            if (canvasObjectUrlRef.current) {
                URL.revokeObjectURL(canvasObjectUrlRef.current);
                canvasObjectUrlRef.current = null;
                canvasObjectUrlFileRef.current = null;
            }
        };
    }, []);

    const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);
    const [isCompareMode, setIsCompareMode] = useState(false);
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

    useEffect(() => {
        canvas.resetView();
        setIsCompareMode(false);
    }, [activeImageUrl]);

    useEffect(() => {
        if (canvasObjectUrlRef.current && activeImageUrl !== canvasObjectUrlRef.current) {
            URL.revokeObjectURL(canvasObjectUrlRef.current);
            canvasObjectUrlRef.current = null;
            canvasObjectUrlFileRef.current = null;
        }
    }, [activeImageUrl]);

    const originalImageUrl = useMemo(() => {
        const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
        return lastUserMsg?.attachments?.[0]?.url || null;
    }, [messages]);

    useEffect(() => {
        if (initialAttachments && initialAttachments.length > 0) {
            setActiveAttachments(initialAttachments);
            setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
        }
    }, [initialAttachments, getStableCanvasUrlFromAttachment]);

    useEffect(() => {
        if (activeAttachments.length > 0) {
            setActiveImageUrl(getStableCanvasUrlFromAttachment(activeAttachments[0]));
        }
    }, [activeAttachments, getStableCanvasUrlFromAttachment]);

    useEffect(() => {
        const container = scrollRef.current;
        if (!container) return;
        requestAnimationFrame(() => {
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        });
    }, [messages, activeAttachments]);

    useEffect(() => {
        const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
        if (!lastMessage) {
            setDisplayedThinkingContent('');
            return;
        }
        
        const thoughts = lastMessage?.thoughts || [];
        const textResponse = lastMessage?.textResponse;
        const thinkingParts: string[] = [];
        thoughts.forEach((thought) => {
            if (thought.type === 'text') {
                thinkingParts.push(thought.content);
            } else {
                thinkingParts.push('[图片思考过程]');
            }
        });
        if (textResponse) {
            thinkingParts.push(`\n\n💬 AI 响应：\n${textResponse}`);
        }
        const fullContent = thinkingParts.join('\n\n');
        
        if (!fullContent) {
            setDisplayedThinkingContent('');
            return;
        }
        
        if (loadingState === 'idle') {
            setDisplayedThinkingContent(fullContent);
            return;
        }
        
        const targetLength = fullContent.length;
        const currentLength = displayedThinkingContent.length;
        
        if (currentLength < targetLength) {
            const chunkSize = 5;
            const nextLength = Math.min(currentLength + chunkSize, targetLength);
            
            const timer = setTimeout(() => {
                setDisplayedThinkingContent(fullContent.substring(0, nextLength));
            }, 30);
            
            return () => clearTimeout(timer);
        } else if (fullContent !== displayedThinkingContent) {
            setDisplayedThinkingContent(fullContent);
        }
    }, [messages, loadingState]);
    
    useEffect(() => {
        if (activeAttachments.length === 0 && !activeImageUrl) {
            const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
            if (lastUserMsg && lastUserMsg.attachments?.[0]?.url) {
                setActiveImageUrl(lastUserMsg.attachments[0].url);
            } else {
                const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
                if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
                    setActiveImageUrl(lastModelMsg.attachments[0].url);
                }
            }
        }

        if (loadingState === 'idle' && messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            if (lastMsg.id !== lastProcessedMsgId) {
                if (lastMsg.role === Role.MODEL && lastMsg.attachments && lastMsg.attachments.length > 0 && lastMsg.attachments[0].url) {
                    setActiveImageUrl(lastMsg.attachments[0].url);
                    setLastProcessedMsgId(lastMsg.id);
                } else if (lastMsg.isError) {
                    setLastProcessedMsgId(lastMsg.id);
                }
            }
        }
    }, [messages, activeAttachments.length, loadingState, lastProcessedMsgId, activeImageUrl]);

    // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
    const handleSend = useCallback((text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        onSend(text, options, attachments, editMode);
    }, [onSend, editMode]);

    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    const sidebarContent = useMemo(() => (
        <div ref={scrollRef} className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
            {messages.map((msg) => {
                const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
                if (isPlaceholder) return null;

                return (
                    <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>
                        <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
                            {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
                            <span>{msg.role === Role.USER ? 'You' : (activeModelConfig?.name || 'AI')}</span>
                        </div>
                        <div className={`p-3 rounded-2xl max-w-full text-sm shadow-sm ${msg.role === Role.USER
                            ? 'bg-slate-800 text-slate-200 rounded-tr-sm'
                            : 'bg-slate-800/50 text-slate-300 border border-slate-700/50 rounded-tl-sm'
                            }`}>
                            {msg.content && <p className="mb-2">{msg.content}</p>}
                            {msg.attachments?.filter(att => att.url && att.url.length > 0).map((att, idx) => (
                                <div
                                    key={idx}
                                    onClick={() => setActiveImageUrl(att.url || null)}
                                    className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${activeImageUrl === att.url ? 'ring-2 ring-yellow-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                                        }`}
                                >
                                    <img src={att.url} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
                                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                        {activeImageUrl === att.url && <div className="bg-yellow-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />}
                                    </div>
                                </div>
                            ))}
                            {msg.isError && (
                                <div className="flex items-center gap-2 text-red-400 text-xs mt-1">
                                    <AlertCircle size={12} /> Error generating
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
            {loadingState !== 'idle' && (() => {
                let statusText = 'Processing request...';
                let statusIcon = <Bot size={16} className="text-slate-500" />;
                
                if (loadingState === 'uploading') {
                    statusText = '上传图片中...';
                    statusIcon = <Layers size={16} className="text-blue-400" />;
                } else if (loadingState === 'loading') {
                    statusText = '重新上下文处理中，正在调整图片上下文...';
                    statusIcon = <Sparkles size={16} className="text-yellow-400" />;
                } else if (loadingState === 'streaming') {
                    statusText = '流式处理中...';
                    statusIcon = <Sparkles size={16} className="text-yellow-400 animate-pulse" />;
                }
                
                const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
                const thoughts = lastMessage?.thoughts || [];
                const textResponse = lastMessage?.textResponse;
                const hasTextContent = lastMessage?.content && lastMessage.content.trim().length > 0;
                const isThinkingComplete = loadingState === 'idle';
                
                return (
                    <div className="flex items-start gap-2">
                        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
                            {statusIcon}
                        </div>
                        <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 flex-1">
                            <div className={`font-medium mb-1 ${loadingState !== 'idle' ? 'animate-pulse' : ''}`}>
                                {statusText}
                            </div>
                            
                            {displayedThinkingContent && (
                                <div className="mt-2">
                                    <ThinkingBlock
                                        content={displayedThinkingContent}
                                        isOpen={isThinkingOpen}
                                        onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                                        isComplete={isThinkingComplete}
                                    />
                                </div>
                            )}
                            
                            {hasTextContent && !thoughts.length && !textResponse && (
                                <div className="mt-2 pt-2 border-t border-slate-700/50 text-slate-500 italic">
                                    {lastMessage.content.substring(0, 100)}
                                    {lastMessage.content.length > 100 ? '...' : ''}
                                </div>
                            )}
                        </div>
                    </div>
                );
            })()}
            <div />
        </div>
    ), [messages, loadingState, activeModelConfig?.name, activeImageUrl, activeAttachments, displayedThinkingContent, isThinkingOpen]);

    const toggleCompare = useCallback(() => setIsCompareMode(prev => !prev), []);
    const handleFullscreen = useCallback(() => {
        if (activeImageUrl) onImageClick(activeImageUrl);
    }, [activeImageUrl, onImageClick]);
    const handleExpand = useCallback(() => {
        if (activeImageUrl && onExpandImage) onExpandImage(activeImageUrl);
    }, [activeImageUrl, onExpandImage]);

    // ✅ 主区域：两栏布局（画布 + 参数面板）
    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            {/* ========== 左侧：画布区域 ========== */}
            <ImageEditMainCanvas
                loadingState={loadingState}
                isCompareMode={isCompareMode}
                activeAttachments={activeAttachments}
                activeImageUrl={activeImageUrl}
                originalImageUrl={originalImageUrl}
                zoom={canvas.zoom}
                isDragging={canvas.isDragging}
                canvasStyle={canvas.canvasStyle}
                onWheel={canvas.handleWheel}
                onMouseDown={canvas.handleMouseDown}
                onMouseMove={canvas.handleMouseMove}
                onMouseUp={canvas.handleMouseUp}
                onZoomIn={canvas.handleZoomIn}
                onZoomOut={canvas.handleZoomOut}
                onReset={canvas.handleReset}
                onFullscreen={activeImageUrl ? handleFullscreen : undefined}
                onExpand={onExpandImage && activeImageUrl ? handleExpand : undefined}
                onToggleCompare={originalImageUrl ? toggleCompare : undefined}
            />

            {/* ========== 右侧：参数面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-yellow-400" />
                        <span className="text-xs font-bold text-white">上下文参数</span>
                    </div>
                    <button
                        onClick={resetParams}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                        title="重置为默认值"
                    >
                        <RotateCcw size={12} />
                    </button>
                </div>

                {/* 参数滚动区 */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
                    <ModeControlsCoordinator
                        mode={editMode}
                        providerId={providerId || 'google'}
                        controls={controls}
                    />
                </div>

                {/* 底部固定区：使用 ChatEditInputArea 组件 */}
                <ChatEditInputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    mode={editMode}
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={setActiveAttachments}
                    activeImageUrl={activeImageUrl}
                    onActiveImageUrlChange={setActiveImageUrl}
                    messages={messages}
                    sessionId={currentSessionId}
                    initialPrompt={initialPrompt}
                    initialAttachments={initialAttachments}
                    providerId={providerId}
                    controls={controls}
                />
            </div>
        </div>
    ), [loadingState, isCompareMode, activeAttachments, activeImageUrl, originalImageUrl, canvas, handleFullscreen, handleExpand, toggleCompare, onExpandImage, controls, providerId, resetParams, editMode, activeModelConfig, onStop, messages, currentSessionId, initialPrompt, initialAttachments, handleSend]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Layers size={14} />}
            sidebar={sidebarContent}
            main={mainContent}
        />
    );
}, arePropsEqual);

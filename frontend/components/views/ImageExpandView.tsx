
import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Expand, AlertCircle, Layers, User, Bot } from 'lucide-react';
import InputArea from '../chat/InputArea';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { processUserAttachments } from '../../hooks/handlers/attachmentUtils';


interface ImageExpandViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];  // 新增
    initialAttachments?: Attachment[];
    providerId?: string;
    sessionId?: string | null;  // ✅ 会话 ID，用于查询附件
}

// 优化：使用 React.memo 配合自定义比较函数，防止不必要的重新渲染
// Optimization: Use React.memo with a custom comparison function to prevent unnecessary re-renders
const arePropsEqual = (prevProps: ImageExpandViewProps, nextProps: ImageExpandViewProps) => {
    // 仅比较 activeModelConfig 的 ID，避免因对象引用变化而重新渲染
    // Only compare the ID of activeModelConfig to prevent re-renders due to object reference changes
    if (prevProps.activeModelConfig?.id !== nextProps.activeModelConfig?.id) {
        return false;
    }

    // 比较其他关键 props
    // Compare other critical props
    if (prevProps.loadingState !== nextProps.loadingState) return false;
    if (prevProps.messages !== nextProps.messages) return false;
    if (prevProps.sessionId !== nextProps.sessionId) return false;
    if (prevProps.providerId !== nextProps.providerId) return false;

    // 如果所有关键 props 都相等，则不重新渲染
    // If all critical props are equal, do not re-render
    return true;
};

type ImageExpandMainCanvasProps = {
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
    onToggleCompare?: () => void;
};

const ImageExpandMainCanvas = memo(({
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
    onToggleCompare,
}: ImageExpandMainCanvasProps) => {
    const cursor =
        isCompareMode ? 'default' : isDragging ? 'grabbing' : activeImageUrl ? 'grab' : 'default';

    return (
        // RIGHT MAIN: Result / Canvas
        <div
            className="flex-1 w-full h-full select-none flex flex-col relative"
            onWheel={isCompareMode ? undefined : onWheel}
            onMouseDown={isCompareMode ? undefined : onMouseDown}
            onMouseMove={isCompareMode ? undefined : onMouseMove}
            onMouseUp={isCompareMode ? undefined : onMouseUp}
            onMouseLeave={isCompareMode ? undefined : onMouseUp}
            style={{ cursor }}
        >
            {/* 棋盘格背景 */}
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
                    <Expand size={12} className="text-orange-400" />
                    {isCompareMode
                        ? '对比模式'
                        : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url
                            ? 'Source Preview'
                            : 'Workspace'}
                    <span className="opacity-50">|</span>
                    <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
                </div>
            </div>

            {/* Main Image Display */}
            <div className="flex-1 flex items-center justify-center p-0 w-full h-full">
                {loadingState !== 'idle' ? (
                    <div className="flex flex-col items-center gap-4 pointer-events-none">
                        <div className="relative">
                            <div className="w-20 h-20 border-4 border-orange-500/30 border-t-orange-500 rounded-full animate-spin"></div>
                        </div>
                        <p className="text-slate-400 animate-pulse">Expanding Image...</p>
                    </div>
                ) : isCompareMode && originalImageUrl && activeImageUrl ? (
                    // 对比模式
                    <div className="relative shadow-2xl transition-transform duration-75 ease-out" style={canvasStyle}>
                        <ImageCompare
                            beforeImage={originalImageUrl}
                            afterImage={activeImageUrl}
                            beforeLabel="原图"
                            afterLabel="扩图结果"
                            accentColor="orange"
                            className="max-w-none rounded-lg border border-slate-800"
                            style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                        />
                    </div>
                ) : activeImageUrl ? (
                    // 普通模式
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
                        <Expand size={48} className="opacity-20" />
                        <div>
                            <h3 className="text-xl font-bold text-slate-500 mb-2">Out-Paint Workspace</h3>
                            <p className="text-sm opacity-60">
                                Attach an image below to start expanding. Select any image from the history to view it
                                here.
                            </p>
                        </div>
                    </div>
                )}
            </div>

            {/* 浮动控制按钮 */}
            {activeImageUrl && (
                <div className="absolute bottom-6 right-6 z-20">
                    <ImageCanvasControls
                        zoom={zoom}
                        onZoomIn={onZoomIn}
                        onZoomOut={onZoomOut}
                        onReset={onReset}
                        onFullscreen={onFullscreen}
                        downloadUrl={activeImageUrl}
                        onToggleCompare={onToggleCompare}
                        isCompareMode={isCompareMode}
                        accentColor="orange"
                    />
                </div>
            )}
        </div>
    );
});

ImageExpandMainCanvas.displayName = 'ImageExpandMainCanvas';

export const ImageExpandView = memo(({
    messages,
    setAppMode,
    onImageClick,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    visibleModels = [],
    initialAttachments,
    providerId,
    sessionId: currentSessionId  // ✅ 接收 sessionId
}: ImageExpandViewProps) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    // State for reference image, synced with InputArea
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);

    // Stable canvas URL (avoid relying on InputArea-managed Blob URLs that may be revoked)
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

    // Track last processed message to auto-update view
    const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);

    // 对比模式状态
    const [isCompareMode, setIsCompareMode] = useState(false);

    // Pan & Zoom Hook
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

    // 重置视图当图片改变时
    useEffect(() => {
        canvas.resetView();
        setIsCompareMode(false);
    }, [activeImageUrl]);

    // Release any prior canvas object URL once we switch away from it (e.g. to a generated result)
    useEffect(() => {
        if (canvasObjectUrlRef.current && activeImageUrl !== canvasObjectUrlRef.current) {
            URL.revokeObjectURL(canvasObjectUrlRef.current);
            canvasObjectUrlRef.current = null;
            canvasObjectUrlFileRef.current = null;
        }
    }, [activeImageUrl]);

    // 获取原图 URL（用于对比）
    const originalImageUrl = useMemo(() => {
        const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
        const att = lastUserMsg?.attachments?.[0];
        return att?.url || att?.tempUrl || null;
    }, [messages]);

    // Sync initial attachments
    useEffect(() => {
        if (initialAttachments && initialAttachments.length > 0) {
            setActiveAttachments(initialAttachments);
            setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
        }
    }, [initialAttachments, getStableCanvasUrlFromAttachment]);

    // Sync uploaded attachment to main view immediately
    useEffect(() => {
        if (activeAttachments.length > 0) {
            setActiveImageUrl(getStableCanvasUrlFromAttachment(activeAttachments[0]));
        }
    }, [activeAttachments, getStableCanvasUrlFromAttachment]);

    // Auto-scroll to bottom of history
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, activeAttachments]);

    // Auto-select latest result logic
    useEffect(() => {
        // 1. Initial Load: If no active image, pick latest from history
        if (activeAttachments.length === 0 && !activeImageUrl) {
            const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
            if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
                setActiveImageUrl(lastModelMsg.attachments[0].url);
            }
        }

        // 2. New Generation Complete: Auto-switch to result
        if (loadingState === 'idle' && messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            // Check if this is a new message we haven't handled yet
            if (lastMsg.id !== lastProcessedMsgId) {
                // If it's a model response with an image
                if (lastMsg.role === Role.MODEL && lastMsg.attachments && lastMsg.attachments.length > 0 && lastMsg.attachments[0].url) {
                    setActiveImageUrl(lastMsg.attachments[0].url);
                    setLastProcessedMsgId(lastMsg.id);
                } else if (lastMsg.isError) {
                    setLastProcessedMsgId(lastMsg.id);
                }
            }
        }
    }, [messages, activeAttachments.length, loadingState, lastProcessedMsgId, activeImageUrl]);

    const handleSend = async (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        try {
            console.log('========== [ImageExpandView] handleSend 开始 ==========');
            console.log('[handleSend] 用户上传的附件数量:', attachments.length);

            // 使用统一的附件处理函数
            const finalAttachments = await processUserAttachments(
                attachments,
                activeImageUrl,
                messages,
                currentSessionId,
                'expand'
            );

            console.log('[handleSend] 最终附件数量:', finalAttachments.length);
            console.log('========== [ImageExpandView] handleSend 结束 ==========');
            onSend(text, options, finalAttachments, mode);
        } catch (error) {
            console.error('[ImageExpandView] handleSend 处理附件失败:', error);
            alert('处理附件失败，请重试');
            return;
        }
    };

    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    // 使用 useMemo 缓存 sidebarContent，防止不必要的重新渲染
    const sidebarContent = useMemo(() => (
        <div className="flex-1 p-4 space-y-6">
                    {messages.map((msg) => {
                        // Filter out empty placeholders
                        const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
                        if (isPlaceholder) return null;

                        return (
                            <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>
                                <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
                                    {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
                                    <span>{msg.role === Role.USER ? 'You' : 'AI Expander'}</span>
                                </div>

                                <div className={`p-3 rounded-2xl max-w-full text-sm shadow-sm ${msg.role === Role.USER
                                    ? 'bg-slate-800 text-slate-200 rounded-tr-sm'
                                    : 'bg-slate-800/50 text-slate-300 border border-slate-700/50 rounded-tl-sm'
                                    }`}>
                                    {msg.content && <p className="mb-2">{msg.content}</p>}
                                    {msg.attachments?.map((att, idx) => {
                                        // ✅ 优先使用 url（永久 URL），如果没有则使用 tempUrl（临时 URL）
                                        const displayUrl = att.url || att.tempUrl || '';
                                        // ✅ 如果没有有效的 URL，不渲染图片
                                        if (!displayUrl) return null;
                                        return (
                                            <div
                                                key={idx}
                                                onClick={() => setActiveImageUrl(displayUrl || null)}
                                                className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${activeImageUrl === displayUrl ? 'ring-2 ring-orange-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                                                    }`}
                                            >
                                                <img src={displayUrl} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
                                                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                                    {activeImageUrl === displayUrl && <div className="bg-orange-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />}
                                                </div>
                                            </div>
                                        );
                                    })}
                                    {msg.isError && (
                                        <div className="flex items-center gap-2 text-red-400 text-xs mt-1">
                                            <AlertCircle size={12} /> Error expanding
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}

                    {loadingState !== 'idle' && (
                        <div className="flex items-start gap-2 animate-pulse">
                            <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center"><Bot size={16} className="text-slate-500" /></div>
                            <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400">
                                Expanding image...
                            </div>
                        </div>
                    )}
                    {/* Dummy div for scroll ref */}
                    <div ref={scrollRef} />
                </div>
    ), [messages, loadingState, activeImageUrl, activeAttachments]);

    const toggleCompare = useCallback(() => setIsCompareMode(prev => !prev), []);
    const handleFullscreen = useCallback(() => {
        if (activeImageUrl) onImageClick(activeImageUrl);
    }, [activeImageUrl, onImageClick]);

    const mainContent = (
        <ImageExpandMainCanvas
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
            onToggleCompare={originalImageUrl ? toggleCompare : undefined}
        />
    );

    // 使用 useMemo 缓存 bottomContent，防止不必要的重新渲染
    const bottomContent = useMemo(() => (
                <InputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    currentModel={activeModelConfig}
                    visibleModels={visibleModels}
                    mode="image-outpainting"
                    setMode={setAppMode}
                    // Sync State
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={setActiveAttachments}
                    providerId={providerId}
                    // ✅ 当 workspace 中有图片时，允许发送（CONTINUITY LOGIC 会自动使用该图片）
                    hasActiveContext={!!activeImageUrl}
                />
    ), [
        handleSend,
        loadingState,
        onStop,
        activeModelConfig,
        visibleModels,
        setAppMode,
        activeAttachments,
        setActiveAttachments,
        providerId,
        activeImageUrl
    ]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Layers size={14} />}
            sidebarContent={sidebarContent}
            mainContent={mainContent}
            bottomContent={bottomContent}
        />
    );
}, arePropsEqual);

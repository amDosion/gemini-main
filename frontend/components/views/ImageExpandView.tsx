
import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Expand, AlertCircle, Layers, User, Bot, SlidersHorizontal, RotateCcw, Image as ImageIcon, Paperclip, X } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { processUserAttachments } from '../../hooks/handlers/attachmentUtils';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';


interface ImageExpandViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];  // 新增
    allVisibleModels?: ModelConfig[];  // 新增：完整模型列表
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
    allVisibleModels = [],  // 新增
    initialAttachments,
    providerId,
    sessionId: currentSessionId  // ✅ 接收 sessionId
}: ImageExpandViewProps) => {
    const { showError } = useToastContext();
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

    // ✅ 参数面板状态
    const expandMode: AppMode = 'image-outpainting';
    const controls = useControlsState(expandMode, activeModelConfig);
    const [prompt, setPrompt] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // 重置参数
    const resetParams = useCallback(() => {
        controls.setAspectRatio('1:1');
        controls.setResolution('1K');
        controls.setNegativePrompt('');
        controls.setSeed(-1);
    }, [controls]);

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

    // ✅ 使用参数面板发送扩图请求
    const handleGenerate = useCallback(async () => {
        // ✅ 修复：允许画布中有图片时发送（CONTINUITY LOGIC）
        if (!prompt.trim() || loadingState !== 'idle' || (activeAttachments.length === 0 && !activeImageUrl)) return;
        
        try {
            console.log('========== [ImageExpandView] handleGenerate 开始 ==========');
            console.log('[handleGenerate] 用户输入:', prompt);
            console.log('[handleGenerate] 当前附件数量:', activeAttachments.length);
            
            const finalAttachments = await processUserAttachments(
                activeAttachments,
                activeImageUrl,
                messages,
                currentSessionId,
                'expand'
            );

            const options: ChatOptions = {
                enableSearch: false,
                enableThinking: false,
                enableCodeExecution: false,
                // 扩图参数
                imageAspectRatio: controls.aspectRatio,
                imageResolution: controls.resolution,
                negativePrompt: controls.negativePrompt || undefined,
                seed: controls.seed !== -1 ? controls.seed : undefined,
            };
            
            console.log('[handleGenerate] 扩图参数:', options);
            console.log('========== [ImageExpandView] handleGenerate 结束 ==========');
            onSend(prompt, options, finalAttachments, expandMode);
            setPrompt(''); // 发送后清空提示词
        } catch (error) {
            console.error('[ImageExpandView] handleGenerate 处理附件失败:', error);
            showError('处理附件失败，请重试');
        }
    }, [prompt, loadingState, activeAttachments, activeImageUrl, messages, currentSessionId, controls, onSend, expandMode, showError]);

    // ✅ 键盘快捷键
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleGenerate();
        }
    }, [handleGenerate]);

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

    // ✅ 主区域：两栏布局（画布 + 参数面板）
    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            {/* ========== 左侧：画布区域 ========== */}
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

            {/* ========== 右侧：参数面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-orange-400" />
                        <span className="text-xs font-bold text-white">扩图参数</span>
                    </div>
                    <button
                        onClick={resetParams}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                        title="重置为默认值"
                    >
                        <RotateCcw size={12} />
                    </button>
                </div>

                {/* 参数滚动区 - 通过 ModeControlsCoordinator 分发对应的参数组件 */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
                    <ModeControlsCoordinator
                        mode={expandMode}
                        providerId={providerId || 'google'}
                        controls={controls}
                    />
                </div>

                {/* 底部固定区：附件预览 + 提示词 + 扩图按钮 */}
                <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
                    {/* 附件预览区 */}
                    {activeAttachments.length > 0 && (
                        <div className="flex gap-2 flex-wrap">
                            {activeAttachments.map((att, idx) => (
                                <div key={idx} className="relative group">
                                    <img 
                                        src={att.url || att.tempUrl || ''} 
                                        className="w-12 h-12 rounded-lg object-cover border border-slate-700" 
                                        alt="待扩图图片"
                                    />
                                    <button
                                        onClick={() => {
                                            const newAtts = activeAttachments.filter((_, i) => i !== idx);
                                            setActiveAttachments(newAtts);
                                            if (newAtts.length === 0) setActiveImageUrl(null);
                                        }}
                                        className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <X size={12} className="text-white" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* 提示词输入 */}
                    <textarea
                        ref={textareaRef}
                        value={prompt}
                        onChange={(e) => {
                            setPrompt(e.target.value);
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder={(activeAttachments.length === 0 && !activeImageUrl) ? "请先上传图片..." : "描述扩展内容..."}
                        className="w-full min-h-[40px] max-h-[150px] bg-slate-800/80 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
                    />

                    {/* 上传按钮 + 扩图按钮 */}
                    <div className="flex gap-2 items-center">
                        {/* 上传按钮 */}
                        <label className="p-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 cursor-pointer transition-colors border border-indigo-500/50 flex-shrink-0 shadow-lg">
                            <input
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    if (file) {
                                        const url = URL.createObjectURL(file);
                                        const newAtt: Attachment = {
                                            id: `att-${Date.now()}`,
                                            name: file.name,
                                            mimeType: file.type,
                                            url: url,
                                            tempUrl: url,
                                            file: file,
                                        };
                                        setActiveAttachments([newAtt]);
                                        setActiveImageUrl(url);
                                    }
                                    e.target.value = '';
                                }}
                            />
                            {activeAttachments.length === 0 ? (
                                <ImageIcon size={18} className="text-white" />
                            ) : (
                                <Paperclip size={18} className="text-white" />
                            )}
                        </label>

                        {/* 扩图按钮 */}
                        <button
                            onClick={handleGenerate}
                            disabled={!prompt.trim() || loadingState !== 'idle' || (activeAttachments.length === 0 && !activeImageUrl)}
                            className="flex-1 py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loadingState !== 'idle' ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    扩图中...
                                </>
                            ) : (
                                <>
                                    <Expand size={18} />
                                    {(activeAttachments.length === 0 && !activeImageUrl) ? '请先上传图片' : '开始扩图'}
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    ), [loadingState, isCompareMode, activeAttachments, activeImageUrl, originalImageUrl, canvas, handleFullscreen, toggleCompare, controls, providerId, prompt, handleKeyDown, handleGenerate, resetParams, expandMode]);

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

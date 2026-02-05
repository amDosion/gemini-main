
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Expand, AlertCircle, Layers, SlidersHorizontal, RotateCcw, Clock, ChevronLeft, ChevronRight, Grid, Image as ImageIcon } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';


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

export const ImageExpandView: React.FC<ImageExpandViewProps> = ({
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

    // ✅ 新增：选中的消息批次 ID 和旋转木马索引
    const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);
    const [carouselIndex, setCarouselIndex] = useState(0);

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

    // ✅ 新增：按消息分组的历史批次（只包含有附件的模型响应）
    const historyBatches = useMemo(() => {
        return messages
            .filter(m => m.role === Role.MODEL && ((m.attachments && m.attachments.length > 0) || m.isError))
            .reverse();
    }, [messages]);

    // ✅ 新增：当前激活的批次消息
    const activeBatchMessage = useMemo(() => {
        if (selectedMsgId) {
            return historyBatches.find(m => m.id === selectedMsgId);
        }
        return historyBatches[0];
    }, [selectedMsgId, historyBatches]);

    // ✅ 新增：当前批次的所有图片
    const displayImages = useMemo(() => {
        return (activeBatchMessage?.attachments || []).filter(att => att.url && att.url.length > 0);
    }, [activeBatchMessage?.attachments]);

    // ✅ 新增：批次切换时重置旋转木马索引
    useEffect(() => {
        setCarouselIndex(0);
    }, [activeBatchMessage?.id]);

    // ✅ 新增：确保 carouselIndex 不越界
    useEffect(() => {
        if (carouselIndex >= displayImages.length && displayImages.length > 0) {
            setCarouselIndex(displayImages.length - 1);
        }
    }, [displayImages.length, carouselIndex]);

    // ✅ 新增：键盘左右键切换图片
    useEffect(() => {
        if (displayImages.length <= 1) return;
        
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
                return;
            }
            
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                setCarouselIndex((prev) => (prev - 1 + displayImages.length) % displayImages.length);
                canvas.resetView();
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                setCarouselIndex((prev) => (prev + 1) % displayImages.length);
                canvas.resetView();
            }
        };
        
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [displayImages.length]);

    // ✅ 新增：当新生成开始时，清除选中状态
    useEffect(() => {
        if (loadingState === 'loading') {
            setSelectedMsgId(null);
        }
    }, [loadingState]);

    // ✅ 参数面板状态
    const expandMode: AppMode = 'image-outpainting';
    const controls = useControlsState(expandMode, activeModelConfig);

    // 重置参数
    const resetParams = useCallback(() => {
        controls.setAspectRatio('1:1');
        controls.setResolution('1K');
        controls.setNegativePrompt('');
        controls.setSeed(-1);
    }, [controls]);

    // Pan & Zoom Hook
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

    // ✅ 切换对比模式
    const toggleCompare = useCallback(() => setIsCompareMode(prev => !prev), []);

    // 重置视图当图片改变时
    useEffect(() => {
        canvas.resetView();
        setIsCompareMode(false);
    }, [activeImageUrl, carouselIndex]);

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

    // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
    const handleSend = useCallback((text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        onSend(text, options, attachments, expandMode);
    }, [onSend, expandMode]);

    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    // 使用 useMemo 缓存 sidebarContent，防止不必要的重新渲染
    // ✅ 改为按批次分组显示历史记录
    const sidebarContent = useMemo(() => (
        <div className="p-3 space-y-3">
            {historyBatches.map((msg) => {
                const firstImage = msg.attachments?.[0]?.url;
                const count = msg.attachments?.length || 0;
                const isSelected = activeBatchMessage?.id === msg.id;

                return (
                    <div
                        key={msg.id}
                        className={`group relative rounded-xl overflow-hidden border cursor-pointer transition-all flex flex-col gap-2 bg-slate-800/40 p-2 ${
                            isSelected ? 'ring-1 ring-orange-500 border-transparent bg-slate-800' : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-800'
                        }`}
                        onClick={() => {
                            setSelectedMsgId(msg.id);
                            if (window.innerWidth < 768) setIsMobileHistoryOpen(false);
                        }}
                    >
                        <div className="aspect-square w-full rounded-lg overflow-hidden bg-slate-900 relative">
                            {msg.isError ? (
                                <div className="w-full h-full flex items-center justify-center text-red-400 bg-red-900/10">
                                    <AlertCircle size={24} />
                                </div>
                            ) : firstImage ? (
                                <>
                                    <img src={firstImage} className="w-full h-full object-cover transition-transform group-hover:scale-105" loading="lazy" alt="Expanded image" />
                                    {count > 1 && (
                                        <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                                            <Layers size={10} /> {count}
                                        </div>
                                    )}
                                </>
                            ) : (
                                <div className="w-full h-full flex items-center justify-center text-slate-600">
                                    <ImageIcon size={24} className="opacity-50" />
                                </div>
                            )}
                        </div>
                        <div className="px-1">
                            <p className="text-[11px] text-slate-300 leading-relaxed font-medium whitespace-pre-wrap break-words line-clamp-2">
                                {msg.content || "扩图结果"}
                            </p>
                            <p className="text-[10px] text-slate-600 mt-1">
                                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </p>
                        </div>
                    </div>
                );
            })}

            {historyBatches.length === 0 && (
                <div className="text-center py-10 text-slate-600 text-xs italic">
                    暂无扩图历史
                </div>
            )}
        </div>
    ), [historyBatches, activeBatchMessage?.id]);

    // ✅ 新增：侧边栏头部额外内容（显示批次数量）
    const sidebarExtraHeader = useMemo(() => (
        <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">
            {historyBatches.length}
        </span>
    ), [historyBatches.length]);

    // ✅ 新增：当前显示的图片 URL（来自旋转木马）
    const currentDisplayUrl = useMemo(() => {
        if (displayImages.length > 0) {
            return displayImages[carouselIndex]?.url || null;
        }
        return activeImageUrl;
    }, [displayImages, carouselIndex, activeImageUrl]);

    // ✅ 新增：判断当前批次是否有错误
    const isBatchError = activeBatchMessage?.isError;

    // ✅ 主区域：两栏布局（画布 + 参数面板）
    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            {/* ========== 左侧：画布区域（带旋转木马） ========== */}
            <div 
                className="flex-1 w-full h-full select-none flex flex-col relative"
                onWheel={isCompareMode ? undefined : canvas.handleWheel}
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

                {/* 主图片显示区域 */}
                {loadingState !== 'idle' ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl">
                            <div className="relative">
                                <div className="w-20 h-20 border-4 border-orange-500/30 border-t-orange-500 rounded-full animate-spin"></div>
                                <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-orange-400 font-bold">EXP</div>
                            </div>
                            <div className="text-center space-y-2">
                                <p className="text-slate-200 font-medium text-lg">扩图中...</p>
                                <p className="text-slate-500 text-sm">这可能需要几秒钟</p>
                            </div>
                        </div>
                    </div>
                ) : isBatchError ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30">
                            <AlertCircle size={48} className="text-red-500 opacity-80" />
                            <div>
                                <h3 className="text-lg font-bold text-slate-200">扩图失败</h3>
                                <p className="text-sm text-red-400 mt-2 max-w-md">{activeBatchMessage?.content || "未知错误"}</p>
                            </div>
                        </div>
                    </div>
                ) : displayImages.length > 0 ? (
                    <>
                        {/* 旋转木马视图 */}
                        <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
                            {/* 主图展示区 - 支持拖拽 */}
                            <div 
                                className="flex-1 w-full flex items-center justify-center relative px-16 overflow-hidden"
                                onMouseDown={isCompareMode ? undefined : canvas.handleMouseDown}
                                onMouseMove={isCompareMode ? undefined : canvas.handleMouseMove}
                                onMouseUp={isCompareMode ? undefined : canvas.handleMouseUp}
                                onMouseLeave={isCompareMode ? undefined : canvas.handleMouseUp}
                                style={{ cursor: isCompareMode ? 'default' : canvas.isDragging ? 'grabbing' : (canvas.zoom > 1 ? 'grab' : 'default') }}
                            >
                                {/* 左箭头 */}
                                {displayImages.length > 1 && (
                                    <button
                                        onClick={() => { setCarouselIndex((prev) => (prev - 1 + displayImages.length) % displayImages.length); canvas.resetView(); }}
                                        className="absolute left-4 z-10 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur border border-white/10 transition-all hover:scale-110"
                                        title="上一张"
                                    >
                                        <ChevronLeft size={24} />
                                    </button>
                                )}
                                
                                {/* 当前图片（支持对比模式） */}
                                <div className="relative group max-w-full max-h-full flex items-center justify-center">
                                    {isCompareMode && originalImageUrl && currentDisplayUrl ? (
                                        <div className="relative shadow-2xl transition-transform duration-75 ease-out" style={canvas.canvasStyle}>
                                            <ImageCompare
                                                beforeImage={originalImageUrl}
                                                afterImage={currentDisplayUrl}
                                                beforeLabel="原图"
                                                afterLabel="扩图结果"
                                                accentColor="orange"
                                                className="max-w-none rounded-lg border border-slate-800"
                                                style={{ maxHeight: '70vh', maxWidth: '80vw' }}
                                            />
                                        </div>
                                    ) : currentDisplayUrl ? (
                                        <img
                                            src={currentDisplayUrl}
                                            className="block max-h-[70vh] max-w-full object-contain rounded-2xl shadow-2xl border border-slate-800/50 select-none"
                                            style={canvas.canvasStyle}
                                            onDoubleClick={() => onImageClick(currentDisplayUrl)}
                                            alt={`扩图结果 ${carouselIndex + 1}`}
                                            draggable={false}
                                        />
                                    ) : (
                                        <div className="w-64 h-64 flex items-center justify-center text-slate-600 bg-slate-900 rounded-2xl">
                                            <ImageIcon size={48} className="opacity-50" />
                                        </div>
                                    )}
                                    {/* 悬浮操作按钮 */}
                                    {currentDisplayUrl && (
                                        <ImageCanvasControls
                                            variant="canvas"
                                            mode="image-outpainting"
                                            modeAware={false}
                                            className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                                            zoom={canvas.zoom}
                                            onZoomIn={canvas.handleZoomIn}
                                            onZoomOut={canvas.handleZoomOut}
                                            onReset={canvas.handleReset}
                                            onFullscreen={() => onImageClick(currentDisplayUrl)}
                                            downloadUrl={currentDisplayUrl}
                                            onToggleCompare={originalImageUrl ? toggleCompare : undefined}
                                            isCompareMode={isCompareMode}
                                            accentColor="orange"
                                        />
                                    )}
                                </div>
                                
                                {/* 右箭头 */}
                                {displayImages.length > 1 && (
                                    <button
                                        onClick={() => { setCarouselIndex((prev) => (prev + 1) % displayImages.length); canvas.resetView(); }}
                                        className="absolute right-4 z-10 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur border border-white/10 transition-all hover:scale-110"
                                        title="下一张"
                                    >
                                        <ChevronRight size={24} />
                                    </button>
                                )}
                                
                                {/* 缩放提示 */}
                                {canvas.zoom !== 1 && (
                                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-slate-400 text-xs bg-black/60 px-3 py-1.5 rounded-full backdrop-blur pointer-events-none">
                                        {Math.round(canvas.zoom * 100)}% · 拖拽移动 · 双击全屏
                                    </div>
                                )}
                            </div>
                            
                            {/* 底部缩略图导航 */}
                            {displayImages.length > 1 && (
                                <div className="flex items-center gap-3 py-4 px-4">
                                    {displayImages.map((att, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => { setCarouselIndex(idx); canvas.resetView(); }}
                                            className={`relative rounded-lg overflow-hidden transition-all duration-200 ${
                                                idx === carouselIndex 
                                                    ? 'ring-2 ring-orange-500 scale-110' 
                                                    : 'opacity-60 hover:opacity-100 hover:scale-105'
                                            }`}
                                        >
                                            {att.url ? (
                                                <img
                                                    src={att.url}
                                                    className="w-16 h-16 object-cover"
                                                    alt={`缩略图 ${idx + 1}`}
                                                />
                                            ) : (
                                                <div className="w-16 h-16 bg-slate-800 flex items-center justify-center">
                                                    <ImageIcon size={20} className="text-slate-600" />
                                                </div>
                                            )}
                                            {idx === carouselIndex && (
                                                <div className="absolute inset-0 bg-orange-500/20" />
                                            )}
                                        </button>
                                    ))}
                                    <span className="ml-2 text-sm text-slate-400 font-mono">
                                        {carouselIndex + 1} / {displayImages.length}
                                    </span>
                                </div>
                            )}
                        </div>
                    </>
                ) : activeImageUrl ? (
                    // 显示用户上传的原图（还没有生成结果时）
                    <div className="flex-1 flex items-center justify-center p-0 w-full h-full">
                        <div
                            className="relative shadow-2xl group transition-transform duration-75 ease-out"
                            style={canvas.canvasStyle}
                            onMouseDown={canvas.handleMouseDown}
                            onMouseMove={canvas.handleMouseMove}
                            onMouseUp={canvas.handleMouseUp}
                            onMouseLeave={canvas.handleMouseUp}
                        >
                            <img
                                src={activeImageUrl}
                                className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
                                style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                                alt="Source Preview"
                            />
                            <ImageCanvasControls
                                variant="canvas"
                                className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                                zoom={canvas.zoom}
                                onZoomIn={canvas.handleZoomIn}
                                onZoomOut={canvas.handleZoomOut}
                                onReset={canvas.handleReset}
                                onFullscreen={() => onImageClick(activeImageUrl)}
                                downloadUrl={activeImageUrl}
                                accentColor="orange"
                            />
                        </div>
                    </div>
                ) : (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                            <Expand size={48} className="opacity-20" />
                            <div>
                                <h3 className="text-xl font-bold text-slate-500 mb-2">Out-Paint Workspace</h3>
                                <p className="text-sm opacity-60">在右侧上传图片，设置参数后点击扩图</p>
                            </div>
                        </div>
                    </div>
                )}

                {/* 批次信息提示 */}
                {displayImages.length > 1 && (
                    <div className="absolute top-4 left-4 z-10 animate-[fadeIn_0.3s_ease-out] pointer-events-none">
                        <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-xl">
                            <Grid size={14} className="text-orange-400" />
                            批次结果 ({displayImages.length})
                        </div>
                    </div>
                )}
            </div>

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

                {/* 底部固定区：使用 ChatEditInputArea 组件 */}
                <ChatEditInputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    mode={expandMode}
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={setActiveAttachments}
                    activeImageUrl={activeImageUrl}
                    onActiveImageUrlChange={setActiveImageUrl}
                    messages={messages}
                    sessionId={currentSessionId}
                    initialAttachments={initialAttachments}
                    providerId={providerId}
                    controls={controls}
                />
            </div>
        </div>
    ), [loadingState, isBatchError, displayImages, activeBatchMessage, currentDisplayUrl, activeImageUrl, originalImageUrl, isCompareMode, canvas, carouselIndex, onImageClick, toggleCompare, controls, providerId, resetParams, expandMode, onStop, messages, currentSessionId, initialAttachments, handleSend, activeAttachments]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Clock size={14} />}
            sidebarExtraHeader={sidebarExtraHeader}
            sidebar={sidebarContent}
            main={mainContent}
        />
    );
};

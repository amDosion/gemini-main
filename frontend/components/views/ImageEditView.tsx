import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Crop, Wand2, Layers, Bot, Sparkles, Palette, PenTool, MessageSquare, SlidersHorizontal, RotateCcw } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCarouselArrows, ImageCarouselThumbnails, type CarouselMediaItem } from '../common/ImageCarouselControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';
import { extractImageHistoryPrompts, useImageHistorySidebar } from '../common/ImageHistorySidebar';
import { useThinkingBlock } from '../../hooks/useThinkingBlock';

interface ImageEditViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    onImageClick: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];  // 当前模式下可见的模型列表
    allVisibleModels?: ModelConfig[];  // ✅ 新增：完整模型列表
    initialPrompt?: string;
    initialAttachments?: Attachment[];
    onExpandImage?: (url: string) => void; // Added prop
    providerId?: string;
    sessionId?: string | null;  // ✅ 会话 ID，用于查询附件
    onDeleteMessage?: (messageId: string) => void;
}

// 优化：使用 React.memo 配合自定义比较函数，防止不必要的重新渲染
// Optimization: Use React.memo with a custom comparison function to prevent unnecessary re-renders
const arePropsEqual = (prevProps: ImageEditViewProps, nextProps: ImageEditViewProps) => {
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
    // ✅ 旋转木马支持（多图预览）
    carouselIndex: number;
    onCarouselPrev: () => void;
    onCarouselNext: () => void;
    onCarouselSelect: (index: number) => void;
    getStableUrl: (att: Attachment) => string | null;
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
    // ✅ 旋转木马支持
    carouselIndex,
    onCarouselPrev,
    onCarouselNext,
    onCarouselSelect,
    getStableUrl,
}: ImageEditMainCanvasProps) => {
    const cursor =
        isCompareMode ? 'default' : isDragging ? 'grabbing' : activeImageUrl ? 'grab' : 'default';

    // ✅ 判断是否为多图模式（用户上传了多个附件）
    const isMultiImageMode = activeAttachments.length > 1;
    // 当前显示的图片 URL（优先使用 att.url，与 AttachmentPreview 一致）
    const currentDisplayUrl = isMultiImageMode && activeAttachments[carouselIndex]
        ? (activeAttachments[carouselIndex].url || activeAttachments[carouselIndex].tempUrl || getStableUrl(activeAttachments[carouselIndex]))
        : activeImageUrl;
    const carouselItems = useMemo<CarouselMediaItem[]>(
        () => activeAttachments.map((att, idx) => {
            const thumbUrl = att.url || att.tempUrl || getStableUrl(att);
            return {
                id: att.id || `${idx}`,
                url: thumbUrl,
                thumbUrl,
                alt: `缩略图 ${idx + 1}`
            };
        }),
        [activeAttachments, getStableUrl]
    );

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
                    <Wand2 size={12} className="text-pink-400" />
                    {isCompareMode
                        ? '对比模式'
                        : isMultiImageMode
                            ? `多图编辑 (${carouselIndex + 1}/${activeAttachments.length})`
                            : activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url
                                ? 'Source Preview'
                                : 'Workspace'}
                    <span className="opacity-50">|</span>
                    <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
                </div>
            </div>

            {/* Main Image Display with Transformations */}
            <div className="flex-1 flex items-center justify-center p-0 w-full relative overflow-hidden">
                {loadingState !== 'idle' ? (() => {
                    // 根据 loadingState 显示不同的过程信息
                    let statusText = 'Processing Image...';

                    if (loadingState === 'uploading') {
                        statusText = '上传图片中...';
                    } else if (loadingState === 'loading') {
                        statusText = 'AI 正在处理图片...';
                    } else if (loadingState === 'streaming') {
                        statusText = '流式处理中...';
                    }

                    return (
                        <div className="flex flex-col items-center gap-4 pointer-events-none">
                            <div className="relative">
                                <div className="w-20 h-20 border-4 border-pink-500/30 border-t-pink-500 rounded-full animate-spin"></div>
                            </div>
                            <p className="text-slate-400 animate-pulse">{statusText}</p>
                        </div>
                    );
                })() : isCompareMode && originalImageUrl && activeImageUrl ? (
                    // 对比模式
                    <div className="relative shadow-2xl transition-transform duration-75 ease-out" style={canvasStyle}>
                        <ImageCompare
                            beforeImage={originalImageUrl}
                            afterImage={activeImageUrl}
                            beforeLabel="原图"
                            afterLabel="编辑结果"
                            accentColor="pink"
                            className="max-w-none rounded-lg border border-slate-800"
                            style={{ maxHeight: '80vh', maxWidth: '80vw' }}
                        />
                    </div>
                ) : currentDisplayUrl ? (
                    // ✅ 普通模式 / 多图旋转木马模式
                    <>
                        <ImageCarouselArrows
                            itemCount={activeAttachments.length}
                            onPrev={onCarouselPrev}
                            onNext={onCarouselNext}
                        />

                        {/* 主图展示 */}
                        <div
                            className="relative shadow-2xl group transition-transform duration-75 ease-out"
                            style={canvasStyle}
                        >
                            <img
                                src={currentDisplayUrl}
                                className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
                                style={{ maxHeight: '70vh', maxWidth: '70vw' }}
                                alt="Main Canvas"
                            />
                        </div>

                    </>
                ) : (
                    <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                        <Crop size={48} className="opacity-20" />
                        <div>
                            <h3 className="text-xl font-bold text-slate-500 mb-2">Editor Workspace</h3>
                            <p className="text-sm opacity-60 mb-4">
                                Attach an image below to start. Gemini allows advanced conversational editing:
                            </p>
                            <div className="grid grid-cols-2 gap-2 text-left text-xs opacity-50">
                                <div className="flex items-center gap-2">
                                    <Palette size={12} /> Style Transfer
                                </div>
                                <div className="flex items-center gap-2">
                                    <Sparkles size={12} /> Inpainting/Replacing
                                </div>
                                <div className="flex items-center gap-2">
                                    <PenTool size={12} /> Sketch to Image
                                </div>
                                <div className="flex items-center gap-2">
                                    <Layers size={12} /> Composition
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* ✅ 底部缩略图导航（多图时显示）- 移到图片区域内部 */}
                {isMultiImageMode && loadingState === 'idle' && (
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20">
                        <ImageCarouselThumbnails
                            items={carouselItems}
                            currentIndex={carouselIndex}
                            onSelect={onCarouselSelect}
                            accentTone="pink"
                            thumbnailSize={56}
                            panelClassName="flex items-center gap-3 py-3 px-4 bg-black/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-xl"
                            counterClassName="ml-2 text-xs text-slate-400 font-mono"
                        />
                    </div>
                )}
            </div>

            {/* 浮动控制按钮 */}
            {currentDisplayUrl && (
                <div className="absolute bottom-6 right-6 z-20">
                    <ImageCanvasControls
                        zoom={zoom}
                        onZoomIn={onZoomIn}
                        onZoomOut={onZoomOut}
                        onReset={onReset}
                        onFullscreen={onFullscreen}
                        downloadUrl={currentDisplayUrl}
                        onExpand={onExpand}
                        onToggleCompare={onToggleCompare}
                        isCompareMode={isCompareMode}
                        accentColor="pink"
                    />
                </div>
            )}
        </div>
    );
});

ImageEditMainCanvas.displayName = 'ImageEditMainCanvas';

export const ImageEditView = memo(({
    messages,
    setAppMode,
    onImageClick,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    visibleModels = [],
    allVisibleModels = [],  // ✅ 新增
    initialPrompt,
    initialAttachments,
    onExpandImage,
    providerId,
    sessionId: currentSessionId,  // ✅ 接收 sessionId
    onDeleteMessage
}: ImageEditViewProps) => {
    const { showError } = useToastContext();

    // State for reference image
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
    // ✅ 新增：存储当前画布图片对应的完整附件对象（包含元数据）
    const [activeCanvasAttachment, setActiveCanvasAttachment] = useState<Attachment | null>(null);
    const [selectedHistoryMsgId, setSelectedHistoryMsgId] = useState<string | null>(null);
    const [carouselInitialIndex, setCarouselInitialIndex] = useState(0);

    // ✅ 包装 setActiveAttachments 以添加调试日志
    const handleAttachmentsChange = useCallback((newAtts: Attachment[]) => {
        setActiveAttachments(newAtts);
    }, []);
    
    // 固定使用 image-chat-edit 模式（此视图专门用于对话式编辑）
    const editMode: AppMode = 'image-chat-edit';

    // State for thinking block
    const {
        isOpen: isThinkingOpen,
        setIsOpen: setIsThinkingOpen,
        displayedContent: displayedThinkingContent,
    } = useThinkingBlock(messages, loadingState);

    // ✅ 多图 URL 缓存（支持多图预览）
    // 使用 Map 缓存每个文件的 Blob URL，避免重复创建和提前 revoke
    const canvasObjectUrlMapRef = useRef<Map<File, string>>(new Map());

    const getStableCanvasUrlFromAttachment = useCallback((att: Attachment) => {
        // ✅ 调试日志

        if (att.file) {
            const file = att.file;
            const cachedUrl = canvasObjectUrlMapRef.current.get(file);
            if (cachedUrl) {
                return cachedUrl;
            }
            // 为新文件创建 Blob URL 并缓存
            const newUrl = URL.createObjectURL(file);
            canvasObjectUrlMapRef.current.set(file, newUrl);
            return newUrl;
        }
        const result = att.url || att.tempUrl || null;
        return result;
    }, []);

    // ✅ 清理不再使用的 Blob URLs（当附件变化时）
    useEffect(() => {
        const currentFiles = new Set(activeAttachments.map(att => att.file).filter(Boolean));
        const urlMap = canvasObjectUrlMapRef.current;

        // 清理不在当前附件列表中的文件 URL
        for (const [file, url] of urlMap.entries()) {
            if (!currentFiles.has(file)) {
                URL.revokeObjectURL(url);
                urlMap.delete(file);
            }
        }
    }, [activeAttachments]);

    // 组件卸载时清理所有 Blob URLs
    useEffect(() => {
        return () => {
            for (const url of canvasObjectUrlMapRef.current.values()) {
                URL.revokeObjectURL(url);
            }
            canvasObjectUrlMapRef.current.clear();
        };
    }, []);

    // Track last processed message to auto-update view
    const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);

    // 对比模式状态
    const [isCompareMode, setIsCompareMode] = useState(false);

    // ✅ 参数面板状态（使用统一的 controls 状态）
    const controls = useControlsState(editMode, activeModelConfig);
    // 注意：prompt 和 textareaRef 现在由 ChatEditInputArea 管理

    // 重置参数
    const resetParams = useCallback(() => {
        controls.setAspectRatio('1:1');
        controls.setResolution('1K');
        controls.setNegativePrompt('');
        controls.setSeed(-1);
        controls.setOutputMimeType('image/png');
        controls.setOutputCompressionQuality(100);
    }, [controls]);

    // Pan & Zoom Hook（替代原有的手动状态管理）
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

    const selectedCanvasMessage = useMemo(() => {
        if (activeAttachments.length > 0) return null;
        if (selectedHistoryMsgId) {
            return messages.find((msg) => msg.id === selectedHistoryMsgId) || null;
        }
        return [...messages].reverse().find((msg) =>
            (msg.attachments || []).some((att) => {
                const stableUrl = getStableCanvasUrlFromAttachment(att);
                return Boolean(att.url || att.tempUrl || stableUrl);
            })
        ) || null;
    }, [activeAttachments.length, getStableCanvasUrlFromAttachment, messages, selectedHistoryMsgId]);

    const canvasDisplayAttachments = useMemo(() => {
        if (activeAttachments.length > 0) {
            return activeAttachments;
        }
        return (selectedCanvasMessage?.attachments || []).filter((att) => {
            const stableUrl = getStableCanvasUrlFromAttachment(att);
            return Boolean(att.url || att.tempUrl || stableUrl);
        });
    }, [activeAttachments, getStableCanvasUrlFromAttachment, selectedCanvasMessage?.attachments]);

    const canvasCarouselResetKey = useMemo(() => {
        if (activeAttachments.length > 0) {
            return activeAttachments.map((att) => att.id || att.url || att.tempUrl || att.name).join('|');
        }
        return selectedCanvasMessage?.id || null;
    }, [activeAttachments, selectedCanvasMessage?.id]);

    const {
        index: carouselIndex,
        goPrev: handleCarouselPrev,
        goNext: handleCarouselNext,
        select: handleCarouselSelect
    } = useImageCarousel({
        itemCount: canvasDisplayAttachments.length,
        initialIndex: carouselInitialIndex,
        resetKey: canvasCarouselResetKey,
        keyboardEnabled: true,
        onNavigate: canvas.resetView
    });

    useEffect(() => {
        const currentAttachment = canvasDisplayAttachments[carouselIndex];
        if (!currentAttachment) return;

        const currentUrl = currentAttachment.url || currentAttachment.tempUrl || getStableCanvasUrlFromAttachment(currentAttachment);
        if (!currentUrl) return;

        if (currentUrl !== activeImageUrl) {
            setActiveImageUrl(currentUrl);
        }
        if (activeCanvasAttachment?.id !== currentAttachment.id) {
            setActiveCanvasAttachment(currentAttachment);
        }
    }, [
        activeCanvasAttachment?.id,
        activeImageUrl,
        canvasDisplayAttachments,
        carouselIndex,
        getStableCanvasUrlFromAttachment
    ]);

    // Reset View when image changes
    useEffect(() => {
        canvas.resetView();
        setIsCompareMode(false);
    }, [activeImageUrl]);

    // 注意：Blob URL 清理现在由 canvasObjectUrlMapRef 的 useEffect 统一管理

    // 获取当前 AI 结果对应的用户上传原图（用于对比）
    const compareSourceImageUrl = useMemo(() => {
        if (!selectedCanvasMessage || selectedCanvasMessage.role !== Role.MODEL || canvasDisplayAttachments.length === 0) {
            return null;
        }

        const selectedMessageIndex = messages.findIndex((msg) => msg.id === selectedCanvasMessage.id);
        if (selectedMessageIndex <= 0) {
            return null;
        }

        for (let i = selectedMessageIndex - 1; i >= 0; i -= 1) {
            const candidate = messages[i];
            if (candidate.role !== Role.USER || !candidate.attachments?.length) {
                continue;
            }

            for (const attachment of candidate.attachments) {
                const sourceUrl = getStableCanvasUrlFromAttachment(attachment);
                if (sourceUrl) {
                    return sourceUrl;
                }
            }
        }

        return null;
    }, [canvasDisplayAttachments.length, getStableCanvasUrlFromAttachment, messages, selectedCanvasMessage]);

    // Sync initial attachments
    useEffect(() => {
        if (initialAttachments && initialAttachments.length > 0) {
            setActiveAttachments(initialAttachments);
            setCarouselInitialIndex(0);
            setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
            // ✅ 同时保存完整的附件对象（包含元数据）
            setActiveCanvasAttachment(initialAttachments[0]);
        } else if (initialAttachments === undefined && activeAttachments.length === 0) {
            // 如果 initialAttachments 被清空（undefined），且当前没有附件，保持空状态
            // 但如果已经有附件（例如从消息中恢复），不要清空
        }
    }, [initialAttachments, getStableCanvasUrlFromAttachment]);

    // Sync uploaded attachment to main view
    // ✅ 与原始代码一致：只在有附件时设置画布图片，不清空画布
    // 原因：发送后附件预览会被清空，但画布应继续显示用户上传的图片，直到 AI 返回结果
    useEffect(() => {
        if (activeAttachments.length > 0) {
            const stableUrl = getStableCanvasUrlFromAttachment(activeAttachments[0]);
            setCarouselInitialIndex(0);
            setActiveImageUrl(stableUrl);
            // ✅ 同时保存完整的附件对象（包含元数据）
            setActiveCanvasAttachment(activeAttachments[0]);
        }
    }, [activeAttachments, getStableCanvasUrlFromAttachment]);

    // Auto-select latest result logic
    useEffect(() => {
        // 1. Initial Load: If no active image, pick latest from history
        // 优先从用户消息中获取（原始图片），如果没有则从模型消息中获取（编辑后的图片）
        if (activeAttachments.length === 0 && !activeImageUrl) {
            // 优先查找用户消息中的图片（对话式编辑的原始图片）
            const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
            if (lastUserMsg && lastUserMsg.attachments?.[0]?.url) {
                setCarouselInitialIndex(0);
                setActiveImageUrl(lastUserMsg.attachments[0].url);
                // ✅ 同时保存完整的附件对象（包含元数据）
                setActiveCanvasAttachment(lastUserMsg.attachments[0]);
            } else {
                // 如果没有用户消息，从模型消息中获取（编辑后的图片）
                const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
                if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
                    setCarouselInitialIndex(0);
                    setActiveImageUrl(lastModelMsg.attachments[0].url);
                    // ✅ 同时保存完整的附件对象（包含元数据）
                    setActiveCanvasAttachment(lastModelMsg.attachments[0]);
                }
            }
        }

        // 2. New Generation Complete: Auto-switch to result
        if (loadingState === 'idle' && messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            // Check if this is a new message we haven't handled yet
            if (lastMsg.id !== lastProcessedMsgId) {
                // If it's a model response with an image
                if (lastMsg.role === Role.MODEL && lastMsg.attachments && lastMsg.attachments.length > 0 && lastMsg.attachments[0].url) {
                    setCarouselInitialIndex(0);
                    setActiveImageUrl(lastMsg.attachments[0].url);
                    // ✅ 同时保存完整的附件对象（包含元数据）
                    setActiveCanvasAttachment(lastMsg.attachments[0]);
                    setLastProcessedMsgId(lastMsg.id);
                } else if (lastMsg.isError) {
                    // Just mark processed so we don't check again
                    setLastProcessedMsgId(lastMsg.id);
                }
            }
        }
    }, [messages, activeAttachments.length, loadingState, lastProcessedMsgId, activeImageUrl]);

    // 注意：handleGenerate 和 handleKeyDown 现在由 ChatEditInputArea 管理

    // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
    const handleSend = useCallback((text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        // ChatEditInputArea 已经处理了所有逻辑，直接转发即可
        onSend(text, options, attachments, editMode);
    }, [onSend, editMode]);

    // Canvas 事件处理器现在由 useImageCanvas Hook 提供

    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    const getHistoryAttachmentUrl = useCallback((attachment: Attachment) => {
        const stableUrl = getStableCanvasUrlFromAttachment(attachment);
        if (attachment.url && attachment.url.length > 0) return attachment.url;
        if (attachment.tempUrl && attachment.tempUrl.length > 0) return attachment.tempUrl;
        return stableUrl;
    }, [getStableCanvasUrlFromAttachment]);

    const getMessageDisplayAttachments = useCallback((attachments?: Attachment[]) => {
        return (attachments || []).filter((attachment) => Boolean(getHistoryAttachmentUrl(attachment)));
    }, [getHistoryAttachmentUrl]);

    const historyMessages = useMemo(() => {
        return messages.filter((msg) => {
            const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
            return !isPlaceholder;
        });
    }, [messages]);

    const loadingHistoryContent = useMemo(() => {
        if (loadingState === 'idle') return null;

        let statusText = 'Processing request...';
        let statusIcon = <Bot size={16} className="text-slate-500" />;

        if (loadingState === 'uploading') {
            statusText = '上传图片中...';
            statusIcon = <Layers size={16} className="text-blue-400" />;
        } else if (loadingState === 'loading') {
            statusText = '对话式编辑中，AI 正在理解您的需求并生成图片...';
            statusIcon = <MessageSquare size={16} className="text-pink-400" />;
        } else if (loadingState === 'streaming') {
            statusText = '流式处理中...';
            statusIcon = <Sparkles size={16} className="text-pink-400 animate-pulse" />;
        }

        const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
        const thoughts = lastMessage?.thoughts || [];
        const textResponse = lastMessage?.textResponse;
        const hasTextContent = lastMessage?.content && lastMessage.content.trim().length > 0;
        const isThinkingComplete = loadingState === 'idle';

        return (
            <div className="rounded-xl border border-slate-700/50 bg-slate-900/60 p-3">
                <div className="flex items-start gap-2">
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
                        {statusIcon}
                    </div>
                    <div className="rounded-xl text-xs text-slate-400 flex-1">
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
            </div>
        );
    }, [displayedThinkingContent, isThinkingOpen, loadingState, messages]);

    const { sidebarExtraHeader, sidebarContent } = useImageHistorySidebar({
        items: historyMessages,
        sessionId: currentSessionId,
        onDeleteMessage,
        activeImageUrl,
        selectedMessageId: selectedHistoryMsgId,
        onSelectedMessageIdChange: setSelectedHistoryMsgId,
        onMobileHistoryOpenChange: setIsMobileHistoryOpen,
        modelLabel: activeModelConfig?.name || 'AI',
        accent: 'pink',
        emptyText: 'No edit history yet.',
        getDisplayAttachments: getMessageDisplayAttachments,
        getAttachmentUrl: getHistoryAttachmentUrl,
        extractPrompts: extractImageHistoryPrompts,
        loadingContent: loadingHistoryContent,
        onSelectItem: ({ message, firstImage }) => {
            setSelectedHistoryMsgId(message.id);
            setCarouselInitialIndex(0);
            handleCarouselSelect(0);
            if (firstImage) {
                setActiveImageUrl(firstImage);
            }
        },
        onSelectPreviewAttachment: ({ message, attachment, index }) => {
            setSelectedHistoryMsgId(message.id);
            setCarouselInitialIndex(index);
            handleCarouselSelect(index);
            setActiveImageUrl(attachment.url);
        },
    });

    const toggleCompare = useCallback(() => setIsCompareMode(prev => !prev), []);
    const handleFullscreen = useCallback(() => {
        if (activeImageUrl) onImageClick(activeImageUrl);
    }, [activeImageUrl, onImageClick]);
    const handleExpand = useCallback(() => {
        if (activeImageUrl && onExpandImage) onExpandImage(activeImageUrl);
    }, [activeImageUrl, onExpandImage]);
    const canCompareWithSource = Boolean(
        compareSourceImageUrl &&
        activeImageUrl &&
        compareSourceImageUrl !== activeImageUrl &&
        selectedCanvasMessage?.role === Role.MODEL
    );

    // ✅ 主区域：两栏布局（画布 + 参数面板）
    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            {/* ========== 左侧：画布区域 ========== */}
            <ImageEditMainCanvas
                loadingState={loadingState}
                isCompareMode={isCompareMode}
                activeAttachments={canvasDisplayAttachments}
                activeImageUrl={activeImageUrl}
                originalImageUrl={compareSourceImageUrl}
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
                onToggleCompare={canCompareWithSource ? toggleCompare : undefined}
                // ✅ 旋转木马支持
                carouselIndex={carouselIndex}
                onCarouselPrev={handleCarouselPrev}
                onCarouselNext={handleCarouselNext}
                onCarouselSelect={handleCarouselSelect}
                getStableUrl={getStableCanvasUrlFromAttachment}
            />

            {/* ========== 右侧：参数面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                {/* 编辑参数头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-pink-400" />
                        <span className="text-xs font-bold text-white">编辑参数</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={resetParams}
                            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                            title="重置为默认值"
                        >
                            <RotateCcw size={12} />
                        </button>
                    </div>
                </div>

                {/* 参数滚动区 */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
                    {/* 编辑参数面板（始终显示） */}
                    <ModeControlsCoordinator
                        mode={editMode}
                        providerId={providerId || 'google'}
                        controls={controls}
                        availableModels={allVisibleModels}
                    />
                </div>

                {/* 底部固定区：使用 ChatEditInputArea 组件（始终显示） */}
                <ChatEditInputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    mode={editMode}
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={handleAttachmentsChange}
                    activeImageUrl={activeImageUrl}
                    onActiveImageUrlChange={setActiveImageUrl}
                    activeCanvasAttachment={activeCanvasAttachment}
                    messages={messages}
                    sessionId={currentSessionId}
                    initialPrompt={initialPrompt}
                    initialAttachments={initialAttachments}
                    providerId={providerId}
                    controls={controls}
                />
            </div>
        </div>
    ), [loadingState, isCompareMode, activeAttachments, canvasDisplayAttachments, activeImageUrl, activeCanvasAttachment, compareSourceImageUrl, canCompareWithSource, canvas, handleFullscreen, handleExpand, toggleCompare, onExpandImage, handleSend, editMode, onStop, messages, currentSessionId, initialPrompt, initialAttachments, providerId, resetParams, carouselIndex, handleCarouselPrev, handleCarouselNext, handleCarouselSelect, getStableCanvasUrlFromAttachment, controls]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={<Layers size={14} />}
            sidebarExtraHeader={sidebarExtraHeader}
            sidebar={sidebarContent}
            main={mainContent}
        />
    );
}, arePropsEqual);

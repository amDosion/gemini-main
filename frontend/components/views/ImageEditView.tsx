
import { safeCopyToClipboard } from '../../utils/safeOps';
import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { createPortal } from 'react-dom';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Crop, Wand2, AlertCircle, Layers, User, Bot, Sparkles, Palette, PenTool, MessageSquare, SlidersHorizontal, RotateCcw, Image as ImageIcon, Copy, Check, Star, FolderOpen, Trash2 } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCarouselArrows, ImageCarouselThumbnails, type CarouselMediaItem } from '../common/ImageCarouselControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { getUrlType } from '../../hooks/handlers/attachmentUtils';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';
import { useHistoryListActions } from '../../hooks/useHistoryListActions';

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

const extractEditHistoryPrompts = (msg: Message): { originalPrompt: string; enhancedPrompt: string } => {
    const rawContent = (msg.content || '').trim();
    let originalPrompt = rawContent;
    let enhancedPrompt = msg.enhancedPrompt?.trim() || '';

    const promptPairMatch = rawContent.match(/^📝\s*([\s\S]*?)(?:\n✨\s*([\s\S]*))?$/);
    if (promptPairMatch) {
        originalPrompt = (promptPairMatch[1] || '').trim();
        if (!enhancedPrompt && promptPairMatch[2]) {
            enhancedPrompt = promptPairMatch[2].trim();
        }
    }

    return {
        originalPrompt: originalPrompt || (msg.role === Role.USER ? '用户消息' : '模型响应'),
        enhancedPrompt
    };
};

interface EditHoverPreviewAttachment {
    id: string;
    url: string;
}

interface EditHoverPreview {
    messageId: string;
    role: Role;
    authorLabel: string;
    anchorX: number;
    anchorY: number;
    originalPrompt: string;
    enhancedPrompt: string;
    attachments: EditHoverPreviewAttachment[];
}

interface EditHoverPreviewSize {
    width: number;
    height: number;
}

interface EditHoverPreviewPosition {
    top: number;
    left: number;
    arrowOffsetY: number;
}

interface EditActionMenuAnchor {
    messageId: string;
    anchorX: number;
    anchorY: number;
}

interface EditActionMenuPosition {
    top: number;
    left: number;
}

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
    const scrollRef = useRef<HTMLDivElement>(null);
    const historyItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
    const actionMenuPanelRef = useRef<HTMLDivElement | null>(null);
    const [openActionMenu, setOpenActionMenu] = useState<EditActionMenuAnchor | null>(null);
    const [actionMenuPosition, setActionMenuPosition] = useState<EditActionMenuPosition | null>(null);

    // State for reference image
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
    // ✅ 新增：存储当前画布图片对应的完整附件对象（包含元数据）
    const [activeCanvasAttachment, setActiveCanvasAttachment] = useState<Attachment | null>(null);

    // ✅ 包装 setActiveAttachments 以添加调试日志
    const handleAttachmentsChange = useCallback((newAtts: Attachment[]) => {
        setActiveAttachments(newAtts);
    }, []);
    
    // 固定使用 image-chat-edit 模式（此视图专门用于对话式编辑）
    const editMode: AppMode = 'image-chat-edit';

    // State for thinking block
    const [isThinkingOpen, setIsThinkingOpen] = useState(true);
    const [displayedThinkingContent, setDisplayedThinkingContent] = useState('');

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
        controls.setOutputCompressionQuality(80);
    }, [controls]);

    // Pan & Zoom Hook（替代原有的手动状态管理）
    const canvas = useImageCanvas({ minZoom: 0.1, maxZoom: 5, zoomStep: 0.2 });

    const {
        index: carouselIndex,
        goPrev: handleCarouselPrev,
        goNext: handleCarouselNext,
        select: handleCarouselSelect
    } = useImageCarousel({
        itemCount: activeAttachments.length,
        keyboardEnabled: true,
        onNavigate: canvas.resetView
    });

    // Reset View when image changes
    useEffect(() => {
        canvas.resetView();
        setIsCompareMode(false);
    }, [activeImageUrl]);

    // 注意：Blob URL 清理现在由 canvasObjectUrlMapRef 的 useEffect 统一管理

    // 获取原图 URL（用于对比）
    const originalImageUrl = useMemo(() => {
        const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
        return lastUserMsg?.attachments?.[0]?.url || null;
    }, [messages]);

    // Sync initial attachments
    useEffect(() => {
        if (initialAttachments && initialAttachments.length > 0) {
            setActiveAttachments(initialAttachments);
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
            setActiveImageUrl(stableUrl);
            // ✅ 同时保存完整的附件对象（包含元数据）
            setActiveCanvasAttachment(activeAttachments[0]);
        }
    }, [activeAttachments, getStableCanvasUrlFromAttachment]);

    // Auto-scroll history
    useEffect(() => {
        const container = scrollRef.current;
        if (!container) return;

        // 使用 requestAnimationFrame 确保 DOM 更新后再滚动
        requestAnimationFrame(() => {
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        });
    }, [messages, activeAttachments]);

    // 流式输出思考过程（打字效果）
    useEffect(() => {
        const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
        if (!lastMessage) {
            setDisplayedThinkingContent('');
            return;
        }
        
        // 合并 thoughts 和 textResponse 的内容
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
        
        // 如果加载完成，立即显示完整内容
        if (loadingState === 'idle') {
            setDisplayedThinkingContent(fullContent);
            return;
        }
        
        // 流式输出：逐步显示思考内容（打字效果）
        const targetLength = fullContent.length;
        const currentLength = displayedThinkingContent.length;
        
        if (currentLength < targetLength) {
            // 使用 requestAnimationFrame 实现平滑的打字效果
            const chunkSize = 5; // 每次显示的字符数（可以调整速度）
            const nextLength = Math.min(currentLength + chunkSize, targetLength);
            
            const timer = setTimeout(() => {
                setDisplayedThinkingContent(fullContent.substring(0, nextLength));
            }, 30); // 30ms 延迟（可以调整速度）
            
            return () => clearTimeout(timer);
        } else if (fullContent !== displayedThinkingContent) {
            // 如果内容已更新但长度相同，直接更新
            setDisplayedThinkingContent(fullContent);
        }
    }, [messages, loadingState]);
    
    // Auto-select latest result logic
    useEffect(() => {
        // 1. Initial Load: If no active image, pick latest from history
        // 优先从用户消息中获取（原始图片），如果没有则从模型消息中获取（编辑后的图片）
        if (activeAttachments.length === 0 && !activeImageUrl) {
            // 优先查找用户消息中的图片（对话式编辑的原始图片）
            const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
            if (lastUserMsg && lastUserMsg.attachments?.[0]?.url) {
                const att = lastUserMsg.attachments[0];
                const urlType = getUrlType(att.url, att.uploadStatus);
                // 对于BASE64 URL，只输出类型和长度，不输出实际内容
                const formatUrlForLog = (url: string | undefined): string => {
                    if (!url) return 'N/A';
                    if (url.startsWith('data:')) {
                        return `Base64 Data URL (长度: ${url.length} 字符)`;
                    }
                    return url.length > 60 ? url.substring(0, 60) + '...' : url;
                };
                setActiveImageUrl(lastUserMsg.attachments[0].url);
                // ✅ 同时保存完整的附件对象（包含元数据）
                setActiveCanvasAttachment(lastUserMsg.attachments[0]);
            } else {
                // 如果没有用户消息，从模型消息中获取（编辑后的图片）
                const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
                if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
                    const att = lastModelMsg.attachments[0];
                    const urlType = getUrlType(att.url, att.uploadStatus);
                    // 对于BASE64 URL，只输出类型和长度，不输出实际内容
                    const formatUrlForLog = (url: string | undefined): string => {
                        if (!url) return 'N/A';
                        if (url.startsWith('data:')) {
                            return `Base64 Data URL (长度: ${url.length} 字符)`;
                        }
                        return url.length > 60 ? url.substring(0, 60) + '...' : url;
                    };
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
                    const att = lastMsg.attachments[0];
                    const urlType = getUrlType(att.url, att.uploadStatus);
                    
                    // 对于BASE64 URL，只输出类型和长度，不输出实际内容
                    const formatUrlForLog = (url: string | undefined): string => {
                        if (!url) return 'N/A';
                        if (url.startsWith('data:')) {
                            return `Base64 Data URL (长度: ${url.length} 字符)`;
                        }
                        return url.length > 80 ? url.substring(0, 80) + '...' : url;
                    };
                    

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
    const [selectedHistoryMsgId, setSelectedHistoryMsgId] = useState<string | null>(null);
    const [hoverPreview, setHoverPreview] = useState<EditHoverPreview | null>(null);
    const [hoverPreviewPosition, setHoverPreviewPosition] = useState<EditHoverPreviewPosition | null>(null);
    const [hoverPreviewSize, setHoverPreviewSize] = useState<EditHoverPreviewSize | null>(null);
    const [isResizingPreview, setIsResizingPreview] = useState(false);
    const [copiedPreviewMessageId, setCopiedPreviewMessageId] = useState<string | null>(null);
    const hidePreviewTimerRef = useRef<number | null>(null);
    const copiedResetTimerRef = useRef<number | null>(null);
    const hoverPreviewPanelRef = useRef<HTMLDivElement | null>(null);
    const previewResizeHandlersRef = useRef<{
        onMouseMove?: (event: MouseEvent) => void;
        onMouseUp?: () => void;
    }>({});

    const clearHidePreviewTimer = useCallback(() => {
        if (hidePreviewTimerRef.current !== null) {
            window.clearTimeout(hidePreviewTimerRef.current);
            hidePreviewTimerRef.current = null;
        }
    }, []);

    const clearCopiedResetTimer = useCallback(() => {
        if (copiedResetTimerRef.current !== null) {
            window.clearTimeout(copiedResetTimerRef.current);
            copiedResetTimerRef.current = null;
        }
    }, []);

    const stopPreviewResize = useCallback(() => {
        const handlers = previewResizeHandlersRef.current;
        if (handlers.onMouseMove) {
            window.removeEventListener('mousemove', handlers.onMouseMove);
        }
        if (handlers.onMouseUp) {
            window.removeEventListener('mouseup', handlers.onMouseUp);
        }
        previewResizeHandlersRef.current = {};
        setIsResizingPreview(false);
    }, []);

    const closeHoverPreview = useCallback(() => {
        clearHidePreviewTimer();
        stopPreviewResize();
        setOpenActionMenu(null);
        setActionMenuPosition(null);
        setHoverPreview(null);
        setHoverPreviewPosition(null);
        setHoverPreviewSize(null);
        setCopiedPreviewMessageId(null);
    }, [clearHidePreviewTimer, stopPreviewResize]);

    const scheduleHideHoverPreview = useCallback(() => {
        if (isResizingPreview) return;
        clearHidePreviewTimer();
        hidePreviewTimerRef.current = window.setTimeout(() => {
            setHoverPreview(null);
            setHoverPreviewPosition(null);
            setHoverPreviewSize(null);
            setCopiedPreviewMessageId(null);
            hidePreviewTimerRef.current = null;
        }, 180);
    }, [clearHidePreviewTimer, isResizingPreview]);

    const getMessageDisplayAttachments = useCallback((msg: Message): EditHoverPreviewAttachment[] => {
        return (msg.attachments || [])
            .map((att, idx) => {
                const stableUrl = getStableCanvasUrlFromAttachment(att);
                const displayUrl = (att.url && att.url.length > 0)
                    ? att.url
                    : (att.tempUrl && att.tempUrl.length > 0)
                        ? att.tempUrl
                        : (stableUrl || '');

                return {
                    id: att.id || `${msg.id}-${idx}`,
                    url: displayUrl
                };
            })
            .filter((item) => item.url.length > 0);
    }, [getStableCanvasUrlFromAttachment]);

    const historyMessages = useMemo(() => {
        return messages.filter((msg) => {
            const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
            return !isPlaceholder;
        });
    }, [messages]);

    const {
        showFavoritesOnly,
        setShowFavoritesOnly,
        filteredItems: filteredHistoryMessages,
        favoriteCount,
        isFavorite,
        isFavoritePending,
        toggleFavorite,
        deleteItem
    } = useHistoryListActions({
        sessionId: currentSessionId,
        items: historyMessages,
        onDeleteItem: onDeleteMessage
    });

    const computeHoverPreviewPosition = useCallback((
        anchorX: number,
        anchorY: number,
        panelWidth: number,
        panelHeight: number
    ): EditHoverPreviewPosition => {
        const gap = 12;
        const viewportPadding = 8;
        const left = Math.max(
            viewportPadding,
            Math.min(anchorX + gap, window.innerWidth - panelWidth - viewportPadding)
        );
        const top = Math.max(
            viewportPadding,
            Math.min(anchorY - panelHeight / 2, window.innerHeight - panelHeight - viewportPadding)
        );
        const arrowOffsetY = Math.max(12, Math.min(panelHeight - 12, anchorY - top));
        return { left, top, arrowOffsetY };
    }, []);

    const showHoverPreview = useCallback((
        e: React.MouseEvent<HTMLDivElement>,
        msg: Message,
        originalPrompt: string,
        enhancedPrompt: string,
        attachments: EditHoverPreviewAttachment[]
    ) => {
        if (window.innerWidth < 768) return;
        clearHidePreviewTimer();
        setOpenActionMenu(null);
        setActionMenuPosition(null);

        const rect = e.currentTarget.getBoundingClientRect();
        const anchorX = rect.right;
        const anchorY = rect.top + rect.height / 2;
        const shouldResetSize = hoverPreview?.messageId !== msg.id;
        if (shouldResetSize) {
            setHoverPreviewSize(null);
        }
        const estimatedPanelWidth = shouldResetSize ? 380 : (hoverPreviewSize?.width ?? 380);
        const estimatedPanelHeight = shouldResetSize ? 280 : (hoverPreviewSize?.height ?? 280);

        setHoverPreview({
            messageId: msg.id,
            role: msg.role,
            authorLabel: msg.role === Role.USER ? 'You' : (activeModelConfig?.name || 'AI'),
            anchorX,
            anchorY,
            originalPrompt,
            enhancedPrompt,
            attachments
        });
        setHoverPreviewPosition(
            computeHoverPreviewPosition(anchorX, anchorY, estimatedPanelWidth, estimatedPanelHeight)
        );
    }, [activeModelConfig?.name, clearHidePreviewTimer, computeHoverPreviewPosition, hoverPreview?.messageId, hoverPreviewSize?.height, hoverPreviewSize?.width]);

    const handlePreviewResizeMouseDown = useCallback((event: React.MouseEvent<HTMLButtonElement>) => {
        if (!hoverPreview) return;

        event.preventDefault();
        event.stopPropagation();
        clearHidePreviewTimer();
        stopPreviewResize();
        setIsResizingPreview(true);

        const startX = event.clientX;
        const startY = event.clientY;
        const previewRect = hoverPreviewPanelRef.current?.getBoundingClientRect();
        const startWidth = previewRect?.width ?? hoverPreviewSize?.width ?? 380;
        const startHeight = previewRect?.height ?? hoverPreviewSize?.height ?? 320;
        const anchorLeft = hoverPreviewPosition?.left ?? 8;
        const anchorTop = hoverPreviewPosition?.top ?? 8;
        const minWidth = 300;
        const minHeight = 220;
        const viewportPadding = 8;

        setHoverPreviewSize({ width: startWidth, height: startHeight });

        const onMouseMove = (moveEvent: MouseEvent) => {
            const deltaX = moveEvent.clientX - startX;
            const deltaY = moveEvent.clientY - startY;

            const maxWidth = Math.max(minWidth, window.innerWidth - anchorLeft - viewportPadding);
            const maxHeight = Math.max(minHeight, window.innerHeight - anchorTop - viewportPadding);

            const nextWidth = Math.max(minWidth, Math.min(maxWidth, startWidth + deltaX));
            const nextHeight = Math.max(minHeight, Math.min(maxHeight, startHeight + deltaY));

            setHoverPreviewSize({ width: nextWidth, height: nextHeight });
        };

        const onMouseUp = () => {
            stopPreviewResize();
        };

        previewResizeHandlersRef.current = { onMouseMove, onMouseUp };
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
    }, [hoverPreview, hoverPreviewPosition?.left, hoverPreviewPosition?.top, hoverPreviewSize?.width, hoverPreviewSize?.height, clearHidePreviewTimer, stopPreviewResize]);

    const handleCopyEnhancedPrompt = useCallback(async () => {
        if (!hoverPreview?.enhancedPrompt) return;

        const textToCopy = hoverPreview.enhancedPrompt;

        await safeCopyToClipboard(textToCopy);
        setCopiedPreviewMessageId(hoverPreview.messageId);
        clearCopiedResetTimer();
        copiedResetTimerRef.current = window.setTimeout(() => {
            setCopiedPreviewMessageId(null);
            copiedResetTimerRef.current = null;
        }, 1500);
    }, [hoverPreview, clearCopiedResetTimer]);

    useEffect(() => {
        if (!hoverPreview || !hoverPreviewPanelRef.current) return;

        const syncPosition = () => {
            if (!hoverPreviewPanelRef.current) return;
            const panelRect = hoverPreviewPanelRef.current.getBoundingClientRect();
            const panelWidth = hoverPreviewSize?.width ?? panelRect.width;
            const panelHeight = hoverPreviewSize?.height ?? panelRect.height;
            const next = computeHoverPreviewPosition(
                hoverPreview.anchorX,
                hoverPreview.anchorY,
                panelWidth,
                panelHeight
            );
            setHoverPreviewPosition((prev) => {
                if (
                    prev &&
                    Math.abs(prev.left - next.left) < 0.5 &&
                    Math.abs(prev.top - next.top) < 0.5 &&
                    Math.abs(prev.arrowOffsetY - next.arrowOffsetY) < 0.5
                ) {
                    return prev;
                }
                return next;
            });
        };

        const rafId = window.requestAnimationFrame(syncPosition);
        return () => {
            window.cancelAnimationFrame(rafId);
        };
    }, [hoverPreview, hoverPreviewSize, computeHoverPreviewPosition]);

    useEffect(() => {
        if (!hoverPreview) return;

        const clearPreview = () => closeHoverPreview();
        const handleWindowScroll = (event: Event) => {
            const target = event.target;
            if (
                target instanceof Node &&
                hoverPreviewPanelRef.current &&
                hoverPreviewPanelRef.current.contains(target)
            ) {
                return;
            }
            closeHoverPreview();
        };

        window.addEventListener('resize', clearPreview);
        window.addEventListener('scroll', handleWindowScroll, true);

        return () => {
            window.removeEventListener('resize', clearPreview);
            window.removeEventListener('scroll', handleWindowScroll, true);
        };
    }, [hoverPreview, closeHoverPreview]);

    useEffect(() => {
        if (filteredHistoryMessages.length === 0) return;

        const handleHistoryNavigation = (e: KeyboardEvent) => {
            if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;

            const target = e.target as HTMLElement | null;
            if (target) {
                const tagName = target.tagName;
                const isFormInput = tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT';
                const isEditable = target.isContentEditable || Boolean(target.closest('[contenteditable="true"]'));
                if (isFormInput || isEditable) {
                    return;
                }
            }

            e.preventDefault();
            closeHoverPreview();

            setSelectedHistoryMsgId((prevId) => {
                const currentIndex = prevId
                    ? filteredHistoryMessages.findIndex((m) => m.id === prevId)
                    : filteredHistoryMessages.length - 1;
                const safeCurrentIndex = currentIndex >= 0 ? currentIndex : filteredHistoryMessages.length - 1;
                const delta = e.key === 'ArrowUp' ? -1 : 1;
                const nextIndex = Math.max(0, Math.min(filteredHistoryMessages.length - 1, safeCurrentIndex + delta));
                const nextMessage = filteredHistoryMessages[nextIndex];

                if (nextMessage) {
                    const nextAttachments = getMessageDisplayAttachments(nextMessage);
                    if (nextAttachments.length > 0) {
                        setActiveImageUrl(nextAttachments[0].url);
                    }
                }

                return nextMessage?.id || prevId;
            });
        };

        window.addEventListener('keydown', handleHistoryNavigation);
        return () => {
            window.removeEventListener('keydown', handleHistoryNavigation);
        };
    }, [filteredHistoryMessages, closeHoverPreview, getMessageDisplayAttachments]);

    useEffect(() => {
        if (filteredHistoryMessages.length === 0) {
            setSelectedHistoryMsgId(null);
            return;
        }

        if (selectedHistoryMsgId && filteredHistoryMessages.some((msg) => msg.id === selectedHistoryMsgId)) {
            return;
        }

        const fallback = filteredHistoryMessages[filteredHistoryMessages.length - 1];
        if (fallback) {
            setSelectedHistoryMsgId(fallback.id);
            const fallbackAttachments = getMessageDisplayAttachments(fallback);
            if (fallbackAttachments.length > 0) {
                setActiveImageUrl(fallbackAttachments[0].url);
            }
        }
    }, [filteredHistoryMessages, getMessageDisplayAttachments, selectedHistoryMsgId]);

    useEffect(() => {
        if (!selectedHistoryMsgId) return;
        const itemEl = historyItemRefs.current[selectedHistoryMsgId];
        if (!itemEl) return;

        requestAnimationFrame(() => {
            itemEl.scrollIntoView({
                block: 'nearest',
                behavior: 'smooth'
            });
        });
    }, [selectedHistoryMsgId]);

    useEffect(() => {
        if (!openActionMenu) return;

        const handleOutsideClick = (event: MouseEvent) => {
            const target = event.target as Node | null;
            if (!target) return;
            if (
                actionMenuPanelRef.current &&
                actionMenuPanelRef.current.contains(target)
            ) {
                return;
            }
            if (
                target instanceof Element &&
                target.closest('[data-history-action-trigger]')
            ) {
                return;
            }
            setOpenActionMenu(null);
            setActionMenuPosition(null);
        };

        window.addEventListener('mousedown', handleOutsideClick);
        return () => {
            window.removeEventListener('mousedown', handleOutsideClick);
        };
    }, [openActionMenu]);

    useEffect(() => {
        if (!openActionMenu) return;

        const syncActionMenuPosition = () => {
            const panelRect = actionMenuPanelRef.current?.getBoundingClientRect();
            const panelWidth = panelRect?.width ?? 110;
            const panelHeight = panelRect?.height ?? 76;
            const viewportPadding = 8;
            const gap = 8;

            let left = openActionMenu.anchorX + gap;
            if (left + panelWidth + viewportPadding > window.innerWidth) {
                left = openActionMenu.anchorX - panelWidth - gap;
            }
            left = Math.max(viewportPadding, Math.min(left, window.innerWidth - panelWidth - viewportPadding));

            let top = openActionMenu.anchorY + gap;
            if (top + panelHeight + viewportPadding > window.innerHeight) {
                top = openActionMenu.anchorY - panelHeight - gap;
            }
            top = Math.max(viewportPadding, Math.min(top, window.innerHeight - panelHeight - viewportPadding));

            setActionMenuPosition((prev) => {
                if (
                    prev &&
                    Math.abs(prev.left - left) < 0.5 &&
                    Math.abs(prev.top - top) < 0.5
                ) {
                    return prev;
                }
                return { left, top };
            });
        };

        const rafId = window.requestAnimationFrame(syncActionMenuPosition);
        window.addEventListener('resize', syncActionMenuPosition);
        return () => {
            window.cancelAnimationFrame(rafId);
            window.removeEventListener('resize', syncActionMenuPosition);
        };
    }, [openActionMenu]);

    useEffect(() => {
        if (!openActionMenu) return;

        const handleWindowScroll = () => {
            setOpenActionMenu(null);
            setActionMenuPosition(null);
        };

        window.addEventListener('scroll', handleWindowScroll, true);
        return () => {
            window.removeEventListener('scroll', handleWindowScroll, true);
        };
    }, [openActionMenu]);

    useEffect(() => {
        return () => {
            clearHidePreviewTimer();
            clearCopiedResetTimer();
            stopPreviewResize();
        };
    }, [clearHidePreviewTimer, clearCopiedResetTimer, stopPreviewResize]);

    const sidebarExtraHeader = useMemo(() => (
        <div className="flex items-center gap-2">
            <label className="inline-flex items-center gap-1 text-[10px] text-slate-400 cursor-pointer select-none">
                <input
                    type="checkbox"
                    className="h-3 w-3 rounded border-slate-600 bg-slate-800 text-amber-400 focus:ring-0"
                    checked={showFavoritesOnly}
                    onChange={(event) => setShowFavoritesOnly(event.target.checked)}
                />
                <span>仅收藏</span>
            </label>
            <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-500">
                {filteredHistoryMessages.length}/{historyMessages.length}
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] rounded bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 text-amber-300">
                <Star size={9} className="fill-amber-300 text-amber-300" />
                {favoriteCount}
            </span>
        </div>
    ), [favoriteCount, filteredHistoryMessages.length, historyMessages.length, setShowFavoritesOnly, showFavoritesOnly]);

    // 使用 useMemo 缓存 sidebarContent，防止不必要的重新渲染
    const sidebarContent = useMemo(() => (
        <div ref={scrollRef} className="flex-1 p-3 space-y-2.5 overflow-y-auto custom-scrollbar">
            {filteredHistoryMessages.map((msg) => {
                const displayAttachments = getMessageDisplayAttachments(msg);
                const firstImage = displayAttachments[0]?.url;
                const count = displayAttachments.length;
                const isUserMessage = msg.role === Role.USER;
                const { originalPrompt, enhancedPrompt } = extractEditHistoryPrompts(msg);
                const favorited = isFavorite(msg.id);
                const isActionMenuOpen = openActionMenu?.messageId === msg.id;

                const isSelected = selectedHistoryMsgId
                    ? selectedHistoryMsgId === msg.id
                    : Boolean(activeImageUrl && displayAttachments.some((att) => att.url === activeImageUrl));

                const itemToneClass = isUserMessage
                    ? (isSelected
                        ? 'ring-1 ring-blue-400/80 border-transparent bg-blue-500/10'
                        : 'border-blue-500/20 bg-blue-500/5 hover:border-blue-400/40')
                    : (isSelected
                        ? 'ring-1 ring-pink-400/80 border-transparent bg-pink-500/10'
                        : 'border-pink-500/20 bg-pink-500/5 hover:border-pink-400/40');

                return (
                    <div
                        key={msg.id}
                        ref={(el) => {
                            historyItemRefs.current[msg.id] = el;
                        }}
                        className="group relative"
                    >
                        <div
                            className={`relative rounded-xl border cursor-pointer transition-all flex items-center gap-3 p-2 ${itemToneClass}`}
                            onMouseEnter={(e) => showHoverPreview(e, msg, originalPrompt, enhancedPrompt, displayAttachments)}
                            onMouseLeave={scheduleHideHoverPreview}
                            onClick={() => {
                                setSelectedHistoryMsgId(msg.id);
                                if (firstImage) {
                                    setActiveImageUrl(firstImage);
                                }
                                if (window.innerWidth < 768) {
                                    setIsMobileHistoryOpen(false);
                                }
                                closeHoverPreview();
                            }}
                        >
                            {favorited && (
                                <span className="absolute right-2 top-2 inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-400/20 border border-amber-300/50 z-10">
                                    <Star size={11} className="fill-amber-300 text-amber-300" />
                                </span>
                            )}

                            <div className="h-14 w-20 flex-shrink-0 rounded-lg overflow-hidden bg-slate-900 relative">
                                <span className={`absolute top-1 left-1 z-10 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium border ${
                                    isUserMessage
                                        ? 'bg-blue-950/85 text-blue-200 border-blue-400/30'
                                        : 'bg-pink-950/85 text-pink-200 border-pink-400/30'
                                }`}>
                                    {isUserMessage ? <User size={9} /> : <Bot size={9} />}
                                    {isUserMessage ? 'USER' : 'AI'}
                                </span>

                                {msg.isError ? (
                                    <div className="w-full h-full flex items-center justify-center text-red-400 bg-red-900/10">
                                        <AlertCircle size={18} />
                                    </div>
                                ) : firstImage ? (
                                    <>
                                        <img src={firstImage} className="w-full h-full object-cover transition-transform group-hover:scale-105" loading="lazy" alt="Edit history preview" />
                                        {count > 1 && (
                                            <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                                                <Layers size={10} /> {count}
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-slate-600">
                                        <ImageIcon size={16} className="opacity-50" />
                                    </div>
                                )}
                            </div>

                            <div className="min-w-0 flex-1">
                                <div className="flex items-center justify-between gap-2">
                                    <span className={`text-[10px] font-medium ${
                                        isUserMessage ? 'text-blue-300' : 'text-pink-300'
                                    }`}>
                                        {isUserMessage ? 'You' : (activeModelConfig?.name || 'AI')}
                                    </span>
                                    <span className="text-[10px] text-slate-500">
                                        {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                </div>
                                <p className="mt-1 text-[11px] text-slate-200 leading-relaxed font-medium line-clamp-2 break-words">
                                    {originalPrompt}
                                </p>
                                <div className="mt-1.5 flex items-center gap-2 text-[10px] text-slate-500">
                                    {isUserMessage ? (
                                        <span className="inline-flex items-center gap-1 rounded-full border border-blue-500/25 bg-blue-500/10 px-1.5 py-0.5 text-blue-300">
                                            用户输入
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center gap-1 rounded-full border border-pink-500/25 bg-pink-500/10 px-1.5 py-0.5 text-pink-300">
                                            AI 响应
                                        </span>
                                    )}
                                    {!isUserMessage && enhancedPrompt && (
                                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-300">
                                            <Sparkles size={10} />
                                            含增强提示词
                                        </span>
                                    )}
                                </div>
                            </div>

                            <div
                                className="absolute right-2 bottom-2 z-20"
                                onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                }}
                            >
                                <button
                                    type="button"
                                    className={`transition-opacity rounded-md border border-slate-600/70 bg-slate-900/90 p-1 text-slate-300 hover:text-white hover:border-slate-400 ${
                                        isActionMenuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                                    }`}
                                    title="历史项操作"
                                    data-history-action-trigger={msg.id}
                                    onClick={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        const rect = event.currentTarget.getBoundingClientRect();
                                        setOpenActionMenu((prev) => (
                                            prev?.messageId === msg.id
                                                ? null
                                                : {
                                                    messageId: msg.id,
                                                    anchorX: rect.right,
                                                    anchorY: rect.bottom
                                                }
                                        ));
                                        setActionMenuPosition(null);
                                    }}
                                >
                                    <FolderOpen size={12} />
                                </button>
                            </div>
                        </div>
                    </div>
                );
            })}

            {filteredHistoryMessages.length === 0 && (
                <div className="text-center py-10 text-slate-600 text-xs italic">
                    {showFavoritesOnly ? '暂无收藏记录。' : 'No edit history yet.'}
                </div>
            )}

            {openActionMenu && typeof document !== 'undefined' && (
                createPortal(
                    <div
                        ref={actionMenuPanelRef}
                        className="fixed z-[90] inline-flex flex-col gap-1 rounded-lg border border-slate-700 bg-slate-950/95 shadow-2xl backdrop-blur-md p-1"
                        style={{
                            top: actionMenuPosition?.top ?? openActionMenu.anchorY,
                            left: actionMenuPosition?.left ?? openActionMenu.anchorX
                        }}
                    >
                        <button
                            type="button"
                            className="whitespace-nowrap px-2.5 py-1.5 rounded text-left text-[11px] text-slate-200 hover:bg-slate-800 flex items-center gap-1.5 disabled:opacity-50"
                            disabled={openActionMenu.messageId ? isFavoritePending(openActionMenu.messageId) : false}
                            onClick={async () => {
                                await toggleFavorite(openActionMenu.messageId);
                                setOpenActionMenu(null);
                                setActionMenuPosition(null);
                            }}
                        >
                            <Star
                                size={11}
                                className={
                                    openActionMenu.messageId && isFavorite(openActionMenu.messageId)
                                        ? 'fill-amber-300 text-amber-300'
                                        : 'text-amber-300'
                                }
                            />
                            {openActionMenu.messageId && isFavorite(openActionMenu.messageId) ? '取消收藏' : '收藏'}
                        </button>
                        <button
                            type="button"
                            className="whitespace-nowrap px-2.5 py-1.5 rounded text-left text-[11px] text-red-300 hover:bg-red-950/50 flex items-center gap-1.5"
                            onClick={() => {
                                deleteItem(openActionMenu.messageId);
                                if (hoverPreview?.messageId === openActionMenu.messageId) {
                                    closeHoverPreview();
                                }
                                setOpenActionMenu(null);
                                setActionMenuPosition(null);
                            }}
                        >
                            <Trash2 size={11} />
                            删除
                        </button>
                    </div>,
                    document.body
                )
            )}

            {loadingState !== 'idle' && (() => {
                        // 根据 loadingState 和 editMode 显示不同的过程信息
                        let statusText = 'Processing request...';
                        let statusIcon = <Bot size={16} className="text-slate-500" />;
                        
                        if (loadingState === 'uploading') {
                            statusText = '上传图片中...';
                            statusIcon = <Layers size={16} className="text-blue-400" />;
                        } else if (loadingState === 'loading') {
                            // 对话式编辑模式的状态消息
                            statusText = '对话式编辑中，AI 正在理解您的需求并生成图片...';
                            statusIcon = <MessageSquare size={16} className="text-pink-400" />;
                        } else if (loadingState === 'streaming') {
                            statusText = '流式处理中...';
                            statusIcon = <Sparkles size={16} className="text-pink-400 animate-pulse" />;
                        }
                        
                        // 检查最新的消息是否有 thoughts 或文本内容
                        const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
                        const thoughts = lastMessage?.thoughts || [];
                        const textResponse = lastMessage?.textResponse;
                        const hasTextContent = lastMessage?.content && lastMessage.content.trim().length > 0;
                        
                        // 判断思考过程是否完成（loadingState 为 idle 时完成）
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

                                        {/* 使用 ThinkingBlock 显示思考过程（包含 thoughts 和 textResponse） */}
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

                                        {/* 显示内容（如果有，且没有 thoughts 和 textResponse） */}
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
                    })()}

            {hoverPreview && typeof document !== 'undefined' && createPortal(
                <div
                    ref={hoverPreviewPanelRef}
                    className="fixed hidden md:block"
                    style={{
                        top: hoverPreviewPosition?.top ?? hoverPreview.anchorY,
                        left: hoverPreviewPosition?.left ?? hoverPreview.anchorX,
                        ...(hoverPreviewSize
                            ? { width: hoverPreviewSize.width, height: hoverPreviewSize.height }
                            : {})
                    }}
                    onMouseEnter={clearHidePreviewTimer}
                    onMouseLeave={scheduleHideHoverPreview}
                >
                    <div className={`group relative rounded-xl border border-slate-700/80 bg-slate-950/95 backdrop-blur-lg p-3 shadow-2xl ${
                        hoverPreviewSize
                            ? 'h-full'
                            : 'inline-block w-fit max-w-[min(75vw,640px)]'
                    }`}>
                        <div
                            className="absolute right-full -translate-y-1/2 h-2.5 w-2.5 rotate-45 border-b border-l border-slate-700/80 bg-slate-950/95"
                            style={{ top: hoverPreviewPosition?.arrowOffsetY ?? '50%' }}
                        />

                        <div className={`pr-2 pb-5 custom-scrollbar ${
                            hoverPreviewSize
                                ? 'h-full overflow-y-auto'
                                : 'max-h-[72vh] overflow-y-auto'
                        }`}>
                            <div className="mb-3 flex items-center gap-2">
                                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border ${
                                    hoverPreview.role === Role.USER
                                        ? 'bg-blue-950/85 text-blue-200 border-blue-400/30'
                                        : 'bg-pink-950/85 text-pink-200 border-pink-400/30'
                                }`}>
                                    {hoverPreview.role === Role.USER ? <User size={10} /> : <Bot size={10} />}
                                    {hoverPreview.authorLabel}
                                </span>
                            </div>

                            <div className="mb-3">
                                <p className="text-[10px] uppercase tracking-wider text-slate-500">原始提示词</p>
                                <p className="mt-1 text-xs text-slate-200 whitespace-pre-wrap break-words">
                                    {hoverPreview.originalPrompt}
                                </p>
                            </div>

                            {hoverPreview.role === Role.MODEL && (
                                <div className="mb-3">
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="text-[10px] uppercase tracking-wider text-emerald-400">增强提示词</p>
                                        {hoverPreview.enhancedPrompt && (
                                            <button
                                                type="button"
                                                onClick={handleCopyEnhancedPrompt}
                                                className="pointer-events-auto inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-200 hover:bg-emerald-500/20 transition-colors"
                                                title="复制增强提示词"
                                            >
                                                {copiedPreviewMessageId === hoverPreview.messageId ? <Check size={11} /> : <Copy size={11} />}
                                                {copiedPreviewMessageId === hoverPreview.messageId ? '已复制' : '复制'}
                                            </button>
                                        )}
                                    </div>
                                    {hoverPreview.enhancedPrompt ? (
                                        <p className="mt-1 text-xs text-emerald-100 whitespace-pre-wrap break-words">
                                            {hoverPreview.enhancedPrompt}
                                        </p>
                                    ) : (
                                        <p className="mt-1 text-xs text-slate-500 italic">未返回增强提示词</p>
                                    )}
                                </div>
                            )}

                            {hoverPreview.attachments.length > 0 && (
                                <div>
                                    <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">附图</p>
                                    <div className="grid grid-cols-3 gap-2">
                                        {hoverPreview.attachments.map((att) => (
                                            <button
                                                key={att.id}
                                                type="button"
                                                className={`relative rounded-md overflow-hidden border transition-colors ${
                                                    activeImageUrl === att.url
                                                        ? 'border-pink-400 ring-1 ring-pink-400/70'
                                                        : 'border-slate-700 hover:border-slate-500'
                                                }`}
                                                onClick={() => {
                                                    setActiveImageUrl(att.url);
                                                    setSelectedHistoryMsgId(hoverPreview.messageId);
                                                }}
                                                title="在画布中查看该图片"
                                            >
                                                <img src={att.url} className="w-full h-14 object-cover bg-slate-900" alt="History attachment" />
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        <button
                            type="button"
                            aria-label="拖动调整提示词预览大小"
                            className="absolute bottom-0 right-0 h-5 w-5 cursor-se-resize bg-transparent"
                            onMouseDown={handlePreviewResizeMouseDown}
                        />
                        {isResizingPreview && (
                            <div className="pointer-events-none absolute bottom-1 left-3 text-[10px] text-slate-500">
                                {Math.round(hoverPreviewSize?.width || 0)} × {Math.round(hoverPreviewSize?.height || 0)}
                            </div>
                        )}
                    </div>
                </div>,
                document.body
            )}
        </div>
    ), [
        historyMessages,
        filteredHistoryMessages,
        showFavoritesOnly,
        favoriteCount,
        setShowFavoritesOnly,
        openActionMenu,
        actionMenuPosition,
        loadingState,
        activeModelConfig?.name,
        activeImageUrl,
        selectedHistoryMsgId,
        isThinkingOpen,
        displayedThinkingContent,
        hoverPreview,
        hoverPreviewPosition,
        hoverPreviewSize,
        isResizingPreview,
        copiedPreviewMessageId,
        getMessageDisplayAttachments,
        showHoverPreview,
        scheduleHideHoverPreview,
        closeHoverPreview,
        clearHidePreviewTimer,
        handleCopyEnhancedPrompt,
        handlePreviewResizeMouseDown,
        isFavorite,
        isFavoritePending,
        toggleFavorite,
        deleteItem
    ]);

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
    ), [loadingState, isCompareMode, activeAttachments, activeImageUrl, activeCanvasAttachment, originalImageUrl, canvas, handleFullscreen, handleExpand, toggleCompare, onExpandImage, handleSend, editMode, onStop, messages, currentSessionId, initialPrompt, initialAttachments, providerId, resetParams, carouselIndex, handleCarouselPrev, handleCarouselNext, handleCarouselSelect, getStableCanvasUrlFromAttachment, controls]);

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

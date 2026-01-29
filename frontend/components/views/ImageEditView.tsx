
import React, { useState, useRef, useEffect, useMemo, useCallback, memo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Crop, Wand2, AlertCircle, Layers, User, Bot, Sparkles, Palette, PenTool, MessageSquare, SlidersHorizontal, RotateCcw, ChevronLeft, ChevronRight, Image as ImageIcon } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCompare } from '../common/ImageCompare';
import { GenViewLayout } from '../common/GenViewLayout';
import { getUrlType, isBlobUrl } from '../../hooks/handlers/attachmentUtils';
import { ThinkingBlock } from '../message/ThinkingBlock';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';

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
                        {/* 左箭头（多图时显示） */}
                        {isMultiImageMode && (
                            <button
                                onClick={onCarouselPrev}
                                className="absolute left-4 z-10 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur border border-white/10 transition-all hover:scale-110"
                                title="上一张"
                            >
                                <ChevronLeft size={24} />
                            </button>
                        )}

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

                        {/* 右箭头（多图时显示） */}
                        {isMultiImageMode && (
                            <button
                                onClick={onCarouselNext}
                                className="absolute right-4 z-10 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur border border-white/10 transition-all hover:scale-110"
                                title="下一张"
                            >
                                <ChevronRight size={24} />
                            </button>
                        )}
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
                        <div className="flex items-center gap-3 py-3 px-4 bg-black/60 backdrop-blur-md rounded-2xl border border-white/10 shadow-xl">
                            {activeAttachments.map((att, idx) => {
                                // ✅ 直接使用 att.url（与 AttachmentPreview 一致）
                                const thumbUrl = att.url || att.tempUrl || getStableUrl(att);
                                return (
                                    <button
                                        key={att.id || `thumb-${idx}`}
                                        onClick={() => onCarouselSelect(idx)}
                                        className={`relative rounded-lg overflow-hidden transition-all duration-200 ${
                                            idx === carouselIndex
                                                ? 'ring-2 ring-pink-500 scale-110'
                                                : 'opacity-60 hover:opacity-100 hover:scale-105'
                                        }`}
                                    >
                                        {thumbUrl ? (
                                            <img
                                                src={thumbUrl}
                                                className="w-14 h-14 object-cover"
                                                alt={`缩略图 ${idx + 1}`}
                                                onError={(e) => {
                                                    // 如果图片加载失败，显示占位图标
                                                    (e.target as HTMLImageElement).style.display = 'none';
                                                    (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                                                }}
                                            />
                                        ) : null}
                                        <div className={`w-14 h-14 bg-slate-800 flex items-center justify-center ${thumbUrl ? 'hidden' : ''}`}>
                                            <ImageIcon size={16} className="text-slate-600" />
                                        </div>
                                        {idx === carouselIndex && (
                                            <div className="absolute inset-0 bg-pink-500/20" />
                                        )}
                                    </button>
                                );
                            })}
                            <span className="ml-2 text-xs text-slate-400 font-mono">
                                {carouselIndex + 1} / {activeAttachments.length}
                            </span>
                        </div>
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
    sessionId: currentSessionId  // ✅ 接收 sessionId
}: ImageEditViewProps) => {
    const { showError } = useToastContext();
    const scrollRef = useRef<HTMLDivElement>(null);

    // State for reference image
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);

    // ✅ 旋转木马索引（多图预览时使用）
    const [carouselIndex, setCarouselIndex] = useState(0);

    // ✅ 包装 setActiveAttachments 以添加调试日志
    const handleAttachmentsChange = useCallback((newAtts: Attachment[]) => {
        console.log('[ImageEditView] handleAttachmentsChange 被调用:', {
            newAttachmentsCount: newAtts.length,
            attachments: newAtts.map(att => ({ id: att.id, name: att.name, hasFile: !!att.file })),
        });
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
        console.log('[getStableCanvasUrlFromAttachment] 处理附件:', {
            id: att.id,
            hasFile: !!att.file,
            hasUrl: !!att.url,
            hasTempUrl: !!att.tempUrl,
            urlPreview: att.url ? (att.url.startsWith('blob:') ? 'blob:...' : att.url.substring(0, 50)) : 'N/A'
        });

        if (att.file) {
            const file = att.file;
            const cachedUrl = canvasObjectUrlMapRef.current.get(file);
            if (cachedUrl) {
                console.log('[getStableCanvasUrlFromAttachment] 使用缓存的 Blob URL');
                return cachedUrl;
            }
            // 为新文件创建 Blob URL 并缓存
            const newUrl = URL.createObjectURL(file);
            canvasObjectUrlMapRef.current.set(file, newUrl);
            console.log('[getStableCanvasUrlFromAttachment] 创建新的 Blob URL:', newUrl.substring(0, 50));
            return newUrl;
        }
        const result = att.url || att.tempUrl || null;
        console.log('[getStableCanvasUrlFromAttachment] 使用现有 URL:', result ? result.substring(0, 50) : 'null');
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

    // ✅ 旋转木马处理函数
    const handleCarouselPrev = useCallback(() => {
        setCarouselIndex((prev) => (prev - 1 + activeAttachments.length) % activeAttachments.length);
        canvas.resetView();
    }, [activeAttachments.length, canvas]);

    const handleCarouselNext = useCallback(() => {
        setCarouselIndex((prev) => (prev + 1) % activeAttachments.length);
        canvas.resetView();
    }, [activeAttachments.length, canvas]);

    const handleCarouselSelect = useCallback((index: number) => {
        setCarouselIndex(index);
        canvas.resetView();
    }, [canvas]);

    // ✅ 当附件变化时，重置旋转木马索引
    useEffect(() => {
        if (carouselIndex >= activeAttachments.length && activeAttachments.length > 0) {
            setCarouselIndex(activeAttachments.length - 1);
        } else if (activeAttachments.length === 0) {
            setCarouselIndex(0);
        }
    }, [activeAttachments.length, carouselIndex]);

    // ✅ 键盘左右键切换图片（多图模式）
    useEffect(() => {
        if (activeAttachments.length <= 1) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            // 如果焦点在输入框内，不处理
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
                return;
            }

            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                handleCarouselPrev();
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                handleCarouselNext();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [activeAttachments.length, handleCarouselPrev, handleCarouselNext]);

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
            console.log('[ImageEditView] 同步 initialAttachments:', initialAttachments);
            setActiveAttachments(initialAttachments);
            setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
        } else if (initialAttachments === undefined && activeAttachments.length === 0) {
            // 如果 initialAttachments 被清空（undefined），且当前没有附件，保持空状态
            // 但如果已经有附件（例如从消息中恢复），不要清空
            console.log('[ImageEditView] initialAttachments 为 undefined，但保持当前附件状态');
        }
    }, [initialAttachments, getStableCanvasUrlFromAttachment]);

    // Sync uploaded attachment to main view
    // ✅ 与原始代码一致：只在有附件时设置画布图片，不清空画布
    // 原因：发送后附件预览会被清空，但画布应继续显示用户上传的图片，直到 AI 返回结果
    useEffect(() => {
        if (activeAttachments.length > 0) {
            const stableUrl = getStableCanvasUrlFromAttachment(activeAttachments[0]);
            console.log('[ImageEditView] 同步附件到画布:', {
                attachmentCount: activeAttachments.length,
                attachmentId: activeAttachments[0].id,
                stableUrl: stableUrl?.substring(0, 50) + '...',
            });
            setActiveImageUrl(stableUrl);
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
                console.log('[ImageEditView] 从用户消息中提取原始图片:', {
                    urlType: urlType,
                    url: formatUrlForLog(att.url),
                    uploadStatus: att.uploadStatus,
                    source: urlType.includes('云存储URL') ? '云存储URL (处理后的永久URL)' : 'AI返回的原始地址或处理后的URL'
                });
                setActiveImageUrl(lastUserMsg.attachments[0].url);
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
                    console.log('[ImageEditView] 从模型消息中提取编辑后的图片:', {
                        urlType: urlType,
                        url: formatUrlForLog(att.url),
                        uploadStatus: att.uploadStatus,
                        source: urlType.includes('云存储URL') ? '云存储URL (处理后的永久URL)' : 'AI返回的原始地址或处理后的URL'
                    });
                    setActiveImageUrl(lastModelMsg.attachments[0].url);
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
                    
                    console.log('[ImageEditView] ========== 从最新消息中提取附件用于显示 ==========');
                    console.log('[ImageEditView] 提取的附件信息:', {
                        messageId: lastMsg.id,
                        attachmentId: att.id || 'N/A',
                        displayUrlType: urlType,
                        displayUrl: formatUrlForLog(att.url),
                        uploadStatus: att.uploadStatus,
                        hasCloudUrl: att.uploadStatus === 'completed' && (att.url?.startsWith('http://') || att.url?.startsWith('https://')),
                        tempUrl: formatUrlForLog(att.tempUrl),
                        source: urlType.includes('云存储URL') ? '云存储URL (处理后的永久URL)' :
                               urlType.includes('Base64') ? 'AI返回的原始Base64地址' :
                               urlType.includes('Blob') ? '处理后的Blob URL (从HTTP临时URL转换)' :
                               urlType.includes('HTTP临时URL') ? 'AI返回的HTTP临时地址' : '未知来源',
                        note: '前端显示将使用此URL'
                    });
                    console.log('[ImageEditView] ============================================');
                    
                    setActiveImageUrl(lastMsg.attachments[0].url);
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
        console.log('========== [ImageEditView] handleSend 开始 ==========');
        console.log('[handleSend] 用户输入:', text);
        console.log('[handleSend] 选择的编辑模式:', editMode);
        console.log('[handleSend] 附件数量:', attachments.length);
        console.log('[handleSend] 选项:', options);
        console.log('========== [ImageEditView] handleSend 结束 ==========');
        // ChatEditInputArea 已经处理了所有逻辑，直接转发即可
        onSend(text, options, attachments, editMode);
    }, [onSend, editMode]);

    // Canvas 事件处理器现在由 useImageCanvas Hook 提供

    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

    // 使用 useMemo 缓存 sidebarContent，防止不必要的重新渲染
    const sidebarContent = useMemo(() => (
        <div ref={scrollRef} className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
                    {messages.map((msg) => {
                        // Filter out empty placeholders to prevent "Double Bubble" issue
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
                                    {/* 原始提示词 */}
                                    {msg.content && <p className="mb-2">{msg.content}</p>}

                                    {/* ✅ 增强后的提示词（单独容器显示，与原始提示词区分） */}
                                    {msg.role === Role.MODEL && msg.enhancedPrompt && (
                                        <div className="mb-3 p-2 bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-lg border border-purple-500/20">
                                            <div className="flex items-center gap-1.5 mb-1">
                                                <Sparkles size={12} className="text-purple-400" />
                                                <span className="text-xs text-purple-400 font-medium">AI 增强提示词</span>
                                            </div>
                                            <p className="text-xs text-slate-300 italic">{msg.enhancedPrompt}</p>
                                        </div>
                                    )}

                                    {/* ✅ 思考过程显示在图片上方（先思考 → 再生成图片） */}
                                    {msg.role === Role.MODEL && (msg.thoughts?.length > 0 || msg.textResponse) && (() => {
                                        const thoughtTexts = (msg.thoughts || [])
                                            .filter((t: { type: string }) => t.type === 'text')
                                            .map((t: { content: string }) => t.content)
                                            .join('\n\n');
                                        const fullContent = [thoughtTexts, msg.textResponse].filter(Boolean).join('\n\n---\n\n');
                                        if (!fullContent) return null;
                                        return (
                                            <div className="mb-3">
                                                <ThinkingBlock
                                                    content={fullContent}
                                                    isOpen={isThinkingOpen}
                                                    onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
                                                    isComplete={true}
                                                />
                                            </div>
                                        );
                                    })()}

                                    {(() => {
                                        const displayAttachments = (msg.attachments || []).filter(att => {
                                            return (att.url && att.url.length > 0) || (att.tempUrl && att.tempUrl.length > 0);
                                        });

                                        if (displayAttachments.length === 0) return null;

                                        const columns = Math.min(displayAttachments.length, 3);

                                        return (
                                            <div
                                                className="grid gap-2 mt-2"
                                                style={{ gridTemplateColumns: `repeat(${columns}, 80px)` }}
                                            >
                                                {displayAttachments.map((att, idx) => {
                                                    // ✅ 修复：优先使用 url，如果为空则使用 tempUrl（用于显示用户上传的附件）
                                                    let displayUrl = att.url && att.url.length > 0 ? att.url : (att.tempUrl || '');

                                                    // ✅ 如果 displayUrl 是 Blob URL 且附件有 File 对象，使用 File 对象创建新的 Blob URL
                                                    if (isBlobUrl(displayUrl) && att.file) {
                                                        try {
                                                            displayUrl = URL.createObjectURL(att.file);
                                                        } catch (error) {
                                                            console.warn('[ImageEditView] 无法从 File 对象创建 Blob URL:', error);
                                                        }
                                                    }

                                                    return (
                                                        <div
                                                            key={idx}
                                                            onClick={() => setActiveImageUrl(displayUrl)}
                                                            className={`relative group rounded-lg overflow-hidden border cursor-pointer transition-all w-[80px] ${activeImageUrl === displayUrl ? 'ring-2 ring-pink-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                                                                }`}
                                                        >
                                                            <img 
                                                                src={displayUrl} 
                                                                className="w-full h-[56px] object-cover bg-slate-900" 
                                                                alt="thumbnail"
                                                                onError={(e) => {
                                                                    if (att.file && isBlobUrl(displayUrl)) {
                                                                        try {
                                                                            const newBlobUrl = URL.createObjectURL(att.file);
                                                                            (e.target as HTMLImageElement).src = newBlobUrl;
                                                                        } catch (error) {
                                                                            console.error('[ImageEditView] 无法从 File 对象恢复 Blob URL:', error);
                                                                        }
                                                                    }
                                                                }}
                                                            />
                                                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                                                {activeImageUrl === displayUrl && <div className="bg-pink-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />}
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        );
                                    })()}
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
                            <div className="flex items-start gap-2">
                                <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
                                    {statusIcon}
                                </div>
                                <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 flex-1">
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
                        );
                    })()}
                    {/* 底部占位符 */}
                    <div />
                </div>
    ), [messages, loadingState, activeModelConfig?.name, activeImageUrl, activeAttachments, editMode, isThinkingOpen]);

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
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-pink-400" />
                        <span className="text-xs font-bold text-white">编辑参数</span>
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
                        mode={editMode}
                        providerId={providerId || 'google'}
                        controls={controls}
                        availableModels={visibleModels}
                    />
                </div>

                {/* 底部固定区：使用 ChatEditInputArea 组件 */}
                <ChatEditInputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    mode={editMode}
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={handleAttachmentsChange}
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
    ), [loadingState, isCompareMode, activeAttachments, activeImageUrl, originalImageUrl, canvas, handleFullscreen, handleExpand, toggleCompare, onExpandImage, handleSend, editMode, onStop, messages, currentSessionId, initialPrompt, initialAttachments, providerId, resetParams, carouselIndex, handleCarouselPrev, handleCarouselNext, handleCarouselSelect, getStableCanvasUrlFromAttachment]);

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

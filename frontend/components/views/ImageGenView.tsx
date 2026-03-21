
import { safeCopyToClipboard } from '../../utils/safeOps';
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { 
  Image as ImageIcon, Layers, Clock, AlertCircle, Grid,
  Wand2, SlidersHorizontal, RotateCcw, Sparkles, Copy, Check, Star, FolderOpen, Trash2
} from 'lucide-react';
import { GenViewLayout } from '../common/GenViewLayout';
import { ImageCanvasControls } from '../common/ImageCanvasControls';
import { ImageCarouselArrows, ImageCarouselThumbnails, type CarouselMediaItem } from '../common/ImageCarouselControls';
import { getUrlType } from '../../hooks/handlers/attachmentUtils';
import { useControlsState } from '../../hooks/useControlsState';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import { useHistoryListActions } from '../../hooks/useHistoryListActions';

interface ImageGenViewProps {
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
    onEditImage?: (url: string, attachment?: Attachment) => void;
    onExpandImage?: (url: string, attachment?: Attachment) => void;  // ✅ 修复：添加可选的 attachment 参数
    providerId?: string;
    sessionId?: string | null;
    onDeleteMessage?: (messageId: string) => void;
}

const extractHistoryPrompts = (msg: Message): { originalPrompt: string; optimizedPrompt: string } => {
    const rawContent = (msg.content || '').trim();
    const attachmentEnhancedPrompt = msg.attachments?.find(att => att.enhancedPrompt?.trim())?.enhancedPrompt?.trim();

    let originalPrompt = rawContent;
    let optimizedPrompt = msg.enhancedPrompt?.trim() || attachmentEnhancedPrompt || '';

    const promptPairMatch = rawContent.match(/^📝\s*([\s\S]*?)(?:\n✨\s*([\s\S]*))?$/);
    if (promptPairMatch) {
        originalPrompt = (promptPairMatch[1] || '').trim();
        if (!optimizedPrompt && promptPairMatch[2]) {
            optimizedPrompt = promptPairMatch[2].trim();
        }
    } else {
        const originalOnlyMatch = rawContent.match(/^📝\s*([\s\S]*)$/);
        if (originalOnlyMatch) {
            originalPrompt = originalOnlyMatch[1].trim();
        }

        if (!optimizedPrompt) {
            const optimizedOnlyMatch = rawContent.match(/^✨\s*([\s\S]*)$/);
            if (optimizedOnlyMatch) {
                optimizedPrompt = optimizedOnlyMatch[1].trim();
            }
        }
    }

    return {
        originalPrompt: originalPrompt || 'Generated Image Batch',
        optimizedPrompt
    };
};

interface HoverPromptPreview {
    messageId: string;
    anchorX: number;
    anchorY: number;
    originalPrompt: string;
    optimizedPrompt: string;
}

interface HoverPromptPreviewSize {
    width: number;
    height: number;
}

interface HoverPromptPreviewPosition {
    top: number;
    left: number;
    arrowOffsetY: number;
}

interface ActionMenuAnchor {
    messageId: string;
    anchorX: number;
    anchorY: number;
}

interface ActionMenuPosition {
    top: number;
    left: number;
}

export const ImageGenView: React.FC<ImageGenViewProps> = ({
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
    onEditImage,
    onExpandImage,
    providerId,
    sessionId,
    onDeleteMessage
}) => {
    // Track selected MESSAGE ID (Batch)
    const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);
    // Mobile History Toggle
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
    const [hoverPreview, setHoverPreview] = useState<HoverPromptPreview | null>(null);
    const [hoverPreviewPosition, setHoverPreviewPosition] = useState<HoverPromptPreviewPosition | null>(null);
    const [hoverPreviewSize, setHoverPreviewSize] = useState<HoverPromptPreviewSize | null>(null);
    const [isResizingPreview, setIsResizingPreview] = useState(false);
    const [copiedPreviewMessageId, setCopiedPreviewMessageId] = useState<string | null>(null);
    const hidePreviewTimerRef = useRef<number | null>(null);
    const copiedResetTimerRef = useRef<number | null>(null);
    const hoverPreviewPanelRef = useRef<HTMLDivElement | null>(null);
    const actionMenuPanelRef = useRef<HTMLDivElement | null>(null);
    const historyItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
    const previewResizeHandlersRef = useRef<{
        onMouseMove?: (event: MouseEvent) => void;
        onMouseUp?: () => void;
    }>({});
    const [openActionMenu, setOpenActionMenu] = useState<ActionMenuAnchor | null>(null);
    const [actionMenuPosition, setActionMenuPosition] = useState<ActionMenuPosition | null>(null);
    
    // ✅ 使用统一的状态管理 hook
    const controls = useControlsState('image-gen', activeModelConfig);
    
    // ✅ 图片缩放 hook（用于单图放大查看）
    const canvas = useImageCanvas({ minZoom: 0.5, maxZoom: 5, initialZoom: 1 });
    const { resetView } = canvas;
    
    // ✅ 本地 UI 状态
    const [prompt, setPrompt] = useState(initialPrompt || '');
    const [showAdvanced, setShowAdvanced] = useState(true); // 默认展开高级参数
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    
    const isLoading = loadingState !== 'idle';

    // ✅ 检测提供商类型
    const isOpenAI = providerId === 'openai';

    // ✅ 最大图片数量（OpenAI 只支持 1 张）
    const maxImageCount = isOpenAI ? 1 : 4;

    // ✅ OpenAI 只支持 1 张图片
    useEffect(() => {
        if (isOpenAI && controls.numberOfImages !== 1) {
            controls.setNumberOfImages(1);
        } else if (controls.numberOfImages > maxImageCount) {
            controls.setNumberOfImages(maxImageCount);
        }
    }, [isOpenAI, controls.numberOfImages, maxImageCount, controls]);

    // ✅ 重置参数
    const resetParams = useCallback(() => {
        controls.setStyle('None');
        controls.setNumberOfImages(1);
        controls.setAspectRatio('1:1');
        controls.setResolution('1K');
        controls.setNegativePrompt('');
        controls.setSeed(-1);
        controls.setOutputMimeType('image/png');
        controls.setOutputCompressionQuality(80);
        controls.setEnhancePrompt(false);
    }, [controls]);

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

    // Auto-switch to latest generation when new one starts
    useEffect(() => {
        if (loadingState === 'loading') {
            setSelectedMsgId(null);
            // Close mobile history if a new generation starts
            setIsMobileHistoryOpen(false);
            closeHoverPreview();
        }
    }, [loadingState, closeHoverPreview]);

    // 1. Group History by Message (Batch)
    const historyBatches = useMemo(() => {
        return messages
            .filter(m => m.role === Role.MODEL && ((m.attachments && m.attachments.length > 0) || m.isError))
            .reverse();
    }, [messages]);

    const {
        showFavoritesOnly,
        setShowFavoritesOnly,
        filteredItems: filteredHistoryBatches,
        favoriteCount,
        isFavorite,
        isFavoritePending,
        toggleFavorite,
        deleteItem
    } = useHistoryListActions({
        sessionId,
        items: historyBatches,
        onDeleteItem: onDeleteMessage
    });

    // 2. Determine Active Batch to Display
    const activeBatchMessage = useMemo(() => {
        if (selectedMsgId) {
            return filteredHistoryBatches.find(m => m.id === selectedMsgId);
        }
        return filteredHistoryBatches[0];
    }, [selectedMsgId, filteredHistoryBatches]);

    const displayImages = useMemo(() => {
        return (activeBatchMessage?.attachments || []).filter(att => att.url && att.url.length > 0);
    }, [activeBatchMessage?.attachments]);

    const carouselItems = useMemo<CarouselMediaItem[]>(
        () => displayImages.map((att, idx) => ({
            id: att.id || `${idx}`,
            url: att.url || null,
            thumbUrl: att.url || null,
            alt: `缩略图 ${idx + 1}`
        })),
        [displayImages]
    );

    const {
        index: carouselIndex,
        goPrev: handleCarouselPrev,
        goNext: handleCarouselNext,
        select: handleCarouselSelect
    } = useImageCarousel({
        itemCount: displayImages.length,
        resetKey: activeBatchMessage?.id || null,
        keyboardEnabled: true,
        onNavigate: canvas.resetView
    });

    // 批次切换时同步重置画布
    useEffect(() => {
        resetView();
    }, [activeBatchMessage?.id, resetView]);
    
    // ✅ 详细日志：记录显示图片时使用的URL类型
    useEffect(() => {
        if (displayImages.length > 0) {
            displayImages.forEach((att, idx) => {
                const urlType = getUrlType(att.url, att.uploadStatus);
                
                const hasCloudUrl = att.uploadStatus === 'completed' && 
                                   (att.url?.startsWith('http://') || att.url?.startsWith('https://'));
                
                // 对于BASE64 URL，只输出类型和长度，不输出实际内容
                const formatUrlForLog = (url: string | undefined): string => {
                    if (!url) return 'N/A';
                    if (url.startsWith('data:')) {
                        return `Base64 Data URL (长度: ${url.length} 字符)`;
                    }
                    return url.length > 80 ? url.substring(0, 80) + '...' : url;
                };

            });
        }
    }, [displayImages]);
    const isBatchError = activeBatchMessage?.isError;

    // ✅ 生成处理函数
    const handleGenerate = useCallback(() => {
        if (!prompt.trim() || isLoading) return;
        
        const options: ChatOptions = {
            enableSearch: false,
            enableThinking: false,
            enableCodeExecution: false,
            // 基础参数
            imageAspectRatio: controls.aspectRatio,
            imageResolution: controls.resolution,
            numberOfImages: controls.numberOfImages,
            imageStyle: controls.style !== 'None' ? controls.style : undefined,
            // Google Imagen 高级参数
            negativePrompt: controls.negativePrompt || undefined,
            seed: controls.seed !== -1 ? controls.seed : undefined,
            outputMimeType: controls.outputMimeType,
            // PNG 是无损格式，不需要压缩质量参数，仅 JPEG 时传递
            ...(controls.outputMimeType === 'image/jpeg' ? { outputCompressionQuality: controls.outputCompressionQuality } : {}),
            enhancePrompt: controls.enhancePrompt,
            // TongYi 专用参数
            promptExtend: controls.promptExtend,
            addMagicSuffix: controls.addMagicSuffix,
        };
        
        onSend(prompt, options, [], 'image-gen');
        setPrompt(''); // 发送后清空提示词
    }, [prompt, controls, isLoading, onSend]);

    // ✅ 键盘快捷键
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleGenerate();
        }
    }, [handleGenerate]);

    // 历史列表快捷键：↑/↓ 切换选中批次
    useEffect(() => {
        if (filteredHistoryBatches.length === 0) return;

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

            setSelectedMsgId((prevId) => {
                const currentIndex = prevId ? filteredHistoryBatches.findIndex((m) => m.id === prevId) : 0;
                const safeCurrentIndex = currentIndex >= 0 ? currentIndex : 0;
                const delta = e.key === 'ArrowUp' ? -1 : 1;
                const nextIndex = Math.max(0, Math.min(filteredHistoryBatches.length - 1, safeCurrentIndex + delta));
                return filteredHistoryBatches[nextIndex]?.id || prevId;
            });
        };

        window.addEventListener('keydown', handleHistoryNavigation);
        return () => {
            window.removeEventListener('keydown', handleHistoryNavigation);
        };
    }, [filteredHistoryBatches, closeHoverPreview]);

    useEffect(() => {
        if (filteredHistoryBatches.length === 0) {
            setSelectedMsgId(null);
            return;
        }

        if (selectedMsgId && filteredHistoryBatches.some((msg) => msg.id === selectedMsgId)) {
            return;
        }

        setSelectedMsgId(filteredHistoryBatches[0].id);
    }, [filteredHistoryBatches, selectedMsgId]);

    useEffect(() => {
        if (!selectedMsgId) return;
        const itemEl = historyItemRefs.current[selectedMsgId];
        if (!itemEl) return;

        requestAnimationFrame(() => {
            itemEl.scrollIntoView({
                block: 'nearest',
                behavior: 'smooth'
            });
        });
    }, [selectedMsgId]);

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

    const computeHoverPreviewPosition = useCallback((
        anchorX: number,
        anchorY: number,
        panelWidth: number,
        panelHeight: number
    ): HoverPromptPreviewPosition => {
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
        messageId: string,
        originalPrompt: string,
        optimizedPrompt: string
    ) => {
        if (window.innerWidth < 768) return;
        clearHidePreviewTimer();
        setOpenActionMenu(null);
        setActionMenuPosition(null);

        const rect = e.currentTarget.getBoundingClientRect();
        const anchorX = rect.right;
        const anchorY = rect.top + rect.height / 2;
        const shouldResetSize = hoverPreview?.messageId !== messageId;
        if (shouldResetSize) {
            setHoverPreviewSize(null);
        }
        const estimatedPanelWidth = shouldResetSize ? 360 : (hoverPreviewSize?.width ?? 360);
        const estimatedPanelHeight = shouldResetSize ? 260 : (hoverPreviewSize?.height ?? 260);

        setHoverPreview({
            messageId,
            anchorX,
            anchorY,
            originalPrompt,
            optimizedPrompt
        });
        setHoverPreviewPosition(
            computeHoverPreviewPosition(anchorX, anchorY, estimatedPanelWidth, estimatedPanelHeight)
        );
    }, [clearHidePreviewTimer, computeHoverPreviewPosition, hoverPreview?.messageId, hoverPreviewSize?.height, hoverPreviewSize?.width]);

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
        const startWidth = previewRect?.width ?? hoverPreviewSize?.width ?? 360;
        const startHeight = previewRect?.height ?? hoverPreviewSize?.height ?? 280;
        const anchorLeft = hoverPreviewPosition?.left ?? 8;
        const anchorTop = hoverPreviewPosition?.top ?? 8;
        const minWidth = 280;
        const minHeight = 190;
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

    const handleCopyOptimizedPrompt = useCallback(async () => {
        if (!hoverPreview?.optimizedPrompt) return;

        const textToCopy = hoverPreview.optimizedPrompt;

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
                // 允许在冒泡内部滚动长提示词，不关闭冒泡
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
        return () => {
            clearHidePreviewTimer();
            clearCopiedResetTimer();
            stopPreviewResize();
        };
    }, [clearHidePreviewTimer, clearCopiedResetTimer, stopPreviewResize]);

    // Sidebar header icon and extra header
    const sidebarHeaderIcon = <Clock size={14} />;
    
    // ✅ 使用 useMemo 缓存 sidebarExtraHeader，确保在 historyBatches 变化时更新
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
                {filteredHistoryBatches.length}/{historyBatches.length}
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] rounded bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 text-amber-300">
                <Star size={9} className="fill-amber-300 text-amber-300" />
                {favoriteCount}
            </span>
        </div>
    ), [favoriteCount, filteredHistoryBatches.length, historyBatches.length, setShowFavoritesOnly, showFavoritesOnly]);

    // ✅ 使用 useMemo 缓存 sidebarContent，确保在 historyBatches 或 selectedMsgId 变化时更新
    const sidebarContent = useMemo(() => (
        <div className="p-3 space-y-2.5">
            {filteredHistoryBatches.map((msg) => {
                const firstImage = msg.attachments?.[0]?.url;
                const count = msg.attachments?.length || 0;
                const isSelected = activeBatchMessage?.id === msg.id;
                const { originalPrompt, optimizedPrompt } = extractHistoryPrompts(msg);
                const favorited = isFavorite(msg.id);
                const isActionMenuOpen = openActionMenu?.messageId === msg.id;

                return (
                    <div
                        key={msg.id}
                        ref={(el) => {
                            historyItemRefs.current[msg.id] = el;
                        }}
                        className="group relative"
                    >
                        <div
                            className={`relative rounded-xl border cursor-pointer transition-all flex items-center gap-3 bg-slate-800/40 p-2 ${
                                isSelected ? 'ring-1 ring-emerald-500 border-transparent bg-slate-800' : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-800'
                            }`}
                            onMouseEnter={(e) => showHoverPreview(e, msg.id, originalPrompt, optimizedPrompt)}
                            onMouseLeave={scheduleHideHoverPreview}
                            onClick={() => {
                                setSelectedMsgId(msg.id);
                                if (window.innerWidth < 768) setIsMobileHistoryOpen(false);
                                closeHoverPreview();
                            }}
                        >
                            {favorited && (
                                <span className="absolute right-2 top-2 inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-400/20 border border-amber-300/50 z-10">
                                    <Star size={11} className="fill-amber-300 text-amber-300" />
                                </span>
                            )}

                            <div className="h-14 w-20 flex-shrink-0 rounded-lg overflow-hidden bg-slate-900 relative">
                                {msg.isError ? (
                                    <div className="w-full h-full flex items-center justify-center text-red-400 bg-red-900/10">
                                        <AlertCircle size={20} />
                                    </div>
                                ) : firstImage ? (
                                    <>
                                        <img src={firstImage} className="w-full h-full object-cover transition-transform group-hover:scale-105" loading="lazy" alt="Generated image" />
                                        {count > 1 && (
                                            <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                                                <Layers size={10} /> {count}
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-slate-600">
                                        <ImageIcon size={18} className="opacity-50" />
                                    </div>
                                )}
                            </div>

                            <div className="min-w-0 flex-1">
                                <p className="text-[11px] text-slate-200 leading-relaxed font-medium line-clamp-2 break-words">
                                    {originalPrompt}
                                </p>
                                <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
                                    <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                    {optimizedPrompt && (
                                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-300">
                                            <Wand2 size={10} />
                                            已优化
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

            {filteredHistoryBatches.length === 0 && (
                <div className="text-center py-10 text-slate-600 text-xs italic">
                    {showFavoritesOnly ? '暂无收藏记录。' : 'No generation history.'}
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
                            : 'inline-block w-fit max-w-[min(70vw,560px)]'
                    }`}>
                        <div
                            className="absolute right-full -translate-y-1/2 h-2.5 w-2.5 rotate-45 border-b border-l border-slate-700/80 bg-slate-950/95"
                            style={{ top: hoverPreviewPosition?.arrowOffsetY ?? '50%' }}
                        />

                        <div className={`pr-2 pb-5 custom-scrollbar ${
                            hoverPreviewSize
                                ? 'h-full overflow-y-auto'
                                : 'max-h-[70vh] overflow-y-auto'
                        }`}>
                            <div className="mb-3">
                                <p className="text-[10px] uppercase tracking-wider text-slate-500">原始提示词</p>
                                <p className="mt-1 text-xs text-slate-200 whitespace-pre-wrap break-words">
                                    {hoverPreview.originalPrompt}
                                </p>
                            </div>

                            <div>
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-[10px] uppercase tracking-wider text-emerald-400">优化后提示词</p>
                                    {hoverPreview.optimizedPrompt && (
                                        <button
                                            type="button"
                                            onClick={handleCopyOptimizedPrompt}
                                            className="pointer-events-auto inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-200 hover:bg-emerald-500/20 transition-colors"
                                            title="复制优化后提示词"
                                        >
                                            {copiedPreviewMessageId === hoverPreview.messageId ? <Check size={11} /> : <Copy size={11} />}
                                            {copiedPreviewMessageId === hoverPreview.messageId ? '已复制' : '复制'}
                                        </button>
                                    )}
                                </div>
                                {hoverPreview.optimizedPrompt ? (
                                    <p className="mt-1 text-xs text-emerald-100 whitespace-pre-wrap break-words">
                                        {hoverPreview.optimizedPrompt}
                                    </p>
                                ) : (
                                    <p className="mt-1 text-xs text-slate-500 italic">未返回优化后的提示词</p>
                                )}
                            </div>
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
        filteredHistoryBatches,
        showFavoritesOnly,
        activeBatchMessage?.id,
        openActionMenu,
        actionMenuPosition,
        hoverPreview,
        hoverPreviewPosition,
        hoverPreviewSize,
        isResizingPreview,
        copiedPreviewMessageId,
        showHoverPreview,
        scheduleHideHoverPreview,
        clearHidePreviewTimer,
        handleCopyOptimizedPrompt,
        handlePreviewResizeMouseDown,
        closeHoverPreview,
        isFavorite,
        isFavoritePending,
        toggleFavorite,
        deleteItem
    ]);

    // ✅ 主区域：两栏布局（结果显示 + 控制面板）
    // 注意：GenViewLayout 的 main 容器已有 overflow-hidden，这里不需要重复
    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            {/* ========== 左侧：结果显示区 ========== */}
            <div className="flex-1 w-full h-full select-none flex flex-col relative">
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

                {/* 主图片显示区域 - 简化布局，居中显示 */}
                {isLoading ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl">
                            <div className="relative">
                                <div className="w-20 h-20 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin"></div>
                                <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-emerald-400 font-bold">GEN</div>
                            </div>
                            <div className="text-center space-y-2">
                                <p className="text-slate-200 font-medium text-lg">生成中...</p>
                                <p className="text-slate-500 text-sm">这可能需要几秒钟</p>
                            </div>
                        </div>
                    </div>
                ) : isBatchError ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30">
                            <AlertCircle size={48} className="text-red-500 opacity-80" />
                            <div>
                                <h3 className="text-lg font-bold text-slate-200">生成失败</h3>
                                <p className="text-sm text-red-400 mt-2 max-w-md">{activeBatchMessage?.content || "未知错误"}</p>
                            </div>
                        </div>
                    </div>
                ) : displayImages.length > 0 ? (
                    <>
                        {/* 旋转木马视图（直接支持缩放） */}
                        <div 
                            className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden"
                            onWheel={canvas.handleWheel}
                        >
                            {/* 主图展示区 - 支持拖拽 */}
                            <div 
                                className="flex-1 w-full flex items-center justify-center relative px-16 overflow-hidden"
                                onMouseDown={canvas.handleMouseDown}
                                onMouseMove={canvas.handleMouseMove}
                                onMouseUp={canvas.handleMouseUp}
                                onMouseLeave={canvas.handleMouseUp}
                                style={{ cursor: canvas.isDragging ? 'grabbing' : (canvas.zoom > 1 ? 'grab' : 'default') }}
                            >
                                <ImageCarouselArrows
                                    itemCount={displayImages.length}
                                    onPrev={handleCarouselPrev}
                                    onNext={handleCarouselNext}
                                />
                                
                                {/* 当前图片 */}
                                <div className="relative group max-w-full max-h-full flex items-center justify-center">
                                    {displayImages[carouselIndex]?.url ? (
                                        <img
                                            src={displayImages[carouselIndex].url}
                                            className="block max-h-[70vh] max-w-full object-contain rounded-2xl shadow-2xl border border-slate-800/50 select-none"
                                            style={canvas.canvasStyle}
                                            onDoubleClick={() => onImageClick(displayImages[carouselIndex].url!)}
                                            alt={`生成图片 ${carouselIndex + 1}`}
                                            draggable={false}
                                        />
                                    ) : (
                                        <div className="w-64 h-64 flex items-center justify-center text-slate-600 bg-slate-900 rounded-2xl">
                                            <ImageIcon size={48} className="opacity-50" />
                                        </div>
                                    )}
                                    {/* 悬浮操作按钮（包含缩放控制） */}
                                    <ImageCanvasControls
                                        variant="canvas"
                                        mode="image-gen"
                                        modeAware={false}
                                        className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                                        zoom={canvas.zoom}
                                        onZoomIn={canvas.handleZoomIn}
                                        onZoomOut={canvas.handleZoomOut}
                                        onReset={canvas.handleReset}
                                        onEdit={onEditImage ? () => onEditImage(displayImages[carouselIndex].url!, displayImages[carouselIndex]) : undefined}
                                        onExpand={onExpandImage ? () => onExpandImage(displayImages[carouselIndex].url!, displayImages[carouselIndex]) : undefined}
                                        onFullscreen={() => onImageClick(displayImages[carouselIndex].url!)}
                                        downloadUrl={displayImages[carouselIndex].url}
                                    />
                                </div>
                                
                                {/* 缩放提示（仅在缩放时显示） */}
                                {canvas.zoom !== 1 && (
                                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-slate-400 text-xs bg-black/60 px-3 py-1.5 rounded-full backdrop-blur pointer-events-none">
                                        {Math.round(canvas.zoom * 100)}% · 拖拽移动 · 双击全屏
                                    </div>
                                )}
                            </div>
                            
                            {/* 底部缩略图导航 */}
                            <ImageCarouselThumbnails
                                items={carouselItems}
                                currentIndex={carouselIndex}
                                onSelect={handleCarouselSelect}
                                accentTone="emerald"
                                panelClassName="flex items-center gap-3 py-4 px-4"
                                counterClassName="ml-2 text-sm text-slate-400 font-mono"
                            />
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                            <ImageIcon size={48} className="opacity-20" />
                            <div>
                                <h3 className="text-xl font-bold text-slate-500 mb-2">Image Generator</h3>
                                <p className="text-sm opacity-60">在右侧输入提示词，设置参数后点击生成</p>
                            </div>
                        </div>
                    </div>
                )}

                {/* 批次信息提示 */}
                {displayImages.length > 1 && (
                    <div className="absolute top-4 left-4 z-10 animate-[fadeIn_0.3s_ease-out] pointer-events-none">
                        <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-xl">
                            <Grid size={14} className="text-emerald-400" />
                            批次结果 ({displayImages.length})
                        </div>
                    </div>
                )}
            </div>

            {/* ========== 中间：控制面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-emerald-400" />
                        <span className="text-xs font-bold text-white">生成参数</span>
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
                        mode="image-gen"
                        providerId={providerId || 'google'}
                        currentModel={activeModelConfig}
                        controls={controls}
                        maxImageCount={maxImageCount}
                    />
                </div>

                {/* 底部固定区：提示词 + 生成按钮 */}
                <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
                    {/* 提示词输入 - 自动调整高度 */}
                    <textarea
                        ref={textareaRef}
                        value={prompt}
                        onChange={(e) => {
                            setPrompt(e.target.value);
                            // 自动调整高度
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 300) + 'px';
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder="描述你想要生成的图片..."
                        className="w-full min-h-[80px] max-h-[300px] bg-slate-800/80 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
                    />

                    {/* 生成按钮 */}
                    <button
                        onClick={handleGenerate}
                        disabled={!prompt.trim() || isLoading}
                        className="w-full py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isLoading ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                生成中...
                            </>
                        ) : (
                            <>
                                <Sparkles size={18} />
                                生成图片
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    ), [
        isLoading,
        isBatchError,
        displayImages,
        activeBatchMessage,
        onImageClick,
        onEditImage,
        onExpandImage,
        prompt,
        controls,
        handleGenerate,
        handleKeyDown,
        maxImageCount,
        resetParams,
        providerId,
        activeModelConfig,
        carouselIndex,
        carouselItems,
        handleCarouselPrev,
        handleCarouselNext,
        handleCarouselSelect,
        canvas
    ]);

    return (
        <GenViewLayout
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            sidebarTitle="History"
            sidebarHeaderIcon={sidebarHeaderIcon}
            sidebarExtraHeader={sidebarExtraHeader}
            sidebar={sidebarContent}
            main={mainContent}
        />
    );
};

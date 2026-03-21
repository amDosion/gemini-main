import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import {
    Video as VideoIcon,
    Check,
    Clock,
    Copy,
    AlertCircle,
    Download,
    Maximize2,
    Film,
    SlidersHorizontal,
    RotateCcw,
    Layers,
    Star,
    FolderOpen,
    Trash2,
    Wand2,
    Play,
    Pause,
    Volume2,
    VolumeX,
} from 'lucide-react';
import { GenViewLayout } from '../common/GenViewLayout';
import { useControlsState } from '../../hooks/useControlsState';
import { useModeControlsSchema } from '../../hooks/useModeControlsSchema';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';
import { buildVideoControlContract, isVideoControlSelectionValid } from '../../utils/videoControlSchema';
import { useHistoryListActions } from '../../hooks/useHistoryListActions';

interface VideoGenViewProps {
    messages: Message[];
    setAppMode: (mode: AppMode) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    visibleModels?: ModelConfig[];
    allVisibleModels?: ModelConfig[];
    initialPrompt?: string;
    providerId?: string;
    sessionId?: string | null;
    onDeleteMessage?: (messageId: string) => void;
}

const extractHistoryPrompts = (msg: Message): { originalPrompt: string; optimizedPrompt: string } => {
    const rawContent = (msg.content || '').trim();
    const attachmentEnhancedPrompt = msg.attachments?.find(att => att.enhancedPrompt?.trim())?.enhancedPrompt?.trim();

    let originalPrompt = rawContent;
    let optimizedPrompt = msg.enhancedPrompt?.trim() || attachmentEnhancedPrompt || '';

    const legacyPromptMatch = rawContent.match(/^Video generated for:\s*"([\s\S]*)"$/);
    if (legacyPromptMatch) {
        originalPrompt = (legacyPromptMatch[1] || '').trim();
    }

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
        originalPrompt: originalPrompt || 'Generated Video Batch',
        optimizedPrompt
    };
};

const extractVideoHistoryMeta = (msg: Message): {
    extensionCount: number;
    totalDurationSeconds: number | null;
    strategyLabel: string | null;
    subtitleLabel: string | null;
    subtitleCount: number;
} => {
    const extensionCount = Number.isFinite(msg.videoExtensionApplied)
        ? Number(msg.videoExtensionApplied)
        : Number.isFinite(msg.videoExtensionCount)
            ? Number(msg.videoExtensionCount)
            : 0;
    const totalDurationSeconds = Number.isFinite(msg.totalDurationSeconds)
        ? Number(msg.totalDurationSeconds)
        : null;
    const continuationStrategy = String(msg.continuationStrategy || '').trim();

    let strategyLabel: string | null = null;
    if (continuationStrategy === 'video_extension_chain') {
        strategyLabel = '官方延长';
    } else if (continuationStrategy === 'video_extension') {
        strategyLabel = '视频续接';
    } else if (continuationStrategy === 'last_frame_bridge') {
        strategyLabel = '末帧桥接';
    }

    const subtitleMode = String(msg.subtitleMode || '').trim().toLowerCase();
    const subtitleCount = Array.isArray(msg.subtitleAttachmentIds) ? msg.subtitleAttachmentIds.length : 0;
    let subtitleLabel: string | null = null;
    if (subtitleMode === 'both' || subtitleMode === 'vtt' || subtitleMode === 'srt') {
        subtitleLabel = '字幕';
    } else if (subtitleCount > 0) {
        subtitleLabel = '字幕附件';
    }

    return {
        extensionCount: extensionCount > 0 ? extensionCount : 0,
        totalDurationSeconds,
        strategyLabel,
        subtitleLabel,
        subtitleCount,
    };
};

interface ActionMenuAnchor {
    messageId: string;
    anchorX: number;
    anchorY: number;
}

interface ActionMenuPosition {
    top: number;
    left: number;
}

interface HoverPromptPreview {
    messageId: string;
    anchorX: number;
    anchorY: number;
    originalPrompt: string;
    optimizedPrompt: string;
    extensionCount: number;
    totalDurationSeconds: number | null;
    strategyLabel: string | null;
    subtitleLabel: string | null;
    subtitleCount: number;
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

export const VideoGenView: React.FC<VideoGenViewProps> = ({
    messages,
    setAppMode,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    visibleModels = [],
    allVisibleModels = [],
    initialPrompt,
    providerId,
    sessionId,
    onDeleteMessage,
}) => {
    const resolvedProviderId = providerId || 'google';

    const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
    const [activeVideoUrl, setActiveVideoUrl] = useState<string | null>(null);
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
    const [hoverPreview, setHoverPreview] = useState<HoverPromptPreview | null>(null);
    const [hoverPreviewPosition, setHoverPreviewPosition] = useState<HoverPromptPreviewPosition | null>(null);
    const [hoverPreviewSize, setHoverPreviewSize] = useState<HoverPromptPreviewSize | null>(null);
    const [isResizingPreview, setIsResizingPreview] = useState(false);
    const [copiedPreviewMessageId, setCopiedPreviewMessageId] = useState<string | null>(null);
    const [openActionMenu, setOpenActionMenu] = useState<ActionMenuAnchor | null>(null);
    const [actionMenuPosition, setActionMenuPosition] = useState<ActionMenuPosition | null>(null);
    const hidePreviewTimerRef = useRef<number | null>(null);
    const copiedResetTimerRef = useRef<number | null>(null);
    const hoverPreviewPanelRef = useRef<HTMLDivElement | null>(null);
    const actionMenuPanelRef = useRef<HTMLDivElement | null>(null);
    const historyItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
    const previewResizeHandlersRef = useRef<{
        onMouseMove?: (event: MouseEvent) => void;
        onMouseUp?: () => void;
    }>({});
    const activeVideoRef = useRef<HTMLVideoElement | null>(null);
    const activeVideoStageRef = useRef<HTMLDivElement | null>(null);
    const videoProgressAnimationFrameRef = useRef<number | null>(null);
    const videoSeekInputRef = useRef<HTMLInputElement | null>(null);
    const videoProgressFillRef = useRef<HTMLDivElement | null>(null);
    const videoProgressThumbRef = useRef<HTMLDivElement | null>(null);
    const videoCurrentTimeLabelRef = useRef<HTMLSpanElement | null>(null);
    const [isVideoPlaying, setIsVideoPlaying] = useState(false);
    const [videoDuration, setVideoDuration] = useState(0);
    const [isVideoFullscreen, setIsVideoFullscreen] = useState(false);
    const [videoVolume, setVideoVolume] = useState(1);
    const [isVideoMuted, setIsVideoMuted] = useState(false);

    const videoMode: AppMode = 'video-gen';
    const controls = useControlsState(videoMode, activeModelConfig);
    const {
        schema: videoControlsSchema,
        loading: isLoadingVideoControlsSchema,
        error: videoControlsSchemaError,
    } = useModeControlsSchema(resolvedProviderId, videoMode, activeModelConfig?.id);
    const videoControlContract = useMemo(
        () => buildVideoControlContract(videoControlsSchema),
        [videoControlsSchema]
    );
    const isVideoControlsReady = useMemo(() => {
        if (isLoadingVideoControlsSchema || videoControlsSchemaError || !videoControlContract.schemaReady) {
            return false;
        }
        return isVideoControlSelectionValid(videoControlContract, {
            aspectRatio: controls.aspectRatio,
            resolution: controls.resolution,
            videoSeconds: controls.videoSeconds,
            videoExtensionCount: controls.videoExtensionCount,
        });
    }, [
        controls.aspectRatio,
        controls.resolution,
        controls.videoSeconds,
        controls.videoExtensionCount,
        isLoadingVideoControlsSchema,
        videoControlsSchemaError,
        videoControlContract,
    ]);
    const videoControlsStatusMessage = useMemo(() => {
        if (videoControlsSchemaError) {
            return '视频参数加载失败，请检查后端 controls 接口返回。';
        }
        if (!videoControlsSchema || isLoadingVideoControlsSchema) {
            return '正在从后端加载视频参数…';
        }
        if (!isVideoControlsReady) {
            return '正在同步视频参数，请稍候再生成。';
        }
        return null;
    }, [
        isLoadingVideoControlsSchema,
        isVideoControlsReady,
        videoControlsSchema,
        videoControlsSchemaError,
    ]);

    useEffect(() => {
        if (!videoControlContract.schemaReady) {
            return;
        }

        const validExtensionCountsForSeconds =
            videoControlContract.validVideoExtensionCountsBySeconds[controls.videoSeconds] ??
            videoControlContract.validVideoExtensionCounts;

        if (!videoControlContract.validAspectRatios.includes(controls.aspectRatio)) {
            controls.setAspectRatio(videoControlContract.defaultAspectRatio);
        }
        if (!videoControlContract.validResolutionTiers.includes(controls.resolution)) {
            controls.setResolution(videoControlContract.defaultResolution);
        }
        if (
            validExtensionCountsForSeconds.length > 0 &&
            !validExtensionCountsForSeconds.includes(controls.videoExtensionCount)
        ) {
            controls.setVideoExtensionCount(videoControlContract.defaultVideoExtensionCount);
        }
        if (
            videoControlContract.validSeconds.length > 0 &&
            !videoControlContract.validSeconds.includes(controls.videoSeconds)
        ) {
            controls.setVideoSeconds(videoControlContract.defaultVideoSeconds);
        }
        if (
            videoControlContract.validStoryboardShotSeconds.length > 0 &&
            !videoControlContract.validStoryboardShotSeconds.includes(controls.storyboardShotSeconds)
        ) {
            controls.setStoryboardShotSeconds(videoControlContract.defaultStoryboardShotSeconds);
        }
        if (
            videoControlContract.validPersonGenerationValues.length > 0 &&
            controls.personGeneration &&
            !videoControlContract.validPersonGenerationValues.includes(controls.personGeneration)
        ) {
            controls.setPersonGeneration(videoControlContract.defaultPersonGeneration);
        }
        if (
            videoControlContract.validSubtitleModes.length > 0 &&
            controls.subtitleMode &&
            !videoControlContract.validSubtitleModes.includes(controls.subtitleMode)
        ) {
            controls.setSubtitleMode(videoControlContract.defaultSubtitleMode);
        }
        if (
            videoControlContract.validSubtitleLanguages.length > 0 &&
            controls.subtitleLanguage &&
            !videoControlContract.validSubtitleLanguages.includes(controls.subtitleLanguage)
        ) {
            controls.setSubtitleLanguage(videoControlContract.defaultSubtitleLanguage);
        }
        if (videoControlContract.fieldPolicies.enhancePromptMandatory && !controls.enhancePrompt) {
            controls.setEnhancePrompt(videoControlContract.defaultEnhancePrompt);
        }
        if (!videoControlContract.fieldPolicies.generateAudioAvailable && controls.generateAudio) {
            controls.setGenerateAudio(videoControlContract.defaultGenerateAudio);
        }
    }, [
        controls.aspectRatio,
        controls.enhancePrompt,
        controls.generateAudio,
        controls.personGeneration,
        controls.resolution,
        controls.storyboardShotSeconds,
        controls.subtitleLanguage,
        controls.subtitleMode,
        controls.videoSeconds,
        controls.videoExtensionCount,
        controls.setAspectRatio,
        controls.setEnhancePrompt,
        controls.setGenerateAudio,
        controls.setPersonGeneration,
        controls.setResolution,
        controls.setStoryboardShotSeconds,
        controls.setSubtitleLanguage,
        controls.setSubtitleMode,
        controls.setVideoSeconds,
        controls.setVideoExtensionCount,
        videoControlContract.defaultAspectRatio,
        videoControlContract.defaultEnhancePrompt,
        videoControlContract.defaultGenerateAudio,
        videoControlContract.defaultPersonGeneration,
        videoControlContract.defaultResolution,
        videoControlContract.defaultStoryboardShotSeconds,
        videoControlContract.defaultSubtitleLanguage,
        videoControlContract.defaultSubtitleMode,
        videoControlContract.defaultVideoSeconds,
        videoControlContract.defaultVideoExtensionCount,
        videoControlContract.fieldPolicies.enhancePromptMandatory,
        videoControlContract.fieldPolicies.generateAudioAvailable,
        videoControlContract.schemaReady,
        videoControlContract.validAspectRatios,
        videoControlContract.validPersonGenerationValues,
        videoControlContract.validResolutionTiers,
        videoControlContract.validStoryboardShotSeconds,
        videoControlContract.validSeconds,
        videoControlContract.validSubtitleLanguages,
        videoControlContract.validSubtitleModes,
        videoControlContract.validVideoExtensionCounts,
        videoControlContract.validVideoExtensionCountsBySeconds,
    ]);

    const resetParams = useCallback(() => {
        controls.setAspectRatio(videoControlContract.defaultAspectRatio);
        controls.setResolution(videoControlContract.defaultResolution);
        controls.setVideoSeconds(videoControlContract.defaultVideoSeconds);
        controls.setVideoExtensionCount(videoControlContract.defaultVideoExtensionCount);
        controls.setStoryboardShotSeconds(videoControlContract.defaultStoryboardShotSeconds);
        controls.setGenerateAudio(videoControlContract.defaultGenerateAudio);
        controls.setPersonGeneration(videoControlContract.defaultPersonGeneration);
        controls.setSubtitleMode(videoControlContract.defaultSubtitleMode);
        controls.setSubtitleLanguage(videoControlContract.defaultSubtitleLanguage);
        controls.setSubtitleScript(videoControlContract.defaultSubtitleScript);
        controls.setStoryboardPrompt(videoControlContract.defaultStoryboardPrompt);
        controls.setNegativePrompt(videoControlContract.defaultNegativePrompt);
        controls.setSeed(videoControlContract.defaultSeed);
        controls.setEnhancePrompt(videoControlContract.defaultEnhancePrompt);
    }, [
        controls,
        videoControlContract.defaultAspectRatio,
        videoControlContract.defaultEnhancePrompt,
        videoControlContract.defaultGenerateAudio,
        videoControlContract.defaultNegativePrompt,
        videoControlContract.defaultPersonGeneration,
        videoControlContract.defaultResolution,
        videoControlContract.defaultSeed,
        videoControlContract.defaultStoryboardPrompt,
        videoControlContract.defaultStoryboardShotSeconds,
        videoControlContract.defaultSubtitleLanguage,
        videoControlContract.defaultSubtitleMode,
        videoControlContract.defaultSubtitleScript,
        videoControlContract.defaultVideoSeconds,
        videoControlContract.defaultVideoExtensionCount,
    ]);

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

    const historyBatches = useMemo(() => {
        return messages
            .filter((message) =>
                message.role === Role.MODEL &&
                (((message.attachments && message.attachments.length > 0) || message.isError))
            )
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
        deleteItem,
    } = useHistoryListActions({
        sessionId,
        items: historyBatches,
        onDeleteItem: onDeleteMessage,
    });

    const activeBatchMessage = useMemo(() => {
        if (selectedMsgId) {
            return filteredHistoryBatches.find((message) => message.id === selectedMsgId);
        }
        return filteredHistoryBatches[0];
    }, [selectedMsgId, filteredHistoryBatches]);

    const displayVideos = useMemo(
        () => (activeBatchMessage?.attachments || []).filter((attachment) => attachment.mimeType?.startsWith('video/')),
        [activeBatchMessage?.attachments]
    );
    const subtitleAttachments = useMemo(
        () => (activeBatchMessage?.attachments || []).filter((attachment) =>
            attachment.mimeType === 'text/vtt' || attachment.mimeType === 'application/x-subrip'
        ),
        [activeBatchMessage?.attachments]
    );
    const activeSubtitleTrack = useMemo(
        () => subtitleAttachments.find((attachment) => attachment.mimeType === 'text/vtt' && attachment.url) || null,
        [subtitleAttachments]
    );
    const downloadableSubtitleAttachment = useMemo(
        () => subtitleAttachments.find((attachment) => attachment.url) || null,
        [subtitleAttachments]
    );

    useEffect(() => {
        if (filteredHistoryBatches.length === 0) {
            setSelectedMsgId(null);
            return;
        }

        if (selectedMsgId && filteredHistoryBatches.some((message) => message.id === selectedMsgId)) {
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
                behavior: 'smooth',
            });
        });
    }, [selectedMsgId]);

    useEffect(() => {
        if (loadingState === 'loading') {
            setSelectedMsgId(null);
            setIsMobileHistoryOpen(false);
            setOpenActionMenu(null);
            setActionMenuPosition(null);
            closeHoverPreview();
        }
    }, [closeHoverPreview, loadingState]);

    useEffect(() => {
        const nextVideoUrl = displayVideos.find((attachment) => attachment.url)?.url || null;
        const hasCurrentVideo = displayVideos.some((attachment) => attachment.url === activeVideoUrl);
        if (!hasCurrentVideo) {
            setActiveVideoUrl(nextVideoUrl);
        }
    }, [activeVideoUrl, displayVideos]);

    useEffect(() => {
        if (!openActionMenu) return;

        const handleOutsideClick = (event: MouseEvent) => {
            const target = event.target as Node | null;
            if (!target) return;
            if (actionMenuPanelRef.current && actionMenuPanelRef.current.contains(target)) {
                return;
            }
            if (target instanceof Element && target.closest('[data-history-action-trigger]')) {
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
        event: React.MouseEvent<HTMLDivElement>,
        messageId: string,
        originalPrompt: string,
        optimizedPrompt: string,
        videoMeta: {
            extensionCount: number;
            totalDurationSeconds: number | null;
            strategyLabel: string | null;
            subtitleLabel: string | null;
            subtitleCount: number;
        }
    ) => {
        if (window.innerWidth < 768) return;
        clearHidePreviewTimer();
        setOpenActionMenu(null);
        setActionMenuPosition(null);

        const rect = event.currentTarget.getBoundingClientRect();
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
            optimizedPrompt,
            extensionCount: videoMeta.extensionCount,
            totalDurationSeconds: videoMeta.totalDurationSeconds,
            strategyLabel: videoMeta.strategyLabel,
            subtitleLabel: videoMeta.subtitleLabel,
            subtitleCount: videoMeta.subtitleCount,
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
    }, [clearHidePreviewTimer, hoverPreview, hoverPreviewPosition?.left, hoverPreviewPosition?.top, hoverPreviewSize?.height, hoverPreviewSize?.width, stopPreviewResize]);

    const handleCopyOptimizedPrompt = useCallback(async () => {
        if (!hoverPreview?.optimizedPrompt) return;

        const textToCopy = hoverPreview.optimizedPrompt;

        const fallbackCopy = () => {
            const textarea = document.createElement('textarea');
            textarea.value = textToCopy;
            textarea.style.position = 'fixed';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
        };

        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(textToCopy);
            } else {
                fallbackCopy();
            }
            setCopiedPreviewMessageId(hoverPreview.messageId);
            clearCopiedResetTimer();
            copiedResetTimerRef.current = window.setTimeout(() => {
                setCopiedPreviewMessageId(null);
                copiedResetTimerRef.current = null;
            }, 1500);
        } catch {
            try {
                fallbackCopy();
                setCopiedPreviewMessageId(hoverPreview.messageId);
                clearCopiedResetTimer();
                copiedResetTimerRef.current = window.setTimeout(() => {
                    setCopiedPreviewMessageId(null);
                    copiedResetTimerRef.current = null;
                }, 1500);
            } catch (error) {
                console.error('[VideoGenView] 复制优化提示词失败:', error);
            }
        }
    }, [clearCopiedResetTimer, hoverPreview]);

    const handleDownload = useCallback((url: string) => {
        const link = document.createElement('a');
        link.href = url;
        link.download = `gemini-video-${Date.now()}.mp4`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }, []);

    const isInteractiveKeyboardTarget = useCallback((target: EventTarget | null): boolean => {
        if (!(target instanceof HTMLElement)) {
            return false;
        }
        const tagName = target.tagName;
        const isFormInput = tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT';
        const isEditable = target.isContentEditable || Boolean(target.closest('[contenteditable="true"]'));
        const isActionable = tagName === 'BUTTON' || tagName === 'A';
        return isFormInput || isEditable || isActionable;
    }, []);

    const activateHistoryMessage = useCallback((message: Message | undefined | null) => {
        if (!message) {
            return;
        }
        setSelectedMsgId(message.id);
        const nextVideo = (message.attachments || []).find(
            (attachment) => attachment.mimeType?.startsWith('video/') && attachment.url
        );
        setActiveVideoUrl(nextVideo?.url || null);
    }, []);

    const handleSend = useCallback((text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
        onSend(text, options, attachments, videoMode);
    }, [onSend, videoMode]);

    const toggleActiveVideoPlayback = useCallback(async () => {
        const video = activeVideoRef.current;
        if (!video) {
            return;
        }

        try {
            if (video.paused) {
                await video.play();
            } else {
                video.pause();
            }
        } catch (error) {
            console.error('[VideoGenView] 切换视频播放状态失败:', error);
        }
    }, []);

    const handleToggleFullscreen = useCallback(async () => {
        const target = activeVideoStageRef.current;
        if (!target || typeof document === 'undefined') {
            return;
        }

        const currentFullscreenElement = document.fullscreenElement;
        try {
            if (currentFullscreenElement === target) {
                if (typeof document.exitFullscreen === 'function') {
                    await document.exitFullscreen();
                }
                return;
            }
            if (typeof target.requestFullscreen === 'function') {
                await target.requestFullscreen();
            }
        } catch (error) {
            console.error('[VideoGenView] 切换全屏失败:', error);
        }
    }, []);

    const formatVideoTime = useCallback((timeInSeconds: number) => {
        if (!Number.isFinite(timeInSeconds) || timeInSeconds < 0) {
            return '0:00.000';
        }
        const totalMilliseconds = Math.floor(timeInSeconds * 1000);
        const hours = Math.floor(totalMilliseconds / 3_600_000);
        const minutes = Math.floor((totalMilliseconds % 3_600_000) / 60_000);
        const seconds = Math.floor((totalMilliseconds % 60_000) / 1000);
        const milliseconds = totalMilliseconds % 1000;

        if (hours > 0) {
            return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`;
        }

        return `${minutes}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`;
    }, []);

    const handleActiveVideoSeek = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        const video = activeVideoRef.current;
        if (!video) {
            return;
        }
        const nextTime = Number(event.target.value);
        video.currentTime = nextTime;
        const duration = video.duration || videoDuration || 0;
        const ratio = duration > 0 ? nextTime / duration : 0;
        if (videoProgressFillRef.current) {
            videoProgressFillRef.current.style.width = `${Math.max(0, Math.min(1, ratio)) * 100}%`;
        }
        if (videoProgressThumbRef.current) {
            videoProgressThumbRef.current.style.left = `${Math.max(0, Math.min(1, ratio)) * 100}%`;
        }
        if (videoCurrentTimeLabelRef.current) {
            videoCurrentTimeLabelRef.current.textContent = formatVideoTime(nextTime);
        }
    }, [formatVideoTime, videoDuration]);

    const handleActiveVideoVolumeChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        const nextVolume = Number(event.target.value);
        setVideoVolume(nextVolume);
        setIsVideoMuted(nextVolume <= 0.001);
    }, []);

    const handleToggleMute = useCallback(() => {
        setIsVideoMuted((previous) => !previous);
    }, []);

    const stopVideoProgressAnimation = useCallback(() => {
        if (videoProgressAnimationFrameRef.current !== null) {
            window.cancelAnimationFrame(videoProgressAnimationFrameRef.current);
            videoProgressAnimationFrameRef.current = null;
        }
    }, []);

    const syncVideoProgressUi = useCallback((currentTime: number, duration: number) => {
        const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : 0;
        const safeCurrentTime = Number.isFinite(currentTime) && currentTime > 0 ? currentTime : 0;
        const ratio = safeDuration > 0 ? safeCurrentTime / safeDuration : 0;
        const progressPercent = `${Math.max(0, Math.min(1, ratio)) * 100}%`;

        if (videoSeekInputRef.current) {
            videoSeekInputRef.current.value = String(safeCurrentTime);
        }
        if (videoProgressFillRef.current) {
            videoProgressFillRef.current.style.width = progressPercent;
        }
        if (videoProgressThumbRef.current) {
            videoProgressThumbRef.current.style.left = progressPercent;
        }
        if (videoCurrentTimeLabelRef.current) {
            videoCurrentTimeLabelRef.current.textContent = formatVideoTime(safeCurrentTime);
        }
    }, [formatVideoTime]);

    const startVideoProgressAnimation = useCallback(() => {
        stopVideoProgressAnimation();

        const syncProgress = () => {
            const video = activeVideoRef.current;
            if (!video) {
                videoProgressAnimationFrameRef.current = null;
                return;
            }

            syncVideoProgressUi(video.currentTime || 0, video.duration || 0);

            if (!video.paused && !video.ended) {
                videoProgressAnimationFrameRef.current = window.requestAnimationFrame(syncProgress);
            } else {
                videoProgressAnimationFrameRef.current = null;
            }
        };

        videoProgressAnimationFrameRef.current = window.requestAnimationFrame(syncProgress);
    }, [stopVideoProgressAnimation, syncVideoProgressUi]);

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
    }, [computeHoverPreviewPosition, hoverPreview, hoverPreviewSize]);

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
    }, [closeHoverPreview, hoverPreview]);

    useEffect(() => {
        return () => {
            clearHidePreviewTimer();
            clearCopiedResetTimer();
            stopPreviewResize();
            stopVideoProgressAnimation();
        };
    }, [clearCopiedResetTimer, clearHidePreviewTimer, stopPreviewResize, stopVideoProgressAnimation]);

    useEffect(() => {
        if (filteredHistoryBatches.length === 0) return;

        const handleHistoryNavigation = (event: KeyboardEvent) => {
            if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
            if (isInteractiveKeyboardTarget(event.target)) {
                return;
            }

            event.preventDefault();
            closeHoverPreview();
            setOpenActionMenu(null);
            setActionMenuPosition(null);

            setSelectedMsgId((prevId) => {
                const currentIndex = prevId ? filteredHistoryBatches.findIndex((message) => message.id === prevId) : 0;
                const safeCurrentIndex = currentIndex >= 0 ? currentIndex : 0;
                const delta = event.key === 'ArrowUp' ? -1 : 1;
                const nextIndex = Math.max(0, Math.min(filteredHistoryBatches.length - 1, safeCurrentIndex + delta));
                const nextMessage = filteredHistoryBatches[nextIndex];
                if (nextMessage) {
                    const nextVideo = (nextMessage.attachments || []).find(
                        (attachment) => attachment.mimeType?.startsWith('video/') && attachment.url
                    );
                    setActiveVideoUrl(nextVideo?.url || null);
                    return nextMessage.id;
                }
                return prevId;
            });
        };

        window.addEventListener('keydown', handleHistoryNavigation);
        return () => {
            window.removeEventListener('keydown', handleHistoryNavigation);
        };
    }, [closeHoverPreview, filteredHistoryBatches, isInteractiveKeyboardTarget]);

    useEffect(() => {
        const handleVideoKeyboardShortcut = (event: KeyboardEvent) => {
            if (event.key !== ' ' || !activeVideoUrl || !activeVideoRef.current) {
                return;
            }
            if (isInteractiveKeyboardTarget(event.target)) {
                return;
            }

            event.preventDefault();
            void toggleActiveVideoPlayback();
        };

        window.addEventListener('keydown', handleVideoKeyboardShortcut);
        return () => {
            window.removeEventListener('keydown', handleVideoKeyboardShortcut);
        };
    }, [activeVideoUrl, isInteractiveKeyboardTarget, toggleActiveVideoPlayback]);

    useEffect(() => {
        if (typeof document === 'undefined') {
            return;
        }

        const syncFullscreenState = () => {
            setIsVideoFullscreen(document.fullscreenElement === activeVideoStageRef.current);
        };

        syncFullscreenState();
        document.addEventListener('fullscreenchange', syncFullscreenState);
        return () => {
            document.removeEventListener('fullscreenchange', syncFullscreenState);
        };
    }, []);

    useEffect(() => {
        setIsVideoPlaying(false);
        setVideoDuration(0);
        stopVideoProgressAnimation();
        syncVideoProgressUi(0, 0);
    }, [activeVideoUrl, stopVideoProgressAnimation]);

    useEffect(() => {
        const video = activeVideoRef.current;
        if (!video) {
            return;
        }
        video.volume = videoVolume;
        video.muted = isVideoMuted;
    }, [isVideoMuted, videoVolume, activeVideoUrl]);

    useEffect(() => {
        if (!isVideoPlaying) {
            stopVideoProgressAnimation();
            return;
        }
        startVideoProgressAnimation();
        return () => {
            stopVideoProgressAnimation();
        };
    }, [isVideoPlaying, startVideoProgressAnimation, stopVideoProgressAnimation]);

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

    const sidebarContent = useMemo(() => (
        <div className="p-3 space-y-2.5">
            {filteredHistoryBatches.map((msg) => {
                const previewVideo = msg.attachments?.find((attachment) => attachment.mimeType?.startsWith('video/') && attachment.url);
                const previewImage = msg.attachments?.find((attachment) => attachment.mimeType?.startsWith('image/') && attachment.url);
                const previewCount = (msg.attachments || []).filter((attachment) =>
                    attachment.mimeType?.startsWith('video/') || attachment.mimeType?.startsWith('image/')
                ).length;
                const isSelected = activeBatchMessage?.id === msg.id;
                const { originalPrompt, optimizedPrompt } = extractHistoryPrompts(msg);
                const { extensionCount, totalDurationSeconds, strategyLabel, subtitleLabel, subtitleCount } = extractVideoHistoryMeta(msg);
                const favorited = isFavorite(msg.id);
                const isActionMenuOpen = openActionMenu?.messageId === msg.id;

                return (
                    <div
                        key={msg.id}
                        ref={(element) => {
                            historyItemRefs.current[msg.id] = element;
                        }}
                        className="group relative"
                    >
                        <div
                            className={`relative rounded-xl border cursor-pointer transition-all flex items-center gap-3 bg-slate-800/40 p-2 ${
                                isSelected ? 'ring-1 ring-indigo-500 border-transparent bg-slate-800' : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-800'
                            }`}
                            data-testid={`video-history-item-${msg.id}`}
                            onMouseEnter={(event) => showHoverPreview(event, msg.id, originalPrompt, optimizedPrompt, {
                                extensionCount,
                                totalDurationSeconds,
                                strategyLabel,
                                subtitleLabel,
                                subtitleCount,
                            })}
                            onMouseLeave={scheduleHideHoverPreview}
                            onClick={() => {
                                activateHistoryMessage(msg);
                                if (window.innerWidth < 768) {
                                    setIsMobileHistoryOpen(false);
                                }
                                setOpenActionMenu(null);
                                setActionMenuPosition(null);
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
                                ) : previewVideo?.url ? (
                                    <>
                                        <video
                                            src={previewVideo.url}
                                            className="w-full h-full object-cover"
                                            muted
                                            playsInline
                                            preload="metadata"
                                        />
                                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                            <div className="bg-black/50 p-1.5 rounded-full backdrop-blur-sm">
                                                <VideoIcon size={14} className="text-white" />
                                            </div>
                                        </div>
                                        {previewCount > 1 && (
                                            <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                                                <Layers size={10} /> {previewCount}
                                            </div>
                                        )}
                                    </>
                                ) : previewImage?.url ? (
                                    <>
                                        <img src={previewImage.url} className="w-full h-full object-cover transition-transform group-hover:scale-105" loading="lazy" alt="Video reference" />
                                        {previewCount > 1 && (
                                            <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                                                <Layers size={10} /> {previewCount}
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-slate-600">
                                        <Film size={18} className="opacity-50" />
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
                                        <span className="inline-flex items-center gap-1 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-indigo-300">
                                            <Wand2 size={10} />
                                            已优化
                                        </span>
                                    )}
                                </div>
                                {(extensionCount > 0 || totalDurationSeconds || strategyLabel || subtitleLabel) && (
                                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]">
                                        {extensionCount > 0 && (
                                            <span className="inline-flex items-center rounded-full border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-cyan-200">
                                                延长 {extensionCount} 次
                                            </span>
                                        )}
                                        {totalDurationSeconds && (
                                            <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-200">
                                                总时长 {totalDurationSeconds}s
                                            </span>
                                        )}
                                        {strategyLabel && (
                                            <span className="inline-flex items-center rounded-full border border-slate-600 bg-slate-800/80 px-1.5 py-0.5 text-slate-300">
                                                {strategyLabel}
                                            </span>
                                        )}
                                        {subtitleLabel && (
                                            <span className="inline-flex items-center rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-1.5 py-0.5 text-fuchsia-200">
                                                {subtitleLabel}
                                            </span>
                                        )}
                                    </div>
                                )}
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
                    {showFavoritesOnly ? '暂无收藏记录。' : 'No video history yet.'}
                </div>
            )}

            {openActionMenu && typeof document !== 'undefined' && createPortal(
                <div
                    ref={actionMenuPanelRef}
                    className="fixed z-[130] inline-flex flex-col gap-1 rounded-lg border border-slate-700 bg-slate-950/95 shadow-2xl backdrop-blur-md p-1"
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
            )}

            {hoverPreview && typeof document !== 'undefined' && createPortal(
                <div
                    ref={hoverPreviewPanelRef}
                    className="fixed z-[140] hidden md:block"
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
                                    <p className="text-[10px] uppercase tracking-wider text-indigo-400">优化后提示词</p>
                                    {hoverPreview.optimizedPrompt && (
                                        <button
                                            type="button"
                                            onClick={handleCopyOptimizedPrompt}
                                            className="pointer-events-auto inline-flex items-center gap-1 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-[10px] text-indigo-200 hover:bg-indigo-500/20 transition-colors"
                                            title="复制优化后提示词"
                                        >
                                            {copiedPreviewMessageId === hoverPreview.messageId ? <Check size={11} /> : <Copy size={11} />}
                                            {copiedPreviewMessageId === hoverPreview.messageId ? '已复制' : '复制'}
                                        </button>
                                    )}
                                </div>
                                {hoverPreview.optimizedPrompt ? (
                                    <p className="mt-1 text-xs text-indigo-100 whitespace-pre-wrap break-words">
                                        {hoverPreview.optimizedPrompt}
                                    </p>
                                ) : (
                                    <p className="mt-1 text-xs text-slate-500 italic">未返回优化后的提示词</p>
                                )}
                            </div>

                            {(hoverPreview.extensionCount > 0 || hoverPreview.totalDurationSeconds || hoverPreview.strategyLabel || hoverPreview.subtitleLabel) && (
                                <div className="mt-3 border-t border-slate-800 pt-3">
                                    <p className="text-[10px] uppercase tracking-wider text-cyan-400">视频信息</p>
                                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]">
                                        {hoverPreview.extensionCount > 0 && (
                                            <span className="inline-flex items-center rounded-full border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-cyan-200">
                                                延长 {hoverPreview.extensionCount} 次
                                            </span>
                                        )}
                                        {hoverPreview.totalDurationSeconds && (
                                            <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-200">
                                                总时长 {hoverPreview.totalDurationSeconds}s
                                            </span>
                                        )}
                                        {hoverPreview.strategyLabel && (
                                            <span className="inline-flex items-center rounded-full border border-slate-600 bg-slate-800/80 px-1.5 py-0.5 text-slate-300">
                                                {hoverPreview.strategyLabel}
                                            </span>
                                        )}
                                        {hoverPreview.subtitleLabel && (
                                            <span className="inline-flex items-center rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-1.5 py-0.5 text-fuchsia-200">
                                                {hoverPreview.subtitleLabel}
                                            </span>
                                        )}
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
        activeBatchMessage?.id,
        clearHidePreviewTimer,
        closeHoverPreview,
        copiedPreviewMessageId,
        deleteItem,
        favoriteCount,
        filteredHistoryBatches,
        activateHistoryMessage,
        handleCopyOptimizedPrompt,
        handlePreviewResizeMouseDown,
        historyBatches.length,
        isFavorite,
        isFavoritePending,
        isResizingPreview,
        loadingState,
        openActionMenu,
        hoverPreview,
        hoverPreviewPosition,
        hoverPreviewSize,
        sessionId,
        scheduleHideHoverPreview,
        showFavoritesOnly,
        showHoverPreview,
        setShowFavoritesOnly,
        toggleFavorite,
    ]);

    const isBatchError = activeBatchMessage?.isError;

    const mainContent = useMemo(() => (
        <div className="flex-1 flex flex-row h-full">
            <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-hidden bg-slate-950 relative">
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

                <div className="absolute top-4 left-4 z-10 pointer-events-none">
                    <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
                        <Film size={12} className="text-indigo-400" />
                        Video Workspace
                    </div>
                </div>

                {loadingState !== 'idle' ? (
                    <div
                        className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl relative z-10"
                        data-testid="video-main-loading-skeleton"
                    >
                        <div className="relative">
                            <div className="w-24 h-24 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                            <div className="absolute inset-0 flex items-center justify-center text-sm font-mono text-indigo-400 font-bold tracking-widest">VEO</div>
                        </div>
                        <div className="text-center">
                            <p className="text-slate-200 font-medium text-lg">生成中...</p>
                            <p className="text-slate-500 text-xs mt-1">视频生成通常会比图片更久一些。</p>
                        </div>
                    </div>
                ) : isBatchError ? (
                    <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30 relative z-10">
                        <AlertCircle size={48} className="text-red-500 opacity-80" />
                        <div>
                            <h3 className="text-lg font-bold text-slate-200">生成失败</h3>
                            <p className="text-sm text-red-400 mt-2 max-w-md">{activeBatchMessage?.content || '未知错误'}</p>
                        </div>
                    </div>
                ) : activeVideoUrl ? (
                    <div
                        ref={activeVideoStageRef}
                        data-testid="video-main-stage"
                        className="relative w-full max-w-5xl rounded-[28px] bg-slate-900/80 backdrop-blur-sm border border-slate-800/60 shadow-2xl overflow-hidden z-10"
                    >
                        <div className="relative group aspect-video bg-black flex items-center justify-center">
                            <video
                                ref={activeVideoRef}
                                data-testid="video-main-player"
                                src={activeVideoUrl}
                                autoPlay
                                loop
                                playsInline
                                preload="metadata"
                                className="h-full w-full object-contain shadow-2xl"
                                onClick={() => {
                                    void toggleActiveVideoPlayback();
                                }}
                                onDoubleClick={() => {
                                    void handleToggleFullscreen();
                                }}
                                onPlay={() => setIsVideoPlaying(true)}
                                onPause={() => {
                                    setIsVideoPlaying(false);
                                    const video = activeVideoRef.current;
                                    if (video) {
                                        syncVideoProgressUi(video.currentTime || 0, video.duration || 0);
                                    }
                                }}
                                onLoadedMetadata={(event) => {
                                    const nextDuration = event.currentTarget.duration || 0;
                                    setVideoDuration(nextDuration);
                                    Array.from(event.currentTarget.textTracks || []).forEach((track, index) => {
                                        track.mode = index === 0 ? 'showing' : 'disabled';
                                    });
                                    syncVideoProgressUi(event.currentTarget.currentTime || 0, nextDuration);
                                }}
                                onDurationChange={(event) => {
                                    const nextDuration = event.currentTarget.duration || 0;
                                    setVideoDuration(nextDuration);
                                    syncVideoProgressUi(event.currentTarget.currentTime || 0, nextDuration);
                                }}
                                onEnded={() => {
                                    setIsVideoPlaying(false);
                                    syncVideoProgressUi(0, videoDuration);
                                }}
                            >
                                {activeSubtitleTrack?.url && (
                                    <track
                                        key={activeSubtitleTrack.id}
                                        src={activeSubtitleTrack.url}
                                        kind="captions"
                                        srcLang={(activeSubtitleTrack.language || 'zh-CN').split('-')[0]}
                                        label={activeSubtitleTrack.language || '字幕'}
                                        default
                                    />
                                )}
                            </video>

                            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-black/15 to-black/40 opacity-0 transition-opacity duration-200 group-hover:opacity-100" />

                            <button
                                type="button"
                                onClick={() => {
                                    void toggleActiveVideoPlayback();
                                }}
                                className="absolute inset-0 z-10 flex items-center justify-center"
                                aria-label={isVideoPlaying ? '暂停视频' : '播放视频'}
                                title={isVideoPlaying ? '暂停视频' : '播放视频'}
                            >
                                <span className={`inline-flex h-16 w-16 items-center justify-center rounded-full border border-white/15 bg-black/55 text-white shadow-2xl backdrop-blur-md transition-all duration-200 ${
                                    isVideoPlaying ? 'opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100' : 'opacity-100'
                                }`}>
                                    {isVideoPlaying ? <Pause size={28} /> : <Play size={28} className="translate-x-0.5" />}
                                </span>
                            </button>
                        </div>

                        <div className="border-t border-slate-800/70 px-5 py-4 bg-slate-950/90">
                            <div className="flex items-center gap-3">
                                <button
                                    type="button"
                                    onClick={() => {
                                        void toggleActiveVideoPlayback();
                                    }}
                                    className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500 hover:bg-slate-800 transition-colors"
                                    title={isVideoPlaying ? '暂停视频' : '播放视频'}
                                    aria-label={isVideoPlaying ? '暂停视频' : '播放视频'}
                                >
                                    {isVideoPlaying ? <Pause size={18} /> : <Play size={18} className="translate-x-0.5" />}
                                </button>
                                <span ref={videoCurrentTimeLabelRef} className="w-[76px] text-right font-mono text-xs text-slate-400 tabular-nums">
                                    0:00.000
                                </span>
                                <div className="relative flex-1 h-8 flex items-center">
                                    <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-slate-800" />
                                    <div
                                        ref={videoProgressFillRef}
                                        className="absolute left-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-cyan-400"
                                        style={{ width: '0%' }}
                                    />
                                    <div
                                        ref={videoProgressThumbRef}
                                        className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/60 bg-white shadow-[0_0_0_4px_rgba(99,102,241,0.18)] pointer-events-none"
                                        style={{ left: '0%' }}
                                    />
                                    <input
                                        ref={videoSeekInputRef}
                                        type="range"
                                        min={0}
                                        max={Math.max(videoDuration, 0.001)}
                                        step="any"
                                        defaultValue={0}
                                        onChange={handleActiveVideoSeek}
                                        className="relative z-10 h-8 w-full cursor-pointer opacity-0"
                                        aria-label="视频进度"
                                    />
                                </div>
                                <span className="w-[76px] font-mono text-xs text-slate-400 tabular-nums">
                                    {formatVideoTime(videoDuration)}
                                </span>
                                <div className="mx-1 h-5 w-px bg-slate-800" />
                                <button
                                    type="button"
                                    onClick={handleToggleMute}
                                    className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500 hover:bg-slate-800 transition-colors"
                                    title={isVideoMuted || videoVolume <= 0.001 ? '取消静音' : '静音'}
                                    aria-label={isVideoMuted || videoVolume <= 0.001 ? '取消静音' : '静音'}
                                >
                                    {isVideoMuted || videoVolume <= 0.001 ? <VolumeX size={18} /> : <Volume2 size={18} />}
                                </button>
                                <input
                                    type="range"
                                    min={0}
                                    max={1}
                                    step={0.01}
                                    value={isVideoMuted ? 0 : videoVolume}
                                    onChange={handleActiveVideoVolumeChange}
                                    className="w-24 accent-indigo-500"
                                    aria-label="视频音量"
                                />
                                <button
                                    type="button"
                                    onClick={() => {
                                        void handleToggleFullscreen();
                                    }}
                                    className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500 hover:bg-slate-800 transition-colors"
                                    title={isVideoFullscreen ? '退出全屏' : '全屏播放'}
                                    aria-label={isVideoFullscreen ? '退出全屏' : '全屏播放'}
                                >
                                    <Maximize2 size={18} />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleDownload(activeVideoUrl)}
                                    className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-600 text-white hover:bg-indigo-500 transition-colors shadow-lg"
                                    title="下载视频"
                                    aria-label="下载视频"
                                >
                                    <Download size={18} />
                                </button>
                                {downloadableSubtitleAttachment?.url && (
                                    <button
                                        type="button"
                                        onClick={() => handleDownload(downloadableSubtitleAttachment.url!)}
                                        className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 px-3 text-xs text-slate-100 hover:border-slate-500 hover:bg-slate-800 transition-colors"
                                        title="下载字幕文件"
                                        aria-label="下载字幕文件"
                                    >
                                        字幕
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="text-center text-slate-600 flex flex-col items-center gap-6 relative z-10">
                        <div className="w-32 h-32 rounded-3xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-inner relative overflow-hidden group">
                            <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                            <VideoIcon size={64} className="opacity-20 group-hover:scale-110 transition-transform duration-500" />
                        </div>
                        <div>
                            <h3 className="text-2xl font-bold text-slate-500 mb-2">Video Generator</h3>
                            <p className="max-w-xs mx-auto text-sm opacity-60">
                                Describe a scene, or upload an image to animate using Google Veo.
                            </p>
                        </div>
                    </div>
                )}
            </div>

            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-indigo-400" />
                        <span className="text-xs font-bold text-white">视频参数</span>
                    </div>
                    <button
                        onClick={resetParams}
                        disabled={!videoControlsSchema || isLoadingVideoControlsSchema || Boolean(videoControlsSchemaError)}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="重置为默认值"
                    >
                        <RotateCcw size={12} />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
                    <ModeControlsCoordinator
                        mode={videoMode}
                        providerId={resolvedProviderId}
                        currentModel={activeModelConfig}
                        controls={controls}
                        controlsSchema={videoControlsSchema}
                        controlsSchemaLoading={isLoadingVideoControlsSchema}
                        controlsSchemaError={videoControlsSchemaError}
                    />
                </div>

                <ChatEditInputArea
                    onSend={handleSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    mode={videoMode}
                    activeAttachments={activeAttachments}
                    onAttachmentsChange={setActiveAttachments}
                    activeImageUrl={activeImageUrl}
                    onActiveImageUrlChange={setActiveImageUrl}
                    messages={messages}
                    sessionId={sessionId ?? null}
                    initialPrompt={initialPrompt}
                    providerId={resolvedProviderId}
                    controls={controls}
                    externalDisabled={Boolean(videoControlsStatusMessage)}
                    externalDisabledReason={videoControlsStatusMessage}
                />
            </div>
        </div>
    ), [
        activeAttachments,
        activeBatchMessage?.content,
        activeImageUrl,
        activeModelConfig,
        activeSubtitleTrack?.id,
        activeSubtitleTrack?.language,
        activeSubtitleTrack?.url,
        activeVideoUrl,
        controls,
        downloadableSubtitleAttachment?.url,
        formatVideoTime,
        handleActiveVideoSeek,
        handleActiveVideoVolumeChange,
        handleDownload,
        handleSend,
        handleToggleFullscreen,
        handleToggleMute,
        initialPrompt,
        isVideoFullscreen,
        isVideoMuted,
        isVideoPlaying,
        isBatchError,
        isLoadingVideoControlsSchema,
        loadingState,
        messages,
        onStop,
        resetParams,
        resolvedProviderId,
        sessionId,
        videoControlsSchema,
        videoControlsSchemaError,
        videoControlsStatusMessage,
        videoMode,
        toggleActiveVideoPlayback,
        videoDuration,
        videoVolume,
    ]);

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

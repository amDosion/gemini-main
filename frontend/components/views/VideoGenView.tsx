import { safeCopyToClipboard } from '../../utils/safeOps';
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Clock, Star } from 'lucide-react';
import { GenViewLayout } from '../common/GenViewLayout';
import { useControlsState } from '../../hooks/useControlsState';
import { useModeControlsSchema } from '../../hooks/useModeControlsSchema';
import {
  buildVideoControlContract,
  isVideoControlSelectionValid,
} from '../../utils/videoControlSchema';
import { useHistoryListActions } from '../../hooks/useHistoryListActions';
import { isHistoryActionSurface } from '../../utils/historyActionSurface';
import { useHoverPromptPreview } from '../../hooks/useHoverPromptPreview';
import { useActionMenu } from '../../hooks/useActionMenu';
import { useVideoPlayerControls } from '../../hooks/views/useVideoPlayerControls';
import type { ActionMenuAnchor, HoverPromptPreview } from './video/types';
import { VideoHistorySidebar } from './video/VideoHistorySidebar';
import { VideoMainCanvas } from './video/VideoMainCanvas';

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

// extractHistoryPrompts / extractVideoHistoryMeta 抽离至 utils/videoHistoryHelpers
// （JIRA-frontend-view-decomposition.md P1 #4 Step 1）
// ActionMenuAnchor / HoverPromptPreview 已抽离至 ./video/types

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
  // hover preview 由 useHoverPromptPreview<HoverPromptPreview> 统一管理
  const {
    preview: hoverPreview,
    position: hoverPreviewPosition,
    size: hoverPreviewSize,
    panelRef: hoverPreviewPanelRef,
    openPreview: openHoverPreviewBase,
    closePreview: closeHoverPreviewBase,
    scheduleClose: scheduleHideHoverPreview,
    cancelScheduledClose: clearHidePreviewTimer,
    startResize: handlePreviewResizeMouseDown,
    isResizing: isResizingPreview,
  } = useHoverPromptPreview<HoverPromptPreview>();

  // action menu 由 useActionMenu 统一管理；isExempted 复用 isHistoryActionSurface
  const {
    anchor: openActionMenu,
    position: actionMenuPosition,
    panelRef: actionMenuPanelRef,
    open: openActionMenuBase,
    close: closeActionMenu,
  } = useActionMenu<ActionMenuAnchor>({ isExempted: (t) => isHistoryActionSurface(t) });

  // View 业务：copy 反馈 + 历史项 ref 表
  const [copiedPreviewMessageId, setCopiedPreviewMessageId] = useState<string | null>(null);
  const copiedResetTimerRef = useRef<number | null>(null);
  const historyItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  // 视频播放器 state/refs/handlers 抽离至 hooks/views/useVideoPlayerControls
  const {
    isVideoPlaying,
    setIsVideoPlaying,
    videoDuration,
    setVideoDuration,
    isVideoFullscreen,
    setIsVideoFullscreen,
    videoVolume,
    isVideoMuted,
    activeVideoRef,
    activeVideoStageRef,
    videoSeekInputRef,
    videoProgressFillRef,
    videoProgressThumbRef,
    videoCurrentTimeLabelRef,
    handleToggleFullscreen,
    formatVideoTime,
    handleActiveVideoSeek,
    handleActiveVideoVolumeChange,
    handleToggleMute,
    stopVideoProgressAnimation,
    syncVideoProgressUi,
    startVideoProgressAnimation,
  } = useVideoPlayerControls();

  const videoMode: AppMode = 'video-gen';
  const controls = useControlsState(videoMode, activeModelConfig);
  const {
    schema: videoControlsSchema,
    loading: isLoadingVideoControlsSchema,
    error: videoControlsSchemaError,
  } = useModeControlsSchema(resolvedProviderId, videoMode, activeModelConfig?.id, {
    // 等 activeModelConfig 就绪才 fetch，避免初次 mount 浪费一次 model_id=undefined 请求
    enabled: !!activeModelConfig?.id,
  });
  const videoControlContract = useMemo(
    () => buildVideoControlContract(videoControlsSchema),
    [videoControlsSchema]
  );
  const isVideoControlsReady = useMemo(() => {
    if (
      isLoadingVideoControlsSchema ||
      videoControlsSchemaError ||
      !videoControlContract.schemaReady
    ) {
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
    controls.resolution,
    controls.storyboardShotSeconds,
    controls.subtitleLanguage,
    controls.subtitleMode,
    controls.videoSeconds,
    controls.videoExtensionCount,
    controls.setAspectRatio,
    controls.setEnhancePrompt,
    controls.setGenerateAudio,
    controls.setResolution,
    controls.setStoryboardShotSeconds,
    controls.setSubtitleLanguage,
    controls.setSubtitleMode,
    controls.setVideoSeconds,
    controls.setVideoExtensionCount,
    videoControlContract.defaultAspectRatio,
    videoControlContract.defaultEnhancePrompt,
    videoControlContract.defaultGenerateAudio,
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
    controls.setSubtitleMode(videoControlContract.defaultSubtitleMode);
    controls.setSubtitleLanguage(videoControlContract.defaultSubtitleLanguage);
    controls.setSubtitleScript(videoControlContract.defaultSubtitleScript);
    controls.setStoryboardPrompt(videoControlContract.defaultStoryboardPrompt);
    controls.setStoryboardSegments([]);
    controls.setNegativePrompt(videoControlContract.defaultNegativePrompt);
    controls.setSeed(videoControlContract.defaultSeed);
    controls.setEnhancePrompt(videoControlContract.defaultEnhancePrompt);
    controls.setEnhancePromptModel('');
  }, [
    controls,
    videoControlContract.defaultAspectRatio,
    videoControlContract.defaultEnhancePrompt,
    videoControlContract.defaultGenerateAudio,
    videoControlContract.defaultNegativePrompt,
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

  const clearCopiedResetTimer = useCallback(() => {
    if (copiedResetTimerRef.current !== null) {
      window.clearTimeout(copiedResetTimerRef.current);
      copiedResetTimerRef.current = null;
    }
  }, []);

  // view 级 closeHoverPreview：严格保持原 VideoGenView 行为
  // ——不关闭 action menu（与 ImageExpandView 刻意不同；调用方需要时显式 closeActionMenu()）
  const closeHoverPreview = useCallback(() => {
    closeHoverPreviewBase();
    setCopiedPreviewMessageId(null);
  }, [closeHoverPreviewBase]);

  const historyBatches = useMemo(() => {
    return messages
      .filter(
        (message) =>
          message.role === Role.MODEL &&
          ((message.attachments && message.attachments.length > 0) || message.isError)
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
    () =>
      (activeBatchMessage?.attachments || []).filter((attachment) =>
        attachment.mimeType?.startsWith('video/')
      ),
    [activeBatchMessage?.attachments]
  );
  const subtitleAttachments = useMemo(
    () =>
      (activeBatchMessage?.attachments || []).filter(
        (attachment) =>
          attachment.mimeType === 'text/vtt' || attachment.mimeType === 'application/x-subrip'
      ),
    [activeBatchMessage?.attachments]
  );
  const activeSubtitleTrack = useMemo(
    () =>
      subtitleAttachments.find(
        (attachment) => attachment.mimeType === 'text/vtt' && attachment.url
      ) || null,
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
      closeActionMenu();
      closeHoverPreview();
    }
  }, [closeActionMenu, closeHoverPreview, loadingState]);

  useEffect(() => {
    const nextVideoUrl = displayVideos.find((attachment) => attachment.url)?.url || null;
    const hasCurrentVideo = displayVideos.some((attachment) => attachment.url === activeVideoUrl);
    if (!hasCurrentVideo) {
      setActiveVideoUrl(nextVideoUrl);
    }
  }, [activeVideoUrl, displayVideos]);

  // useHoverPromptPreview 已托管 position 计算 / rAF 同步 / scroll+resize listener；
  // useActionMenu 已托管 outside-click / rAF position sync / scroll-close listener。
  // 这里仅保留 view 业务 wrapper：window<768 屏蔽 + isHistoryActionSurface 豁免 +
  // action menu 协调关闭 + 视频元数据装填到 hoverPreview。
  const showHoverPreview = useCallback(
    (
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
      if (isHistoryActionSurface(event.target)) return;
      clearHidePreviewTimer();
      closeActionMenu();

      const rect = event.currentTarget.getBoundingClientRect();
      const anchorX = rect.right;
      const anchorY = rect.top + rect.height / 2;
      openHoverPreviewBase({
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
    },
    [clearHidePreviewTimer, closeActionMenu, openHoverPreviewBase]
  );

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
    const isEditable =
      target.isContentEditable || Boolean(target.closest('[contenteditable="true"]'));
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

  const handleSend = useCallback(
    (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
      onSend(text, options, attachments, videoMode);
    },
    [onSend, videoMode]
  );

  const toggleActiveVideoPlayback = useCallback(async () => {
    const video = activeVideoRef.current;
    if (!video) {
      return;
    }

    if (video.paused) {
      await video.play();
    } else {
      video.pause();
    }
  }, []);

  // hook 自己已处理 rAF position-sync + scroll/resize listener + unmount cleanup；
  // 这里仅保留 view 特有 timer cleanup（copy 反馈 + video 进度 rAF）
  useEffect(() => {
    return () => {
      clearCopiedResetTimer();
      stopVideoProgressAnimation();
    };
  }, [clearCopiedResetTimer, stopVideoProgressAnimation]);

  useEffect(() => {
    if (filteredHistoryBatches.length === 0) return;

    const handleHistoryNavigation = (event: KeyboardEvent) => {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
      if (isInteractiveKeyboardTarget(event.target)) {
        return;
      }

      event.preventDefault();
      closeHoverPreview();
      closeActionMenu();

      setSelectedMsgId((prevId) => {
        const currentIndex = prevId
          ? filteredHistoryBatches.findIndex((message) => message.id === prevId)
          : 0;
        const safeCurrentIndex = currentIndex >= 0 ? currentIndex : 0;
        const delta = event.key === 'ArrowUp' ? -1 : 1;
        const nextIndex = Math.max(
          0,
          Math.min(filteredHistoryBatches.length - 1, safeCurrentIndex + delta)
        );
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

  const sidebarExtraHeader = useMemo(
    () => (
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
    ),
    [
      favoriteCount,
      filteredHistoryBatches.length,
      historyBatches.length,
      setShowFavoritesOnly,
      showFavoritesOnly,
    ]
  );

  // sidebarContent / mainContent 由子组件接管渲染；原 useMemo 的 deps
  // 几乎在每次渲染都会变化（loadingState/controls/...），useMemo 本身收益微乎其微，
  // 因此此处仅保留 plain JSX 转发——React 元素重建是 O(1)，下游 VideoHistorySidebar /
  // VideoMainCanvas 自身的内部 memoization 与 useEffect 仍保持原行为。
  const sidebarContent = (
    <VideoHistorySidebar
      filteredHistoryBatches={filteredHistoryBatches}
      activeBatchMessageId={activeBatchMessage?.id}
      showFavoritesOnly={showFavoritesOnly}
      isFavorite={isFavorite}
      isFavoritePending={isFavoritePending}
      toggleFavorite={toggleFavorite}
      deleteItem={deleteItem}
      historyItemRefs={historyItemRefs}
      hoverPreview={hoverPreview}
      hoverPreviewPosition={hoverPreviewPosition}
      hoverPreviewSize={hoverPreviewSize}
      hoverPreviewPanelRef={hoverPreviewPanelRef}
      clearHidePreviewTimer={clearHidePreviewTimer}
      scheduleHideHoverPreview={scheduleHideHoverPreview}
      showHoverPreview={showHoverPreview}
      closeHoverPreview={closeHoverPreview}
      handleCopyOptimizedPrompt={handleCopyOptimizedPrompt}
      copiedPreviewMessageId={copiedPreviewMessageId}
      handlePreviewResizeMouseDown={handlePreviewResizeMouseDown}
      isResizingPreview={isResizingPreview}
      openActionMenu={openActionMenu}
      actionMenuPosition={actionMenuPosition}
      actionMenuPanelRef={actionMenuPanelRef}
      openActionMenuBase={openActionMenuBase}
      closeActionMenu={closeActionMenu}
      activateHistoryMessage={activateHistoryMessage}
      setIsMobileHistoryOpen={setIsMobileHistoryOpen}
    />
  );

  const isBatchError = activeBatchMessage?.isError;

  const mainContent = (
    <VideoMainCanvas
      loadingState={loadingState}
      isBatchError={Boolean(isBatchError)}
      activeBatchMessage={activeBatchMessage}
      activeVideoUrl={activeVideoUrl}
      activeSubtitleTrack={activeSubtitleTrack}
      downloadableSubtitleAttachment={downloadableSubtitleAttachment}
      activeVideoRef={activeVideoRef}
      activeVideoStageRef={activeVideoStageRef}
      videoSeekInputRef={videoSeekInputRef}
      videoProgressFillRef={videoProgressFillRef}
      videoProgressThumbRef={videoProgressThumbRef}
      videoCurrentTimeLabelRef={videoCurrentTimeLabelRef}
      isVideoPlaying={isVideoPlaying}
      setIsVideoPlaying={setIsVideoPlaying}
      videoDuration={videoDuration}
      setVideoDuration={setVideoDuration}
      isVideoFullscreen={isVideoFullscreen}
      isVideoMuted={isVideoMuted}
      videoVolume={videoVolume}
      toggleActiveVideoPlayback={toggleActiveVideoPlayback}
      handleToggleFullscreen={handleToggleFullscreen}
      handleToggleMute={handleToggleMute}
      handleActiveVideoSeek={handleActiveVideoSeek}
      handleActiveVideoVolumeChange={handleActiveVideoVolumeChange}
      syncVideoProgressUi={syncVideoProgressUi}
      formatVideoTime={formatVideoTime}
      handleDownload={handleDownload}
      videoMode={videoMode}
      resolvedProviderId={resolvedProviderId}
      activeModelConfig={activeModelConfig}
      controls={controls}
      videoControlsSchema={videoControlsSchema}
      isLoadingVideoControlsSchema={isLoadingVideoControlsSchema}
      videoControlsSchemaError={videoControlsSchemaError}
      resetParams={resetParams}
      handleSend={handleSend}
      onStop={onStop}
      activeAttachments={activeAttachments}
      setActiveAttachments={setActiveAttachments}
      activeImageUrl={activeImageUrl}
      setActiveImageUrl={setActiveImageUrl}
      messages={messages}
      sessionId={sessionId}
      initialPrompt={initialPrompt}
      videoControlsStatusMessage={videoControlsStatusMessage}
    />
  );

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

import { safeCopyToClipboard } from '../../utils/safeOps';
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Clock, Star } from 'lucide-react';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { type CarouselMediaItem } from '../common/ImageCarouselControls';
import { GenViewLayout } from '../common/GenViewLayout';
import { useToastContext } from '../../contexts/ToastContext';
import { useControlsState } from '../../hooks/useControlsState';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import { useHistoryListActions } from '../../hooks/useHistoryListActions';
import { isHistoryActionSurface } from '../../utils/historyActionSurface';
import { useHoverPromptPreview } from '../../hooks/useHoverPromptPreview';
import { useActionMenu, type ActionMenuAnchorBase } from '../../hooks/useActionMenu';
import { HistoryActionMenuPortal } from '../common/HistoryActionMenuPortal';
import { HoverPromptPreviewPortal } from '../common/HoverPromptPreviewPortal';
import { ExpandHistoryRow } from './expand/ExpandHistoryRow';
import { ExpandMainCanvas } from './expand/ExpandMainCanvas';

const extractHistoryPrompts = (
  msg: Message
): { originalPrompt: string; optimizedPrompt: string } => {
  const rawContent = (msg.content || '').trim();
  const attachmentEnhancedPrompt = msg.attachments
    ?.find((att) => att.enhancedPrompt?.trim())
    ?.enhancedPrompt?.trim();

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
    originalPrompt: originalPrompt || '扩图结果',
    optimizedPrompt,
  };
};

// ImageExpandView 不需要扩展 hook 默认 payload — 直接用 hook 的 default 类型
type ActionMenuAnchor = ActionMenuAnchorBase;

interface ImageExpandViewProps {
  messages: Message[];
  setAppMode: (mode: AppMode) => void;
  onImageClick: (url: string) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  visibleModels?: ModelConfig[]; // 新增
  allVisibleModels?: ModelConfig[]; // 新增：完整模型列表
  initialAttachments?: Attachment[];
  providerId?: string;
  sessionId?: string | null; // ✅ 会话 ID，用于查询附件
  onDeleteMessage?: (messageId: string) => void;
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
  allVisibleModels = [], // 新增
  initialAttachments,
  providerId,
  sessionId: currentSessionId, // ✅ 接收 sessionId
  onDeleteMessage,
}: ImageExpandViewProps) => {
  const { showError } = useToastContext();
  const scrollRef = useRef<HTMLDivElement>(null);

  // State for reference image, synced with InputArea
  const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
  const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);

  // ✅ 新增：选中的消息批次 ID 和旋转木马索引
  const [selectedMsgId, setSelectedMsgId] = useState<string | null>(null);

  // Mobile History Toggle
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
  // hover preview 由 useHoverPromptPreview 统一管理（state + ref + listener cleanup）
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
  } = useHoverPromptPreview();

  // action menu 由 useActionMenu 统一管理；isExempted 复用 isHistoryActionSurface
  const {
    anchor: openActionMenu,
    position: actionMenuPosition,
    panelRef: actionMenuPanelRef,
    open: openActionMenuBase,
    close: closeActionMenu,
  } = useActionMenu<ActionMenuAnchor>({ isExempted: (t) => isHistoryActionSurface(t) });

  // View 业务：复制反馈 + 历史项 ref 表（保留）
  const [copiedPreviewMessageId, setCopiedPreviewMessageId] = useState<string | null>(null);
  const copiedResetTimerRef = useRef<number | null>(null);
  const historyItemRefs = useRef<Record<string, HTMLDivElement | null>>({});

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
      .filter(
        (m) => m.role === Role.MODEL && ((m.attachments && m.attachments.length > 0) || m.isError)
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
    sessionId: currentSessionId,
    items: historyBatches,
    onDeleteItem: onDeleteMessage,
  });

  // ✅ 新增：当前激活的批次消息
  const activeBatchMessage = useMemo(() => {
    if (selectedMsgId) {
      return filteredHistoryBatches.find((m) => m.id === selectedMsgId);
    }
    return filteredHistoryBatches[0];
  }, [selectedMsgId, filteredHistoryBatches]);

  // ✅ 新增：当前批次的所有图片
  const displayImages = useMemo(() => {
    return (activeBatchMessage?.attachments || []).filter((att) => att.url && att.url.length > 0);
  }, [activeBatchMessage?.attachments]);

  // ── Hover preview helpers（view wrappers）──

  const clearCopiedResetTimer = useCallback(() => {
    if (copiedResetTimerRef.current !== null) {
      window.clearTimeout(copiedResetTimerRef.current);
      copiedResetTimerRef.current = null;
    }
  }, []);

  // view 级 closeHoverPreview：协调 hook 关闭 + action menu 关闭 + copy 反馈清空
  const closeHoverPreview = useCallback(() => {
    closeHoverPreviewBase();
    closeActionMenu();
    setCopiedPreviewMessageId(null);
  }, [closeHoverPreviewBase, closeActionMenu]);

  // ✅ 新增：当新生成开始时，清除选中状态
  useEffect(() => {
    if (loadingState === 'loading') {
      setSelectedMsgId(null);
      setIsMobileHistoryOpen(false);
      closeHoverPreview();
    }
  }, [loadingState, closeHoverPreview]);

  // 选中项同步
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

  // 自动滚动到选中项
  useEffect(() => {
    if (!selectedMsgId) return;
    const itemEl = historyItemRefs.current[selectedMsgId];
    if (!itemEl) return;
    requestAnimationFrame(() => {
      itemEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
  }, [selectedMsgId]);

  // 键盘导航 ↑/↓
  useEffect(() => {
    if (filteredHistoryBatches.length === 0) return;

    const handleHistoryNavigation = (e: KeyboardEvent) => {
      if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
      const target = e.target as HTMLElement | null;
      if (target) {
        const tagName = target.tagName;
        if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT') return;
        if (target.isContentEditable || Boolean(target.closest('[contenteditable="true"]'))) return;
      }
      e.preventDefault();
      closeHoverPreview();
      setSelectedMsgId((prevId) => {
        const currentIndex = prevId ? filteredHistoryBatches.findIndex((m) => m.id === prevId) : 0;
        const safeCurrentIndex = currentIndex >= 0 ? currentIndex : 0;
        const delta = e.key === 'ArrowUp' ? -1 : 1;
        const nextIndex = Math.max(
          0,
          Math.min(filteredHistoryBatches.length - 1, safeCurrentIndex + delta)
        );
        return filteredHistoryBatches[nextIndex]?.id || prevId;
      });
    };

    window.addEventListener('keydown', handleHistoryNavigation);
    return () => {
      window.removeEventListener('keydown', handleHistoryNavigation);
    };
  }, [filteredHistoryBatches, closeHoverPreview]);

  // ── Hover preview view wrapper ──
  // useHoverPromptPreview 已托管 position 计算 / rAF 同步 / scroll+resize listener。
  // 这里仅保留 view 业务：window<768 屏蔽、isHistoryActionSurface 豁免、action menu 协调关闭。

  const showHoverPreview = useCallback(
    (
      e: React.MouseEvent<HTMLDivElement>,
      messageId: string,
      originalPrompt: string,
      optimizedPrompt: string
    ) => {
      if (window.innerWidth < 768) return;
      if (isHistoryActionSurface(e.target)) return;
      clearHidePreviewTimer();
      closeActionMenu();
      const rect = e.currentTarget.getBoundingClientRect();
      const anchorX = rect.right;
      const anchorY = rect.top + rect.height / 2;
      openHoverPreviewBase({ messageId, anchorX, anchorY, originalPrompt, optimizedPrompt });
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
  }, [hoverPreview, clearCopiedResetTimer]);

  // copy 反馈定时器 unmount cleanup（hook 自己已 cleanup 自身 timer/listener）
  useEffect(() => {
    return () => {
      clearCopiedResetTimer();
    };
  }, [clearCopiedResetTimer]);

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

  const carouselItems = useMemo<CarouselMediaItem[]>(
    () =>
      displayImages.map((att, idx) => ({
        id: att.id || `${idx}`,
        url: att.url || null,
        thumbUrl: att.url || null,
        alt: `缩略图 ${idx + 1}`,
      })),
    [displayImages]
  );

  const {
    index: carouselIndex,
    goPrev: handleCarouselPrev,
    goNext: handleCarouselNext,
    select: handleCarouselSelect,
  } = useImageCarousel({
    itemCount: displayImages.length,
    resetKey: activeBatchMessage?.id || null,
    keyboardEnabled: true,
    onNavigate: canvas.resetView,
  });

  // ✅ 切换对比模式
  const toggleCompare = useCallback(() => setIsCompareMode((prev) => !prev), []);

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
    const lastUserMsg = [...messages]
      .reverse()
      .find((m) => m.role === Role.USER && m.attachments?.length);
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
      const lastModelMsg = [...messages]
        .reverse()
        .find((m) => m.role === Role.MODEL && m.attachments?.length);
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
        if (
          lastMsg.role === Role.MODEL &&
          lastMsg.attachments &&
          lastMsg.attachments.length > 0 &&
          lastMsg.attachments[0].url
        ) {
          setActiveImageUrl(lastMsg.attachments[0].url);
          setLastProcessedMsgId(lastMsg.id);
        } else if (lastMsg.isError) {
          setLastProcessedMsgId(lastMsg.id);
        }
      }
    }
  }, [messages, activeAttachments.length, loadingState, lastProcessedMsgId, activeImageUrl]);

  // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
  const handleSend = useCallback(
    (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
      onSend(text, options, attachments, expandMode);
    },
    [onSend, expandMode]
  );

  // ✅ 统一历史列表：左图右提示词 + 收藏/操作/悬浮预览
  const sidebarContent = useMemo(
    () => (
      <div className="p-3 space-y-2.5">
        {filteredHistoryBatches.map((msg) => {
          const { originalPrompt, optimizedPrompt } = extractHistoryPrompts(msg);
          return (
            <ExpandHistoryRow
              key={msg.id}
              msg={msg}
              firstImage={msg.attachments?.[0]?.url}
              count={msg.attachments?.length || 0}
              isSelected={activeBatchMessage?.id === msg.id}
              originalPrompt={originalPrompt}
              optimizedPrompt={optimizedPrompt}
              favorited={isFavorite(msg.id)}
              isActionMenuOpen={openActionMenu?.messageId === msg.id}
              openActionMenu={openActionMenu}
              historyItemRefs={historyItemRefs}
              showHoverPreview={showHoverPreview}
              scheduleHideHoverPreview={scheduleHideHoverPreview}
              setSelectedMsgId={setSelectedMsgId}
              setIsMobileHistoryOpen={setIsMobileHistoryOpen}
              closeHoverPreview={closeHoverPreview}
              closeActionMenu={closeActionMenu}
              openActionMenuBase={openActionMenuBase}
            />
          );
        })}

        {filteredHistoryBatches.length === 0 && (
          <div className="text-center py-10 text-slate-600 text-xs italic">
            {showFavoritesOnly ? '暂无收藏记录。' : '暂无扩图历史'}
          </div>
        )}

        {openActionMenu && (
          <HistoryActionMenuPortal
            openActionMenu={openActionMenu}
            actionMenuPosition={actionMenuPosition}
            actionMenuPanelRef={actionMenuPanelRef}
            closeHoverPreview={closeHoverPreview}
            closeActionMenu={closeActionMenu}
            isFavorite={isFavorite}
            isFavoritePending={isFavoritePending}
            toggleFavorite={toggleFavorite}
            deleteItem={deleteItem}
            hoverPreviewMessageId={hoverPreview?.messageId ?? null}
          />
        )}

        <HoverPromptPreviewPortal
          preview={hoverPreview}
          position={hoverPreviewPosition}
          size={hoverPreviewSize}
          panelRef={hoverPreviewPanelRef}
          clearHidePreviewTimer={clearHidePreviewTimer}
          scheduleHideHoverPreview={scheduleHideHoverPreview}
          handleCopyOptimizedPrompt={handleCopyOptimizedPrompt}
          copiedPreviewMessageId={copiedPreviewMessageId}
          handlePreviewResizeMouseDown={handlePreviewResizeMouseDown}
          isResizingPreview={isResizingPreview}
        />
      </div>
    ),
    [
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
      deleteItem,
    ]
  );

  const sidebarHeaderIcon = <Clock size={14} />;

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
  const mainContent = useMemo(
    () => (
      <ExpandMainCanvas
        loadingState={loadingState}
        isBatchError={isBatchError}
        displayImages={displayImages}
        activeBatchMessage={activeBatchMessage}
        currentDisplayUrl={currentDisplayUrl}
        activeImageUrl={activeImageUrl}
        setActiveImageUrl={setActiveImageUrl}
        originalImageUrl={originalImageUrl}
        isCompareMode={isCompareMode}
        toggleCompare={toggleCompare}
        canvas={canvas}
        carouselIndex={carouselIndex}
        carouselItems={carouselItems}
        handleCarouselPrev={handleCarouselPrev}
        handleCarouselNext={handleCarouselNext}
        handleCarouselSelect={handleCarouselSelect}
        onImageClick={onImageClick}
        controls={controls}
        providerId={providerId}
        resetParams={resetParams}
        expandMode={expandMode}
        onStop={onStop}
        messages={messages}
        currentSessionId={currentSessionId}
        initialAttachments={initialAttachments}
        handleSend={handleSend}
        activeAttachments={activeAttachments}
        setActiveAttachments={setActiveAttachments}
      />
    ),
    [
      loadingState,
      isBatchError,
      displayImages,
      activeBatchMessage,
      currentDisplayUrl,
      activeImageUrl,
      originalImageUrl,
      isCompareMode,
      canvas,
      carouselIndex,
      carouselItems,
      handleCarouselPrev,
      handleCarouselNext,
      handleCarouselSelect,
      onImageClick,
      toggleCompare,
      controls,
      providerId,
      resetParams,
      expandMode,
      onStop,
      messages,
      currentSessionId,
      initialAttachments,
      handleSend,
      activeAttachments,
    ]
  );

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

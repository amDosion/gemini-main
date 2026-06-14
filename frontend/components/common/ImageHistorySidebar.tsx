import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Star } from 'lucide-react';
import { Message, Attachment } from '../../types/types';
import { useHistoryListActions } from '../../hooks/useHistoryListActions';
import { isHistoryActionSurface } from '../../utils/historyActionSurface';
import { safeCopyToClipboard } from '../../utils/safeOps';
import {
  type ImageHistoryPromptParts,
  type ImageHistoryPreviewAttachment,
  type ImageHistoryHoverPreview,
  type ImageHistoryHoverPreviewPosition,
  type ImageHistoryHoverPreviewSize,
  type ImageHistoryActionMenuAnchor,
  type ImageHistoryActionMenuPosition,
  type ImageHistoryAccent,
  type ImageHistorySidebarOptions,
  ACCENT_CLASSES,
  getImageHistoryAttachmentPreviewUrl,
  getImageHistoryAuthorLabel,
  selectImageHistoryPrimaryPreviewAttachment,
} from './imageHistorySidebarHelpers';
import { ImageHistoryHoverPreviewPanel } from './ImageHistoryHoverPreviewPanel';
import { HistoryActionMenuPortal } from './HistoryActionMenuPortal';
import { ImageHistoryListRow } from './ImageHistoryListRow';
import {
  VirtualizedHistoryList,
  type VirtualizedHistoryListHandle,
} from './VirtualizedHistoryList';

// Re-export for backwards compat
export type {
  ImageHistoryPromptParts,
  ImageHistoryPreviewAttachment,
} from './imageHistorySidebarHelpers';
export { extractImageHistoryPrompts } from './imageHistorySidebarHelpers';

export function useImageHistorySidebar({
  items,
  sessionId,
  onDeleteMessage,
  activeImageUrl,
  selectedMessageId,
  onSelectedMessageIdChange,
  onMobileHistoryOpenChange,
  modelLabel = 'AI',
  accent = 'orange',
  emptyText = 'No history yet.',
  secondaryPromptLabel = '增强提示词',
  secondaryPromptMissingText = '未返回增强提示词',
  secondaryPromptCopyTitle = '复制增强提示词',
  secondaryPromptBadgeText = '含增强提示词',
  fallbackSelection = 'last',
  disableFallbackSelection = false,
  getDisplayAttachments,
  getAttachmentUrl,
  extractPrompts,
  onSelectItem,
  onSelectPreviewAttachment,
  loadingContent,
}: ImageHistorySidebarOptions): {
  sidebarExtraHeader: React.ReactNode;
  sidebarContent: React.ReactNode;
} {
  const tone = ACCENT_CLASSES[accent];
  const historyItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const virtualListRef = useRef<VirtualizedHistoryListHandle>(null);
  const actionMenuPanelRef = useRef<HTMLDivElement | null>(null);
  const hoverPreviewPanelRef = useRef<HTMLDivElement | null>(null);
  const hidePreviewTimerRef = useRef<number | null>(null);
  const copiedResetTimerRef = useRef<number | null>(null);
  const previewResizeHandlersRef = useRef<{
    onMouseMove?: (event: MouseEvent) => void;
    onMouseUp?: () => void;
  }>({});
  const [openActionMenu, setOpenActionMenu] = useState<ImageHistoryActionMenuAnchor | null>(null);
  const [actionMenuPosition, setActionMenuPosition] =
    useState<ImageHistoryActionMenuPosition | null>(null);
  const [hoverPreview, setHoverPreview] = useState<ImageHistoryHoverPreview | null>(null);
  const [hoverPreviewPosition, setHoverPreviewPosition] =
    useState<ImageHistoryHoverPreviewPosition | null>(null);
  const [hoverPreviewSize, setHoverPreviewSize] = useState<ImageHistoryHoverPreviewSize | null>(
    null
  );
  const [isResizingPreview, setIsResizingPreview] = useState(false);
  const [copiedPreviewMessageId, setCopiedPreviewMessageId] = useState<string | null>(null);
  const hoverPreviewRef = useRef<ImageHistoryHoverPreview | null>(null);
  const hoverPreviewSizeRef = useRef<ImageHistoryHoverPreviewSize | null>(null);
  const isResizingPreviewRef = useRef(false);
  hoverPreviewRef.current = hoverPreview;
  hoverPreviewSizeRef.current = hoverPreviewSize;
  isResizingPreviewRef.current = isResizingPreview;

  const {
    showFavoritesOnly,
    setShowFavoritesOnly,
    filteredItems,
    favoriteCount,
    isFavorite,
    isFavoritePending,
    toggleFavorite,
    deleteItem,
  } = useHistoryListActions({
    sessionId,
    items,
    onDeleteItem: onDeleteMessage,
  });

  const getPreviewAttachments = useCallback(
    (message: Message): ImageHistoryPreviewAttachment[] => {
      return getDisplayAttachments(message.attachments)
        .map((attachment, index) => {
          const id = attachment.id || `${message.id}-${index}`;
          const url = getImageHistoryAttachmentPreviewUrl(
            attachment,
            id,
            getAttachmentUrl(attachment)
          );
          return {
            id,
            url,
          };
        })
        .filter((attachment) => attachment.url.length > 0);
    },
    [getAttachmentUrl, getDisplayAttachments]
  );

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

  const closeHoverPreviewOnly = useCallback(() => {
    clearHidePreviewTimer();
    stopPreviewResize();
    setHoverPreview(null);
    setHoverPreviewPosition(null);
    setHoverPreviewSize(null);
    setCopiedPreviewMessageId(null);
  }, [clearHidePreviewTimer, stopPreviewResize]);

  const scheduleHideHoverPreview = useCallback(() => {
    if (isResizingPreviewRef.current) return;
    clearHidePreviewTimer();
    hidePreviewTimerRef.current = window.setTimeout(() => {
      setHoverPreview(null);
      setHoverPreviewPosition(null);
      setHoverPreviewSize(null);
      setCopiedPreviewMessageId(null);
      hidePreviewTimerRef.current = null;
    }, 180);
  }, [clearHidePreviewTimer]);

  const computeHoverPreviewPosition = useCallback(
    (
      anchorX: number,
      anchorY: number,
      panelWidth: number,
      panelHeight: number
    ): ImageHistoryHoverPreviewPosition => {
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
    },
    []
  );

  const showHoverPreview = useCallback(
    (
      event: React.MouseEvent,
      message: Message,
      originalPrompt: string,
      enhancedPrompt: string,
      attachments: ImageHistoryPreviewAttachment[]
    ) => {
      if (window.innerWidth < 768) return;
      if (isHistoryActionSurface(event.target)) return;
      clearHidePreviewTimer();
      setOpenActionMenu(null);
      setActionMenuPosition(null);
      const rect = event.currentTarget.getBoundingClientRect();
      const anchorX = rect.right;
      const anchorY = rect.top + rect.height / 2;
      const currentPreview = hoverPreviewRef.current;
      const currentPreviewSize = hoverPreviewSizeRef.current;
      const shouldResetSize = currentPreview?.messageId !== message.id;
      if (shouldResetSize) {
        setHoverPreviewSize(null);
      }
      const estimatedPanelWidth = shouldResetSize ? 380 : (currentPreviewSize?.width ?? 380);
      const estimatedPanelHeight = shouldResetSize ? 280 : (currentPreviewSize?.height ?? 280);
      setHoverPreview({
        messageId: message.id,
        role: message.role,
        authorLabel: getImageHistoryAuthorLabel(message, modelLabel),
        anchorX,
        anchorY,
        originalPrompt,
        enhancedPrompt,
        attachments,
      });
      setHoverPreviewPosition(
        computeHoverPreviewPosition(anchorX, anchorY, estimatedPanelWidth, estimatedPanelHeight)
      );
    },
    [
      clearHidePreviewTimer,
      computeHoverPreviewPosition,
      modelLabel,
    ]
  );

  const handlePreviewResizeMouseDown = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
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
    },
    [
      clearHidePreviewTimer,
      hoverPreview,
      hoverPreviewPosition?.left,
      hoverPreviewPosition?.top,
      hoverPreviewSize?.height,
      hoverPreviewSize?.width,
      stopPreviewResize,
    ]
  );

  const handleCopyEnhancedPrompt = useCallback(async () => {
    if (!hoverPreview?.enhancedPrompt) return;
    clearCopiedResetTimer();
    const copied = await safeCopyToClipboard(hoverPreview.enhancedPrompt);
    if (!copied) return;
    setCopiedPreviewMessageId(hoverPreview.messageId);
    copiedResetTimerRef.current = window.setTimeout(() => {
      setCopiedPreviewMessageId(null);
      copiedResetTimerRef.current = null;
    }, 1200);
  }, [clearCopiedResetTimer, hoverPreview]);

  useEffect(() => {
    return () => {
      clearHidePreviewTimer();
      clearCopiedResetTimer();
      stopPreviewResize();
    };
  }, [clearCopiedResetTimer, clearHidePreviewTimer, stopPreviewResize]);

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

    const handleWindowResize = () => closeHoverPreview();
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

    window.addEventListener('resize', handleWindowResize);
    window.addEventListener('scroll', handleWindowScroll, true);
    return () => {
      window.removeEventListener('resize', handleWindowResize);
      window.removeEventListener('scroll', handleWindowScroll, true);
    };
  }, [closeHoverPreview, hoverPreview]);

  useEffect(() => {
    if (!openActionMenu) return;

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target;
      if (isHistoryActionSurface(target)) {
        return;
      }
      setOpenActionMenu(null);
      setActionMenuPosition(null);
    };

    window.addEventListener('mousedown', handlePointerDown);
    return () => {
      window.removeEventListener('mousedown', handlePointerDown);
    };
  }, [openActionMenu]);

  useEffect(() => {
    if (!openActionMenu) return;

    const computePosition = () => {
      const panel = actionMenuPanelRef.current;
      const panelWidth = panel?.offsetWidth ?? 112;
      const panelHeight = panel?.offsetHeight ?? 72;
      const gap = 8;
      const padding = 8;
      let left = openActionMenu.anchorX + gap;
      if (left + panelWidth + padding > window.innerWidth) {
        left = openActionMenu.anchorX - panelWidth - gap;
      }
      left = Math.max(padding, Math.min(left, window.innerWidth - panelWidth - padding));

      let top = openActionMenu.anchorY + gap;
      if (top + panelHeight + padding > window.innerHeight) {
        top = openActionMenu.anchorY - panelHeight - gap;
      }
      top = Math.max(padding, Math.min(top, window.innerHeight - panelHeight - padding));
      setActionMenuPosition({ top, left });
    };

    computePosition();
    window.addEventListener('resize', computePosition);
    window.addEventListener('scroll', computePosition, true);
    return () => {
      window.removeEventListener('resize', computePosition);
      window.removeEventListener('scroll', computePosition, true);
    };
  }, [openActionMenu]);

  useEffect(() => {
    if (filteredItems.length === 0) {
      onSelectedMessageIdChange?.(null);
      return;
    }
    if (selectedMessageId && filteredItems.some((message) => message.id === selectedMessageId)) {
      return;
    }
    if (disableFallbackSelection) {
      return;
    }
    const fallbackIndex = fallbackSelection === 'first' ? 0 : filteredItems.length - 1;
    const fallback = filteredItems[fallbackIndex];
    if (fallback) {
      onSelectedMessageIdChange?.(fallback.id);
      const displayAttachments = getDisplayAttachments(fallback.attachments);
      const previewAttachments = getPreviewAttachments(fallback);
      onSelectItem({
        message: fallback,
        displayAttachments,
        previewAttachments,
        firstImage:
          selectImageHistoryPrimaryPreviewAttachment(displayAttachments, previewAttachments)
            ?.displayUrl || undefined,
      });
    }
  }, [
    fallbackSelection,
    disableFallbackSelection,
    filteredItems,
    getDisplayAttachments,
    getPreviewAttachments,
    onSelectItem,
    onSelectedMessageIdChange,
    selectedMessageId,
  ]);

  // 通过 ref 持有 filteredItems / selectedMessageId,避免每次选中项或历史变化都重挂
  // window keydown listener;handler 始终读取最新值,与原先"每次变化重挂监听"行为一致,
  // 但 deps 收敛后监听只在 mount/unmount 及回调 prop 变化时增删。
  const filteredItemsRef = useRef(filteredItems);
  filteredItemsRef.current = filteredItems;
  const selectedMessageIdRef = useRef(selectedMessageId);
  selectedMessageIdRef.current = selectedMessageId;

  useEffect(() => {
    const handleHistoryNavigation = (event: KeyboardEvent) => {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;

      const target = event.target;
      if (target instanceof HTMLElement) {
        const tagName = target.tagName;
        const isFormInput = tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT';
        const isEditable =
          target.isContentEditable || Boolean(target.closest('[contenteditable="true"]'));
        if (isFormInput || isEditable) {
          return;
        }
      }

      const items = filteredItemsRef.current;
      if (items.length === 0) return;

      event.preventDefault();
      closeHoverPreview();

      const currentSelectedMessageId = selectedMessageIdRef.current;
      const defaultIndex = fallbackSelection === 'first' ? 0 : items.length - 1;
      const currentIndex = currentSelectedMessageId
        ? items.findIndex((message) => message.id === currentSelectedMessageId)
        : defaultIndex;
      const safeCurrentIndex = currentIndex >= 0 ? currentIndex : defaultIndex;
      const delta = event.key === 'ArrowUp' ? -1 : 1;
      const nextIndex = Math.max(0, Math.min(items.length - 1, safeCurrentIndex + delta));
      const nextMessage = items[nextIndex];
      if (!nextMessage) return;

      const displayAttachments = getDisplayAttachments(nextMessage.attachments);
      const previewAttachments = getPreviewAttachments(nextMessage);
      onSelectedMessageIdChange?.(nextMessage.id);
      onSelectItem({
        message: nextMessage,
        displayAttachments,
        previewAttachments,
        firstImage:
          selectImageHistoryPrimaryPreviewAttachment(displayAttachments, previewAttachments)
            ?.displayUrl || undefined,
      });
    };

    window.addEventListener('keydown', handleHistoryNavigation);
    return () => {
      window.removeEventListener('keydown', handleHistoryNavigation);
    };
  }, [
    closeHoverPreview,
    fallbackSelection,
    getDisplayAttachments,
    getPreviewAttachments,
    onSelectItem,
    onSelectedMessageIdChange,
  ]);

  useEffect(() => {
    if (!selectedMessageId) return;
    // virtualized 分支：先把 row 滚到可见范围，再让 ref 接管 scrollIntoView（rAF 确保已挂载）
    if (virtualListRef.current?.isVirtualized) {
      const idx = filteredItems.findIndex((m) => m.id === selectedMessageId);
      if (idx >= 0) {
        virtualListRef.current.scrollToIndex(idx);
      }
    }
    requestAnimationFrame(() => {
      const itemEl = historyItemRefs.current[selectedMessageId];
      if (!itemEl || typeof itemEl.scrollIntoView !== 'function') return;
      itemEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
  }, [selectedMessageId, filteredItems]);

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
          {filteredItems.length}/{items.length}
        </span>
        <span className="inline-flex items-center gap-1 text-[10px] rounded bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 text-amber-300">
          <Star size={9} className="fill-amber-300 text-amber-300" />
          {favoriteCount}
        </span>
      </div>
    ),
    [favoriteCount, filteredItems.length, items.length, setShowFavoritesOnly, showFavoritesOnly]
  );

  const listContent = useMemo(
    () => (
      <VirtualizedHistoryList
        ref={virtualListRef}
        items={filteredItems}
        estimatedRowHeight={92}
        className="flex-1 p-3 overflow-y-auto custom-scrollbar space-y-2.5"
        getKey={(message) => message.id}
        renderRow={(message) => (
          <ImageHistoryListRow
            message={message}
            tone={tone}
            modelLabel={modelLabel}
            secondaryPromptBadgeText={secondaryPromptBadgeText}
            selectedMessageId={selectedMessageId}
            activeImageUrl={activeImageUrl}
            openActionMenu={openActionMenu}
            historyItemRefs={historyItemRefs}
            isFavorite={isFavorite}
            getDisplayAttachments={getDisplayAttachments}
            getPreviewAttachments={getPreviewAttachments}
            extractPrompts={extractPrompts}
            showHoverPreview={showHoverPreview}
            scheduleHideHoverPreview={scheduleHideHoverPreview}
            closeHoverPreviewOnly={closeHoverPreviewOnly}
            closeHoverPreview={closeHoverPreview}
            onSelectedMessageIdChange={onSelectedMessageIdChange}
            onSelectItem={onSelectItem}
            onMobileHistoryOpenChange={onMobileHistoryOpenChange}
            setOpenActionMenu={setOpenActionMenu}
            setActionMenuPosition={setActionMenuPosition}
          />
        )}
      >
        {filteredItems.length === 0 && (
          <div className="text-center py-10 text-slate-600 text-xs italic">
            {showFavoritesOnly ? '暂无收藏记录。' : emptyText}
          </div>
        )}

        {loadingContent}
      </VirtualizedHistoryList>
    ),
    [
      activeImageUrl,
      closeHoverPreview,
      closeHoverPreviewOnly,
      emptyText,
      extractPrompts,
      filteredItems,
      getDisplayAttachments,
      getPreviewAttachments,
      historyItemRefs,
      isFavorite,
      loadingContent,
      modelLabel,
      onMobileHistoryOpenChange,
      onSelectItem,
      onSelectedMessageIdChange,
      openActionMenu,
      scheduleHideHoverPreview,
      selectedMessageId,
      setActionMenuPosition,
      setOpenActionMenu,
      secondaryPromptBadgeText,
      showFavoritesOnly,
      showHoverPreview,
      tone,
    ]
  );

  const sidebarContent = (
    <>
      {listContent}

      {openActionMenu && (
        <HistoryActionMenuPortal
          openActionMenu={openActionMenu}
          actionMenuPosition={actionMenuPosition}
          actionMenuPanelRef={actionMenuPanelRef}
          closeHoverPreviewOnly={closeHoverPreviewOnly}
          closeHoverPreview={closeHoverPreview}
          closeActionMenu={() => {
            setOpenActionMenu(null);
            setActionMenuPosition(null);
          }}
          isFavorite={isFavorite}
          isFavoritePending={isFavoritePending}
          toggleFavorite={toggleFavorite}
          deleteItem={deleteItem}
          hoverPreviewMessageId={hoverPreview?.messageId ?? null}
        />
      )}

      {hoverPreview && (
        <ImageHistoryHoverPreviewPanel
          hoverPreview={hoverPreview}
          hoverPreviewPosition={hoverPreviewPosition}
          hoverPreviewSize={hoverPreviewSize}
          hoverPreviewPanelRef={hoverPreviewPanelRef}
          clearHidePreviewTimer={clearHidePreviewTimer}
          scheduleHideHoverPreview={scheduleHideHoverPreview}
          tone={tone}
          secondaryPromptLabel={secondaryPromptLabel}
          secondaryPromptMissingText={secondaryPromptMissingText}
          secondaryPromptCopyTitle={secondaryPromptCopyTitle}
          copiedPreviewMessageId={copiedPreviewMessageId}
          handleCopyEnhancedPrompt={handleCopyEnhancedPrompt}
          activeImageUrl={activeImageUrl}
          items={items}
          onSelectedMessageIdChange={onSelectedMessageIdChange}
          getDisplayAttachments={getDisplayAttachments}
          onSelectPreviewAttachment={onSelectPreviewAttachment}
          onSelectItem={onSelectItem}
          handlePreviewResizeMouseDown={handlePreviewResizeMouseDown}
          isResizingPreview={isResizingPreview}
        />
      )}
    </>
  );

  return { sidebarExtraHeader, sidebarContent };
}

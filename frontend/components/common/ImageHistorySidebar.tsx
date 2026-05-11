import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  AlertCircle, Bot, Check, Copy, FolderOpen, Image as ImageIcon,
  Layers, Sparkles, Star, Trash2, User,
} from 'lucide-react';
import { Message, Role, Attachment } from '../../types/types';
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
  USER_SELECTED_CLASS,
  USER_IDLE_CLASS,
  getAttachmentPreviewGridClass,
  getAttachmentPreviewButtonClass,
  getAttachmentPreviewImageClass,
} from './imageHistorySidebarHelpers';

// Re-export for backwards compat
export type { ImageHistoryPromptParts, ImageHistoryPreviewAttachment } from './imageHistorySidebarHelpers';
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const historyItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const actionMenuPanelRef = useRef<HTMLDivElement | null>(null);
  const hoverPreviewPanelRef = useRef<HTMLDivElement | null>(null);
  const hidePreviewTimerRef = useRef<number | null>(null);
  const copiedResetTimerRef = useRef<number | null>(null);
  const previewResizeHandlersRef = useRef<{
    onMouseMove?: (event: MouseEvent) => void;
    onMouseUp?: () => void;
  }>({});
  const [openActionMenu, setOpenActionMenu] = useState<ImageHistoryActionMenuAnchor | null>(null);
  const [actionMenuPosition, setActionMenuPosition] = useState<ImageHistoryActionMenuPosition | null>(null);
  const [hoverPreview, setHoverPreview] = useState<ImageHistoryHoverPreview | null>(null);
  const [hoverPreviewPosition, setHoverPreviewPosition] = useState<ImageHistoryHoverPreviewPosition | null>(null);
  const [hoverPreviewSize, setHoverPreviewSize] = useState<ImageHistoryHoverPreviewSize | null>(null);
  const [isResizingPreview, setIsResizingPreview] = useState(false);
  const [copiedPreviewMessageId, setCopiedPreviewMessageId] = useState<string | null>(null);

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

  const getPreviewAttachments = useCallback((message: Message): ImageHistoryPreviewAttachment[] => {
    return getDisplayAttachments(message.attachments)
      .map((attachment, index) => {
        const url = getAttachmentUrl(attachment) || '';
        return {
          id: attachment.id || `${message.id}-${index}`,
          url,
        };
      })
      .filter((attachment) => attachment.url.length > 0);
  }, [getAttachmentUrl, getDisplayAttachments]);

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

  const computeHoverPreviewPosition = useCallback((
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
  }, []);

  const showHoverPreview = useCallback((
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
    const shouldResetSize = hoverPreview?.messageId !== message.id;
    if (shouldResetSize) {
      setHoverPreviewSize(null);
    }
    const estimatedPanelWidth = shouldResetSize ? 380 : (hoverPreviewSize?.width ?? 380);
    const estimatedPanelHeight = shouldResetSize ? 280 : (hoverPreviewSize?.height ?? 280);
    setHoverPreview({
      messageId: message.id,
      role: message.role,
      authorLabel: message.role === Role.USER ? 'You' : modelLabel,
      anchorX,
      anchorY,
      originalPrompt,
      enhancedPrompt,
      attachments,
    });
    setHoverPreviewPosition(computeHoverPreviewPosition(anchorX, anchorY, estimatedPanelWidth, estimatedPanelHeight));
  }, [
    clearHidePreviewTimer,
    computeHoverPreviewPosition,
    hoverPreview?.messageId,
    hoverPreviewSize?.height,
    hoverPreviewSize?.width,
    modelLabel,
  ]);

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
  }, [
    clearHidePreviewTimer,
    hoverPreview,
    hoverPreviewPosition?.left,
    hoverPreviewPosition?.top,
    hoverPreviewSize?.height,
    hoverPreviewSize?.width,
    stopPreviewResize,
  ]);

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
        firstImage: previewAttachments[0]?.url,
      });
    }
  }, [
    fallbackSelection,
    filteredItems,
    getDisplayAttachments,
    getPreviewAttachments,
    onSelectItem,
    onSelectedMessageIdChange,
    selectedMessageId,
  ]);

  useEffect(() => {
    if (filteredItems.length === 0) return;

    const handleHistoryNavigation = (event: KeyboardEvent) => {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;

      const target = event.target as HTMLElement | null;
      if (target) {
        const tagName = target.tagName;
        const isFormInput = tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT';
        const isEditable = target.isContentEditable || Boolean(target.closest('[contenteditable="true"]'));
        if (isFormInput || isEditable) {
          return;
        }
      }

      event.preventDefault();
      closeHoverPreview();

      const defaultIndex = fallbackSelection === 'first' ? 0 : filteredItems.length - 1;
      const currentIndex = selectedMessageId
        ? filteredItems.findIndex((message) => message.id === selectedMessageId)
        : defaultIndex;
      const safeCurrentIndex = currentIndex >= 0 ? currentIndex : defaultIndex;
      const delta = event.key === 'ArrowUp' ? -1 : 1;
      const nextIndex = Math.max(0, Math.min(filteredItems.length - 1, safeCurrentIndex + delta));
      const nextMessage = filteredItems[nextIndex];
      if (!nextMessage) return;

      const displayAttachments = getDisplayAttachments(nextMessage.attachments);
      const previewAttachments = getPreviewAttachments(nextMessage);
      onSelectedMessageIdChange?.(nextMessage.id);
      onSelectItem({
        message: nextMessage,
        displayAttachments,
        previewAttachments,
        firstImage: previewAttachments[0]?.url,
      });
    };

    window.addEventListener('keydown', handleHistoryNavigation);
    return () => {
      window.removeEventListener('keydown', handleHistoryNavigation);
    };
  }, [
    closeHoverPreview,
    fallbackSelection,
    filteredItems,
    getDisplayAttachments,
    getPreviewAttachments,
    onSelectItem,
    onSelectedMessageIdChange,
    selectedMessageId,
  ]);

  useEffect(() => {
    if (!selectedMessageId) return;
    const itemEl = historyItemRefs.current[selectedMessageId];
    if (!itemEl || typeof itemEl.scrollIntoView !== 'function') return;
    requestAnimationFrame(() => {
      itemEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
  }, [selectedMessageId]);

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
        {filteredItems.length}/{items.length}
      </span>
      <span className="inline-flex items-center gap-1 text-[10px] rounded bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 text-amber-300">
        <Star size={9} className="fill-amber-300 text-amber-300" />
        {favoriteCount}
      </span>
    </div>
  ), [favoriteCount, filteredItems.length, items.length, setShowFavoritesOnly, showFavoritesOnly]);

  const sidebarContent = useMemo(() => (
    <div ref={scrollRef} className="flex-1 p-3 space-y-2.5 overflow-y-auto custom-scrollbar">
      {filteredItems.map((message) => {
        const displayAttachments = getDisplayAttachments(message.attachments);
        const previewAttachments = getPreviewAttachments(message);
        const firstImage = previewAttachments[0]?.url;
        const count = previewAttachments.length;
        const isUserMessage = message.role === Role.USER;
        const { originalPrompt, enhancedPrompt } = extractPrompts(message);
        const favorited = isFavorite(message.id);
        const isActionMenuOpen = openActionMenu?.messageId === message.id;
        const isSelected = selectedMessageId
          ? selectedMessageId === message.id
          : Boolean(activeImageUrl && previewAttachments.some((attachment) => attachment.url === activeImageUrl));

        const itemToneClass = isUserMessage
          ? (isSelected ? USER_SELECTED_CLASS : USER_IDLE_CLASS)
          : (isSelected ? tone.modelSelected : tone.modelIdle);

        return (
          <div
            key={message.id}
            ref={(element) => {
              historyItemRefs.current[message.id] = element;
            }}
            className="group relative"
          >
            <div
              className={`relative rounded-xl border cursor-pointer transition-all flex items-center gap-3 p-2 ${itemToneClass}`}
              onMouseEnter={(event) => showHoverPreview(event, message, originalPrompt, enhancedPrompt, previewAttachments)}
              onMouseLeave={scheduleHideHoverPreview}
              onClick={() => {
                onSelectedMessageIdChange?.(message.id);
                onSelectItem({ message, displayAttachments, previewAttachments, firstImage });
                if (window.innerWidth < 768) {
                  onMobileHistoryOpenChange?.(false);
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
                    : tone.modelPill
                }`}>
                  {isUserMessage ? <User size={9} /> : <Bot size={9} />}
                  {isUserMessage ? 'USER' : 'AI'}
                </span>

                {message.isError ? (
                  <div className="w-full h-full flex items-center justify-center text-red-400 bg-red-900/10">
                    <AlertCircle size={18} />
                  </div>
                ) : firstImage ? (
                  <>
                    <img src={firstImage} className="w-full h-full object-cover transition-transform group-hover:scale-105" loading="lazy" alt="History preview" />
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
                  <span className={`text-[10px] font-medium ${isUserMessage ? 'text-blue-300' : tone.modelLabel}`}>
                    {isUserMessage ? 'You' : modelLabel}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
                    <span className={`inline-flex items-center gap-1 rounded-full border ${tone.modelBadge}`}>
                      AI 响应
                    </span>
                  )}
                  {!isUserMessage && enhancedPrompt && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-300">
                      <Sparkles size={10} />
                      {secondaryPromptBadgeText}
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
                  data-history-action-trigger={message.id}
                  onMouseEnter={(event) => {
                    event.stopPropagation();
                    closeHoverPreview();
                  }}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    closeHoverPreview();
                    const rect = event.currentTarget.getBoundingClientRect();
                    setOpenActionMenu((prev) => (
                      prev?.messageId === message.id
                        ? null
                        : {
                            messageId: message.id,
                            anchorX: rect.right,
                            anchorY: rect.bottom,
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

      {filteredItems.length === 0 && (
        <div className="text-center py-10 text-slate-600 text-xs italic">
          {showFavoritesOnly ? '暂无收藏记录。' : emptyText}
        </div>
      )}

      {openActionMenu && typeof document !== 'undefined' && (
        createPortal(
          <div
            ref={actionMenuPanelRef}
            data-history-action-menu
            className="fixed z-[90] inline-flex flex-col gap-1 rounded-lg border border-slate-700 bg-slate-950/95 shadow-2xl backdrop-blur-md p-1"
            onMouseEnter={closeHoverPreview}
            style={{
              top: actionMenuPosition?.top ?? openActionMenu.anchorY,
              left: actionMenuPosition?.left ?? openActionMenu.anchorX,
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

      {loadingContent}

      {hoverPreview && typeof document !== 'undefined' && createPortal(
        <div
          ref={hoverPreviewPanelRef}
          className="fixed hidden md:block"
          style={{
            top: hoverPreviewPosition?.top ?? hoverPreview.anchorY,
            left: hoverPreviewPosition?.left ?? hoverPreview.anchorX,
            ...(hoverPreviewSize
              ? { width: hoverPreviewSize.width, height: hoverPreviewSize.height }
              : {}),
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
                    : tone.modelPill
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
                    <p className="text-[10px] uppercase tracking-wider text-emerald-400">{secondaryPromptLabel}</p>
                    {hoverPreview.enhancedPrompt && (
                      <button
                        type="button"
                        onClick={handleCopyEnhancedPrompt}
                        className="pointer-events-auto inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-200 hover:bg-emerald-500/20 transition-colors"
                        title={secondaryPromptCopyTitle}
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
                    <p className="mt-1 text-xs text-slate-500 italic">{secondaryPromptMissingText}</p>
                  )}
                </div>
              )}

              {hoverPreview.attachments.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">附图</p>
                  <div
                    data-history-attachment-grid
                    className={`${getAttachmentPreviewGridClass(hoverPreview.attachments.length)} ${
                      hoverPreview.attachments.length > 6
                        ? 'max-h-[220px] overflow-y-auto pr-1 custom-scrollbar'
                        : ''
                    }`}
                  >
                    {hoverPreview.attachments.map((attachment, index) => (
                      <button
                        key={attachment.id}
                        type="button"
                        className={`relative rounded-md overflow-hidden border transition-colors bg-slate-900/80 flex items-center justify-center ${getAttachmentPreviewButtonClass(hoverPreview.attachments.length)} ${
                          activeImageUrl === attachment.url
                            ? tone.activeThumb
                            : 'border-slate-700 hover:border-slate-500'
                        }`}
                        onClick={() => {
                          const selectedMessage = items.find((item) => item.id === hoverPreview.messageId);
                          onSelectedMessageIdChange?.(hoverPreview.messageId);
                          if (selectedMessage) {
                            const displayAttachments = getDisplayAttachments(selectedMessage.attachments);
                            const payload = {
                              message: selectedMessage,
                              displayAttachments,
                              previewAttachments: hoverPreview.attachments,
                              attachment,
                              index,
                            };
                            if (onSelectPreviewAttachment) {
                              onSelectPreviewAttachment(payload);
                            } else {
                              onSelectItem({
                                message: selectedMessage,
                                displayAttachments,
                                previewAttachments: hoverPreview.attachments,
                                firstImage: attachment.url,
                              });
                            }
                          }
                        }}
                        title="在画布中查看该图片"
                      >
                        <img src={attachment.url} className={getAttachmentPreviewImageClass(hoverPreview.attachments.length)} alt="History attachment" />
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
      <div />
    </div>
  ), [
    activeImageUrl,
    actionMenuPosition,
    clearHidePreviewTimer,
    closeHoverPreview,
    copiedPreviewMessageId,
    deleteItem,
    emptyText,
    extractPrompts,
    filteredItems,
    getDisplayAttachments,
    getPreviewAttachments,
    handleCopyEnhancedPrompt,
    handlePreviewResizeMouseDown,
    hoverPreview,
    hoverPreviewPosition,
    hoverPreviewSize,
    isResizingPreview,
    isFavorite,
    isFavoritePending,
    items,
    loadingContent,
    modelLabel,
    onMobileHistoryOpenChange,
    onSelectItem,
    onSelectPreviewAttachment,
    onSelectedMessageIdChange,
    openActionMenu,
    scheduleHideHoverPreview,
    selectedMessageId,
    secondaryPromptBadgeText,
    secondaryPromptCopyTitle,
    secondaryPromptLabel,
    secondaryPromptMissingText,
    showFavoritesOnly,
    showHoverPreview,
    tone,
    toggleFavorite,
  ]);

  return { sidebarExtraHeader, sidebarContent };
}

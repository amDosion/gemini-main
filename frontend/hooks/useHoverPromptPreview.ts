import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Hover prompt preview hook（含 viewport-clamp position + resize listener）。
 *
 * 替代 ImageExpandView + VideoGenView 中重复的 hover preview state/ref/effect
 * （见 JIRA-frontend-hook-utility-extraction.md A.1.2）。
 *
 * 行为（按 ImageExpandView.tsx:383-474 抽离）：
 * - openPreview(payload) → setPreview + 初始 position (基于估算 panel 尺寸)
 * - 不同 messageId 重置 size
 * - useEffect + requestAnimationFrame 同步真实 panel 尺寸到 position
 * - scheduleClose(delayMs=300) → 延迟关闭；resize 进行中拒绝 schedule
 * - cancelScheduledClose → 清 timer
 * - startResize(e) → 挂 window mousemove/mouseup listener 更新 size
 * - 卸载时清 timer + 移除全局 listener
 */

export interface HoverPromptPreviewBase {
  messageId: string;
  anchorX: number;
  anchorY: number;
  originalPrompt: string;
  optimizedPrompt: string;
}

export interface HoverPromptPreviewSize {
  width: number;
  height: number;
}

export interface HoverPromptPreviewPosition {
  top: number;
  left: number;
  arrowOffsetY: number;
}

export interface UseHoverPromptPreviewResult<P extends HoverPromptPreviewBase> {
  preview: P | null;
  position: HoverPromptPreviewPosition | null;
  size: HoverPromptPreviewSize | null;
  panelRef: React.RefObject<HTMLDivElement>;
  openPreview: (payload: P) => void;
  closePreview: () => void;
  scheduleClose: (delayMs?: number) => void;
  cancelScheduledClose: () => void;
  startResize: (e: React.MouseEvent) => void;
  isResizing: boolean;
}

const DEFAULT_HIDE_DELAY_MS = 300;
const ESTIMATED_PANEL_WIDTH = 360;
const ESTIMATED_PANEL_HEIGHT = 260;
const MIN_PANEL_WIDTH = 280;
const MIN_PANEL_HEIGHT = 190;
const VIEWPORT_PADDING = 8;
const ANCHOR_GAP = 12;
const ARROW_MIN_OFFSET = 12;
const POSITION_DELTA_THRESHOLD = 0.5;

function computePosition(
  anchorX: number,
  anchorY: number,
  panelW: number,
  panelH: number
): HoverPromptPreviewPosition {
  const left = Math.max(
    VIEWPORT_PADDING,
    Math.min(anchorX + ANCHOR_GAP, window.innerWidth - panelW - VIEWPORT_PADDING)
  );
  const top = Math.max(
    VIEWPORT_PADDING,
    Math.min(anchorY - panelH / 2, window.innerHeight - panelH - VIEWPORT_PADDING)
  );
  const arrowOffsetY = Math.max(
    ARROW_MIN_OFFSET,
    Math.min(panelH - ARROW_MIN_OFFSET, anchorY - top)
  );
  return { left, top, arrowOffsetY };
}

export function useHoverPromptPreview<
  P extends HoverPromptPreviewBase = HoverPromptPreviewBase,
>(): UseHoverPromptPreviewResult<P> {
  const [preview, setPreview] = useState<P | null>(null);
  const [position, setPosition] = useState<HoverPromptPreviewPosition | null>(null);
  const [size, setSize] = useState<HoverPromptPreviewSize | null>(null);
  const [isResizing, setIsResizing] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const hideTimerRef = useRef<number | null>(null);
  const resizeHandlersRef = useRef<{
    onMouseMove?: (e: MouseEvent) => void;
    onMouseUp?: () => void;
  }>({});
  const isResizingRef = useRef(false);

  const clearHideTimer = useCallback(() => {
    if (hideTimerRef.current !== null) {
      window.clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  }, []);

  const detachResizeListeners = useCallback(() => {
    const handlers = resizeHandlersRef.current;
    if (handlers.onMouseMove) window.removeEventListener('mousemove', handlers.onMouseMove);
    if (handlers.onMouseUp) window.removeEventListener('mouseup', handlers.onMouseUp);
    resizeHandlersRef.current = {};
    isResizingRef.current = false;
    setIsResizing(false);
  }, []);

  const closePreview = useCallback(() => {
    clearHideTimer();
    detachResizeListeners();
    setPreview(null);
    setPosition(null);
    setSize(null);
  }, [clearHideTimer, detachResizeListeners]);

  const openPreview = useCallback(
    (payload: P) => {
      clearHideTimer();
      setPreview((prev) => {
        if (!prev || prev.messageId !== payload.messageId) {
          setSize(null);
        }
        return payload;
      });
      setPosition(
        computePosition(
          payload.anchorX,
          payload.anchorY,
          ESTIMATED_PANEL_WIDTH,
          ESTIMATED_PANEL_HEIGHT
        )
      );
    },
    [clearHideTimer]
  );

  const scheduleClose = useCallback(
    (delayMs = DEFAULT_HIDE_DELAY_MS) => {
      if (isResizingRef.current) return;
      clearHideTimer();
      hideTimerRef.current = window.setTimeout(() => {
        closePreview();
        hideTimerRef.current = null;
      }, delayMs);
    },
    [clearHideTimer, closePreview]
  );

  const cancelScheduledClose = useCallback(() => {
    clearHideTimer();
  }, [clearHideTimer]);

  const startResize = useCallback(
    (e: React.MouseEvent) => {
      if (!preview) return;
      e.preventDefault();
      e.stopPropagation();
      clearHideTimer();
      detachResizeListeners();
      isResizingRef.current = true;
      setIsResizing(true);

      const startX = e.clientX;
      const startY = e.clientY;
      const rect = panelRef.current?.getBoundingClientRect();
      const startWidth = rect?.width ?? size?.width ?? ESTIMATED_PANEL_WIDTH;
      const startHeight = rect?.height ?? size?.height ?? ESTIMATED_PANEL_HEIGHT;
      const anchorLeft = position?.left ?? VIEWPORT_PADDING;
      const anchorTop = position?.top ?? VIEWPORT_PADDING;

      setSize({ width: startWidth, height: startHeight });

      const onMouseMove = (moveEvent: MouseEvent) => {
        const deltaX = moveEvent.clientX - startX;
        const deltaY = moveEvent.clientY - startY;
        const maxWidth = Math.max(
          MIN_PANEL_WIDTH,
          window.innerWidth - anchorLeft - VIEWPORT_PADDING
        );
        const maxHeight = Math.max(
          MIN_PANEL_HEIGHT,
          window.innerHeight - anchorTop - VIEWPORT_PADDING
        );
        setSize({
          width: Math.max(MIN_PANEL_WIDTH, Math.min(maxWidth, startWidth + deltaX)),
          height: Math.max(MIN_PANEL_HEIGHT, Math.min(maxHeight, startHeight + deltaY)),
        });
      };
      const onMouseUp = () => {
        detachResizeListeners();
      };
      resizeHandlersRef.current = { onMouseMove, onMouseUp };
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    },
    [
      preview,
      size?.width,
      size?.height,
      position?.left,
      position?.top,
      clearHideTimer,
      detachResizeListeners,
    ]
  );

  // Sync position with real panel rect via requestAnimationFrame
  useEffect(() => {
    if (!preview || !panelRef.current) return undefined;
    const sync = () => {
      if (!panelRef.current) return;
      const rect = panelRef.current.getBoundingClientRect();
      const panelW = size?.width ?? rect.width;
      const panelH = size?.height ?? rect.height;
      const next = computePosition(preview.anchorX, preview.anchorY, panelW, panelH);
      setPosition((prev) => {
        if (
          prev &&
          Math.abs(prev.left - next.left) < POSITION_DELTA_THRESHOLD &&
          Math.abs(prev.top - next.top) < POSITION_DELTA_THRESHOLD &&
          Math.abs(prev.arrowOffsetY - next.arrowOffsetY) < POSITION_DELTA_THRESHOLD
        ) {
          return prev;
        }
        return next;
      });
    };
    const rafId = window.requestAnimationFrame(sync);
    return () => {
      window.cancelAnimationFrame(rafId);
    };
  }, [preview, size]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearHideTimer();
      detachResizeListeners();
    };
  }, [clearHideTimer, detachResizeListeners]);

  return {
    preview,
    position,
    size,
    panelRef,
    openPreview,
    closePreview,
    scheduleClose,
    cancelScheduledClose,
    startResize,
    isResizing,
  };
}

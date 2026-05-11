import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Action menu hook（含 viewport-clamp position + outside-click/scroll/resize）。
 *
 * 替代 ImageExpandView + VideoGenView 中重复的 action-menu state/ref/effect
 * （见 JIRA-frontend-hook-utility-extraction.md §A.1.4）。
 *
 * 行为（抽离自 ImageExpandView.tsx:144-145/327-379，VideoGenView.tsx:195-196/535-611）：
 * - open(anchor) → 设置 anchor，立即用 fallback 尺寸算一次 position（避免首帧抖动）
 * - 当 anchor 非空时挂三组 listener：
 *   1. window.mousedown：panel 内 / isExempted 命中不关，其余命中关闭
 *   2. requestAnimationFrame + window.resize：用真实 panel rect 同步 position
 *   3. window.scroll（capture=true）：滚动直接关闭
 * - close() / unmount 时清理 listener 与 rAF
 */

export interface ActionMenuAnchorBase {
  messageId: string;
  anchorX: number;
  anchorY: number;
}

export interface ActionMenuPosition {
  top: number;
  left: number;
}

export interface UseActionMenuOptions {
  /**
   * target 命中此函数视为"内部"，不关闭 menu（如历史区域操作面板）。
   * 签名与 ImageExpandView 的 isHistoryActionSurface 对齐（接受 EventTarget | null）。
   *
   * @example
   *   useActionMenu({ isExempted: (t) => isHistoryActionSurface(t) })
   */
  isExempted?: (target: EventTarget | null) => boolean;
  fallbackPanelWidth?: number;
  fallbackPanelHeight?: number;
  gap?: number;
  viewportPadding?: number;
}

export interface UseActionMenuResult<A extends ActionMenuAnchorBase> {
  anchor: A | null;
  position: ActionMenuPosition | null;
  panelRef: React.RefObject<HTMLDivElement | null>;
  open: (anchor: A) => void;
  close: () => void;
  isOpen: boolean;
}

const DEFAULT_FALLBACK_PANEL_WIDTH = 110;
const DEFAULT_FALLBACK_PANEL_HEIGHT = 76;
const DEFAULT_GAP = 8;
const DEFAULT_VIEWPORT_PADDING = 8;
const POSITION_DELTA_THRESHOLD = 0.5;

function computeMenuPosition(
  anchorX: number,
  anchorY: number,
  panelWidth: number,
  panelHeight: number,
  gap: number,
  viewportPadding: number
): ActionMenuPosition {
  let left = anchorX + gap;
  if (left + panelWidth + viewportPadding > window.innerWidth) {
    left = anchorX - panelWidth - gap;
  }
  left = Math.max(
    viewportPadding,
    Math.min(left, window.innerWidth - panelWidth - viewportPadding)
  );

  let top = anchorY + gap;
  if (top + panelHeight + viewportPadding > window.innerHeight) {
    top = anchorY - panelHeight - gap;
  }
  top = Math.max(
    viewportPadding,
    Math.min(top, window.innerHeight - panelHeight - viewportPadding)
  );

  return { top, left };
}

export function useActionMenu<A extends ActionMenuAnchorBase = ActionMenuAnchorBase>(
  options?: UseActionMenuOptions
): UseActionMenuResult<A> {
  const fallbackPanelWidth = options?.fallbackPanelWidth ?? DEFAULT_FALLBACK_PANEL_WIDTH;
  const fallbackPanelHeight = options?.fallbackPanelHeight ?? DEFAULT_FALLBACK_PANEL_HEIGHT;
  const gap = options?.gap ?? DEFAULT_GAP;
  const viewportPadding = options?.viewportPadding ?? DEFAULT_VIEWPORT_PADDING;

  const [anchor, setAnchor] = useState<A | null>(null);
  const [position, setPosition] = useState<ActionMenuPosition | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  // isExempted ref 镜像 — 避免调用方内联函数导致 mousedown listener 频繁 detach/re-attach
  // （performance-optimizer Step 4 LOW）
  const isExemptedRef = useRef<UseActionMenuOptions['isExempted']>(options?.isExempted);
  isExemptedRef.current = options?.isExempted;

  const open = useCallback(
    (next: A) => {
      setAnchor(next);
      setPosition(
        computeMenuPosition(
          next.anchorX,
          next.anchorY,
          fallbackPanelWidth,
          fallbackPanelHeight,
          gap,
          viewportPadding
        )
      );
    },
    [fallbackPanelWidth, fallbackPanelHeight, gap, viewportPadding]
  );

  const close = useCallback(() => {
    setAnchor(null);
    setPosition(null);
  }, []);

  useEffect(() => {
    if (!anchor) return undefined;
    const handleOutsideClick = (event: MouseEvent) => {
      const target = event.target;
      if (!target) return;
      // contains 只对 Node 生效；isExempted 接收全部 EventTarget（与原 isHistoryActionSurface 一致）
      if (target instanceof Node && panelRef.current?.contains(target)) return;
      if (isExemptedRef.current?.(target)) return;
      close();
    };
    window.addEventListener('mousedown', handleOutsideClick);
    return () => {
      window.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [anchor, close]);

  useEffect(() => {
    if (!anchor) return undefined;
    const sync = () => {
      const rect = panelRef.current?.getBoundingClientRect();
      const panelWidth = rect?.width ?? fallbackPanelWidth;
      const panelHeight = rect?.height ?? fallbackPanelHeight;
      const next = computeMenuPosition(
        anchor.anchorX,
        anchor.anchorY,
        panelWidth,
        panelHeight,
        gap,
        viewportPadding
      );
      setPosition((prev) => {
        if (
          prev &&
          Math.abs(prev.left - next.left) < POSITION_DELTA_THRESHOLD &&
          Math.abs(prev.top - next.top) < POSITION_DELTA_THRESHOLD
        ) {
          return prev;
        }
        return next;
      });
    };
    const rafId = window.requestAnimationFrame(sync);
    window.addEventListener('resize', sync);
    return () => {
      window.cancelAnimationFrame(rafId);
      window.removeEventListener('resize', sync);
    };
  }, [anchor, fallbackPanelWidth, fallbackPanelHeight, gap, viewportPadding]);

  useEffect(() => {
    if (!anchor) return undefined;
    const handleScroll = () => close();
    const scrollOpts: AddEventListenerOptions = { capture: true, passive: true };
    window.addEventListener('scroll', handleScroll, scrollOpts);
    return () => {
      window.removeEventListener('scroll', handleScroll, scrollOpts);
    };
  }, [anchor, close]);

  return {
    anchor,
    position,
    panelRef,
    open,
    close,
    isOpen: anchor !== null,
  };
}

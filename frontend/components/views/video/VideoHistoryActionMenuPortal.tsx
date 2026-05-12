/**
 * VideoGenView 历史侧边栏行操作菜单 Portal（收藏 / 删除）。
 *
 * 1:1 抽离自 `VideoGenView.tsx` L903-955 action menu portal。
 * 注意：与 ImageHistoryActionMenuPortal（z-[90]）不同，此处使用 z-[130]。
 */

import React from 'react';
import { createPortal } from 'react-dom';
import { Star, Trash2 } from 'lucide-react';
import type { ActionMenuPosition } from '../../../hooks/useActionMenu';
import type { ActionMenuAnchor, HoverPromptPreview } from './types';

export interface VideoHistoryActionMenuPortalProps {
  openActionMenu: ActionMenuAnchor;
  actionMenuPosition: ActionMenuPosition | null;
  actionMenuPanelRef: React.RefObject<HTMLDivElement | null>;
  closeHoverPreview: () => void;
  closeActionMenu: () => void;
  isFavorite: (messageId: string) => boolean;
  isFavoritePending: (messageId: string) => boolean;
  toggleFavorite: (messageId: string) => Promise<void> | void;
  deleteItem: (messageId: string) => void;
  hoverPreview: HoverPromptPreview | null;
}

export const VideoHistoryActionMenuPortal: React.FC<VideoHistoryActionMenuPortalProps> = ({
  openActionMenu,
  actionMenuPosition,
  actionMenuPanelRef,
  closeHoverPreview,
  closeActionMenu,
  isFavorite,
  isFavoritePending,
  toggleFavorite,
  deleteItem,
  hoverPreview,
}) => {
  if (typeof document === 'undefined') return null;
  return createPortal(
    <div
      ref={actionMenuPanelRef}
      data-history-action-menu
      className="fixed z-[130] inline-flex flex-col gap-1 rounded-lg border border-slate-700 bg-slate-950/95 shadow-2xl backdrop-blur-md p-1"
      onMouseEnter={closeHoverPreview}
      style={{
        top: actionMenuPosition?.top ?? openActionMenu.anchorY,
        left: actionMenuPosition?.left ?? openActionMenu.anchorX,
      }}
    >
      <button
        type="button"
        className="whitespace-nowrap px-2.5 py-1.5 rounded text-left text-[11px] text-slate-200 hover:bg-slate-800 flex items-center gap-1.5 disabled:opacity-50"
        disabled={
          openActionMenu.messageId ? isFavoritePending(openActionMenu.messageId) : false
        }
        onClick={async () => {
          await toggleFavorite(openActionMenu.messageId);
          closeActionMenu();
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
        {openActionMenu.messageId && isFavorite(openActionMenu.messageId)
          ? '取消收藏'
          : '收藏'}
      </button>
      <button
        type="button"
        className="whitespace-nowrap px-2.5 py-1.5 rounded text-left text-[11px] text-red-300 hover:bg-red-950/50 flex items-center gap-1.5"
        onClick={() => {
          deleteItem(openActionMenu.messageId);
          if (hoverPreview?.messageId === openActionMenu.messageId) {
            closeHoverPreview();
          }
          closeActionMenu();
        }}
      >
        <Trash2 size={11} />
        删除
      </button>
    </div>,
    document.body
  );
};

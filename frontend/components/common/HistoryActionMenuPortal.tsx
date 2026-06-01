/**
 * 通用历史行操作菜单 Portal（收藏 / 删除）。
 *
 * 由 `ImageHistorySidebar` / `ImageExpandView` / `VideoHistorySidebar` 共用。
 *
 * 与原 `ImageHistoryActionMenuPortal` + `VideoHistoryActionMenuPortal` 合并而来：
 *  - 收敛关闭 API 为单个 `closeActionMenu` 回调（Image 侧合成 `setOpen(null) + setPos(null)`）
 *  - 通过 `zClass` 切换层级（Image=`z-[90]`、Video=`z-[130]`）
 */

import React from 'react';
import { createPortal } from 'react-dom';
import { Star, Trash2 } from 'lucide-react';

export interface HistoryActionMenuAnchor {
  messageId: string;
  anchorX: number;
  anchorY: number;
}

export interface HistoryActionMenuPosition {
  top: number;
  left: number;
}

export interface HistoryActionMenuPortalProps {
  openActionMenu: HistoryActionMenuAnchor;
  actionMenuPosition: HistoryActionMenuPosition | null;
  actionMenuPanelRef: React.RefObject<HTMLDivElement | null>;
  closeHoverPreviewOnly: () => void;
  closeHoverPreview: () => void;
  closeActionMenu: () => void;
  isFavorite: (messageId: string) => boolean;
  isFavoritePending: (messageId: string) => boolean;
  toggleFavorite: (messageId: string) => Promise<void> | void;
  deleteItem: (messageId: string) => void;
  hoverPreviewMessageId: string | null;
  /** Portal 层级 class。默认 `z-[90]`（Image 视图）；Video 视图传入 `z-[130]`。 */
  zClass?: string;
}

export const HistoryActionMenuPortal: React.FC<HistoryActionMenuPortalProps> = ({
  openActionMenu,
  actionMenuPosition,
  actionMenuPanelRef,
  closeHoverPreviewOnly,
  closeHoverPreview,
  closeActionMenu,
  isFavorite,
  isFavoritePending,
  toggleFavorite,
  deleteItem,
  hoverPreviewMessageId,
  zClass = 'z-[90]',
}) => {
  if (typeof document === 'undefined') return null;
  return createPortal(
    <div
      ref={actionMenuPanelRef}
      data-history-action-menu
      className={`fixed ${zClass} inline-flex flex-col gap-1 rounded-lg border border-slate-700 bg-slate-950/95 shadow-2xl backdrop-blur-md p-1`}
      onMouseEnter={closeHoverPreviewOnly}
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
        {openActionMenu.messageId && isFavorite(openActionMenu.messageId) ? '取消收藏' : '收藏'}
      </button>
      <button
        type="button"
        className="whitespace-nowrap px-2.5 py-1.5 rounded text-left text-[11px] text-red-300 hover:bg-red-950/50 flex items-center gap-1.5"
        onClick={() => {
          deleteItem(openActionMenu.messageId);
          if (hoverPreviewMessageId === openActionMenu.messageId) {
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

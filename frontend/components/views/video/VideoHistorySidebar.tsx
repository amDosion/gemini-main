/**
 * VideoGenView 历史侧边栏内容。
 *
 * 1:1 抽离自 `VideoGenView.tsx` L697-1104 sidebarContent useMemo body
 * （行列表 + 行操作菜单 portal + hover preview portal）。
 */

import React from 'react';
import type { Message } from '../../../types/types';
import type {
  HoverPromptPreviewPosition,
  HoverPromptPreviewSize,
} from '../../../hooks/useHoverPromptPreview';
import type { ActionMenuPosition } from '../../../hooks/useActionMenu';
import type { ActionMenuAnchor, HoverPromptPreview } from './types';
import { VideoHistoryRow } from './VideoHistoryRow';
import { VideoHistoryActionMenuPortal } from './VideoHistoryActionMenuPortal';
import { VideoHoverPreviewPortal } from './VideoHoverPreviewPortal';

export interface VideoHistorySidebarProps {
  filteredHistoryBatches: Message[];
  activeBatchMessageId: string | undefined;
  showFavoritesOnly: boolean;
  isFavorite: (messageId: string) => boolean;
  isFavoritePending: (messageId: string) => boolean;
  toggleFavorite: (messageId: string) => Promise<void> | void;
  deleteItem: (messageId: string) => void;
  historyItemRefs: React.MutableRefObject<Record<string, HTMLDivElement | null>>;
  // hover preview
  hoverPreview: HoverPromptPreview | null;
  hoverPreviewPosition: HoverPromptPreviewPosition | null;
  hoverPreviewSize: HoverPromptPreviewSize | null;
  hoverPreviewPanelRef: React.RefObject<HTMLDivElement | null>;
  clearHidePreviewTimer: () => void;
  scheduleHideHoverPreview: () => void;
  showHoverPreview: (
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
  ) => void;
  closeHoverPreview: () => void;
  handleCopyOptimizedPrompt: () => Promise<void> | void;
  copiedPreviewMessageId: string | null;
  handlePreviewResizeMouseDown: (event: React.MouseEvent) => void;
  isResizingPreview: boolean;
  // action menu
  openActionMenu: ActionMenuAnchor | null;
  actionMenuPosition: ActionMenuPosition | null;
  actionMenuPanelRef: React.RefObject<HTMLDivElement | null>;
  openActionMenuBase: (anchor: ActionMenuAnchor) => void;
  closeActionMenu: () => void;
  // row callbacks
  activateHistoryMessage: (message: Message) => void;
  setIsMobileHistoryOpen: (open: boolean) => void;
}

export const VideoHistorySidebar: React.FC<VideoHistorySidebarProps> = ({
  filteredHistoryBatches,
  activeBatchMessageId,
  showFavoritesOnly,
  isFavorite,
  isFavoritePending,
  toggleFavorite,
  deleteItem,
  historyItemRefs,
  hoverPreview,
  hoverPreviewPosition,
  hoverPreviewSize,
  hoverPreviewPanelRef,
  clearHidePreviewTimer,
  scheduleHideHoverPreview,
  showHoverPreview,
  closeHoverPreview,
  handleCopyOptimizedPrompt,
  copiedPreviewMessageId,
  handlePreviewResizeMouseDown,
  isResizingPreview,
  openActionMenu,
  actionMenuPosition,
  actionMenuPanelRef,
  openActionMenuBase,
  closeActionMenu,
  activateHistoryMessage,
  setIsMobileHistoryOpen,
}) => {
  return (
    <div className="p-3 space-y-2.5">
      {filteredHistoryBatches.map((msg) => {
        const isSelected = activeBatchMessageId === msg.id;
        const favorited = isFavorite(msg.id);
        const isActionMenuOpen = openActionMenu?.messageId === msg.id;

        return (
          <VideoHistoryRow
            key={msg.id}
            msg={msg}
            isSelected={isSelected}
            favorited={favorited}
            isActionMenuOpen={isActionMenuOpen}
            openActionMenu={openActionMenu}
            historyItemRefs={historyItemRefs}
            showHoverPreview={showHoverPreview}
            scheduleHideHoverPreview={scheduleHideHoverPreview}
            activateHistoryMessage={activateHistoryMessage}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
            closeActionMenu={closeActionMenu}
            closeHoverPreview={closeHoverPreview}
            openActionMenuBase={openActionMenuBase}
          />
        );
      })}

      {filteredHistoryBatches.length === 0 && (
        <div className="text-center py-10 text-slate-600 text-xs italic">
          {showFavoritesOnly ? '暂无收藏记录。' : 'No video history yet.'}
        </div>
      )}

      {openActionMenu && (
        <VideoHistoryActionMenuPortal
          openActionMenu={openActionMenu}
          actionMenuPosition={actionMenuPosition}
          actionMenuPanelRef={actionMenuPanelRef}
          closeHoverPreview={closeHoverPreview}
          closeActionMenu={closeActionMenu}
          isFavorite={isFavorite}
          isFavoritePending={isFavoritePending}
          toggleFavorite={toggleFavorite}
          deleteItem={deleteItem}
          hoverPreview={hoverPreview}
        />
      )}

      {hoverPreview && (
        <VideoHoverPreviewPortal
          hoverPreview={hoverPreview}
          hoverPreviewPosition={hoverPreviewPosition}
          hoverPreviewSize={hoverPreviewSize}
          hoverPreviewPanelRef={hoverPreviewPanelRef}
          clearHidePreviewTimer={clearHidePreviewTimer}
          scheduleHideHoverPreview={scheduleHideHoverPreview}
          handleCopyOptimizedPrompt={handleCopyOptimizedPrompt}
          copiedPreviewMessageId={copiedPreviewMessageId}
          handlePreviewResizeMouseDown={handlePreviewResizeMouseDown}
          isResizingPreview={isResizingPreview}
        />
      )}
    </div>
  );
};

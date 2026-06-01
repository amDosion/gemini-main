/**
 * ImageExpandView 历史侧边栏单条 row。
 *
 * 1:1 抽离自 `ImageExpandView.tsx` L474-595 filteredHistoryBatches.map row JSX。
 */

import React from 'react';
import { AlertCircle, FolderOpen, Image as ImageIcon, Layers, Star, Wand2 } from 'lucide-react';
import { Attachment, Message } from '../../../types/types';
import type { ActionMenuAnchorBase } from '../../../hooks/useActionMenu';
import { CachedImage } from '../../common/CachedImage';
import { HISTORY_THUMBNAIL_CACHE_PROPS } from '../../common/historyThumbnailCache';
import { getPreferredImageAttachmentUrl } from '../../../utils/attachmentUrl';
import { getImageHistoryAttachmentPreviewUrl } from '../../common/imageHistorySidebarHelpers';

export interface ExpandHistoryRowProps {
  msg: Message;
  firstImage: string | undefined;
  firstImageAttachment?: Attachment;
  count: number;
  isSelected: boolean;
  originalPrompt: string;
  optimizedPrompt: string;
  favorited: boolean;
  isActionMenuOpen: boolean;
  openActionMenu: ActionMenuAnchorBase | null;
  historyItemRefs: React.MutableRefObject<Record<string, HTMLDivElement | null>>;
  showHoverPreview: (
    event: React.MouseEvent<HTMLDivElement>,
    messageId: string,
    originalPrompt: string,
    optimizedPrompt: string
  ) => void;
  scheduleHideHoverPreview: () => void;
  setSelectedMsgId: (id: string | null) => void;
  setIsMobileHistoryOpen: (open: boolean) => void;
  closeHoverPreview: () => void;
  closeActionMenu: () => void;
  openActionMenuBase: (anchor: ActionMenuAnchorBase) => void;
}

const ExpandHistoryRowComponent: React.FC<ExpandHistoryRowProps> = ({
  msg,
  firstImage,
  firstImageAttachment,
  count,
  isSelected,
  originalPrompt,
  optimizedPrompt,
  favorited,
  isActionMenuOpen,
  openActionMenu,
  historyItemRefs,
  showHoverPreview,
  scheduleHideHoverPreview,
  setSelectedMsgId,
  setIsMobileHistoryOpen,
  closeHoverPreview,
  closeActionMenu,
  openActionMenuBase,
}) => {
  const firstImagePreviewId = firstImageAttachment?.id || `${msg.id}-0`;
  const resolvedFirstImage = firstImageAttachment
    ? getImageHistoryAttachmentPreviewUrl(
        firstImageAttachment,
        firstImagePreviewId,
        getPreferredImageAttachmentUrl(firstImageAttachment) || firstImage
      )
    : firstImage;

  return (
    <div
      ref={(el) => {
        historyItemRefs.current[msg.id] = el;
      }}
      className="group relative"
    >
      <div
        className={`relative rounded-xl border cursor-pointer transition-all flex items-center gap-3 bg-slate-800/40 p-2 ${
          isSelected
            ? 'ring-1 ring-orange-500 border-transparent bg-slate-800'
            : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-800'
        }`}
        onMouseEnter={(e) => showHoverPreview(e, msg.id, originalPrompt, optimizedPrompt)}
        onMouseLeave={() => scheduleHideHoverPreview()}
        onClick={() => {
          setSelectedMsgId(msg.id);
          if (window.innerWidth < 768) setIsMobileHistoryOpen(false);
          closeHoverPreview();
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
          ) : resolvedFirstImage ? (
            <>
              <CachedImage
                source={{
                  ...firstImageAttachment,
                  attachmentId: firstImagePreviewId,
                  url: resolvedFirstImage,
                }}
                src={resolvedFirstImage}
                {...HISTORY_THUMBNAIL_CACHE_PROPS}
                className="w-full h-full object-cover transition-transform group-hover:scale-105"
                alt="Expanded image"
              />
              {count > 1 && (
                <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                  <Layers size={10} /> {count}
                </div>
              )}
            </>
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-600">
              <ImageIcon size={18} className="opacity-50" />
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-[11px] text-slate-200 leading-relaxed font-medium line-clamp-2 break-words">
            {originalPrompt}
          </p>
          <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
            <span>
              {new Date(msg.timestamp).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
            {optimizedPrompt && (
              <span className="inline-flex items-center gap-1 rounded-full border border-orange-500/30 bg-orange-500/10 px-1.5 py-0.5 text-orange-300">
                <Wand2 size={10} />
                已优化
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
            data-history-action-trigger={msg.id}
            onMouseEnter={(event) => {
              event.stopPropagation();
              closeHoverPreview();
            }}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              closeHoverPreview();
              const rect = event.currentTarget.getBoundingClientRect();
              if (openActionMenu?.messageId === msg.id) {
                closeActionMenu();
              } else {
                openActionMenuBase({
                  messageId: msg.id,
                  anchorX: rect.right,
                  anchorY: rect.bottom,
                });
              }
            }}
          >
            <FolderOpen size={12} />
          </button>
        </div>
      </div>
    </div>
  );
};

export const ExpandHistoryRow = ExpandHistoryRowComponent;

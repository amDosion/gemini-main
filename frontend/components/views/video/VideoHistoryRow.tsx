/**
 * VideoGenView 历史侧边栏单条 row。
 *
 * 1:1 抽离自 `VideoGenView.tsx` L700-894 filteredHistoryBatches.map row JSX。
 */

import React from 'react';
import {
  AlertCircle,
  FolderOpen,
  Film,
  Layers,
  Star,
  Wand2,
  Video as VideoIcon,
} from 'lucide-react';
import type { Message } from '../../../types/types';
import { extractHistoryPrompts, extractVideoHistoryMeta } from '../../../utils/videoHistoryHelpers';
import type { ActionMenuAnchor } from './types';

export interface VideoHistoryRowProps {
  msg: Message;
  isSelected: boolean;
  favorited: boolean;
  isActionMenuOpen: boolean;
  openActionMenu: ActionMenuAnchor | null;
  historyItemRefs: React.MutableRefObject<Record<string, HTMLDivElement | null>>;
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
  scheduleHideHoverPreview: () => void;
  activateHistoryMessage: (message: Message) => void;
  setIsMobileHistoryOpen: (open: boolean) => void;
  closeActionMenu: () => void;
  closeHoverPreview: () => void;
  openActionMenuBase: (anchor: ActionMenuAnchor) => void;
}

export const VideoHistoryRow: React.FC<VideoHistoryRowProps> = ({
  msg,
  isSelected,
  favorited,
  isActionMenuOpen,
  openActionMenu,
  historyItemRefs,
  showHoverPreview,
  scheduleHideHoverPreview,
  activateHistoryMessage,
  setIsMobileHistoryOpen,
  closeActionMenu,
  closeHoverPreview,
  openActionMenuBase,
}) => {
  const previewVideo = msg.attachments?.find(
    (attachment) => attachment.mimeType?.startsWith('video/') && attachment.url
  );
  const previewImage = msg.attachments?.find(
    (attachment) => attachment.mimeType?.startsWith('image/') && attachment.url
  );
  const previewCount = (msg.attachments || []).filter(
    (attachment) =>
      attachment.mimeType?.startsWith('video/') || attachment.mimeType?.startsWith('image/')
  ).length;
  const { originalPrompt, optimizedPrompt } = extractHistoryPrompts(msg);
  const { extensionCount, totalDurationSeconds, strategyLabel, subtitleLabel, subtitleCount } =
    extractVideoHistoryMeta(msg);

  return (
    <div
      key={msg.id}
      ref={(element) => {
        historyItemRefs.current[msg.id] = element;
      }}
      className="group relative"
    >
      <div
        className={`relative rounded-xl border cursor-pointer transition-all flex items-center gap-3 bg-slate-800/40 p-2 ${
          isSelected
            ? 'ring-1 ring-indigo-500 border-transparent bg-slate-800'
            : 'border-slate-700/50 hover:border-slate-600 hover:bg-slate-800'
        }`}
        data-testid={`video-history-item-${msg.id}`}
        onMouseEnter={(event) =>
          showHoverPreview(event, msg.id, originalPrompt, optimizedPrompt, {
            extensionCount,
            totalDurationSeconds,
            strategyLabel,
            subtitleLabel,
            subtitleCount,
          })
        }
        onMouseLeave={() => scheduleHideHoverPreview()}
        onClick={() => {
          activateHistoryMessage(msg);
          if (window.innerWidth < 768) {
            setIsMobileHistoryOpen(false);
          }
          closeActionMenu();
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
          ) : previewVideo?.url ? (
            <>
              <video
                src={previewVideo.url}
                className="w-full h-full object-cover"
                muted
                playsInline
                preload="metadata"
              />
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="bg-black/50 p-1.5 rounded-full backdrop-blur-sm">
                  <VideoIcon size={14} className="text-white" />
                </div>
              </div>
              {previewCount > 1 && (
                <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                  <Layers size={10} /> {previewCount}
                </div>
              )}
            </>
          ) : previewImage?.url ? (
            <>
              <img
                src={previewImage.url}
                className="w-full h-full object-cover transition-transform group-hover:scale-105"
                loading="lazy"
                alt="Video reference"
              />
              {previewCount > 1 && (
                <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded-md flex items-center gap-1 font-medium border border-white/10">
                  <Layers size={10} /> {previewCount}
                </div>
              )}
            </>
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-600">
              <Film size={18} className="opacity-50" />
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
              <span className="inline-flex items-center gap-1 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-1.5 py-0.5 text-indigo-300">
                <Wand2 size={10} />
                已优化
              </span>
            )}
          </div>
          {(extensionCount > 0 || totalDurationSeconds || strategyLabel || subtitleLabel) && (
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]">
              {extensionCount > 0 && (
                <span className="inline-flex items-center rounded-full border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-cyan-200">
                  延长 {extensionCount} 次
                </span>
              )}
              {totalDurationSeconds && (
                <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-200">
                  总时长 {totalDurationSeconds}s
                </span>
              )}
              {strategyLabel && (
                <span className="inline-flex items-center rounded-full border border-slate-600 bg-slate-800/80 px-1.5 py-0.5 text-slate-300">
                  {strategyLabel}
                </span>
              )}
              {subtitleLabel && (
                <span className="inline-flex items-center rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-1.5 py-0.5 text-fuchsia-200">
                  {subtitleLabel}
                </span>
              )}
            </div>
          )}
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

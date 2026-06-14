/**
 * ImageHistorySidebar 单条消息行组件。
 *
 * 1:1 抽离自 `ImageHistorySidebar.tsx` L541-715 filteredItems.map row JSX
 * （< 800 行合规拆分）。
 */

import React from 'react';
import {
  AlertCircle,
  Bot,
  FolderOpen,
  Image as ImageIcon,
  Layers,
  Sparkles,
  Star,
  User,
} from 'lucide-react';
import { Message, Role, Attachment } from '../../types/types';
import {
  type ImageHistoryPromptParts,
  type ImageHistoryPreviewAttachment,
  type ImageHistoryActionMenuAnchor,
  type ImageHistoryActionMenuPosition,
  type ImageHistoryAccent,
  ACCENT_CLASSES,
  USER_SELECTED_CLASS,
  USER_IDLE_CLASS,
  getImageHistoryAuthorLabel,
  getImageHistoryStablePreviewUrl,
  selectImageHistoryPrimaryPreviewAttachment,
} from './imageHistorySidebarHelpers';
import { CachedImage } from './CachedImage';
import { HISTORY_THUMBNAIL_CACHE_PROPS } from './historyThumbnailCache';

export interface ImageHistoryListRowProps {
  message: Message;
  tone: (typeof ACCENT_CLASSES)[ImageHistoryAccent];
  modelLabel: string;
  secondaryPromptBadgeText: string;
  selectedMessageId?: string | null;
  activeImageUrl?: string | null;
  openActionMenu: ImageHistoryActionMenuAnchor | null;
  historyItemRefs: React.RefObject<Record<string, HTMLDivElement | null>>;
  isFavorite: (messageId: string) => boolean;
  getDisplayAttachments: (attachments?: Attachment[]) => Attachment[];
  getPreviewAttachments: (message: Message) => ImageHistoryPreviewAttachment[];
  extractPrompts: (message: Message) => ImageHistoryPromptParts;
  showHoverPreview: (
    event: React.MouseEvent,
    message: Message,
    originalPrompt: string,
    enhancedPrompt: string,
    previewAttachments: ImageHistoryPreviewAttachment[]
  ) => void;
  scheduleHideHoverPreview: () => void;
  closeHoverPreviewOnly: () => void;
  closeHoverPreview: () => void;
  onSelectedMessageIdChange?: (messageId: string | null) => void;
  onSelectItem: (payload: {
    message: Message;
    displayAttachments: Attachment[];
    previewAttachments: ImageHistoryPreviewAttachment[];
    firstImage?: string;
    firstImageSourceAttachment?: Attachment | null;
  }) => void;
  onMobileHistoryOpenChange?: (open: boolean) => void;
  setOpenActionMenu: React.Dispatch<React.SetStateAction<ImageHistoryActionMenuAnchor | null>>;
  setActionMenuPosition: React.Dispatch<
    React.SetStateAction<ImageHistoryActionMenuPosition | null>
  >;
}

const ImageHistoryListRowComponent: React.FC<ImageHistoryListRowProps> = ({
  message,
  tone,
  modelLabel,
  secondaryPromptBadgeText,
  selectedMessageId,
  activeImageUrl,
  openActionMenu,
  historyItemRefs,
  isFavorite,
  getDisplayAttachments,
  getPreviewAttachments,
  extractPrompts,
  showHoverPreview,
  scheduleHideHoverPreview,
  closeHoverPreviewOnly,
  closeHoverPreview,
  onSelectedMessageIdChange,
  onSelectItem,
  onMobileHistoryOpenChange,
  setOpenActionMenu,
  setActionMenuPosition,
}) => {
  const displayAttachments = getDisplayAttachments(message.attachments);
  const previewAttachments = getPreviewAttachments(message);
  const primaryPreview = selectImageHistoryPrimaryPreviewAttachment(
    displayAttachments,
    previewAttachments
  );
  const previewDisplayUrls = previewAttachments.map((attachment) => {
    return getImageHistoryStablePreviewUrl(displayAttachments, attachment) || attachment.url;
  });
  const firstImageDisplayUrl = primaryPreview?.displayUrl;
  const firstImageAttachment = primaryPreview?.sourceAttachment ?? null;
  const firstImagePreviewAttachment = primaryPreview?.attachment;
  const count = previewAttachments.length;
  const isUserMessage = message.role === Role.USER;
  const authorLabel = getImageHistoryAuthorLabel(message, modelLabel);
  const { originalPrompt, enhancedPrompt } = extractPrompts(message);
  const favorited = isFavorite(message.id);
  const isActionMenuOpen = openActionMenu?.messageId === message.id;
  const isSelected = selectedMessageId
    ? selectedMessageId === message.id
    : Boolean(
        activeImageUrl && previewDisplayUrls.some((url) => url === activeImageUrl)
      );

  const itemToneClass = isUserMessage
    ? isSelected
      ? USER_SELECTED_CLASS
      : USER_IDLE_CLASS
    : isSelected
      ? tone.modelSelected
      : tone.modelIdle;

  return (
    <div
      ref={(element) => {
        if (historyItemRefs.current) {
          historyItemRefs.current[message.id] = element;
        }
      }}
      className="group relative"
    >
      <div
        className={`relative rounded-xl border cursor-pointer transition-all flex items-center gap-3 p-2 ${itemToneClass}`}
        onMouseEnter={(event) =>
          showHoverPreview(event, message, originalPrompt, enhancedPrompt, previewAttachments)
        }
        onMouseLeave={scheduleHideHoverPreview}
        onClick={() => {
          onSelectedMessageIdChange?.(message.id);
          onSelectItem({
            message,
            displayAttachments,
            previewAttachments,
            firstImage: firstImageDisplayUrl,
            firstImageSourceAttachment: firstImageAttachment,
          });
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
          <span
            className={`absolute top-1 left-1 z-10 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium border ${
              isUserMessage ? 'bg-blue-950/85 text-blue-200 border-blue-400/30' : tone.modelPill
            }`}
          >
            {isUserMessage ? <User size={9} /> : <Bot size={9} />}
            {isUserMessage ? 'USER' : 'AI'}
          </span>

          {message.isError ? (
            <div className="w-full h-full flex items-center justify-center text-red-400 bg-red-900/10">
              <AlertCircle size={18} />
            </div>
          ) : firstImageDisplayUrl ? (
            <>
              <CachedImage
                source={{
                  ...firstImageAttachment,
                  attachmentId: firstImageAttachment?.id || firstImagePreviewAttachment?.id,
                  url: firstImageDisplayUrl,
                }}
                src={firstImageDisplayUrl}
                {...HISTORY_THUMBNAIL_CACHE_PROPS}
                className="w-full h-full object-cover transition-transform group-hover:scale-105"
                alt="History preview"
              />
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
            <span
              className={`text-[10px] font-medium ${isUserMessage ? 'text-blue-300' : tone.modelLabel}`}
            >
              {authorLabel}
            </span>
            <span className="text-[10px] text-slate-500">
              {new Date(message.timestamp).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
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
              <span
                className={`inline-flex items-center gap-1 rounded-full border ${tone.modelBadge}`}
              >
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
              closeHoverPreviewOnly();
            }}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              closeHoverPreviewOnly();
              const rect = event.currentTarget.getBoundingClientRect();
              setOpenActionMenu((prev) =>
                prev?.messageId === message.id
                  ? null
                  : {
                      messageId: message.id,
                      anchorX: rect.right,
                      anchorY: rect.bottom,
                    }
              );
              setActionMenuPosition(null);
            }}
          >
            <FolderOpen size={12} />
          </button>
        </div>
      </div>
    </div>
  );
};

export const ImageHistoryListRow = React.memo(ImageHistoryListRowComponent);
ImageHistoryListRow.displayName = 'ImageHistoryListRow';

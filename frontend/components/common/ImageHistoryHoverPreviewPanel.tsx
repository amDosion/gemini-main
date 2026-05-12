/**
 * ImageHistorySidebar 悬浮预览 Portal Panel。
 *
 * 1:1 抽离自 `ImageHistorySidebar.tsx` L787-955 hover preview portal
 * （JIRA-frontend-deep-architecture-split.md #6 — < 800 行合规拆分）。
 */

import React from 'react';
import { createPortal } from 'react-dom';
import { Bot, Check, Copy, User } from 'lucide-react';
import { Message, Role, Attachment } from '../../types/types';
import {
  type ImageHistoryHoverPreview,
  type ImageHistoryHoverPreviewPosition,
  type ImageHistoryHoverPreviewSize,
  type ImageHistoryPreviewAttachment,
  type ImageHistoryAccent,
  ACCENT_CLASSES,
  getAttachmentPreviewGridClass,
  getAttachmentPreviewButtonClass,
  getAttachmentPreviewImageClass,
} from './imageHistorySidebarHelpers';

export interface ImageHistoryHoverPreviewPanelProps {
  hoverPreview: ImageHistoryHoverPreview;
  hoverPreviewPosition: ImageHistoryHoverPreviewPosition | null;
  hoverPreviewSize: ImageHistoryHoverPreviewSize | null;
  hoverPreviewPanelRef: React.RefObject<HTMLDivElement | null>;
  clearHidePreviewTimer: () => void;
  scheduleHideHoverPreview: () => void;
  tone: (typeof ACCENT_CLASSES)[ImageHistoryAccent];
  secondaryPromptLabel: string;
  secondaryPromptMissingText: string;
  secondaryPromptCopyTitle: string;
  copiedPreviewMessageId: string | null;
  handleCopyEnhancedPrompt: () => Promise<void> | void;
  activeImageUrl?: string | null;
  items: Message[];
  onSelectedMessageIdChange?: (messageId: string | null) => void;
  getDisplayAttachments: (attachments?: Attachment[]) => Attachment[];
  onSelectPreviewAttachment?: (payload: {
    message: Message;
    displayAttachments: Attachment[];
    previewAttachments: ImageHistoryPreviewAttachment[];
    attachment: ImageHistoryPreviewAttachment;
    index: number;
  }) => void;
  onSelectItem: (payload: {
    message: Message;
    displayAttachments: Attachment[];
    previewAttachments: ImageHistoryPreviewAttachment[];
    firstImage?: string;
  }) => void;
  handlePreviewResizeMouseDown: (event: React.MouseEvent<HTMLButtonElement>) => void;
  isResizingPreview: boolean;
}

export const ImageHistoryHoverPreviewPanel: React.FC<ImageHistoryHoverPreviewPanelProps> = ({
  hoverPreview,
  hoverPreviewPosition,
  hoverPreviewSize,
  hoverPreviewPanelRef,
  clearHidePreviewTimer,
  scheduleHideHoverPreview,
  tone,
  secondaryPromptLabel,
  secondaryPromptMissingText,
  secondaryPromptCopyTitle,
  copiedPreviewMessageId,
  handleCopyEnhancedPrompt,
  activeImageUrl,
  items,
  onSelectedMessageIdChange,
  getDisplayAttachments,
  onSelectPreviewAttachment,
  onSelectItem,
  handlePreviewResizeMouseDown,
  isResizingPreview,
}) => {
  if (typeof document === 'undefined') return null;
  return createPortal(
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
      <div
        className={`group relative rounded-xl border border-slate-700/80 bg-slate-950/95 backdrop-blur-lg p-3 shadow-2xl ${
          hoverPreviewSize ? 'h-full' : 'inline-block w-fit max-w-[min(75vw,640px)]'
        }`}
      >
        <div
          className="absolute right-full -translate-y-1/2 h-2.5 w-2.5 rotate-45 border-b border-l border-slate-700/80 bg-slate-950/95"
          style={{ top: hoverPreviewPosition?.arrowOffsetY ?? '50%' }}
        />

        <div
          className={`pr-2 pb-5 custom-scrollbar ${
            hoverPreviewSize ? 'h-full overflow-y-auto' : 'max-h-[72vh] overflow-y-auto'
          }`}
        >
          <div className="mb-3 flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border ${
                hoverPreview.role === Role.USER
                  ? 'bg-blue-950/85 text-blue-200 border-blue-400/30'
                  : tone.modelPill
              }`}
            >
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
                <p className="text-[10px] uppercase tracking-wider text-emerald-400">
                  {secondaryPromptLabel}
                </p>
                {hoverPreview.enhancedPrompt && (
                  <button
                    type="button"
                    onClick={handleCopyEnhancedPrompt}
                    className="pointer-events-auto inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-200 hover:bg-emerald-500/20 transition-colors"
                    title={secondaryPromptCopyTitle}
                  >
                    {copiedPreviewMessageId === hoverPreview.messageId ? (
                      <Check size={11} />
                    ) : (
                      <Copy size={11} />
                    )}
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
                      const selectedMessage = items.find(
                        (item) => item.id === hoverPreview.messageId
                      );
                      onSelectedMessageIdChange?.(hoverPreview.messageId);
                      if (selectedMessage) {
                        const displayAttachments = getDisplayAttachments(
                          selectedMessage.attachments
                        );
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
                    <img
                      src={attachment.url}
                      className={getAttachmentPreviewImageClass(hoverPreview.attachments.length)}
                      alt="History attachment"
                    />
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
  );
};

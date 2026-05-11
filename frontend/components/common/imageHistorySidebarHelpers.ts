/**
 * ImageHistorySidebar 内部 types + 类名常量 + 帮助函数。
 *
 * 1:1 抽离自 `ImageHistorySidebar.tsx` L12-166
 * （< 800 行合规拆分）。
 */

import { Message, Role, Attachment } from '../../types/types';

export interface ImageHistoryPromptParts {
  originalPrompt: string;
  enhancedPrompt: string;
}

export interface ImageHistoryPreviewAttachment {
  id: string;
  url: string;
}

export interface ImageHistoryHoverPreview {
  messageId: string;
  role: Role;
  authorLabel: string;
  anchorX: number;
  anchorY: number;
  originalPrompt: string;
  enhancedPrompt: string;
  attachments: ImageHistoryPreviewAttachment[];
}

export interface ImageHistoryHoverPreviewPosition {
  top: number;
  left: number;
  arrowOffsetY: number;
}

export interface ImageHistoryHoverPreviewSize {
  width: number;
  height: number;
}

export interface ImageHistoryActionMenuAnchor {
  messageId: string;
  anchorX: number;
  anchorY: number;
}

export interface ImageHistoryActionMenuPosition {
  top: number;
  left: number;
}

export type ImageHistoryAccent = 'orange' | 'pink' | 'emerald';

export interface ImageHistorySidebarOptions {
  items: Message[];
  sessionId?: string | null;
  onDeleteMessage?: (messageId: string) => void;
  activeImageUrl?: string | null;
  selectedMessageId?: string | null;
  onSelectedMessageIdChange?: (messageId: string | null) => void;
  onMobileHistoryOpenChange?: (open: boolean) => void;
  modelLabel?: string;
  accent?: ImageHistoryAccent;
  emptyText?: string;
  secondaryPromptLabel?: string;
  secondaryPromptMissingText?: string;
  secondaryPromptCopyTitle?: string;
  secondaryPromptBadgeText?: string;
  fallbackSelection?: 'first' | 'last';
  getDisplayAttachments: (attachments?: Attachment[]) => Attachment[];
  getAttachmentUrl: (attachment: Attachment) => string | null;
  extractPrompts: (message: Message) => ImageHistoryPromptParts;
  onSelectItem: (payload: {
    message: Message;
    displayAttachments: Attachment[];
    previewAttachments: ImageHistoryPreviewAttachment[];
    firstImage?: string;
  }) => void;
  onSelectPreviewAttachment?: (payload: {
    message: Message;
    displayAttachments: Attachment[];
    previewAttachments: ImageHistoryPreviewAttachment[];
    attachment: ImageHistoryPreviewAttachment;
    index: number;
  }) => void;
  loadingContent?: React.ReactNode;
}

export const ACCENT_CLASSES: Record<ImageHistoryAccent, {
  modelSelected: string;
  modelIdle: string;
  modelLabel: string;
  modelPill: string;
  modelBadge: string;
  activeThumb: string;
}> = {
  orange: {
    modelSelected: 'ring-1 ring-orange-400/80 border-transparent bg-orange-500/10',
    modelIdle: 'border-orange-500/20 bg-orange-500/5 hover:border-orange-400/40',
    modelLabel: 'text-orange-300',
    modelPill: 'bg-orange-950/85 text-orange-200 border-orange-400/30',
    modelBadge: 'border-orange-500/25 bg-orange-500/10 px-1.5 py-0.5 text-orange-300',
    activeThumb: 'border-orange-400 ring-1 ring-orange-400/70',
  },
  pink: {
    modelSelected: 'ring-1 ring-pink-400/80 border-transparent bg-pink-500/10',
    modelIdle: 'border-pink-500/20 bg-pink-500/5 hover:border-pink-400/40',
    modelLabel: 'text-pink-300',
    modelPill: 'bg-pink-950/85 text-pink-200 border-pink-400/30',
    modelBadge: 'border-pink-500/25 bg-pink-500/10 px-1.5 py-0.5 text-pink-300',
    activeThumb: 'border-pink-400 ring-1 ring-pink-400/70',
  },
  emerald: {
    modelSelected: 'ring-1 ring-emerald-400/80 border-transparent bg-emerald-500/10',
    modelIdle: 'border-emerald-500/20 bg-emerald-500/5 hover:border-emerald-400/40',
    modelLabel: 'text-emerald-300',
    modelPill: 'bg-emerald-950/85 text-emerald-200 border-emerald-400/30',
    modelBadge: 'border-emerald-500/25 bg-emerald-500/10 px-1.5 py-0.5 text-emerald-300',
    activeThumb: 'border-emerald-400 ring-1 ring-emerald-400/70',
  },
};

export const USER_SELECTED_CLASS = 'ring-1 ring-blue-400/80 border-transparent bg-blue-500/10';
export const USER_IDLE_CLASS = 'border-blue-500/20 bg-blue-500/5 hover:border-blue-400/40';

export const getAttachmentPreviewGridClass = (count: number): string => {
  if (count <= 1) return 'grid grid-cols-1 gap-2';
  if (count === 2) return 'grid grid-cols-2 gap-2';
  if (count === 3) return 'grid grid-cols-3 gap-2';
  return 'grid grid-cols-4 gap-2';
};

export const getAttachmentPreviewButtonClass = (count: number): string => (
  count <= 1
    ? 'h-28 p-2'
    : 'aspect-square p-1'
);

export const getAttachmentPreviewImageClass = (count: number): string => (
  count <= 1
    ? 'max-h-24 max-w-full object-contain'
    : 'h-full w-full object-contain'
);

export const extractImageHistoryPrompts = (message: Message): ImageHistoryPromptParts => {
  const rawContent = (message.content || '').trim();
  let originalPrompt = rawContent;
  let enhancedPrompt = message.enhancedPrompt?.trim() || '';

  const promptPairMatch = rawContent.match(/^📝\s*([\s\S]*?)(?:\n✨\s*([\s\S]*))?$/);
  if (promptPairMatch) {
    originalPrompt = (promptPairMatch[1] || '').trim();
    if (!enhancedPrompt && promptPairMatch[2]) {
      enhancedPrompt = promptPairMatch[2].trim();
    }
  }

  return {
    originalPrompt: originalPrompt || (message.role === Role.USER ? '用户消息' : '模型响应'),
    enhancedPrompt,
  };
};


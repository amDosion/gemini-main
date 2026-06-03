/**
 * ImageHistorySidebar 内部 types + 类名常量 + 帮助函数。
 *
 * 1:1 抽离自 `ImageHistorySidebar.tsx` L12-166
 * （< 800 行合规拆分）。
 */

import { Message, Role, Attachment } from '../../types/types';
import {
  isDataAttachmentUrl,
  getPreferredAttachmentUrl,
  isTemporaryAttachmentUrl,
} from '../../utils/attachmentUrl';

export interface ImageHistoryPromptParts {
  originalPrompt: string;
  enhancedPrompt: string;
}

export interface ImageHistoryPreviewAttachment {
  id: string;
  url: string;
}

export interface ImageHistoryPrimaryPreviewAttachment {
  attachment: ImageHistoryPreviewAttachment;
  sourceAttachment: Attachment | null;
  displayUrl: string;
  index: number;
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
  disableFallbackSelection?: boolean;
  getDisplayAttachments: (attachments?: Attachment[]) => Attachment[];
  getAttachmentUrl: (attachment: Attachment) => string | null;
  extractPrompts: (message: Message) => ImageHistoryPromptParts;
  onSelectItem: (payload: {
    message: Message;
    displayAttachments: Attachment[];
    previewAttachments: ImageHistoryPreviewAttachment[];
    firstImage?: string;
    firstImageSourceAttachment?: Attachment | null;
  }) => void;
  onSelectPreviewAttachment?: (payload: {
    message: Message;
    displayAttachments: Attachment[];
    previewAttachments: ImageHistoryPreviewAttachment[];
    attachment: ImageHistoryPreviewAttachment;
    sourceAttachment: Attachment | null;
    displayUrl: string;
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
export {
  HISTORY_THUMBNAIL_RAW_FALLBACK_DELAY_MS as IMAGE_HISTORY_RAW_FALLBACK_DELAY_MS,
} from './historyThumbnailCache';

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

export const getImageHistoryLocalBlobPreviewUrl = (attachmentId: string): string =>
  `local-blob:${attachmentId}`;

const getSafeImageHistoryPreviewUrl = (
  attachment: Attachment | null | undefined,
  fallbackId: string,
  preferredUrl?: string | null
): string | null => {
  const normalizedPreferredUrl = (preferredUrl || '').trim();
  const preferredAttachmentUrl = getPreferredAttachmentUrl(attachment);
  if (preferredAttachmentUrl && !isTemporaryAttachmentUrl(preferredAttachmentUrl)) {
    return preferredAttachmentUrl;
  }
  if (normalizedPreferredUrl && !isTemporaryAttachmentUrl(normalizedPreferredUrl)) {
    return normalizedPreferredUrl;
  }

  const attachmentId = attachment?.id || fallbackId;
  if (attachment?.file && attachmentId) {
    return getImageHistoryLocalBlobPreviewUrl(attachmentId);
  }
  if (preferredAttachmentUrl && isDataAttachmentUrl(preferredAttachmentUrl)) {
    return preferredAttachmentUrl;
  }
  if (normalizedPreferredUrl && isDataAttachmentUrl(normalizedPreferredUrl)) {
    return normalizedPreferredUrl;
  }
  return null;
};

export const getImageHistoryAttachmentPreviewUrl = (
  attachment: Attachment,
  fallbackId: string,
  preferredUrl?: string | null
): string => {
  return getSafeImageHistoryPreviewUrl(attachment, fallbackId, preferredUrl) || '';
};

export const getImageHistoryAuthorLabel = (
  message: Message,
  _fallbackModelLabel: string
): string => {
  if (message.role === Role.USER) return 'You';

  const modelLabel =
    message.modelName ||
    message.model_name ||
    message.modelId ||
    message.model_id ||
    message.modeModelId ||
    message.mode_model_id ||
    'AI';

  return modelLabel.trim() || 'AI';
};

export const resolveImageHistoryRowSourceAttachment = (
  displayAttachments: Attachment[],
  previewAttachment: ImageHistoryPreviewAttachment | null | undefined,
  firstImage: string | null | undefined
): Attachment | null => {
  if (!previewAttachment && !firstImage) return null;
  const previewId = previewAttachment?.id || '';
  const previewUrl = previewAttachment?.url || firstImage || '';
  const attachmentUrls = (attachment: Attachment): Array<string | undefined | null> => {
    const rawAttachment = attachment as Attachment & {
      temp_url?: string | null;
      cloud_url?: string | null;
      file_uri?: string | null;
    };
    return [
      rawAttachment.url,
      rawAttachment.tempUrl,
      rawAttachment.temp_url,
      rawAttachment.cloudUrl,
      rawAttachment.cloud_url,
      rawAttachment.fileUri,
      rawAttachment.file_uri,
    ];
  };
  const isTemporaryPreviewUrl = isTemporaryAttachmentUrl(previewUrl);

  if (previewId) {
    const idMatch = displayAttachments.find((attachment) => attachment.id === previewId);
    const idMatchUsesPreviewUrl = idMatch
      ? attachmentUrls(idMatch).some((url) => url === previewUrl)
      : false;
    if (idMatch && (!previewUrl || isTemporaryPreviewUrl || idMatchUsesPreviewUrl)) {
      return idMatch;
    }
    // Reaching here means the preview URL is a concrete (non-temporary) URL that
    // does NOT match the id-matched attachment. Trust the id only when the
    // attachment has a durable url and no local `file`: its durable url is the
    // correct source. If the attachment carries a stale `file`, returning it
    // would force a local-blob preview of the wrong image, so fall through to
    // URL-based matching and never attach that mismatched metadata.
    if (idMatch && !idMatch.file && getPreferredAttachmentUrl(idMatch)) {
      return idMatch;
    }
  }

  if (previewUrl) {
    return (
      displayAttachments.find((attachment) =>
        attachmentUrls(attachment).some((url) => url === previewUrl)
      ) || null
    );
  }

  return null;
};

export const getImageHistoryStablePreviewUrl = (
  displayAttachments: Attachment[],
  previewAttachment: ImageHistoryPreviewAttachment | null | undefined
): string | null => {
  if (!previewAttachment?.url) return null;
  const sourceAttachment = resolveImageHistoryRowSourceAttachment(
    displayAttachments,
    previewAttachment,
    previewAttachment.url
  );
  return (
    getSafeImageHistoryPreviewUrl(sourceAttachment, previewAttachment.id, previewAttachment.url) ||
    (!isTemporaryAttachmentUrl(previewAttachment.url) || isDataAttachmentUrl(previewAttachment.url)
      ? previewAttachment.url
      : null)
  );
};

const isRenderableHistoryPreview = (
  displayUrl: string,
  sourceAttachment: Attachment | null
): boolean => {
  if (!displayUrl) return false;
  if (!isTemporaryAttachmentUrl(displayUrl)) return true;
  return Boolean(sourceAttachment?.file);
};

export const selectImageHistoryPrimaryPreviewAttachment = (
  displayAttachments: Attachment[],
  previewAttachments: ImageHistoryPreviewAttachment[]
): ImageHistoryPrimaryPreviewAttachment | null => {
  let fallback: ImageHistoryPrimaryPreviewAttachment | null = null;

  for (let index = 0; index < previewAttachments.length; index += 1) {
    const attachment = previewAttachments[index];
    if (!attachment?.url) continue;
    const sourceAttachment = resolveImageHistoryRowSourceAttachment(
      displayAttachments,
      attachment,
      attachment.url
    );
    const displayUrl =
      getSafeImageHistoryPreviewUrl(sourceAttachment, attachment.id, attachment.url) ||
      (!isTemporaryAttachmentUrl(attachment.url) || isDataAttachmentUrl(attachment.url)
        ? attachment.url
        : '');
    if (!displayUrl) continue;

    const candidate = {
      attachment,
      sourceAttachment,
      displayUrl,
      index,
    };
    fallback = fallback || candidate;

    if (isRenderableHistoryPreview(displayUrl, sourceAttachment)) {
      return candidate;
    }
  }

  return fallback;
};

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

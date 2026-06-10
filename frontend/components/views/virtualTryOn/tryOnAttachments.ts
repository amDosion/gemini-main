import { Attachment } from '../../../types/types';
import { getPreferredImageAttachmentUrl } from '../../../utils/attachmentUrl';
import { getImageHistoryAttachmentPreviewUrl } from '../../common/imageHistorySidebarHelpers';

/** Stable React key derived from an attachment's identifying fields. */
export const getAttachmentStableKey = (attachment: Attachment): string => {
  const parts = [
    attachment.id,
    attachment.url,
    attachment.fileUri,
    attachment.name,
    attachment.mimeType,
  ].filter((part): part is string => Boolean(part && part.length > 0));

  return parts.join('|');
};

/** Resolve the best previewable URL for an attachment, or null when none exists. */
export const getDisplayImageAttachment = (
  attachment: Attachment,
  fallbackId: string
): Attachment | null => {
  const sourceAttachment = attachment.id ? attachment : { ...attachment, id: fallbackId };
  const url = getImageHistoryAttachmentPreviewUrl(
    sourceAttachment,
    fallbackId,
    getPreferredImageAttachmentUrl(sourceAttachment)
  );
  if (!url) return null;
  return url === sourceAttachment.url ? sourceAttachment : { ...sourceAttachment, url };
};

/**
 * Map a list of attachments to their displayable form, dropping any without a
 * previewable URL. `idPrefix` seeds the per-item fallback id (`${idPrefix}-${index}`).
 */
export const mapDisplayImageAttachments = (
  attachments: Attachment[] | undefined,
  idPrefix: string
): Attachment[] =>
  (attachments || [])
    .map((attachment, index) => getDisplayImageAttachment(attachment, `${idPrefix}-${index}`))
    .filter((attachment): attachment is Attachment => Boolean(attachment));

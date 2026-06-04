import type { Attachment, Message } from '../types/types';

const normalizePart = (value: unknown): string => String(value ?? '').trim();

// Attachments reach the frontend camelCase-only (CaseConversionMiddleware converts
// every app-owned response; session attachments flow through sessionNormalizer).
// The former snake_case fallbacks (temp_url/cloud_url/...) were always undefined and
// have been removed — see .investigations/case-conversion-audit-2026-06-04.md.
export const buildAttachmentMediaSignature = (
  attachment: Attachment | null | undefined
): string => {
  if (!attachment) return '';
  return [
    attachment.id,
    attachment.url,
    attachment.tempUrl,
    attachment.cloudUrl,
    attachment.fileUri,
    attachment.uploadStatus,
    attachment.uploadTaskId,
    attachment.uploadError,
    attachment.mimeType,
    attachment.name,
    attachment.size,
  ]
    .map(normalizePart)
    .join('\u001f');
};

export const buildMessageMediaSignature = (message: Message | null | undefined): string => {
  if (!message) return '';
  return [
    message.id,
    message.role,
    message.isError ? 'error' : '',
    ...(message.attachments || []).map(buildAttachmentMediaSignature),
  ]
    .map(normalizePart)
    .join('\u001e');
};

export const buildMessagesMediaSignature = (messages: Message[] | null | undefined): string => {
  return (messages || []).map(buildMessageMediaSignature).join('\u001d');
};

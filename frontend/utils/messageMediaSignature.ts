import type { Attachment, Message } from '../types/types';

const normalizePart = (value: unknown): string => String(value ?? '').trim();

type AttachmentMediaSignatureFields = Attachment & {
  mime_type?: unknown;
  temp_url?: unknown;
  upload_status?: unknown;
  upload_task_id?: unknown;
  upload_error?: unknown;
  cloud_url?: unknown;
  file_uri?: unknown;
};

export const buildAttachmentMediaSignature = (
  attachment: Attachment | null | undefined
): string => {
  if (!attachment) return '';
  const mediaAttachment = attachment as AttachmentMediaSignatureFields;
  return [
    mediaAttachment.id,
    mediaAttachment.url,
    mediaAttachment.tempUrl,
    mediaAttachment.temp_url,
    mediaAttachment.cloudUrl,
    mediaAttachment.cloud_url,
    mediaAttachment.fileUri,
    mediaAttachment.file_uri,
    mediaAttachment.uploadStatus,
    mediaAttachment.upload_status,
    mediaAttachment.uploadTaskId,
    mediaAttachment.upload_task_id,
    mediaAttachment.uploadError,
    mediaAttachment.upload_error,
    mediaAttachment.mimeType,
    mediaAttachment.mime_type,
    mediaAttachment.name,
    mediaAttachment.size,
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

import { AppMode, Attachment, ChatSession, Message } from '../types/types';
import {
  getPreferredAttachmentUrl,
  isTemporaryAttachmentUrl,
} from '../utils/attachmentUrl';

type RawChatSession = Partial<ChatSession> & {
  id?: unknown;
  title?: unknown;
  messages?: unknown;
  created_at?: unknown;
  persona_id?: unknown;
  mode?: unknown;
};

type RawMessage = Partial<Message> & {
  attachments?: unknown;
};

type RawAttachment = Partial<Attachment> & {
  mime_type?: unknown;
  temp_url?: unknown;
  upload_status?: unknown;
  upload_task_id?: unknown;
  upload_error?: unknown;
  cloud_url?: unknown;
  file_uri?: unknown;
  message_id?: unknown;
  session_id?: unknown;
  user_id?: unknown;
  created_at?: unknown;
  google_file_uri?: unknown;
  google_file_expiry?: unknown;
  enhanced_prompt?: unknown;
  openai_response_id?: unknown;
};

const normalizeNumber = (value: unknown, fallback: number): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
};

const normalizeOptionalString = (value: unknown): string | undefined =>
  typeof value === 'string' && value.length > 0 ? value : undefined;

const firstOptionalString = (...values: unknown[]): string | undefined => {
  for (const value of values) {
    const normalized = normalizeOptionalString(value);
    if (normalized) return normalized;
  }
  return undefined;
};

export const recoverSessionAttachmentUrl = (attachment: Attachment): Attachment => {
  if (!isTemporaryAttachmentUrl(attachment.url)) {
    return attachment;
  }

  const durableUrl = getPreferredAttachmentUrl(attachment);
  if (!durableUrl || isTemporaryAttachmentUrl(durableUrl)) {
    return attachment;
  }

  return {
    ...attachment,
    url: durableUrl,
    cloudUrl: attachment.cloudUrl || durableUrl,
    uploadStatus: 'completed',
  };
};

const normalizeAttachment = (source: RawAttachment): Attachment => {
  const createdAt = normalizeNumber(source.createdAt ?? source.created_at, 0);
  const googleFileExpiry = normalizeNumber(
    source.googleFileExpiry ?? source.google_file_expiry,
    0
  );

  return recoverSessionAttachmentUrl({
    ...(source as object),
    id: String(source.id ?? ''),
    name: typeof source.name === 'string' ? source.name : '',
    mimeType: firstOptionalString(source.mimeType, source.mime_type) || '',
    url: firstOptionalString(source.url),
    tempUrl: firstOptionalString(source.tempUrl, source.temp_url),
    uploadStatus: firstOptionalString(source.uploadStatus, source.upload_status) as
      | Attachment['uploadStatus']
      | undefined,
    uploadTaskId: firstOptionalString(source.uploadTaskId, source.upload_task_id),
    uploadError: firstOptionalString(source.uploadError, source.upload_error),
    cloudUrl: firstOptionalString(source.cloudUrl, source.cloud_url),
    fileUri: firstOptionalString(source.fileUri, source.file_uri),
    messageId: firstOptionalString(source.messageId, source.message_id),
    sessionId: firstOptionalString(source.sessionId, source.session_id),
    userId: firstOptionalString(source.userId, source.user_id),
    createdAt: createdAt || undefined,
    googleFileUri: firstOptionalString(source.googleFileUri, source.google_file_uri),
    googleFileExpiry: googleFileExpiry || undefined,
    enhancedPrompt: firstOptionalString(source.enhancedPrompt, source.enhanced_prompt),
    openaiResponseId: firstOptionalString(source.openaiResponseId, source.openai_response_id),
  } as Attachment);
};

const normalizeMessage = (source: RawMessage): Message => {
  const attachments = Array.isArray(source.attachments)
    ? source.attachments.map((attachment) => normalizeAttachment(attachment as RawAttachment))
    : source.attachments;

  return {
    ...(source as object),
    attachments,
  } as Message;
};

export const normalizeChatSession = (source: RawChatSession): ChatSession => {
  const createdAt = normalizeNumber(source.createdAt ?? source.created_at, 0);
  const personaId = source.personaId ?? source.persona_id;
  const mode = typeof source.mode === 'string' ? (source.mode as AppMode) : undefined;

  return {
    ...(source as object),
    id: String(source.id ?? ''),
    title: typeof source.title === 'string' ? source.title : 'New Chat',
    messages: Array.isArray(source.messages)
      ? source.messages.map((message) => normalizeMessage(message as RawMessage))
      : [],
    createdAt,
    personaId: typeof personaId === 'string' && personaId ? personaId : undefined,
    mode,
  } as ChatSession;
};

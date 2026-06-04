import { AppMode, Attachment, ChatSession, Message } from '../types/types';
import { getPreferredAttachmentUrl, isTemporaryAttachmentUrl } from '../utils/attachmentUrl';

type RawChatSession = Partial<ChatSession> & {
  id?: unknown;
  title?: unknown;
  messages?: unknown;
  mode?: unknown;
};

type RawMessage = Partial<Message> & {
  attachments?: unknown;
};

type RawAttachment = Partial<Attachment>;

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

// The frontend reads camelCase ONLY here. Every app-owned session source is delivered
// as camelCase by the backend: GET /api/sessions, /api/sessions/{id}, the /api/init*
// bootstrap endpoints, AND /api/init/sessions/more are all marked
// @case_conversion_options(always_convert_response=True), so they are converted even
// past the middleware's 2 MiB ceiling (a paginated page of long first-messages can
// cross it). There is no longer any snake_case session source, so the previous
// camelKey ?? snake_key dual-reads were removed.
// See .investigations/case-conversion-audit-2026-06-04.md.
const normalizeAttachment = (source: RawAttachment): Attachment => {
  const createdAt = normalizeNumber(source.createdAt, 0);
  const googleFileExpiry = normalizeNumber(source.googleFileExpiry, 0);

  return recoverSessionAttachmentUrl({
    ...(source as object),
    id: String(source.id ?? ''),
    name: typeof source.name === 'string' ? source.name : '',
    mimeType: normalizeOptionalString(source.mimeType) || '',
    url: normalizeOptionalString(source.url),
    tempUrl: normalizeOptionalString(source.tempUrl),
    uploadStatus: normalizeOptionalString(source.uploadStatus) as
      | Attachment['uploadStatus']
      | undefined,
    uploadTaskId: normalizeOptionalString(source.uploadTaskId),
    uploadError: normalizeOptionalString(source.uploadError),
    cloudUrl: normalizeOptionalString(source.cloudUrl),
    fileUri: normalizeOptionalString(source.fileUri),
    messageId: normalizeOptionalString(source.messageId),
    sessionId: normalizeOptionalString(source.sessionId),
    userId: normalizeOptionalString(source.userId),
    createdAt: createdAt || undefined,
    googleFileUri: normalizeOptionalString(source.googleFileUri),
    googleFileExpiry: googleFileExpiry || undefined,
    enhancedPrompt: normalizeOptionalString(source.enhancedPrompt),
    openaiResponseId: normalizeOptionalString(source.openaiResponseId),
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
  const createdAt = normalizeNumber(source.createdAt, 0);
  const personaId = source.personaId;
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
